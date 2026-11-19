# Product Backlog

**SentinelAI** · Actualizado: 16-11-2026

Este documento expresa el alcance del proyecto como **historias de usuario**. El equipo planificó y ejecutó el trabajo con un backlog de tareas técnicas (`docs/SentinelAI_Plan_Sprints.xlsx`). Las historias se redactaron en noviembre de 2026 a partir de ese backlog y del sistema construido, para describir el mismo alcance desde el punto de vista de quien lo usa. Cada historia indica las tareas que la implementan.

## Usuarios

| Usuario | Quién es | Qué busca |
|---|---|---|
| **Desarrollador** | Integrante de un equipo de desarrollo pequeño, sin especialista de seguridad | Entender cada hallazgo y saber qué corregir primero |
| **Analista** | Persona que revisa los resultados de los escaneos: analista de calidad o de seguridad, o estudiante que practica el triage | Revisar con la evidencia a la vista y dejar su decisión registrada |

## Resumen

| Estado | Historias | Qué significa |
|---|---|---|
| Hecha | 17 | Integrada en la rama `main` |
| En revisión | 6 | Implementada, con pull request abierto |
| En curso | 3 | Implementada en una rama sin pull request, o parcialmente lista |
| Pendiente | 1 | No iniciada |
| **Total** | **27** | |

Cada historia se considera terminada cuando cumple sus criterios de aceptación y la definición de terminado (`docs/producto/DEFINITION_OF_DONE.md`).

| Épica | Historias | Hechas |
|---|---|---|
| 1. Laboratorio y escaneo | HU-01 a HU-02 | 2 de 2 |
| 2. Ingesta y normalización | HU-03 a HU-07 | 5 de 5 |
| 3. Enriquecimiento con IA | HU-08 a HU-12 | 5 de 5 |
| 4. Revisión en el dashboard | HU-13 a HU-17 | 3 de 5 |
| 5. Decisión humana | HU-18 a HU-20 | 0 de 3 |
| 6. Informe | HU-21 a HU-22 | 0 de 2 |
| 7. Calidad de la IA | HU-23 a HU-25 | 0 de 3 |
| 8. Operación y confianza en los cambios | HU-26 a HU-27 | 2 de 2 |

## Épica 1 · Laboratorio y escaneo

### HU-01 · Escanear una aplicación vulnerable dentro de un laboratorio aislado

Como **analista** que revisa los hallazgos, **quiero** escanear una aplicación vulnerable dentro de un laboratorio aislado, **para** practicar sin riesgo de afectar sistemas de terceros.

Criterios de aceptación:

- El laboratorio se levanta con `docker compose up`.
- El contenedor objetivo no alcanza internet: un `ping` desde su red falla.
- El primer escaneo de ZAP queda guardado como archivo JSON.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S1 | Hecha | T-005, T-006, T-007 |

### HU-02 · Lanzar un escaneo con un solo comando y conservar su resultado

Como **analista** que revisa los hallazgos, **quiero** lanzar un escaneo con un solo comando y conservar su resultado, **para** repetir los escaneos sin recordar las opciones de ZAP.

Criterios de aceptación:

- Un script ofrece los modos de escaneo y verifica que el objetivo esté arriba antes de empezar.
- Un resultado se puede congelar como fixture versionado, sin sobrescribir uno existente.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S2 | Hecha | T-018 |


## Épica 2 · Ingesta y normalización

### HU-03 · Importar un reporte de ZAP y ver sus alertas como hallazgos en un formato común

Como **analista** que revisa los hallazgos, **quiero** importar un reporte de ZAP y ver sus alertas como hallazgos en un formato común, **para** no depender del formato de cada herramienta.

Criterios de aceptación:

- `POST /scans/import` responde 201 con el resumen de hallazgos nuevos y repetidos.
- La severidad queda en una escala única de cinco niveles.
- Un archivo que no es un reporte de ZAP se rechaza con 422.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S3 | Hecha | T-019, T-020, T-022 |

### HU-04 · Que las alertas repetidas se agrupen en un solo hallazgo con su número de ocurrencias

Como **desarrollador** que debe corregir, **quiero** que las alertas repetidas se agrupen en un solo hallazgo con su número de ocurrencias, **para** no revisar decenas de líneas que describen el mismo problema.

Criterios de aceptación:

- Dos alertas con la misma regla, ruta normalizada, parámetro y método son un solo hallazgo.
- Importar otro escaneo del mismo objetivo reconoce los hallazgos ya conocidos y no los duplica.
- Importar dos veces el mismo reporte se rechaza con 409.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S2-S3 | Hecha | T-014, T-024 |

