# Esquema del hallazgo normalizado

**SentinelAI · v1.0.0 · tarea T-001**

Este documento fija el contrato de datos del proyecto. Todo lo demás (modelo de datos, API, prompt, dashboard e informe) depende de él, así que conviene discutirlo y cerrarlo entre los tres antes de escribir código de backend.

Archivos que lo acompañan:

| Archivo | Para qué sirve |
|---|---|
| `finding.schema.json` | Esquema formal (JSON Schema 2020-12). Valida en CI y en los tests. |
| `ejemplo_hallazgo.json` | Un hallazgo real de ZAP contra Juice Shop, completo hasta la validación humana. |
| `normalizacion.py` | Implementación de referencia de `path_template`, `dedupe_key` y el mapeo de severidad. |

---

## 1. La idea central: cuatro capas separadas

El registro tiene cuatro zonas y **ninguna escribe sobre otra**. Es la decisión de diseño que sostiene la trazabilidad que promete la propuesta.

| Capa | Bloques | Quién escribe | Se modifica |
|---|---|---|---|
| Origen | `source`, `evidence` | El importador, copiando la herramienta | Nunca |
| Normalizada | `location`, `severity`, `classification`, `dedupe` | SentinelAI, con reglas deterministas | Solo al reprocesar |
| Interpretada | `ai` | El modelo local | Al reenriquecer, versionado |
| Decidida | `validation`, `status` | Una persona | Cada revisión |

Si alguien pregunta en la defensa "¿cómo saben que la IA no alteró el hallazgo?", la respuesta es esta tabla: `source.raw` guarda el bloque crudo de ZAP y el modelo escribe únicamente dentro de `ai`.

---

## 2. Campos

### Identidad y contexto

| Campo | Tipo | Nota |
|---|---|---|
| `schema_version` | semver | Versión del esquema con que se escribió el registro. Un cambio incompatible sube el *major* y obliga a migración. |
| `finding_id` / `scan_id` / `target.target_id` | UUID | |
| `target.environment` | enum: `lab` | Solo admite un valor, a propósito. Deja constancia en cada registro de que nunca se escaneó infraestructura de terceros. Es su respaldo frente a la Ley 21.459 y cuesta un campo. |

### `source` — lo que dijo la herramienta

`raw` guarda el bloque completo tal como salió, sin recortar ni corregir. Es la evidencia original que la propuesta se compromete a conservar. `rule_id` es el identificador propio de la herramienta (en ZAP, `pluginid`): **no es comparable entre herramientas**, y de ahí sale la regla de deduplicación de la sección 4.

### `location` — dónde

`url` es la URL concreta. `path_template` es la versión normalizada, y es lo que hace que el listado sea legible. Ver sección 3.

### `evidence` — la prueba

`instance_count` es el total real de URLs agrupadas; `instances` guarda como máximo 50 para no inflar la base. **No borren `instance_count` cuando trunquen la lista**: si el hallazgo aparece en 400 URLs, ese número es parte de la severidad real.

### `severity` — cuán grave

`tool_raw` conserva la palabra de la herramienta sin traducir. `normalized` es la escala común. Ver sección 5.

### `classification` — con qué se corresponde

`cwe_id` es el único puente confiable entre herramientas distintas. ZAP lo entrega en casi todos sus hallazgos. Guárdenlo como entero, no como texto: `"79"` y `79` no se agrupan solos.

### `ai` — lo que interpretó el modelo

`null` mientras no se haya intentado enriquecer. Si el modelo falla tras tres intentos, se escribe `state: "failed"` con `failure_reason` y el resto en `null`.

Regla dura: **un campo que el modelo no produjo válidamente se queda en `null`**. Nada de rellenar con un valor por defecto ni con "Medium" para que el tablero se vea completo. Un hallazgo sin enriquecer debe verse distinto en la interfaz de uno enriquecido; si no, la métrica de cobertura miente.

Sobre `confidence`: es la autoevaluación del modelo, no una medida de exactitud. Un LLM puede declarar 0.95 y equivocarse. Muéstrenlo, pero la afirmación defendible sobre calidad sale del golden set (sección 6), no de este número. Vale la pena que lo tengan claro porque es una pregunta probable en la defensa.

