# IA · Modelo, prompt y validación

**Responsable:** Joaquín Herrera · **Tareas:** T-009, T-028 a T-031, T-033, T-034 · **Actualizado:** 14-10-2026

Documento de referencia para reproducir cualquier salida del modelo. Si algo de lo que está aquí cambia (modelo, prompt o parámetros), se actualiza este archivo **y** `PROMPT_VERSION` en `backend/app/ia/prompt.py`.

---

## 1. Decisión de modelo (T-009)

| | |
|---|---|
| **Modelo** | `llama3.1:8b-instruct-q4_K_M` (Ollama) |
| **Tamaño** | 4.9 GB en disco · 5.3 GB cargado · contexto 4096 tokens |
| **Nodo de inferencia** | PC de Joaquín · RTX 3060 Ti 8 GB · `100% GPU` según `ollama ps` |
| **Latencia medida** | Mediana 1.6 a 2.1 s por hallazgo con el prompt completo (4 corridas) |
| **Arranque en frío** | ~15 s (primera llamada tras 5 min sin uso) |
| **Proyección** | ~10 minutos para 300 hallazgos |

**Por qué este modelo:** un 8B cuantizado a 4 bits cabe completo en 8 GB de VRAM, y eso evita repartir el cálculo con la CPU. La latencia queda muy por debajo del umbral de 15 s que exigía el plan, así que **se enriquecen todos los hallazgos**, sin lotes ni filtros por severidad.

**Plan B:** si el nodo no está disponible o la latencia supera 40 s, se pasa a un modelo más chico (familia 3B) o se enriquecen solo los hallazgos de severidad alta. Evidencia completa en `docs/evidencias/latencia_ollama.md`.

## 2. Parámetros de la llamada

| Parámetro | Valor | Motivo |
|---|---|---|
| `format` | `"json"` | Fuerza a Ollama a devolver JSON sintácticamente válido |
| `temperature` | `0.1` | Clasificación, no creatividad |
| `keep_alive` | `"10m"` | Evita el arranque en frío entre hallazgos de un mismo lote |
| `seed` | sin fijar | Fijarla (`OLLAMA_SEED`) solo para demos: esconde la variación real del modelo |
| `timeout` | 120 s | Margen sobre el arranque en frío |

Todo se configura con variables de entorno en `backend/app/config.py`: `OLLAMA_URL`, `OLLAMA_MODEL`, `OLLAMA_TIMEOUT_S`, `OLLAMA_KEEP_ALIVE` y `OLLAMA_SEED`.

## 3. Prompt vigente: v2 (T-029, T-033)

El texto exacto está en `backend/app/ia/prompt.py`. Pide seis campos: `explicacion`, `impacto`, `owasp`, `prioridad`, `confianza` y `remediacion`.

**Qué cambió de v1 a v2:**

1. Cada categoría OWASP lleva una descripción con ejemplos, tomada de la descripción oficial de OWASP.
2. Un aviso explícito de que la numeración cambió respecto de 2021.
3. Reglas contra exagerar el impacto: una defensa ausente no equivale a un ataque.
4. Una guía para la prioridad, que parte de la severidad de ZAP, y para la confianza.

**Resultados** (5 hallazgos × 3 repeticiones; 3 hallazgos con criterio definido, 9 respuestas puntuables por corrida):

| | v1 | v2 |
|---|---|---|
| Acierto OWASP (2 corridas) | 3/9 y 4/9 → **7/18** | 7/9 y 6/9 → **13/18** |
| JSON válido con los 6 campos | 30/30 | 30/30 |
| XSS (A05) | 6/6 | 6/6 |
| CORS (A01 o A02) | 1/6 | 6/6 |
| CSP sin cabecera (A02) | 0/6 | 1/6 |

**Hallazgos relevantes para el informe:**