### HU-05 · Que cada hallazgo conserve sin cambios lo que entregó el escáner

Como **analista** que revisa los hallazgos, **quiero** que cada hallazgo conserve sin cambios lo que entregó el escáner, **para** contrastar cualquier interpretación con la evidencia original.

Criterios de aceptación:

- El bloque original de la alerta se guarda completo junto al hallazgo.
- Cada reporte importado guarda su huella SHA-256.
- Ningún proceso posterior modifica la evidencia original.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S3 | Hecha | T-021 |

### HU-06 · Que el sistema rechace reportes de equipos que no son del laboratorio

Como **analista** que revisa los hallazgos, **quiero** que el sistema rechace reportes de equipos que no son del laboratorio, **para** no registrar resultados de sistemas que no estamos autorizados a analizar.

Criterios de aceptación:

- La API responde 403 si el objetivo del reporte no está en la lista del laboratorio.
- La base de datos rechaza registrar un objetivo cuyo entorno no sea el laboratorio.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S2-S3 | Hecha | T-012, T-022 |

### HU-07 · Subir el reporte desde el dashboard

Como **analista** que revisa los hallazgos, **quiero** subir el reporte desde el dashboard, **para** no usar la línea de comandos para importar.

Criterios de aceptación:

- La pantalla Inicio acepta el archivo arrastrándolo o eligiéndolo.
- Muestra el resultado de la importación y enlaza a los hallazgos de ese escaneo.
- Cada error (objetivo fuera del laboratorio, reporte repetido, archivo inválido) tiene un mensaje claro.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S5 | Hecha | Sin tarea propia: surgió al revisar el dashboard |


## Épica 3 · Enriquecimiento con IA

### HU-08 · Una explicación del hallazgo en lenguaje claro, con una recomendación de remediación

Como **desarrollador** que debe corregir, **quiero** una explicación del hallazgo en lenguaje claro, con una recomendación de remediación, **para** entender qué corregir sin ser especialista en seguridad.

Criterios de aceptación:

- Cada sugerencia trae explicación, impacto, categoría OWASP Top 10:2025, prioridad, confianza y remediación.
- La sugerencia se obtiene con `POST /findings/{id}/enrich`.
- La pantalla la presenta siempre como sugerencia, no como decisión.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S4 | Hecha | T-028, T-029, T-032, T-033 |

### HU-09 · Que el modelo de lenguaje corra en un equipo propio

Como **analista** que revisa los hallazgos, **quiero** que el modelo de lenguaje corra en un equipo propio, **para** que la evidencia de seguridad no salga de la organización.

Criterios de aceptación:

- El modelo se ejecuta con Ollama en un equipo local.
- La API no llama a ningún servicio externo.
- La latencia por hallazgo está medida y documentada.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S1 | Hecha | T-008, T-009 |

### HU-10 · Que una respuesta inválida del modelo no se guarde como si fuera válida

Como **analista** que revisa los hallazgos, **quiero** que una respuesta inválida del modelo no se guarde como si fuera válida, **para** que el dashboard no muestre datos a medias.

Criterios de aceptación:

- La salida del modelo se valida contra un esquema antes de guardarse.
- Tras tres intentos inválidos, el hallazgo queda marcado "sin enriquecer" con el motivo.
- Un intento fallido no reemplaza una sugerencia válida anterior.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S4 | Hecha | T-030, T-031 |

### HU-11 · Enriquecer de una vez todos los hallazgos de un escaneo

Como **analista** que revisa los hallazgos, **quiero** enriquecer de una vez todos los hallazgos de un escaneo, **para** no pedir la sugerencia uno por uno.

Criterios de aceptación:

- `POST /scans/{id}/enrich` procesa los hallazgos pendientes y guarda cada resultado al terminarlo.
- Si el modelo se cae a la mitad, lo ya procesado queda guardado y se puede reintentar.
- Si el modelo no responde, la API contesta 503 y no guarda nada.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S4 | Hecha | T-038 (reemplazó a T-036 y T-037) |

### HU-12 · Saber qué modelo y qué versión del prompt generó cada sugerencia

Como **analista** que revisa los hallazgos, **quiero** saber qué modelo y qué versión del prompt generó cada sugerencia, **para** poder comparar resultados entre versiones.

Criterios de aceptación:

- Cada sugerencia guarda el modelo, la versión y la huella del prompt, los intentos, la latencia y la fecha.
- Las sugerencias anteriores se conservan como historial; solo una es la vigente.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S4 | Hecha | T-034, T-035 |


