# Golden set de 17 hallazgos con dos revisores

**Tareas:** T-043, T-044, T-046 · **Revisores:** Felipe Cayún y Joaquín Herrera · **Actualizado:** 25-11-2026

Mide qué tan bien el modelo local clasifica, prioriza, propone remediación y se apega a la evidencia, con dos personas que revisan por separado las mismas 17 respuestas. Reemplaza la muestra de 10 hallazgos de octubre (`metricas_golden_set.md`), que tenía un solo revisor.

## Muestra y método

- **Hallazgos:** los 17 que dejan los tres fixtures acordados (`full_v1`, `ajax_v2`, `ajax_auth_v1`), uno por alerta de ZAP (ver la corrección en `escaneo_autenticado.md`).
- **Respuestas del modelo:** una sola corrida de Llama 3.1 8B con el prompt v2, hecha por Joaquín y compartida a las dos bases con `scripts/compartir_enriquecimientos.py` (`respuestas_modelo/enriquecimientos_20261118.json`, 17 de 17 válidas). Los dos revisores juzgan exactamente el mismo texto.
- **Anotación:** cada revisor en el dashboard de su propia base, sin ver las respuestas del otro. Responde las cuatro preguntas de "¿Qué tal la sugerencia del modelo?" y registra su decisión.
- **Intercambio:** `scripts/intercambio.py exportar --que validaciones`. Los archivos quedan en `golden_set/`.
- **Cálculo:** de cada revisor vale su última validación por hallazgo; los "No sé" no cuentan. El acuerdo de las cuatro preguntas y de la decisión se calcula con `backend/scripts/acuerdo_revisores.py`, que lee los archivos y se puede repetir sin levantar el laboratorio.

## Ronda 1: anotación independiente (19-11-2026)

Archivos: `golden_set/ronda1_felipe.json`, `golden_set/ronda1_joaquin.json`.

| Pregunta | Felipe | Joaquín | Acuerdo | κ |
|---|---|---|---|---|
| Categoría OWASP correcta | 5/14 (36 %) | 12/14 (86 %) | 5/13 (38 %) | 0,07 |
| Prioridad correcta | 6/17 (35 %) | 14/16 (88 %) | 6/16 (38 %) | −0,05 |
| Remediación útil | 12/17 (71 %) | 15/17 (88 %) | 10/17 (59 %) | −0,20 |
| Inventó algo | 3/17 (18 %) | 2/17 (12 %) | 14/17 (82 %) | 0,30 |
| Decisión (confirmado, falso positivo, …) | — | — | 7/17 (41 %) | 0,00 |

### Qué muestra

El acuerdo en categoría, prioridad y decisión es el que se esperaría por azar (κ cercano a 0). No es que un revisor se haya equivocado: **juzgaron cosas distintas**, porque la rúbrica no decía contra qué se compara la sugerencia del modelo.

- **Categoría:** Felipe la comparó con la tabla CWE → OWASP; Joaquín aceptó la del modelo cuando el mecanismo calzaba. Por ejemplo, para una cabecera faltante el modelo dijo A02 y la tabla dice A06: Felipe marcó "No" y Joaquín "Sí".
- **Prioridad:** Felipe usó la prioridad de la regla; Joaquín marcó "Sí" cuando la del modelo le pareció razonable, incluso en casos donde su propia prioridad final era otra.
- **Decisión:** Joaquín marcó 9 hallazgos como falso positivo o duplicado (socket.io, alertas informativas, la segunda redirección, el segundo reporte del JWT), aplicando el criterio de la rúbrica de octubre. Felipe confirmó 16 de 17.
- **Invención:** es la pregunta más objetiva (el dato está en la evidencia o no está) y la única con acuerdo alto: 82 %. El modelo inventó en el 12 % al 18 % de los hallazgos, según el revisor.

Esta ronda muestra lo que mide: **sin una regla común, la calidad del modelo depende de quién lo juzga**, entre 36 % y 86 % en categoría. Por eso no se informa un acierto único de esta ronda.

### Medición objetiva contra la referencia

Dos de las preguntas tienen una referencia fija en el proyecto, y se pueden medir sin revisores:

| Qué | Resultado |
|---|---|
| Categoría del modelo igual a la tabla CWE → OWASP | 4 de 13 (31 %). Los otros 4 hallazgos no tienen CWE en la tabla |
| Prioridad del modelo igual a la regla por severidad | 6 de 17 (35 %) |

El modelo tiende a A01 y A02 (11 de 17 respuestas) y a subir la prioridad: en 11 de 17 hallazgos dio una más alta que la regla y en ninguno una más baja. Es consistente con la medición de octubre y con la decisión mixta del proyecto: la categoría la da la tabla, la prioridad la regla, la IA explica y una persona decide (`docs/diseno/IA_MODELO_Y_PROMPT.md`, sección 5).

## Calibración (19 y 20-11-2026)

