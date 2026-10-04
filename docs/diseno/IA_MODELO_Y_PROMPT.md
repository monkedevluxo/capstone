# IA · Modelo, prompt y validación

**Responsable:** Joaquín Herrera · **Tareas:** T-009, T-028 a T-031, T-033, T-034 · **Actualizado:** 04-10-2026

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

## 5. Decisión pendiente del grupo

**¿Quién asigna la categoría OWASP?**

- **A**: el modelo, como hoy.
- **B**: una tabla CWE → OWASP 2025, y el modelo solo explica, describe el impacto y propone la remediación.
- **Mixta**: la tabla asigna la categoría, el modelo propone la suya y, si no coinciden, el hallazgo se marca para revisión.

El módulo funciona igual con cualquiera de las tres: B o la mixta agregan un paso después de `enriquecer()`, sin cambiar el cliente ni la validación.
