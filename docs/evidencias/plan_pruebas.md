# Plan de pruebas y resultados

**Evidencia 9** del Encargo 1 · **Responsable:** Felipe Cayún · **Actualizado:** 16-11-2026

Reúne las pruebas del proyecto como casos con resultado esperado y obtenido, y registra las incidencias que encontraron y las mejoras que se aplicaron a partir de ellas.

## 1. Niveles de prueba

| Nivel | Qué verifica | Cómo se ejecuta | Cuándo |
|---|---|---|---|
| Unitarias | Funciones aisladas: parser, normalización, tabla CWE → OWASP, validación de la IA, informe | `python -m pytest tests/` | En cada PR, en el CI |
| Integración | API contra PostgreSQL real: ingesta, consulta, enriquecimiento, restricciones de la base | Job "Migraciones y restricciones" del CI | En cada PR |
| Extremo a extremo | El flujo completo, de un reporte de ZAP al informe técnico | `./lab/e2e.sh` | Antes de cada entrega y de la demo |
| Laboratorio | Aislamiento de red y escaneos reales | Ping desde `lab_interna`, `./lab/escanear.sh` | Al montar el entorno y al escanear |
| Validación manual | Calidad de la IA contra criterio humano (golden set) | Anotación sin ver al modelo y métricas | Una vez por versión del prompt |

## 2. Pruebas automáticas

Funciones de prueba en `backend/tests/` (algunas están parametrizadas, así que pytest reporta más casos que funciones):

| Archivo | Funciones | Qué cubre |
|---|---|---|
| `test_zap_parser.py` | 20 | Conversión de alertas de ZAP al esquema normalizado, CWE, ocurrencias y claves |
| `test_owasp_por_cwe.py` | 17 | Tabla CWE → OWASP 2025 y regla de prioridad por severidad |
| `test_enriquecer.py` | 21 | Validación de la salida del modelo, reintentos y marca "sin enriquecer" |
| `test_cliente_ollama.py` | 3 | Cliente de Ollama ante cortes de conexión |
| `test_esquema.py` | 2 | El hallazgo de ejemplo cumple el JSON Schema |
| `test_ingesta.py` | 14 | Importación, deduplicación y rechazos contra PostgreSQL |
| `test_enriquecimiento_api.py` | 14 | Endpoints de enriquecimiento contra PostgreSQL |
| `test_resumen_filtros_api.py` | 16 | Resumen y filtros de la API contra PostgreSQL |
| `test_informe.py` | 10 | Informe técnico: prioridad, decisión vigente, descartados, orden, métricas y escape HTML |

Las pruebas de integración se saltan si no hay PostgreSQL disponible, y el CI las corre siempre con una base real.

## 3. Casos de prueba

