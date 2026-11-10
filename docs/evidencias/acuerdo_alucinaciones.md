# Acuerdo entre revisores · Alucinaciones del modelo

**Fecha:** 09-11-2026 · **Revisores:** Joaquín Herrera y Felipe Cayún · **Tareas:** T-043, T-046

Dos personas revisaron por separado las mismas 20 respuestas del modelo (10 hallazgos del golden set × 2 corridas) y marcaron si cada una afirma algo que la evidencia de ZAP no respalda. Felipe revisó sin ver las marcas de Joaquín.

| Revisión | Archivo |
|---|---|
| Joaquín | `revision_alucinaciones.csv` |
| Felipe | `revision_alucinaciones_felipe.csv` |

## Criterio común

- **Sí:** la respuesta afirma un hecho falso o exagera el impacto más allá de la evidencia.
- **No:** la respuesta es coherente con la evidencia, aunque sea vaga o genérica.
- No detectar un falso positivo es un error de criterio, no una alucinación, salvo que la respuesta afirme algo falso sobre el hallazgo.

## Resultados

| | Felipe | Joaquín |
|---|---|---|
| Respuestas marcadas como alucinación | 6/20 (30%) | 4/20 (20%) |

| | Joaquín: sí | Joaquín: no |
|---|---|---|
| **Felipe: sí** | 4 | 2 |
| **Felipe: no** | 0 | 14 |

- **Acuerdo observado:** 18/20 (90%)
- **Kappa de Cohen:** 0,74 (acuerdo sustancial)

Cálculo: acuerdo esperado por azar = (6/20 × 4/20) + (14/20 × 16/20) = 0,62; κ = (0,90 − 0,62) / (1 − 0,62) = 0,74.

## Casos en desacuerdo

**H03, corridas 1 y 2 (Off-site Redirect).** El modelo describe la redirección al repositorio oficial de GitHub como una "URL no confiable" (C1) y como un redireccionamiento "sin autorización" (C2). Felipe las marca como alucinación porque ese destino está permitido de forma intencional por la aplicación, y el hallazgo figura como falso positivo en el golden set. Joaquín no las marca porque el modelo describe el mecanismo genérico de una redirección abierta.

La diferencia no es de lectura de la evidencia, sino de si la afirmación se evalúa contra el caso concreto o contra el tipo de vulnerabilidad. Para el golden set completo (S6) se propone evaluar siempre contra el caso concreto.

## Casos en acuerdo

Ambos revisores marcan como alucinación:

- **H02 C2:** califica una redirección como "acceso no autorizado".
- **H04 C1:** afirma que "no hay protección" contra XSS por la falta de una cabecera.
- **H07 C1 y C2:** inventa una "URL de redirección" y asume que el `sid` de socket.io es la sesión del usuario.

## Conclusión

La tasa de alucinación del modelo se ubica entre **20% y 30%** según el revisor, con un acuerdo sustancial entre ambos (κ = 0,74). Las alucinaciones observadas son sutiles: términos de seguridad mal aplicados, afirmaciones categóricas donde corresponde una hipótesis y detalles técnicos inventados. Ninguna es detectable revisando solo el formato de la respuesta, lo que refuerza la necesidad de validación humana.
