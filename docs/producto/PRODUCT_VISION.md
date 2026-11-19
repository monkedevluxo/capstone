# Visión del producto

**SentinelAI** · Proyecto de Título · Capstone · Duoc UC · Grupo 3 · Actualizado: 16-11-2026

## El problema

Las herramientas de análisis dinámico de seguridad (DAST), como OWASP ZAP, entregan muchas alertas y poca claridad. En un solo escaneo de nuestro laboratorio, la ausencia de la cabecera Content-Security-Policy apareció en 11 URL distintas y la divulgación de marcas de tiempo en 15. Son decenas de líneas que describen un puñado de problemas.

Ese ruido tiene tres consecuencias para quien debe corregir:

- **No se sabe por dónde empezar.** Cuando todo parece urgente, lo importante queda sin atender.
- **Los reportes están escritos para especialistas.** Convertirlos en una tarea de corrección exige trabajo manual y repetitivo.
- **Las decisiones no quedan registradas.** Si alguien descarta una alerta como falso positivo, rara vez queda escrito quién lo decidió ni por qué.

## Para quién es

| Usuario | Qué necesita |
|---|---|
| **Equipo de desarrollo pequeño, sin especialista de seguridad** | Entender qué significa cada hallazgo y qué corregir primero |
| **Analista de calidad o de seguridad** | Revisar los hallazgos con la evidencia a la vista y dejar su decisión registrada |
| **Estudiante o docente de seguridad** | Un entorno autorizado donde practicar el triage de resultados reales |

El proyecto se desarrolla en un contexto académico y sus usuarios son simulados: lo usa el propio equipo sobre un laboratorio aislado.

## Qué es SentinelAI

Una plataforma web que recibe los reportes de un escáner de seguridad, los ordena y ayuda a una persona a decidir qué hacer con cada hallazgo. El flujo completo es:

**escaneo → normalización → sugerencia de la IA → decisión humana → informe**

## Propuesta de valor

1. **Menos ruido.** Las alertas repetidas se agrupan en un solo hallazgo con su número de ocurrencias. Un escaneo nuevo reconoce lo que ya se conocía en lugar de duplicarlo.
2. **Explicación en lenguaje claro.** Un modelo de lenguaje explica cada hallazgo, propone su categoría OWASP Top 10:2025 y recomienda cómo remediarlo.
3. **La evidencia nunca sale del equipo.** El modelo corre en una máquina propia, con Ollama. Los hallazgos de seguridad son información sensible y no se envían a un servicio en la nube.
4. **La IA sugiere y la persona decide.** La pantalla separa tres capas: lo que reportó el escáner, lo que interpretó el modelo y lo que decidió una persona. La decisión queda guardada con nombre y fecha.
5. **Evidencia íntegra.** Cada hallazgo conserva sin modificar el bloque original que entregó el escáner, y cada reporte importado guarda su huella SHA-256.

## Qué lo hace distinto

- **Mide a su propia IA en vez de confiar en ella.** Las respuestas del modelo se comparan con el criterio de personas que anotan sin ver esas respuestas (golden set). Las mediciones mostraron que el modelo declara la misma confianza cuando acierta que cuando se equivoca.
- **Corrigió su diseño con esos datos.** A partir de las mediciones, la prioridad la propone una regla fija por severidad y la categoría se contrasta con la tabla oficial CWE → OWASP. Cuando el modelo y la tabla no coinciden, el hallazgo se marca para revisar primero.
- **El marco ético está en la infraestructura.** La red del laboratorio no tiene salida a internet, la API rechaza reportes de equipos que no sean del laboratorio y la base de datos rechaza registrar objetivos fuera de él.

## Alcance del producto mínimo

| Incluye | No incluye |
|---|---|
| Importar reportes JSON de OWASP ZAP | Otros escáneres (Nikto y OpenVAS quedaron fuera en la replanificación del 15-10-2026) |
| Normalizar y deduplicar hallazgos | Lanzar escaneos desde la plataforma |
| Enriquecer con un modelo local (Llama 3.1 8B) | Escanear sistemas de terceros o en internet |
| Dashboard con totales, filtros y detalle por capas | Cuentas de usuario y permisos |
| Registrar la decisión humana con trazabilidad | Corrección automática de vulnerabilidades |
| Informe técnico exportable | Integración con sistemas de tickets |

## Restricciones

- **Legales y éticas:** solo se trabaja sobre aplicaciones deliberadamente vulnerables en un laboratorio local y autorizado. La Ley 21.459 sobre delitos informáticos delimita el alcance.
- **De hardware:** el modelo debe correr en equipos de estudiante. Se usa una versión cuantizada de 8 mil millones de parámetros en una tarjeta gráfica doméstica.
- **De tiempo:** 14 semanas de desarrollo, en 7 sprints de 2 semanas, con tres integrantes que compatibilizan el proyecto con otras responsabilidades.

## Cómo sabremos que funciona

| Objetivo | Cómo se verifica |
|---|---|
| El flujo completo opera de punta a punta | Prueba de extremo a extremo, del reporte de ZAP al informe técnico |
| Los hallazgos no se duplican | Importar dos veces el mismo reporte se rechaza, y escaneos distintos reconocen los hallazgos ya conocidos |
| La calidad de la IA es conocida | Acierto de categoría, acierto de prioridad y tasa de alucinación, medidos contra el golden set con dos revisores |
| Toda decisión es trazable | Cada validación guarda revisor, fecha, comentario y la sugerencia de la IA que se estaba juzgando |
| El laboratorio está aislado | El contenedor objetivo no alcanza internet; se comprueba con un comando |

## Documentos relacionados

- Definición de terminado: `docs/producto/DEFINITION_OF_DONE.md`
- Planificación por sprint: `docs/SentinelAI_Plan_Sprints.xlsx`
- Decisiones sobre la IA: `docs/diseno/IA_MODELO_Y_PROMPT.md`
- Métricas del modelo: `docs/evidencias/metricas_golden_set.md`
