# Requisitos no funcionales

**SentinelAI** · Actualizado: 18-11-2026

Los requisitos funcionales están expresados como historias de usuario en `docs/producto/PRODUCT_BACKLOG.md`. Este documento define **con qué calidad** debe operar el sistema. Cada requisito tiene un criterio medible y dice cómo se verifica; los casos de prueba (CP-xx) están en `docs/evidencias/plan_pruebas.md`.

| Estado | Significado |
|---|---|
| ✅ Cumple | Verificado con una prueba o una medición registrada |
| 🔶 Parcial | Cumple en parte, o se verificó solo de forma manual |
| ⬜ Sin medir | Definido, todavía sin evidencia |

---

## 1. Seguridad

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-01 | El objetivo vulnerable no tiene salida a internet | Un ping desde la red `lab_interna` falla con "Network unreachable" | CP-01, `docs/evidencias/T006_aislamiento.txt` | ✅ |
| RNF-02 | Solo se importan resultados de objetivos del laboratorio | Un reporte con otro objetivo se rechaza con 403, y la base rechaza registrar un objetivo fuera del laboratorio | Tests de ingesta y paso "Verificar restricciones del proyecto" del CI | ✅ |
| RNF-03 | Ningún servicio queda expuesto a otros equipos de la red | Todos los puertos se publican en `127.0.0.1` | `docker-compose.yml` | ✅ |
| RNF-04 | El navegador no habla directo con la API | La dirección de la API solo la conoce el servidor del dashboard; no hay CORS habilitado | `docker-compose.yml` (variable `API_URL` sin prefijo público) | ✅ |
| RNF-05 | La evidencia del escáner no se ejecuta al mostrarla | Todo texto que viene de ZAP se muestra como texto, en el dashboard y en el informe | CP-15, `test_informe.py` | ✅ |
| RNF-06 | No hay secretos en el repositorio | Las credenciales se leen de variables de entorno; `.env` no se versiona | `backend/app/config.py`, `.gitignore` | ✅ |
| RNF-07 | Los contenedores propios no corren como administrador | La imagen de la API usa un usuario sin privilegios | `backend/Dockerfile` | ✅ |

**Límite conocido.** El sistema no tiene cuentas de usuario: está pensado para operar en un equipo local de laboratorio. Desplegarlo en una red compartida exigiría autenticación (ver `docs/diseno/DISENO.md`, decisión D-12).

## 2. Privacidad de la información

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-08 | La evidencia de seguridad no sale de equipos propios | El modelo de lenguaje corre con Ollama en un equipo del equipo; la API no llama a servicios externos | `backend/app/ia/cliente.py`, `docs/evidencias/latencia_ollama.md` | ✅ |

