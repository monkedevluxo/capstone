# Retrospectivas por sprint

**SentinelAI** · Borrador del 18-11-2026, para revisión del equipo

> **Cómo se hicieron.** El equipo no registró retrospectivas formales al cierre de cada sprint. Este documento las reconstruye el 18-11-2026 a partir de la evidencia del repositorio (historial de commits y pull requests, planilla de sprints, plan de pruebas e informes de fase), y debe ser revisado y corregido por los tres integrantes antes de darlo por cerrado. Desde el S6, la retrospectiva se hace al cierre de cada sprint.

Cada sprint se revisa con tres preguntas: qué funcionó, qué no funcionó y qué cambiamos. Las acciones indican si se aplicaron.

## Ritmo de trabajo

Commits integrados en `main`, contados por fecha de autoría. No incluye el trabajo de ramas que todavía no se integran.

| Sprint | Fechas | Commits | Días con commits |
|---|---|---|---|
| Antes del S1 | hasta el 06-09 | 9 | 3 |
| S1 | 07-09 a 20-09 | 11 | 2 |
| S2 | 21-09 a 04-10 | 15 | 4 |
| S3 | 05-10 a 18-10 | 21 | 2 |
| S4 | 19-10 a 01-11 | 0 | 0 |
| S5 | 02-11 a 15-11 | 54 | 7 |
| S6 (en curso) | 16-11 a 29-11 | 23 | 2, al 18-11 |

Reproducible con `git log --format=%ad --date=short main`.

El trabajo se concentró en pocos días, cerca de cada entrega: 18 de los 21 commits del S3 son del 14 de octubre, dos días antes de la segunda entrega, y el S4 no tiene ninguno. Es el patrón más claro de las retrospectivas y el que más afectó al plan.

---

## S1 · Laboratorio y riesgo del modelo (07-09 a 20-09)

**Hito:** laboratorio aislado en pie, un reporte de ZAP guardado y la latencia de Ollama medida. **Cumplido.**

| Funcionó | No funcionó | Qué cambiamos |
|---|---|---|
| Medir la latencia del modelo antes de comprometer la arquitectura. Confirmó que un modelo local era viable (CP-13) | La instalación del entorno en Windows con Docker Desktop consumió más tiempo del previsto | Se pasó a Docker Engine dentro de WSL2 y se escribió una guía de instalación común. **Aplicada** (`GUIA_INSTALACION.md`) |
| Verificar el aislamiento de red con un comando, no solo con la configuración (CP-01) | | |

## S2 · Modelo de datos (21-09 a 04-10)

**Hito:** el esquema completo se crea con Alembic sobre una base vacía, con el DER documentado. **Cumplido.**

| Funcionó | No funcionó | Qué cambiamos |
|---|---|---|
| Definir el contrato del hallazgo normalizado antes de programar: cada uno avanzó en paralelo sobre la misma estructura | 10 de los 15 commits del sprint son de un solo día (29-09) | — |
| Escribir las pruebas del parser como especificación antes de implementarlo | ZAP no podía escribir sus reportes por permisos de carpeta (IN-02) | Verificación de permisos dentro del script de escaneo. **Aplicada** |
| Integración continua desde el principio | | Todo cambio entra por pull request con CI. **Aplicada** desde el 29-09 |

## S3 · Ingesta y Hito 1 (05-10 a 18-10)

**Hito 1:** se importa un escaneo real de ZAP y se consulta por la API con severidad unificada y sin duplicados. **Cumplido.**

| Funcionó | No funcionó | Qué cambiamos |
|---|---|---|
| Medir al modelo contra un golden set inicial antes de confiar en él | El modelo acertó la prioridad 40 %, menos que una regla fija (60 %), y declaró la misma confianza al equivocarse (IN-06) | Decisión mixta: la regla propone la prioridad y la tabla CWE la categoría; la IA explica. **Aplicada** |
| Se cumplió el Hito 1 a tiempo para la segunda entrega | El plan de 9 sprints terminaba en enero de 2027, después del cierre del semestre | Replanificación a 7 sprints el 15-10, con reducción de alcance. **Aplicada** |
| | Casi todo el trabajo del sprint se integró en un día (14-10) | — |

## S4 · IA integrada (19-10 a 01-11)

**Hito:** enriquecimiento disponible en la API, con la decisión mixta, y escaneos completos procesados en segundo plano. **No cumplido en el sprint.** Se cumplió en el S5 (pull request #19, 13-11).

| Funcionó | No funcionó | Qué cambiamos |
|---|---|---|
| — | No se integró ningún cambio en el sprint. Tras la segunda entrega, el avance se detuvo dos semanas | *Por completar por el equipo:* causas y acción acordada |
| | El procesamiento en segundo plano resultó innecesario a esta escala | Enriquecimiento por lote síncrono, con guardado por hallazgo; se eliminaron T-036 y T-037. **Aplicada** en el S5 |

## S5 · Validación y dashboard (02-11 a 15-11)

**Hito 2:** métricas reproducibles sobre 30 a 50 hallazgos con dos revisores, y un dashboard con resumen, filtros y evidencia junto a la sugerencia de la IA. **Cumplido en parte:** el dashboard sí; el golden set con dos revisores pasó al S6.

| Funcionó | No funcionó | Qué cambiamos |
|---|---|---|
| El sprint recuperó el atraso del S4: enriquecimiento en la API, tabla CWE → OWASP, escaneo autenticado y dashboard | El escaneo con Ajax Spider quedó colgado más de 3 horas (IN-01) | Límites de tiempo fijos en el script de escaneo. **Aplicada** |
| Probar con un modelo simulado y una base de pruebas separada, sin tocar los datos de la demostración | La anotación del golden set no empezó: dependía de que el enriquecimiento real estuviera listo | Herramientas para compartir las sugerencias del modelo y anotar desde el dashboard. **Aplicada** en el S6 |
| | La muestra planificada (30 a 50) superaba lo que producen los escaneos: hay 17 hallazgos únicos | Se anotan los 17 con dos revisores y la limitación se informa. **Aplicada** (pull request #30) |
| | El trabajo se acumuló en la segunda semana: ramas grandes, que luego esperaron revisión | *Por completar por el equipo* |

## S6 · Cierre funcional (16-11 a 29-11, en curso)

Se completa al cierre del sprint. Lo observado hasta el 18-11:

- **Funcionó:** el informe técnico, la prueba de extremo a extremo y la corrección de la muestra entraron rápido, con revisión cruzada.
- **No funcionó:** varias ramas apiladas esperan una sola aprobación. El pull request #28 (detalle y decisión humana) lleva dos días sin revisión y bloquea a otras cuatro.
- **Actualización 19-11:** el pull request #28 entró el 18-11, y las ramas que dependían de él, entre el 18 y el 19-11.
- **En evaluación:** dos scripts que resuelven lo mismo (compartir sugerencias del modelo entre equipos) se desarrollaron en paralelo, por falta de coordinación.

---

## Acciones para el cierre del proyecto

| Acción | Origen | Responsable |
|---|---|---|
| Revisión semanal breve del avance, con los tres | Ritmo irregular (S2 a S5) | Equipo |
| Pull requests más chicos y revisión dentro de 24 horas | Ramas que esperan revisión (S5, S6) | Equipo |
| Avisar en el grupo antes de empezar una tarea que no está asignada | Trabajo duplicado (S6) | Equipo |
| Retrospectiva al cierre del S6 y del S7, registrada en este documento | Ausencia de retrospectivas formales | Equipo |