| ID | Caso | Resultado esperado | Resultado obtenido | Estado | Evidencia |
|---|---|---|---|---|---|
| CP-01 | Ping a internet desde la red del laboratorio | Falla con "Network unreachable" | Falla con "Network unreachable" | ✅ | `T006_aislamiento.txt` |
| CP-02 | Ping a internet fuera de la red del laboratorio | Responde | Responde, 0 % de pérdida | ✅ | `T006_aislamiento.txt` |
| CP-03 | Escaneo full con el spider tradicional | Encuentra hallazgos de Juice Shop | 5 tipos de alerta, sin inyección | ✅ | `lab/fixtures/zap_juiceshop_full_v1.json` |
| CP-04 | Escaneo full con Ajax Spider y límites de tiempo | Más tipos de alerta que el spider tradicional y termina solo | 13 tipos, incluida inyección SQL, en unos 15 minutos | ✅ | `lab/fixtures/zap_juiceshop_ajax_v2.json` |
| CP-05 | Escaneo con sesión iniciada | Alertas que solo aparecen autenticado | 15 tipos; nuevo: JWT en `localStorage` (CWE-922) | ✅ | `escaneo_autenticado.md` |
| CP-06 | Escáner sin Juice Shop arriba | Se detiene antes de lanzar ZAP e indica cómo corregirlo | "Juice Shop no está arriba. Prueba: docker compose up -d" | ✅ | `lab/escanear.sh` |
| CP-07 | Congelar un fixture con un nombre ya usado | Se niega a sobrescribirlo | "ya existe. Usa otro nombre" | ✅ | `lab/congelar_fixture.sh` |
| CP-08 | Importar un reporte de ZAP por la API | 201 y hallazgos nuevos | 201 · 13 hallazgos nuevos | ✅ | `lab/e2e.sh`, paso 3 |
| CP-09 | Importar el mismo reporte dos veces | 409, sin duplicar datos | 409 | ✅ | `lab/e2e.sh`, paso 4 |
| CP-10 | Resumen de la API después de importar | Cuenta los mismos hallazgos importados | 13 = 13 | ✅ | `lab/e2e.sh`, paso 5 |
| CP-11 | Enriquecer sin Ollama disponible | La API responde 503 y los hallazgos quedan "sin enriquecer"; el flujo sigue | 503 y "Sin enriquecer" en el informe | ✅ | `lab/e2e.sh`, paso 6 |
| CP-12 | Formato de la salida del modelo | JSON válido según el esquema | 26 de 26 válidas al primer intento | ✅ | `enriquecimiento_ajax_v2.md` |
| CP-13 | Latencia del modelo local | Bajo 15 s por hallazgo | Mediana de 1,1 s por hallazgo en GPU | ✅ | `latencia_ollama.md` |
| CP-14 | Informe técnico de un escaneo | 5 secciones y una ficha por hallazgo | 5 secciones y 13 fichas para 13 hallazgos | ✅ | `lab/e2e.sh`, paso 7 |
| CP-15 | Evidencia con código malicioso en el informe | Se muestra como texto y no se ejecuta | `<script>` escapado | ✅ | `test_informe.py` |
| CP-16 | Categoría OWASP del modelo contra el criterio humano | Medir el acierto | 8/20 (40 %); 8/12 (67 %) sin casos ambiguos | 📊 | `metricas_golden_set.md` |
| CP-17 | Prioridad del modelo contra una regla fija por severidad | Medir cuál acierta más | Modelo 8/20 (40 %), regla 6/10 (60 %) | 📊 | `metricas_golden_set.md` |
| CP-18 | Alucinaciones del modelo, dos revisores | Medir la tasa y el acuerdo entre revisores | 20 % y 30 % según revisor; acuerdo 90 %, κ = 0,74 | 📊 | `acuerdo_alucinaciones.md` |

✅ cumple lo esperado · 📊 medición: el resultado es un dato, no un aprobado o reprobado

## 4. Incidencias y mejoras aplicadas

| ID | Incidencia | Cómo se detectó | Causa | Mejora aplicada |
|---|---|---|---|---|
| IN-01 | El escaneo full con Ajax Spider quedó colgado más de 3 horas | Seguimiento del escaneo con `docker stats` | ZAP abría navegadores headless sin cerrarlos (687 procesos) mientras Juice Shop no recibía carga | Límites de tiempo: 5 minutos de exploración, 5 por regla y 60 de escaneo activo. Terminó en unos 15 minutos y quedaron fijos en `lab/escanear.sh` |
| IN-02 | ZAP no podía escribir sus resultados (`Permission denied`) | Primer escaneo | `lab/salidas` pertenecía a `root` | `chown` de la carpeta y verificación de permisos en `lab/escanear.sh` antes de escanear (CP-06) |
| IN-03 | La evidencia de H07 apareció como `#NAME?` | Revisión de la planilla de alucinaciones | Excel interpretó como fórmula un valor que empieza con `-` | Se restauró el valor original y se dejó la regla de no editar las evidencias CSV con Excel |
| IN-04 | La prueba de extremo a extremo reportó 2 fichas en un informe con 13 hallazgos | `lab/e2e.sh`, paso 7 | El conteo usaba `grep -c`, que cuenta líneas, y las fichas comparten línea | Se cambió a `grep -o … \| wc -l`, que cuenta apariciones. El informe estaba bien; el error era de la prueba |
| IN-05 | El spider tradicional no encontraba la inyección SQL | Comparación de CP-03 con CP-04 | Juice Shop arma su contenido con JavaScript y el spider tradicional no lo ejecuta | Ajax Spider como escaneo de referencia para los fixtures |
| IN-06 | La prioridad del modelo acierta menos que una regla fija, y su confianza es igual de alta cuando falla | CP-17 | El modelo no distingue la urgencia de cada caso | Decisión mixta: la regla propone la prioridad, la tabla CWE la categoría y la IA explica (`IA_MODELO_Y_PROMPT.md`, sección 5) |

## 5. Pendiente

- Golden set completo: anotación de todos los hallazgos de `ajax_v2`, `full_v1` y `ajax_auth_v1` por dos revisores (T-043), y recalcular CP-16 a CP-18 con esa muestra.
- Agregar al E2E el registro de una decisión humana cuando el endpoint de validaciones esté en `main`.
