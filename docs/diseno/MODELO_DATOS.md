# Modelo de datos

**SentinelAI · PostgreSQL 16 · tareas T-011, T-012, T-013, T-017 y T-066**

Deriva de `finding.schema.json` v1.0.0. Describe lo implementado en `backend/app/models.py` y en las dos migraciones de `backend/migrations/versions/` (sección 8), revisado el 25-11-2026. Si cambia el modelo, cambia esto.

---

## 1. La decisión de fondo

**Un hallazgo pertenece al objetivo, no al escaneo.** Se discutió al inicio del S2 y se adoptó así.

La unicidad es `(target_id, dedupe_key)`. Reescanear Juice Shop no crea filas nuevas: agrega una fila en `finding_observations` y actualiza `last_seen_at`.

La alternativa obvia (cada escaneo crea sus hallazgos) es más simple pero pierde algo que vale bastante en la defensa: con este modelo pueden decir *"este XSS lleva tres escaneos abierto"* y *"estos cuatro se remediaron entre el escaneo 2 y el 3"*. Con el modelo simple, cada escaneo es una isla y esa pregunta no tiene respuesta.

La alternativa simple habría sido mover `scan_id` a `findings` y eliminar `finding_observations`. Se descartó para conservar el historial entre escaneos: con los tres escaneos de Juice Shop, 33 alertas quedan en 17 hallazgos únicos, y cada uno sabe qué escaneos lo vieron.

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

### Diccionario de datos

Todas las tablas usan `id` UUID generado por la base (`gen_random_uuid()`). Las fechas son `timestamptz`.

**`targets`**: `nombre`, `base_url` (única), `environment` (solo `'lab'`), `created_at`.

**`scans`**: `target_id`, `tool` (enum `herramienta`), `tool_version`, `status` (enum `estado_escaneo`), `started_at`, `finished_at`, `report_sha256` (hash del JSON importado; un reporte repetido se rechaza con 409) y `stats` (JSONB con `hallazgos`, `nuevos`, `repetidos`, `descartados` y `por_severidad`).

**`findings`**:

| Grupo | Columnas |
|---|---|
| Origen | `target_id`, `schema_version`, `tool`, `rule_id`, `rule_name`, `source_raw` (JSONB: la alerta de ZAP tal cual llegó) |
| Contenido | `titulo`, `descripcion`, `url`, `path_template`, `method`, `param`, `evidence_snippet` |
| Clasificación | `severity` (enum `severidad`), `severity_tool_raw`, `tool_confidence`, `cvss_score`, `cwe_id`, `wasc_id` |
| Deduplicación | `dedupe_key` (16 caracteres, única por objetivo), `correlation_key`, `occurrences`, `first_seen_at`, `last_seen_at` |
| Ciclo de vida | `status` (enum `estado_hallazgo`), `created_at`, `updated_at` |

**`finding_observations`**: `finding_id`, `scan_id` (par único), `instance_count` (cuántas instancias vio ese escaneo), `observed_at`.

**`finding_instances`**: `finding_id`, `url`, `method`, `param`. Se guardan al crear el hallazgo, con un máximo por hallazgo.

**`ai_enrichments`**:

| Grupo | Columnas |
|---|---|
| Trazabilidad | `finding_id`, `state` (`ok` o `failed`), `model`, `prompt_version`, `prompt_sha256`, `generated_at`, `latency_ms`, `attempts`, `is_current` |
| Sugerencia | `explanation`, `impact`, `owasp_version` (por defecto `2025`), `owasp_category`, `priority`, `confidence`, `remediation_summary`, `remediation_steps` (JSONB) |
| Fallo | `failure_reason` (solo si `state = 'failed'`) |

**`validations`**: `finding_id`, `enrichment_id` (qué sugerencia se juzgó; queda en null si esa sugerencia se borra), `decision` (enum `decision_validacion`), `reviewer`, `reviewed_at`, `priority_override`, `comment`, y las banderas del golden set `ai_owasp_correcto`, `ai_prioridad_correcta`, `ai_remediacion_util`, `ai_alucinacion` y `ai_nota`.

### Enumeraciones

| Tipo | Valores |
|---|---|
| `herramienta` | `zap`, `nikto`, `openvas` (hoy solo se importa ZAP) |
| `severidad` | `critica`, `alta`, `media`, `baja`, `informativa` |
| `prioridad` | `p1`, `p2`, `p3`, `p4` |
| `estado_hallazgo` | `nuevo`, `en_triage`, `confirmado`, `falso_positivo`, `riesgo_aceptado`, `remediado`, `duplicado` |
| `estado_escaneo` | `pendiente`, `ejecutando`, `importado`, `fallido` |
| `estado_ia` | `ok`, `failed` |
| `categoria_owasp` | `A01:2025` a `A10:2025` |
| `decision_validacion` | `confirmado`, `falso_positivo`, `riesgo_aceptado`, `duplicado`, `requiere_segunda_opinion` |

Las borraduras van en cascada desde el objetivo: borrar un objetivo borra sus escaneos, hallazgos, observaciones, instancias, sugerencias y decisiones.

---

## 3. Deduplicación en la base, no en el código

```sql
UNIQUE (target_id, dedupe_key)
```

La ingesta usa `INSERT ... ON CONFLICT DO UPDATE`:

