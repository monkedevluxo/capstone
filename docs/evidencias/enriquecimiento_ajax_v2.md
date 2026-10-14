# Evidencia · Enriquecimiento sobre `zap_juiceshop_ajax_v2`

**Responsable:** Joaquín Herrera · **Fecha:** 14-10-2026 · **Comando:** `python -m app.ia.enriquecer ..\lab\fixtures\zap_juiceshop_ajax_v2.json --max 13`

Primera prueba del pipeline completo (fixture → parser → modelo → validación) sobre hallazgos que **el prompt nunca había visto**: SQL Injection, External Redirect, Off-site Redirect, Information Disclosure y User Agent Fuzzer. Se ejecutó dos veces seguidas, con los mismos parámetros, para medir la consistencia.

**Configuración:** `llama3.1:8b-instruct-q4_K_M` · prompt v2 · temperatura 0.1 · sin seed · RTX 3060 Ti (100% GPU).

## Resultados por hallazgo

| Hallazgo | Sev. ZAP | CWE | Corrida 1 | Corrida 2 | Criterio | Acierto |
|---|---|---|---|---|---|---|
| External Redirect | High | 601 | A01 p1 | A01 p1 | A01 | 2/2 |
| Off-site Redirect | High | 601 | A01 p1 | A05 p1 | A01 | 1/2 |
| SQL Injection | High | 89 | A05 p1 | A05 p1 | A05 | 2/2 |
| CSP Header Not Set | Medium | 693 | A05 p1 | A05 p2 | A02 | 0/2 |
| Cross-Domain Misconfiguration | Medium | 264 | A01 p1 | A01 p1 | A01 o A02 | 2/2 |
| Missing Anti-clickjacking Header | Medium | 1021 | A02 p2 | A02 p2 | A02 | 2/2 |
| Session ID in URL Rewrite | Medium | 598 | A01 p1 | A01 p1 | A07 | 0/2 |
| Private IP Disclosure | Low | 497 | A01 p2 | A01 p1 | discutible | — |
| Timestamp Disclosure - Unix | Low | 497 | A02 p2 | A02 p2 | discutible | — |
| X-Content-Type-Options Header Missing | Low | 693 | A02 p2 | A02 p2 | A02 | 2/2 |
| Information Disclosure (browser storage) | Info | 359 | A06 p2 | A02 p2 | discutible | — |
| Modern Web Application | Info | — | A05 p4 | A05 p4 | sin categoría aplicable | — |
| User Agent Fuzzer | Info | — | A05 p3 | A05 p2 | sin categoría aplicable | — |

## Métricas

| Métrica | Resultado |
|---|---|
| Hallazgos enriquecidos (formato válido) | **26/26**, todos al primer intento |
| Acierto OWASP en casos con criterio claro (8 hallazgos × 2 corridas) | **11/16 (69%)** |
| Categoría distinta entre corridas | 2 de 13 hallazgos (Off-site Redirect, Information Disclosure) |
| Prioridad distinta entre corridas | 3 de 13 hallazgos (CSP, Private IP, User Agent Fuzzer) |
| Prioridad que respeta la regla del prompt (tramo según severidad ZAP) | 11/26 |
| Latencia | Arranque en frío 86.6 s · luego 1.4 a 2.4 s por hallazgo |

## Observaciones

1. **Generaliza en casos nuevos claros.** SQL Injection (A05) y External Redirect (A01) salen correctos en ambas corridas, sin que el prompt los mencione.
2. **CSP sigue en A05.** Acumulado de todas las pruebas: 15 de 16 respuestas. El sesgo hacia la numeración de 2021 persiste a pesar de la instrucción explícita.
3. **Mismo CWE, distinta categoría.** Private IP Disclosure y Timestamp Disclosure comparten el CWE-497, y el modelo los clasifica en A01 y A02 respectivamente. Una tabla CWE → OWASP les asignaría siempre la misma.
4. **La prioridad no sigue la regla.** Hallazgos Medium quedan en p1 (CSP, CORS, Session ID) y hallazgos informativos en p2 o p3 (User Agent Fuzzer, Information Disclosure). Solo 11 de 26 respuestas quedan en el tramo que pide el prompt.
5. **La confianza sigue sin discriminar.** Va de 0.8 a 1.0 en aciertos y errores por igual. Única excepción: Modern Web Application, con 0.20, que coincide con lo que pide el prompt para hallazgos informativos.
6. **Arranque en frío de 86 s**, cerca del timeout de 120 s. Si un equipo más lento lo supera, se ajusta `OLLAMA_TIMEOUT_S`.

**Conclusión:** el formato es 100% confiable gracias a la validación, y el contenido es bueno en los casos claros, pero inconsistente en prioridad y en categorías ambiguas. Estos datos respaldan la propuesta de derivar la **prioridad** de una regla fija y la **categoría** de una tabla por CWE (opciones B o mixta, en `docs/diseno/IA_MODELO_Y_PROMPT.md`, sección 5).