## Épica 4 · Revisión en el dashboard

### HU-13 · Ver un resumen con el total de hallazgos por severidad

Como **desarrollador** que debe corregir, **quiero** ver un resumen con el total de hallazgos por severidad, **para** saber de un vistazo cuánto hay y cuán grave es.

Criterios de aceptación:

- El dashboard muestra los totales por severidad, los marcados para revisar y los que están sin enriquecer.
- Los totales coinciden siempre con la lista que se ve debajo.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S5 | Hecha | T-049, T-050 |

### HU-14 · Filtrar y buscar los hallazgos

Como **desarrollador** que debe corregir, **quiero** filtrar y buscar los hallazgos, **para** concentrarme en los que me corresponden.

Criterios de aceptación:

- Se puede filtrar por severidad, categoría OWASP y escaneo, y buscar por título o ruta.
- Los filtros quedan en la dirección de la página, así una vista se puede compartir.
- Si ningún hallazgo cumple los filtros, la pantalla lo dice y ofrece limpiarlos.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S5 | Hecha | T-051, T-054 |

### HU-15 · Ver primero los hallazgos donde la categoría del modelo no coincide con la tabla oficial

Como **analista** que revisa los hallazgos, **quiero** ver primero los hallazgos donde la categoría del modelo no coincide con la tabla oficial, **para** revisar antes los casos en que la IA puede estar equivocada.

Criterios de aceptación:

- Cada hallazgo muestra la categoría de la tabla CWE → OWASP junto a la del modelo.
- Si difieren, o el CWE no está en la tabla, el hallazgo se marca "Revisar" con el motivo.
- La confianza que declara el modelo se muestra con una nota sobre cómo interpretarla.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S5 | Hecha | T-051, T-053 |

### HU-16 · Ver el detalle de un hallazgo con la evidencia del escáner y la sugerencia de la IA lado a lado

Como **desarrollador** que debe corregir, **quiero** ver el detalle de un hallazgo con la evidencia del escáner y la sugerencia de la IA lado a lado, **para** comparar lo que se reportó con lo que se interpretó.

Criterios de aceptación:

- El detalle separa tres capas: escáner, modelo y persona.
- La evidencia del escáner se muestra como texto, nunca como HTML.
- Desde el detalle se puede pedir o repetir la sugerencia de la IA.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S5 | En revisión | T-052 (PR #28) |

### HU-17 · Ver el historial de escaneos importados

Como **analista** que revisa los hallazgos, **quiero** ver el historial de escaneos importados, **para** saber qué se ha analizado y qué falta enriquecer.

Criterios de aceptación:

- La pantalla Escaneos lista cada escaneo con su fecha, herramienta, objetivo y conteos.
- Desde cada escaneo se llega a sus hallazgos y se pueden enriquecer los pendientes.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S6 | En curso | Sin tarea propia (rama `luciano/escaneos`) |


## Épica 5 · Decisión humana

### HU-18 · Registrar mi decisión sobre un hallazgo con mi nombre y la fecha

Como **analista** que revisa los hallazgos, **quiero** registrar mi decisión sobre un hallazgo con mi nombre y la fecha, **para** que quede constancia de quién decidió y por qué.

Criterios de aceptación:

- Se puede confirmar, marcar como falso positivo o aceptar el riesgo, con un comentario.
- El estado del hallazgo cambia en la misma operación que guarda la decisión.
- El historial de decisiones se conserva: una decisión nueva no borra las anteriores.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S6 | En revisión | T-056, T-057 (PR #28) |

### HU-19 · Marcar un hallazgo como duplicado de otro

Como **analista** que revisa los hallazgos, **quiero** marcar un hallazgo como duplicado de otro, **para** sacarlo de la cola sin afirmar que es un falso positivo.

Criterios de aceptación:

- "Duplicado" es un estado propio del hallazgo.
- Los duplicados no cuentan como falsos positivos en las métricas ni en el informe.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S6 | En revisión | T-057 (PR #28) |

### HU-20 · Corregir la prioridad que propone la regla

Como **analista** que revisa los hallazgos, **quiero** corregir la prioridad que propone la regla, **para** que la prioridad final refleje mi criterio.

Criterios de aceptación:

- La prioridad parte de una regla fija según la severidad.
- La persona puede cambiarla al decidir, y queda registrado que fue una corrección.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S6 | En revisión | T-056, T-057 (PR #28) |


## Épica 6 · Informe

### HU-21 · Un informe técnico exportable con los hallazgos priorizados

Como **desarrollador** que debe corregir, **quiero** un informe técnico exportable con los hallazgos priorizados, **para** entregarlo o archivarlo fuera de la plataforma.

Criterios de aceptación:

- El informe es una página HTML autocontenida que se puede imprimir o guardar como PDF.
- Cada hallazgo muestra su evidencia original, la sugerencia de la IA y la última decisión humana.
- Los falsos positivos y los duplicados van en una sección aparte.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S6 | En revisión | T-058, T-059 (PR #22) |

### HU-22 · Generar el informe desde el dashboard

Como **desarrollador** que debe corregir, **quiero** generar el informe desde el dashboard, **para** no depender de la línea de comandos.

Criterios de aceptación:

- El módulo Informe del dashboard genera y muestra el informe del objetivo.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S6 | Pendiente | Sin tarea propia (depende del PR #22) |


## Épica 7 · Calidad de la IA

### HU-23 · Evaluar la sugerencia del modelo en el mismo momento en que decido

Como **analista** que revisa los hallazgos, **quiero** evaluar la sugerencia del modelo en el mismo momento en que decido, **para** medir la calidad de la IA sin un trabajo aparte.

Criterios de aceptación:

- Al decidir, se puede indicar si la categoría y la prioridad son correctas, si la remediación es útil y si el modelo inventó algo.
- Cada respuesta queda asociada a la sugerencia exacta que se juzgó.
- Un revisor no ve las respuestas de los demás.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S6 | En revisión | T-043, T-056 (PR #28) |

### HU-24 · Conocer el acierto del modelo y el acuerdo entre revisores

Como **analista** que revisa los hallazgos, **quiero** conocer el acierto del modelo y el acuerdo entre revisores, **para** saber cuánto confiar en las sugerencias.

Criterios de aceptación:

- Se calculan el acierto de categoría y de prioridad, la utilidad de la remediación y la tasa de alucinación.
- El acuerdo entre dos revisores se informa con el índice kappa y su tamaño de muestra.
- Las métricas se pueden reproducir desde los datos guardados.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S5-S6 | En curso | T-045, T-046, T-048 |

### HU-25 · Juntar las anotaciones hechas en equipos distintos

Como **analista** que revisa los hallazgos, **quiero** juntar las anotaciones hechas en equipos distintos, **para** que varios revisores evalúen las mismas sugerencias.

Criterios de aceptación:

- Las sugerencias y las decisiones se exportan e importan entre bases de datos.
- Importar es idempotente y no sobrescribe datos existentes.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Media | S6 | En curso | Sin tarea propia (rama `luciano/intercambio`) |


## Épica 8 · Operación y confianza en los cambios

### HU-26 · Levantar todo el sistema con un comando

Como **desarrollador** que debe corregir, **quiero** levantar todo el sistema con un comando, **para** probarlo sin instalar cada componente a mano.

Criterios de aceptación:

- `docker compose up` levanta la base, la API y el dashboard.
- El README explica la instalación desde cero.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S1-S5 | Hecha | T-005, T-010, T-049 |

### HU-27 · Que cada cambio se verifique automáticamente antes de integrarse

Como **desarrollador** que debe corregir, **quiero** que cada cambio se verifique automáticamente antes de integrarse, **para** no romper lo que ya funciona.

Criterios de aceptación:

- Cada pull request ejecuta las pruebas, aplica y revierte las migraciones, y compila el dashboard.
- La rama principal exige los checks en verde y la aprobación de otro integrante.

| Prioridad | Sprint | Estado | Tareas |
|---|---|---|---|
| Alta | S2-S5 | Hecha | T-025 (la integración continua no tuvo tarea propia) |

## Fuera del alcance

Estas necesidades se identificaron y se dejaron fuera del producto mínimo. Quedan como trabajo futuro.

| Necesidad | Motivo |
|---|---|
| Lanzar el escaneo desde el dashboard | Exige que la plataforma controle el escáner, lo que une dos redes que hoy están separadas a propósito |
| Importar resultados de otros escáneres (Nikto, OpenVAS) | Se eliminó en la replanificación del 15-10-2026 para cerrar dentro del semestre. El modelo de datos ya admite más de una herramienta |
| Cuentas de usuario y permisos | El sistema opera en un laboratorio local. Hoy el revisor se identifica con su nombre |
| Marcar un hallazgo como remediado al volver a escanear | El estado existe en el modelo, pero falta la verificación automática |
| Integración con sistemas de tickets | Fuera del objetivo del proyecto |