```python
stmt = insert(Finding).values(**valores)
stmt = stmt.on_conflict_do_update(
    constraint="uq_findings_target_dedupe",
    set_={"last_seen_at": func.now(), "occurrences": stmt.excluded.occurrences},
).returning(Finding.id, literal_column("(xmax = 0)").label("es_nuevo"))
```

`occurrences` queda con el conteo del último escaneo que vio el hallazgo; el de cada escaneo se guarda en `finding_observations.instance_count`. `xmax = 0` solo es verdadero en una fila recién insertada, y así la ingesta distingue "nuevo" de "ya conocido" en una sola sentencia (`backend/app/ingesta.py`).

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
| `ix_scans_target_started` | Los escaneos de un objetivo, del más reciente al más antiguo. |
| `ix_enrichments_finding` | Las sugerencias de un hallazgo, vigente o no. |
| `ix_instances_finding` | Las URLs concretas de un hallazgo. |
| `ix_validations_reviewer` | Las decisiones de un revisor, para el golden set. |

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

CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
CHECK (cvss_score IS NULL OR (cvss_score >= 0 AND cvss_score <= 10))
CHECK (occurrences >= 1)
```

El segundo es el importante. Impide por construcción que un enriquecimiento fallido quede con campos rellenados a medias, que es la forma más fácil de que el tablero mienta sin que nadie se dé cuenta.

Los enums son **nativos de PostgreSQL**, no columnas de texto. Un valor fuera del enum lo rechaza la base aunque el código tenga un bug. Agregar un valor exige migración, y eso es deseable: obliga a decidirlo en vez de que aparezca solo.

---

## 6. `ai_enrichments` es histórico

Reenriquecer con otro prompt **agrega una fila** y marca la anterior con `is_current = false`. Sin eso no pueden demostrar que ajustar el prompt mejoró algo, que es exactamente la tarea T-047.

`validations.enrichment_id` apunta a qué salida se estaba juzgando. Sin esa columna, comparar la versión 1.0 del prompt contra la 1.2 es ambiguo: no se sabe cuál de las dos evaluó cada revisor.

`prompt_sha256` guarda el hash del prompt exacto enviado. Junto con `model` y `prompt_version`, es lo que permite reproducir una corrida meses después.

---

## 7. Las métricas de la IA son una consulta

Las cuatro banderas `ai_*` de `validations` se completan durante el triage normal. Las métricas del informe salen de aquí (el informe toma solo la última decisión de cada revisor por hallazgo):

```sql
SELECT
  count(*) FILTER (WHERE ai_owasp_correcto)     * 1.0 / count(ai_owasp_correcto)     AS acierto_owasp,
  count(*) FILTER (WHERE ai_prioridad_correcta) * 1.0 / count(ai_prioridad_correcta) AS acierto_prioridad,
  count(*) FILTER (WHERE ai_remediacion_util)   * 1.0 / count(ai_remediacion_util)   AS remediacion_util,
  count(*) FILTER (WHERE ai_alucinacion)        * 1.0 / count(ai_alucinacion)        AS tasa_alucinacion,
  count(*) AS revisados
FROM validations v
JOIN ai_enrichments e ON e.id = v.enrichment_id
WHERE e.prompt_version = 'v2';
```

`v2` es la versión vigente del prompt (`PROMPT_VERSION` en `backend/app/ia/prompt.py`).

Filtrar por `prompt_version` es lo que convierte "el prompt mejoró" en un número comparable.

---

## 8. Migraciones

El esquema lo crean dos migraciones de Alembic, en `backend/migrations/versions/`:

| Revisión | Archivo | Qué hace |
|---|---|---|
| `418a070dfa63` | `20260915_0110_esquema_inicial.py` | Las siete tablas, los enums nativos, los índices (incluido el parcial `uq_enrichment_vigente ... WHERE is_current`) y las restricciones |
| `7c2e9d41b3a5` | `20261115_2130_estado_duplicado.py` | Agrega `duplicado` a `estado_hallazgo` (T-057). Su `downgrade` no quita el valor: PostgreSQL no permite sacar un valor de un enum sin reescribir la columna |

```bash
docker compose exec api alembic upgrade head
```

---

## 9. Cómo se verifica

| Comprobación | Dónde |
|---|---|
| `alembic upgrade head` crea el esquema completo sobre una base vacía | CI, trabajo "Migraciones y restricciones", en cada PR |
| El modelo y las migraciones no se desincronizan | CI, `alembic check` |
| `alembic downgrade base` y `upgrade head` otra vez, sin tipos huérfanos | CI, último paso del mismo trabajo |
| La base rechaza un objetivo fuera del laboratorio, un enriquecimiento fallido con datos a medias, dos sugerencias vigentes, una confianza fuera de rango y un hallazgo duplicado en el mismo objetivo | `backend/scripts/verificar_bd.py`, en el CI |
| Reimportar el mismo reporte no crea filas: se rechaza con 409 por su `report_sha256`. Otro escaneo que ve el mismo hallazgo agrega una observación y no un hallazgo nuevo | `backend/tests/test_ingesta.py` |
| El listado del dashboard con 500 hallazgos | Sin medición: el laboratorio llega a 17 hallazgos únicos |

Un constraint que nadie probó es un comentario: por eso `verificar_bd.py` intenta insertar lo que la base debe rechazar y falla el CI si lo acepta.