1. El equipo acordó una regla común y la dejó escrita en `rubrica_anotacion.md` (sección "Regla común…").
2. Se comparó cada hallazgo de los dos archivos contra esa regla. Resultado:
   - **Por regla (sin discusión):** 1 corrección de Felipe (Cross-Domain: "No sé", porque el CWE 264 no está en la tabla) y 14 de Joaquín (categoría y prioridad), más una prioridad final p4 en SQL Injection que fue un error de selección.
   - **Por criterio (conversado):** 20 diferencias en decisión, remediación e invención. Felipe pasó a falso positivo o duplicado los 9 hallazgos donde aplicó el criterio de octubre que había dejado de usar. Joaquín reconoció que en Timestamp la IA sí inventó (una cabecera Date que no está en la evidencia).
3. Cada revisor volvió a guardar en el dashboard solo sus hallazgos corregidos. La anotación anterior queda en el historial.

## Ronda 2: con regla común (20-11-2026)

Archivos: `golden_set/ronda2_felipe.json`, `golden_set/ronda2_joaquin.json`. Se calcula igual:

```bash
python3 backend/scripts/acuerdo_revisores.py \
    docs/evidencias/golden_set/ronda2_felipe.json \
    docs/evidencias/golden_set/ronda2_joaquin.json
```

| Pregunta | Felipe | Joaquín | Acuerdo | κ |
|---|---|---|---|---|
| Categoría OWASP correcta | 4/13 (31 %) | 4/13 (31 %) | 13/13 (100 %) | 1,00 |
| Prioridad correcta | 5/17 (29 %) | 4/17 (24 %) | 16/17 (94 %) | 0,85 |
| Remediación útil | 12/17 (71 %) | 13/17 (76 %) | 12/17 (71 %) | 0,25 |
| Inventó algo | 3/17 (18 %) | 3/17 (18 %) | 17/17 (100 %) | 1,00 |
| Decisión (confirmado, falso positivo, …) | — | — | 16/17 (94 %) | 0,91 |

### Qué queda en desacuerdo

- **Prioridad, 1 caso:** Timestamp Disclosure. Felipe deja la de la regla (p3) y Joaquín la baja a p4 porque los números no revelan nada. Los dos aplican bien la regla; difieren en su prioridad final.
- **Decisión, 1 caso:** Cross-Domain Misconfiguration. Felipe lo confirma (CORS abierto en rutas públicas) y Joaquín lo deja como riesgo aceptado (sin datos sensibles en la evidencia).
- **Remediación útil, 5 casos:** Off-site Redirect, Session ID in URL, los dos User Agent Fuzzer y Private IP. Es la pregunta con más juicio: si una remediación correcta pero genérica sirve o no. La regla común la acotó, pero no la resolvió.

**Cómo se cierran.** Estos 7 desacuerdos no se fuerzan a un solo valor y no cambian los resultados que se informan: la prioridad y la remediación útil se reportan como rango entre los dos revisores (24 % a 29 % y 71 % a 76 %, en la tabla siguiente), y la decisión de Cross-Domain (confirmado o riesgo aceptado) no altera el conteo de falsos positivos y duplicados, que es 9 para los dos. Quedan registrados aquí con el criterio de cada revisor.

### Resultado sobre el modelo

Con la regla común, los dos revisores coinciden en lo que el modelo hace bien y mal:

| Qué | Resultado |
|---|---|
| Categoría OWASP correcta | 4 de 13 (31 %), igual a la medición objetiva contra la tabla |
| Prioridad correcta | 4 a 5 de 17 (24 % a 29 %) |
| Remediación útil | 12 a 13 de 17 (71 % a 76 %) |
| Inventó algo | 3 de 17 (18 %): Session ID in URL, Timestamp y Modern Web Application |
| Falsos positivos y duplicados de ZAP | 9 de 17 según los dos revisores (7 falsos positivos y 2 duplicados) |

El modelo explica y propone remediaciones útiles en la mayoría de los casos, pero falla en clasificar y priorizar, y en casi uno de cada cinco hallazgos agrega algo que no está en la evidencia. Respalda la decisión mixta del proyecto: la categoría la da la tabla CWE, la prioridad la regla, la IA explica y una persona decide.

## Limitaciones

- **Muestra chica:** 17 hallazgos de una sola aplicación. Con n tan bajo, un hallazgo mueve el porcentaje en 6 puntos y el κ es inestable.
- **La ronda 2 no es independiente:** los revisores conversaron antes de corregir, así que su acuerdo será más alto por construcción. Por eso se informan las dos rondas: la 1 muestra el problema de método, la 2 el resultado con la regla común.
- **Una sola corrida del modelo:** no mide cuánto varían sus respuestas entre corridas.
- **La categoría según la regla es casi mecánica:** compara con la tabla. Es una decisión deliberada para que no dependa del revisor; lo que sigue siendo juicio humano es la decisión, la remediación y la invención.