### `validation` — lo que decidió una persona

`decision`, `reviewer` y `reviewed_at` son obligatorios. `priority_override` deja registro de cuando una persona corrige la prioridad sugerida por el modelo, que es exactamente el dato que necesitan para medirlo.

---

## 3. Normalización de rutas

Sin esto, un escaneo de Juice Shop les devuelve el mismo XSS reportado cuarenta veces, una por cada producto. Es la causa número uno del ruido que la propuesta dice combatir.

Reglas, en orden:

1. Descartar esquema y host.
2. Segmentos: solo dígitos → `{id}`; UUID → `{uuid}`; hex de 8 o más caracteres → `{hash}`. La extensión se separa antes y se conserva.
3. Pasar a minúsculas.
4. Quitar la barra final.
5. De la query, conservar los **nombres** de parámetros ordenados alfabéticamente y descartar los valores.

El punto 5 importa: el mismo endpoint atacado por dos parámetros distintos son dos hallazgos distintos y no deben colapsarse.

```
/rest/products/47/reviews                    →  /rest/products/{id}/reviews
/rest/products/search?q=<script>alert(1)>    →  /rest/products/search?q
/api/Users/0c5d8e77-3b41-...-1e07f2a95d10    →  /api/users/{uuid}
/assets/a3f91bc2e7d40518.js                  →  /assets/{hash}.js
```

`normalizacion.py` implementa esto y trae los casos de prueba. Corran `python normalizacion.py` antes de tocarlo.

---

## 4. Deduplicación: dos claves, no una

Es la decisión de diseño más discutible del esquema, así que llévenla explicada a la defensa.

**`dedupe.key` — dentro de una misma herramienta.**

```
sha256(tool | rule_id | path_template | param | method)[:16]
```

Determinista: reimportar el mismo escaneo no crea registros nuevos, solo incrementa `occurrences`. Incluye `tool` a propósito, porque ZAP y Nikto no comparten numeración de reglas: sin ese campo, la regla 40012 de una y la 40012 de la otra colapsarían en un mismo hallazgo aunque no tengan nada que ver.

**`dedupe.correlation_key` — entre herramientas distintas.**

```
sha256(cwe_id | path_template | param)[:16]     // null si no hay CWE
```

Agrupa por CWE, que es lo único comparable entre herramientas. **Sugiere, no fusiona.** Los registros siguen separados y la interfaz muestra "2 herramientas reportan esto". Fusionar de verdad significaría descartar la evidencia de una de las dos, que es justo lo que la propuesta promete no hacer.

La distinción también les da una respuesta honesta a "¿y si el agrupamiento se equivoca?": la clave intra-herramienta es exacta y la cruzada es una sugerencia reversible.

---

## 5. Escala de severidad

Escala común: `critica` · `alta` · `media` · `baja` · `informativa`.

| ZAP `riskcode` | ZAP | Normalizada |
|---|---|---|
| 3 | High | `alta` |
| 2 | Medium | `media` |
| 1 | Low | `baja` |
| 0 | Informational | `informativa` |

**ZAP no produce `critica`.** Su escala llega hasta High. Ese nivel queda reservado para OpenVAS con CVSS ≥ 9.0. Es tentador mapear High → crítica para que el tablero se vea más dramático, pero eso falsea el dato y es una pregunta fácil de hacer en la defensa.

Para OpenVAS: ≥ 9.0 `critica` · ≥ 7.0 `alta` · ≥ 4.0 `media` · > 0 `baja` · 0 `informativa`.

`severity.tool_confidence` mapea el `confidence` de ZAP (`0`–`4`). Un hallazgo con confianza `0` es un falso positivo declarado por la propia herramienta: es candidato inmediato a filtrarse y da una métrica gratis para el informe.

---

## 6. OWASP Top 10: usen la edición 2025

