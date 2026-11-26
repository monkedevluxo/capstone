# Evidencias del proyecto

**Tarea:** T-067 · **Responsable:** Felipe Cayún · **Actualizado:** 25-11-2026

Índice de las diez evidencias comprometidas con el docente en la definición del proyecto (`docs/institucional/fase1/Encargo1_Definición_Proyecto_SentinelAI.docx`, sección 6), con dónde está cada una en el repositorio y su estado.

Estados: ✅ lista · 🟡 en curso · ⏳ pendiente

## Las diez evidencias

| # | Evidencia | Entrega | Dónde está | Estado |
|---|---|---|---|---|
| 1 | Documento de definición y arquitectura | Avance | `docs/institucional/fase1/`, `docs/diseno/` | ✅ |
| 2 | Repositorio GitHub y bitácora de trabajo | Avance | Historial de commits y pull requests, `docs/SentinelAI_Plan_Sprints.xlsx` | ✅ |
| 3 | Laboratorio en Docker Compose | Avance | `docker-compose.yml`, `T006_aislamiento.txt`, `lab/` | ✅ |
| 4 | Modelo de datos y API inicial | Avance | `docs/diseno/MODELO_DATOS.md`, `backend/migrations/`, `backend/app/models.py`, `backend/app/rutas.py` | ✅ |
| 5 | Importador y normalizador de resultados | Avance | `backend/app/parsers/zap.py`, `backend/app/ingesta.py`, `lab/fixtures/`, `docs/diseno/ESQUEMA_HALLAZGO.md` | ✅ |
| 6 | Dashboard funcional | Final | `frontend/`, `capturas/` | ✅ |
| 7 | Módulo de análisis con IA local | Final | `backend/app/ia/`, `docs/diseno/IA_MODELO_Y_PROMPT.md`, `respuestas_modelo/` | ✅ |
| 8 | Reporte técnico generado por la plataforma | Final | `backend/app/informe.py`, `backend/app/informe_consulta.py`, `backend/app/informe_export.py`, `frontend/src/app/informe/`, `docs/guias/INFORME_TECNICO.md` | ✅ |
| 9 | Plan de pruebas y resultados | Final | `plan_pruebas.md`, `backend/tests/`, `.github/workflows/ci.yml`, `lab/e2e.sh`, golden set (abajo) | ✅ |
| 10 | Documentación técnica y presentación final | Final | `README.md`, `docs/guias/`, `docs/diseno/` | ⏳ |

### Qué falta en cada una

- **6 · Dashboard:** el listado con filtros y totales (PR #21), la vista de detalle y el registro de la decisión humana (PR #28), página de escaneos (PR #35) y botón Informe (PR #40) están en `main`. Las capturas de resumen, lista filtrada, detalle y validación están en `capturas/` (T-060).
- **8 · Reporte técnico:** completo (PR #22 y #40). Se abre con el botón Informe del dashboard (`GET /informe`) o desde la terminal, con 19 funciones de prueba.
- **9 · Plan de pruebas y resultados:** las pruebas existen (tests automáticos en CI, prueba de extremo a extremo y golden set), y `plan_pruebas.md` las reúne como casos con resultado esperado y obtenido, más las incidencias y mejoras aplicadas. El golden set de 17 hallazgos está completo con dos revisores, una ronda de calibración y el acuerdo entre ambos (CP-22, `golden_set_17.md`).
- **10 · Documentación y presentación final:** corresponde al sprint de cierre.

## Archivos de esta carpeta

### Laboratorio

| Archivo | Qué demuestra |
|---|---|
| `T006_aislamiento.txt` | La red del laboratorio no tiene salida a internet: el ping desde `lab_interna` falla y fuera de ella responde. Respaldo técnico del marco ético (Ley 21.459) |
| `escaneo_autenticado.md` | Escaneo con sesión iniciada (15 tipos de alerta contra 13 sin sesión), la propuesta de muestra para el golden set, la decisión del equipo y la corrección a 17 hallazgos reales |

### Inteligencia artificial

| Archivo | Qué demuestra |
|---|---|
| `latencia_ollama.md` | Latencia del modelo local por hallazgo, medida en GPU |
| `contenedor_ollama.md` | El backend alcanza a Ollama desde su contenedor |
| `enriquecimiento_ajax_v2.md` | Primera prueba del pipeline completo sobre hallazgos que el prompt no conocía |
| `respuestas_modelo/` | Respuestas crudas del modelo en cada prueba, guardadas sin modificar, y los 17 enriquecimientos que comparten los revisores del golden set (`enriquecimientos_20261118.json`) |

### Golden set y calidad de la IA

| Archivo | Qué demuestra |
|---|---|
| `validacion_manual.csv` | Criterio humano para 10 hallazgos, anotado sin ver las respuestas del modelo |
| `rubrica_anotacion.md` | Cómo se decidieron la categoría, la prioridad y los falsos positivos |
| `metricas_golden_set.md` | Acierto de categoría y de prioridad, y tasa de alucinación del modelo contra el criterio humano |
| `revision_alucinaciones.csv` | Revisión de alucinaciones de Joaquín Herrera (20 respuestas) |
| `revision_alucinaciones_felipe.csv` | Segunda revisión independiente, de Felipe Cayún |
| `acuerdo_alucinaciones.md` | Acuerdo entre los dos revisores: 90 % (18 de 20), κ de Cohen 0,74 |
| `golden_set_17.md` | Golden set de 17 hallazgos con dos revisores: la ronda independiente (acuerdo casi nulo en categoría y prioridad, y por qué), la regla común, la calibración y la ronda 2 |
| `golden_set/` | Exports de las anotaciones de cada revisor por ronda, para repetir el cálculo con `backend/scripts/acuerdo_revisores.py` |

### Dashboard

| Archivo | Qué demuestra |
|---|---|
| `capturas/` | El dashboard con los datos de la demo: resumen, lista filtrada, detalle de un hallazgo con sus tres capas y una decisión humana registrada. El índice de la carpeta dice de dónde salen los datos |

## Cómo reproducir las evidencias principales

```bash
docker compose up -d

# 3 · Aislamiento del laboratorio (debe fallar el primero y responder el segundo)
docker run --rm --network capstone_lab_interna alpine ping -c 2 -W 2 8.8.8.8
docker run --rm alpine ping -c 2 8.8.8.8

# 5 · Escaneo e importación
./lab/escanear.sh ajax

# 8 y 9 · Flujo completo, de reporte a decisión humana e informe, sobre la base de pruebas
./lab/e2e.sh

# 8 · Informe técnico de la base de la demo
docker compose exec -T api python scripts/informe.py > informe.html
```
