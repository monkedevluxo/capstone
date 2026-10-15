# Métricas del modelo contra el golden set (T-045)

**Generado:** 14-10-2026 23:52 · **Modelo:** `llama3.1:8b-instruct-q4_K_M` · **Prompt:** v2 · **Corridas por hallazgo:** 2

**Anotación humana:** `docs/evidencias/validacion_manual.csv` (Felipe, sin ver las respuestas del modelo).
**Respuestas del modelo:** `docs/evidencias/respuestas_modelo/golden_set_20261014_234209.json`

Reproducir sin Ollama:
```powershell
cd backend
python scripts/metricas_golden_set.py --desde ..\docs\evidencias\respuestas_modelo\golden_set_20261014_234209.json --ambiguos H02,H03,H05,H10
```

## Resultados

| Métrica | Resultado |
|---|---|
| Hallazgos del golden set cruzados con los fixtures | 10/10 |
| Respuestas del modelo con formato válido | 20/20 (100%) |
| **Acierto OWASP 2025** (todos los hallazgos) | **8/20 (40%)** |
| Acierto OWASP 2025 sin los casos ambiguos (H02, H03, H05, H10) | 8/12 (67%) |
| **Acierto de prioridad (exacta), modelo** | **8/20 (40%)** |
| Acierto de prioridad (a un tramo o menos), modelo | 13/20 (65%) |
| **Acierto de prioridad (exacta), regla fija por severidad** | **6/10 (60%)** |
| Acierto de prioridad (a un tramo o menos), regla fija | 7/10 (70%) |
| Falsos positivos que el modelo trató como urgentes (p1 o p2) | 6/6 (100%) |
| Hallazgos con categoría distinta entre corridas | 2/10 |
| Hallazgos con prioridad distinta entre corridas | 3/10 |
| Confianza media cuando acierta / cuando falla | 0.90 (n=8) / 0.93 (n=12) |
| **Tasa de alucinación** | **4/20 (20%)** |

Los denominadores cuentan **respuestas** (hallazgos × corridas), salvo la regla fija, que es determinista y se cuenta una vez por hallazgo.

## Detalle por hallazgo

| ID | Hallazgo | Sev. ZAP | Humano (OWASP, prioridad) | Modelo (por corrida) | Regla fija | Falso positivo |
|---|---|---|---|---|---|---|
| H01 | SQL Injection | High | A05 p1 | A05:2025 p1 · A05:2025 p1 | p1 |  |
| H02 | External Redirect | High | A02 p1 | A01:2025 p1 · A01:2025 p1 | p1 |  |
| H03 | Off-site Redirect | High | A02 p4 | A01:2025 p1 · A01:2025 p1 | p1 | sí |
| H04 | Content Security Policy (CSP) Header Not Set | Medium | A02 p2 | A05:2025 p1 · A02:2025 p2 | p2 |  |
| H05 | Cross-Domain Misconfiguration | Medium | A02 p2 | A01:2025 p1 · A01:2025 p1 | p2 |  |
| H06 | Missing Anti-clickjacking Header | Medium | A02 p4 | A02:2025 p2 · A02:2025 p2 | p2 | sí |
| H07 | Session ID in URL Rewrite | Medium | A07 p4 | A01:2025 p1 · A01:2025 p1 | p2 | sí |
| H08 | Private IP Disclosure | Low | A02 p3 | A01:2025 p1 · A02:2025 p2 | p3 |  |
| H09 | X-Content-Type-Options Header Missing | Low | A02 p3 | A02:2025 p2 · A02:2025 p3 | p3 |  |
| H10 | Information Disclosure - Information in Browser sessionStorage | Informational | A01 p3 | A06:2025 p3 · A06:2025 p3 | p4 |  |

## Método

- **OWASP:** acierto si la categoría del modelo está entre las que el anotador aceptó. Las filas sin categoría humana (no aplica) no se puntúan. Los casos que la rúbrica declara ambiguos (admiten más de una categoría razonable) se reportan también por separado.
- **Prioridad:** exacta, o a un tramo de distancia (p2 contra p3 cuenta como cercana).
- **Regla fija:** High → p1, Medium → p2, Low → p3, Informational → p4. Es la línea base contra la que se compara el modelo.
- **Alucinación:** una persona revisa cada respuesta en `revision_alucinaciones.csv` y marca `si` cuando el modelo afirma algo que la evidencia de ZAP no respalda. La tasa es marcas `si` sobre respuestas revisadas.

## Limitaciones

- Muestra inicial del golden set (10 hallazgos, un anotador). El golden set completo, con dos revisores por hallazgo, corresponde al S6 (T-041 a T-044).
- Temperatura 0.1 sin seed: los resultados varían entre corridas. Por eso se reporta más de una corrida.