- **CSP queda en A05 en 11 de 12 respuestas**, incluso con la v2, que dice explícitamente que A05 ya no es Misconfiguration. Es evidencia de que el modelo arrastra la numeración de 2021.
- **La confianza no distingue aciertos de errores:** con la v2 da 0.93 cuando acierta y 0.90 cuando falla. **No se debe usar para ordenar la revisión.**
- **No respeta la regla de prioridad:** CSP es Medium en ZAP y le asignó p1.
- **Alucinaciones observadas:** ubica un timestamp "en la URL de un archivo CSS" cuando está en el contenido; atribuye "ejecución de código arbitrario" a un XSS reflejado.
- **Variación entre corridas:** ±1 de 9 con temperatura 0.1. Una sola corrida no basta para concluir.
- **Riesgo de sobreajuste:** la v2 menciona "cabeceras" y "CORS", que coinciden con los casos de prueba. Hay que validarla con hallazgos que no conoce (fixture `ajax_v2`, golden set del S6).

Respuestas completas en `docs/evidencias/respuestas_modelo/`. Script de medición: `lab/prueba_prompt.py --prompt v1|v2`.

## 4. Validación y reintentos (T-030, T-031)

Código en `backend/app/ia/`:

| Archivo | Qué hace |
|---|---|
| `cliente.py` | Llama a Ollama con timeout. Errores tipados: `timeout`, `ollama_no_disponible`, `respuesta_http_invalida` |
| `esquema.py` | Valida con Pydantic. OWASP debe ser `A01` a `A10:2025`, prioridad `p1` a `p4` y confianza en `[0, 1]` |
| `prompt.py` | Prompt v2 y armado de los datos que ve el modelo (solo evidencia) |
| `enriquecer.py` | Orquesta: prompt → modelo → validación → reintento con reparación |

**Flujo:**

```
intento 1 ─ válido ──────────────────────────────→ state = ok
    │ inválido
    ▼
intento 2: el mismo prompt + "tu respuesta no es válida por: …"
    │ inválido
    ▼
intento 3 ─ inválido ──→ state = failed, failure_reason, campos de contenido en NULL
```

**Reglas:**

- Se normaliza el **formato** (`a02:2025` → `A02:2025`, `P2` → `p2`), nunca el **contenido**. `A05:2021` se rechaza y se le pide corregir, no se "traduce".
- Si Ollama está apagado, no se reintenta: el hallazgo se marca de inmediato y el lote sigue.
- Un fallo nunca deja campos a medias. Esto coincide con la restricción `ck_enrichment_fallo_sin_datos` de la base.
- La salida usa los nombres exactos de las columnas de `ai_enrichments`: `AiEnrichment(finding_id=..., **enriquecer(hallazgo))`.
- `prompt_sha256` es el hash del prompt del intento 1. Con él, más `model` y `prompt_version`, se reproduce la corrida.

**Probar:**

```powershell
cd C:\Proyectotitulo\capstone\backend
python -m pytest tests/test_enriquecer.py -v            # sin Ollama
$env:OLLAMA_URL = "http://localhost:11434"
python -m app.ia.enriquecer ..\lab\fixtures\zap_juiceshop_ajax_v1.json   # con Ollama real
```

## 5. Alternativas para clasificar y priorizar, y recomendación

**La pregunta:** ¿quién asigna la categoría OWASP y la prioridad de cada hallazgo? Hoy lo hace el modelo, y las pruebas muestran que formatea bien pero que el contenido es irregular.

### 5.1 Evidencia que motiva la decisión

| Observación | Dato | Fuente |
|---|---|---|
| El formato siempre es válido | 26/26 respuestas en `ajax_v2`, 60/60 en las pruebas del prompt | `evidencias/enriquecimiento_ajax_v2.md` |
| Acierta la categoría en casos claros, no siempre | 11/16 en `ajax_v2`; 13/18 con el prompt v2 | ídem, sección 3 de este documento |
| Sesgo persistente hacia OWASP 2021 | CSP clasificado como A05 en 15 de 16 respuestas, pese a la instrucción explícita | ídem |
| Mismo CWE, distinta categoría | CWE-497 en A01 (Private IP) y A02 (Timestamp) | `evidencias/enriquecimiento_ajax_v2.md` |
| La prioridad no sigue la regla pedida | 11/26 respuestas dentro del tramo según la severidad de ZAP | ídem |
| La confianza no discrimina | 0.93 cuando acierta contra 0.90 cuando falla | sección 3 |
| Contra la anotación humana | ver `evidencias/metricas_golden_set.md` (modelo contra regla fija) | T-045 |

### 5.2 Las tres alternativas

**A · El modelo decide todo (situación actual).**
El modelo entrega categoría, prioridad, explicación y remediación. La persona que valida corrige lo que esté mal.