**Importante para su presentación.** La propuesta habla del OWASP Top 10 sin especificar edición, y la 2021 quedó superada. La edición vigente es el Top 10:2025, publicado en noviembre de 2025 y finalizado en enero de 2026; la próxima no se espera hasta alrededor de 2028–2029. Los cambios respecto de 2021: dos categorías nuevas, Software Supply Chain Failures (#3) y Mishandling of Exceptional Conditions (#10); Security Misconfiguration subió al #2; y SSRF dejó de ser categoría propia y quedó dentro de Broken Access Control.

Fuente: <https://owasp.org/Top10/2025/>. Verifíquenla directamente antes de citarla en el informe.

Enum del esquema:

| ID | Categoría |
|---|---|
| `A01:2025` | Broken Access Control (absorbe SSRF, CWE-918) |
| `A02:2025` | Security Misconfiguration |
| `A03:2025` | Software Supply Chain Failures |
| `A04:2025` | Cryptographic Failures |
| `A05:2025` | Injection (incluye XSS) |
| `A06:2025` | Insecure Design |
| `A07:2025` | Authentication Failures |
| `A08:2025` | Software or Data Integrity Failures |
| `A09:2025` | Security Logging & Alerting Failures |
| `A10:2025` | Mishandling of Exceptional Conditions |

Dos consecuencias prácticas:

- **El campo `ai.owasp.version` es obligatorio.** Guardar la edición junto a la categoría vale poco hoy y mucho después: sin él, un `A10` guardado en 2026 es ambiguo para siempre.
- **Confirmen la edición con el profesor.** Si el ramo trabaja sobre la 2021, agreguen `"2021"` al enum de `version` y el set de categorías correspondiente. El esquema ya lo admite. Pero si el modelo clasifica con una edición y el informe declara otra, es un error que se nota.

Cuidado adicional: mucho material de entrenamiento de los LLM es anterior a 2025, así que **el modelo tenderá a clasificar con las categorías de 2021** si no se lo indican. El prompt debe traer la lista de 2025 explícita, y el validador debe rechazar cualquier valor fuera del enum. Este es un caso concreto donde su validación Pydantic (T-030) se gana el sueldo, y es buen material para la sección de resultados.

---

## 7. Ciclo de vida de `status`

```
nuevo ──→ en_triage ──┬──→ confirmado ──→ remediado
                      ├──→ falso_positivo
                      └──→ riesgo_aceptado
```

`nuevo` lo pone la ingesta. Todas las demás transiciones exigen un bloque `validation` con autor y fecha. La transición no se guarda sin ese registro: es la implementación literal de "la validación final es siempre humana y queda registrada".

---

## 8. El golden set sale del triage

`validation.ai_review` tiene cuatro banderas: `owasp_correcto`, `prioridad_correcta`, `remediacion_util` y `alucinacion`.

Están dentro del flujo normal de revisión a propósito. Si los revisores las completan mientras hacen triage, en la semana 11 ya tienen la muestra anotada acumulada y el sprint S6 se reduce a calcular y documentar, en vez de anotar cincuenta hallazgos a mano contra el reloj.

Las tres métricas del informe salen directo de ahí:

- Acierto de categoría OWASP = `owasp_correcto` verdadero / revisados
- Acierto de prioridad = `prioridad_correcta` verdadero / revisados
- Tasa de alucinación = `alucinacion` verdadero / revisados

---

## 9. Antes de darlo por cerrado

- [ ] Los tres revisaron el esquema y están de acuerdo con los nombres de los campos.
- [ ] Confirmada con el profesor la edición del OWASP Top 10 a usar.
- [ ] `python normalizacion.py` pasa todos los casos.
- [ ] `ejemplo_hallazgo.json` valida contra `finding.schema.json` en CI.
- [ ] Definido qué pasa con un hallazgo de ZAP sin CWE (hoy: `correlation_key` en `null`, se agrupa solo dentro de ZAP).
- [ ] Decidido si `evidence.request` y `evidence.response` se truncan y a cuántos KB.

Ese penúltimo punto es el que más se les va a colar: revisen cuántos hallazgos de su primer escaneo vienen sin CWE antes de dar por buena la estrategia de correlación.