## 3. Integridad y trazabilidad

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-09 | La evidencia original se conserva sin cambios | Cada hallazgo guarda el bloque original de la alerta, y cada reporte su huella SHA-256 | Tests de ingesta; sección "Escaneos de origen" del informe | ✅ |
| RNF-10 | Un reporte no se importa dos veces | El segundo intento responde 409 y no modifica datos | CP-09 | ✅ |
| RNF-11 | Una importación no queda a medias | La ingesta ocurre en una transacción: si falla, no se guarda nada | Tests de ingesta | ✅ |
| RNF-12 | Toda sugerencia de la IA es trazable | Guarda el modelo, la versión y la huella del prompt, los intentos, la latencia y la fecha | Tests de enriquecimiento | ✅ |
| RNF-13 | Toda decisión humana es trazable | Guarda revisor, fecha, comentario y la sugerencia exacta que se juzgó; nada se borra | Tests de validaciones *(pull request #28)* | 🔶 |

## 4. Rendimiento

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-14 | El modelo responde en un tiempo usable | Menos de 15 s por hallazgo con el modelo cargado | CP-13: mediana de 1,1 s por hallazgo en una RTX 3060 Ti; la primera llamada tarda 14 s mientras carga el modelo | ✅ |
| RNF-15 | Un escaneo completo se enriquece en minutos | Menos de 2 minutos para los 17 hallazgos del golden set, con el modelo en GPU | Medición del lote real (T-039) | ⬜ |
| RNF-16 | La importación es rápida | Menos de 5 s para el reporte más grande de los fixtures | Sin medición registrada | ⬜ |
| RNF-17 | El sistema cabe en un equipo de estudiante | Opera con 16 GB de RAM, con el modelo en otro equipo o en GPU | Desarrollo en notebooks de 16 GB; `README.md`, sección "Presupuesto de memoria" | ✅ |

## 5. Disponibilidad y tolerancia a fallas

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-18 | El sistema funciona sin el modelo | Si Ollama no responde, la API contesta 503, no guarda nada y el resto del flujo sigue | CP-11 | ✅ |
| RNF-19 | Una respuesta inválida del modelo no se guarda como válida | La salida se valida contra un esquema; tras 3 intentos el hallazgo queda "sin enriquecer" con el motivo | CP-12, `test_enriquecer.py` | ✅ |
| RNF-20 | Un corte del modelo a mitad de lote no pierde trabajo | Lo ya procesado queda guardado y se puede reintentar | Tests del cliente de Ollama y del enriquecimiento por lote | ✅ |
| RNF-21 | El dashboard informa cuando la API no responde | Muestra un aviso claro, sin exponer la dirección interna | Revisión manual en el navegador | 🔶 |

## 6. Usabilidad y accesibilidad

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-22 | La interfaz está en español y sin jerga innecesaria | Textos, mensajes de error y estados en español | Revisión manual | ✅ |
| RNF-23 | Se distingue qué dijo el escáner, qué sugirió la IA y qué decidió una persona | Tres capas visualmente separadas; la IA se presenta como "sugerencia, no decisión" | Pantalla de detalle *(pull request #28)* | 🔶 |
| RNF-24 | Funciona en escritorio y en teléfono | Sin desplazamiento horizontal entre 390 y 1440 px de ancho | Capturas a 390, 1024, 1280 y 1440 px durante el desarrollo | 🔶 |
| RNF-25 | Se puede usar con teclado | Todos los controles alcanzables con el teclado y con nombre para lectores de pantalla | Revisión manual; sin auditoría formal | 🔶 |

## 7. Mantenibilidad

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-26 | Cada cambio se verifica antes de integrarse | La rama `main` exige pruebas y migraciones en verde y la aprobación de otro integrante | Integración continua y protección de `main` | ✅ |
| RNF-27 | El esquema de la base evoluciona de forma controlada | Todo cambio va en una migración de Alembic que se puede revertir y reaplicar | Paso "Revertir y reaplicar migraciones" del CI | ✅ |
| RNF-28 | Las reglas de negocio tienen una sola fuente | La regla "revisar" se calcula desde la misma tabla en la API, el dashboard y el informe | Test de equivalencia entre la consulta SQL y la función `evaluar()` | ✅ |
| RNF-29 | El comportamiento esperado está escrito como pruebas | Pruebas unitarias y de integración en `backend/tests/` | 119 funciones de prueba en `main` al 18-11-2026 | ✅ |

## 8. Portabilidad y despliegue

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-30 | El sistema se levanta con un comando | `docker compose up -d` levanta base, API y dashboard | `README.md` y `docs/guias/MANUAL_TECNICO.md` | ✅ |
| RNF-31 | Funciona sin internet una vez instalado | Imágenes descargadas y fuentes del dashboard empaquetadas | Prueba sin conexión antes de la demostración | ⬜ |
| RNF-32 | Es reproducible por alguien que no escribió el código | Una persona nueva lo levanta siguiendo solo la documentación | Definición de terminado de cada entrega | 🔶 |

## 9. Ética y cumplimiento legal

| ID | Requisito | Criterio | Verificación | Estado |
|---|---|---|---|---|
| RNF-33 | Solo se escanean objetivos autorizados | Únicamente aplicaciones deliberadamente vulnerables en el laboratorio local, conforme a la Ley 21.459 | RNF-01 y RNF-02; `README.md`, "Marco ético y legal" | ✅ |
| RNF-34 | Una persona decide sobre cada hallazgo | El estado de un hallazgo solo cambia con una validación humana registrada | Endpoint de validaciones *(pull request #28)* | 🔶 |

---

## Resumen

| Estado | Requisitos |
|---|---|
| ✅ Cumple | 24 |
| 🔶 Parcial | 7 |
| ⬜ Sin medir | 3 |
| **Total** | **34** |

Tres de los parciales pasan a cumplir cuando se integre el pull request #28. Los tres sin medir se cierran antes de la defensa: la medición del lote real (RNF-15), la de importación (RNF-16) y la prueba sin conexión (RNF-31).