**B · Reglas deterministas, el modelo solo redacta.**
La **categoría** sale de una tabla CWE → OWASP 2025, construida con el mapeo oficial de OWASP. La **prioridad** sale de una regla según la severidad de ZAP. El modelo solo escribe la explicación, el impacto y la remediación.

**Mixta · La regla propone, el modelo contrasta, la persona decide.**
La tabla CWE asigna la categoría de referencia y el modelo propone la suya. **Si no coinciden, el hallazgo se marca "revisar"** y queda primero en la cola de validación. La prioridad sale de la regla. El modelo redacta la explicación, el impacto y la remediación.

| Criterio | A · Modelo | B · Reglas | Mixta |
|---|---|---|---|
| Reproducibilidad de la categoría | Baja (cambia entre corridas) | Total | Total (la de referencia) |
| Reproducibilidad de la prioridad | Baja | Total | Total |
| Hallazgos sin CWE (informativos) | Inventa una categoría (Modern Web App → A05) | "No aplica", que es lo correcto | "No aplica" |
| CWE ambiguo o fuera de la tabla | Lo resuelve, con errores | Queda sin categoría | Usa la del modelo, marcado "revisar" |
| Aporte visible de la IA | Clasifica y redacta | Solo redacta | Redacta **y** detecta discrepancias |
| Señal para priorizar la revisión humana | Ninguna confiable (la confianza no discrimina) | Ninguna | **La discrepancia** regla/modelo |
| Coherencia con "la validación final es humana" | Media | Alta | **Alta, y además guía la validación** |
| Cambios en el código | Ninguno | Tabla + regla; se ignoran dos campos del modelo | Tabla + regla + comparación |
| Cambios en la base de datos | Ninguno | Ninguno (la tabla vive en el código) | Ninguno: la discrepancia se calcula al consultar |
| Esfuerzo estimado | 0 | ~1 día | ~1 a 1,5 días |
| Cómo se presenta el proyecto | "La IA clasifica y prioriza" | "La IA explica y recomienda" | "La IA explica, recomienda y señala lo dudoso" |

### 5.3 Recomendación: **Mixta para la categoría, regla fija para la prioridad**

1. **Prioridad por regla** (High → p1, Medium → p2, Low → p3, Informational → p4), ajustable por la persona que valida. Es la parte donde el modelo rinde peor (11/26 dentro del tramo) y donde una regla simple es transparente y defendible.
2. **Categoría mixta.** La tabla CWE da la categoría de referencia y el modelo la suya. Las discrepancias se convierten en el criterio para **ordenar la revisión humana**, que es justo lo que la confianza del modelo no logra hacer.
3. **El modelo conserva lo que hace bien:** explicar, describir el impacto y proponer la remediación. El formato ya está garantizado por la validación (sección 4).

**Por qué no A:** sus errores son sistemáticos (CSP en A05) y la confianza no permite detectarlos, así que toda la carga de detección recae en la persona.
**Por qué no B pura:** se pierde la capacidad del modelo de clasificar hallazgos sin CWE claro, y la IA queda reducida a redactar.

**Qué se mantiene igual:** `enriquecer()`, la validación y los reintentos. El modelo sigue entregando su categoría y su prioridad, que quedan guardadas en `ai_enrichments` como **sugerencia**, para poder seguir midiéndolas contra el golden set (T-046, T-047).

### 5.4 Implementación propuesta (si el grupo aprueba)

| Paso | Dónde | Responsable |
|---|---|---|
| Tabla CWE → OWASP 2025 para los CWE presentes en los fixtures, citando el mapeo oficial | `backend/app/ia/owasp_por_cwe.py` | Joaquín |
| Regla de prioridad por severidad | mismo módulo | Joaquín |
| Campos calculados `owasp_referencia`, `requiere_revision` y `prioridad_regla` en la respuesta de la API | endpoint de consulta de hallazgos | Luciano |
| Mostrar la discrepancia y ordenar la cola de validación por ella | dashboard (S7) | Luciano |
| Medir cuántos errores del modelo detecta la discrepancia | `scripts/metricas_golden_set.py` | Joaquín |

**Decisión del grupo:** _pendiente — registrar aquí la opción elegida, la fecha y quiénes la tomaron._
