# Modelo de datos

**SentinelAI · PostgreSQL · tareas T-011, T-012, T-013, T-017**

Deriva de `finding.schema.json` v1.0.0. Si cambia el esquema, cambia esto.

---

## 1. La decisión que hay que discutir primero

**Un hallazgo pertenece al objetivo, no al escaneo.**

La unicidad es `(target_id, dedupe_key)`. Reescanear Juice Shop no crea filas nuevas: agrega una fila en `finding_observations` y actualiza `last_seen_at`.

La alternativa obvia (cada escaneo crea sus hallazgos) es más simple pero pierde algo que vale bastante en la defensa: con este modelo pueden decir *"este XSS lleva tres escaneos abierto"* y *"estos cuatro se remediaron entre el escaneo 2 y el 3"*. Con el modelo simple, cada escaneo es una isla y esa pregunta no tiene respuesta.

Si deciden que es demasiado, la simplificación es contenida: mueven `scan_id` a `findings` y eliminan `finding_observations`. Pero tómenlo como decisión explícita, no por omisión.

---

## 2. Las siete tablas

| Tabla | Qué guarda | Se modifica |
|---|---|---|
| `targets` | Aplicaciones del laboratorio | Casi nunca |
| `scans` | Cada ejecución de una herramienta | Solo al terminar |
| `findings` | El problema, normalizado | `occurrences`, `last_seen_at`, `status` |
| `finding_observations` | Qué escaneo vio qué hallazgo | Solo inserción |
| `finding_instances` | URLs concretas agrupadas | Solo inserción |
| `ai_enrichments` | Salida del modelo, con histórico | Solo `is_current` |
| `validations` | Decisiones humanas, con histórico | Solo inserción |

Las dos últimas son **append-only** a propósito: una revisión que se sobrescribe deja de ser evidencia.

---

## 3. Deduplicación en la base, no en el código

```sql
UNIQUE (target_id, dedupe_key)
```

La ingesta usa `INSERT ... ON CONFLICT DO UPDATE`:

```python
stmt = insert(Finding).values(**datos)
stmt = stmt.on_conflict_do_update(
    constraint="uq_findings_target_dedupe",
    set_={"occurrences": Finding.occurrences + 1, "last_seen_at": func.now()},
).returning(Finding.id)
```

Esto importa más de lo que parece. Si la deduplicación vive en la aplicación (consultar, decidir, insertar), dos importaciones concurrentes producen duplicados y el bug aparece justo cuando demuestran el sistema. Con la restricción en la base, el duplicado es imposible: la segunda transacción choca y se convierte en actualización.

---

## 4. Índices y por qué cada uno

| Índice | Consulta que resuelve |
|---|---|
| `uq_findings_target_dedupe` | La ingesta. Es el que hace posible el upsert. |
| `ix_findings_dashboard` (target, status, severity) | El listado filtrado del dashboard. Es la consulta más frecuente del sistema. |
| `ix_findings_correlation` | "¿Qué otras herramientas reportan esto?" |
| `ix_findings_cwe` | Agrupación por CWE en el informe. |
| `uq_enrichment_vigente` | Índice **parcial y único** sobre `finding_id WHERE is_current`. |
| `ix_observations_scan` | "¿Qué vio el escaneo N?" |
| `ix_validations_finding_fecha` | La validación más reciente de un hallazgo. |

El índice parcial merece atención. Garantiza a nivel de base que haya **como máximo un enriquecimiento vigente por hallazgo**, sin impedir guardar el histórico. Es una función específica de PostgreSQL y queda bien mencionarla en la defensa como justificación técnica de haber elegido Postgres y no SQLite.

---

## 5. Constraints que hacen cumplir las reglas del proyecto

Las promesas de la propuesta están escritas como restricciones, no como convenciones que alguien recuerde respetar.

```sql
-- "Nunca se opera sobre infraestructura de terceros"
CHECK (environment = 'lab')

-- "Un campo que el modelo no produjo válidamente se queda en null"
CHECK (state = 'ok' OR (owasp_category IS NULL AND priority IS NULL
       AND explanation IS NULL AND remediation_summary IS NULL))

-- Un motivo de fallo solo tiene sentido si hubo fallo
CHECK (state = 'failed' OR failure_reason IS NULL)

CHECK (confidence >= 0 AND confidence <= 1)
CHECK (cvss_score BETWEEN 0 AND 10)
```

El segundo es el importante. Impide por construcción que un enriquecimiento fallido quede con campos rellenados a medias, que es la forma más fácil de que el tablero mienta sin que nadie se dé cuenta.

Los enums son **nativos de PostgreSQL**, no columnas de texto. Un valor fuera del enum lo rechaza la base aunque el código tenga un bug. Agregar un valor exige migración, y eso es deseable: obliga a decidirlo en vez de que aparezca solo.

---

## 6. `ai_enrichments` es histórico

Reenriquecer con otro prompt **agrega una fila** y marca la anterior con `is_current = false`. Sin eso no pueden demostrar que ajustar el prompt mejoró algo, que es exactamente la tarea T-047.

`validations.enrichment_id` apunta a qué salida se estaba juzgando. Sin esa columna, comparar la versión 1.0 del prompt contra la 1.2 es ambiguo: no se sabe cuál de las dos evaluó cada revisor.

`prompt_sha256` guarda el hash del prompt exacto enviado. Junto con `model` y `prompt_version`, es lo que permite reproducir una corrida meses después.

---

## 7. Las métricas del S6 son una consulta

Las cuatro banderas `ai_*` de `validations` se completan durante el triage normal. Las tres métricas del informe salen de aquí:

```sql
SELECT
  count(*) FILTER (WHERE ai_owasp_correcto)     * 1.0 / count(ai_owasp_correcto)     AS acierto_owasp,
  count(*) FILTER (WHERE ai_prioridad_correcta) * 1.0 / count(ai_prioridad_correcta) AS acierto_prioridad,
  count(*) FILTER (WHERE ai_alucinacion)        * 1.0 / count(ai_alucinacion)        AS tasa_alucinacion,
  count(*) AS revisados
FROM validations v
JOIN ai_enrichments e ON e.id = v.enrichment_id
WHERE e.prompt_version = 'p-1.2.0';
```

Filtrar por `prompt_version` es lo que convierte "el prompt mejoró" en un número comparable.

---

## 8. Puesta en marcha

```bash
pip install sqlalchemy alembic psycopg[binary]
alembic init migrations
# en migrations/env.py:  from models import Base; target_metadata = Base.metadata
alembic revision --autogenerate -m "esquema inicial"
alembic upgrade head
```

`gen_random_uuid()` viene incluida desde PostgreSQL 13. En versiones anteriores hay que habilitar `pgcrypto`.

**Revisen la migración autogenerada antes de aplicarla.** Alembic no siempre detecta bien los índices parciales ni los tipos enum nativos: verifiquen que `uq_enrichment_vigente` aparezca con su cláusula `WHERE is_current` y que los `CREATE TYPE` estén antes de las tablas que los usan.

---

## 9. Antes de darlo por cerrado

- [ ] Decidido en equipo: hallazgo por objetivo (actual) o hallazgo por escaneo (simple).
- [ ] `alembic upgrade head` crea el esquema completo sobre una base vacía.
- [ ] `alembic downgrade base` lo revierte sin dejar tipos huérfanos.
- [ ] Verificado que reimportar el mismo JSON no crea filas nuevas, solo sube `occurrences`.
- [ ] Probado que el CHECK de enriquecimiento fallido efectivamente rechaza una fila mal formada.
- [ ] Medido el listado del dashboard con al menos 500 hallazgos cargados.

El penúltimo es el que se salta todo el mundo: escriban el test que intenta insertar un enriquecimiento inválido y confirma que la base lo rechaza. Un constraint que nadie probó es un comentario.
