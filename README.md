# SentinelAI

**Hallazgos de seguridad web priorizados con IA local**

Proyecto de Título · Capstone · Duoc UC · Grupo 3

[![CI](https://github.com/monkedevluxo/capstone/actions/workflows/ci.yml/badge.svg)](https://github.com/monkedevluxo/capstone/actions/workflows/ci.yml)

---

## Qué es

Una plataforma web que centraliza los resultados de herramientas de análisis de seguridad ejecutadas sobre una aplicación deliberadamente vulnerable en un laboratorio aislado. Normaliza los hallazgos, los enriquece con un modelo de lenguaje ejecutado localmente y los presenta priorizados.

El flujo es: **escaneo → normalización → enriquecimiento con IA → validación humana → informe**.

### Qué hace la IA, y qué no

El modelo corre localmente con Ollama e **interpreta evidencia ya recolectada**. No escanea, no ataca y no descubre vulnerabilidades por sí mismo. Su trabajo es:

- **Explicar** el hallazgo técnico en lenguaje comprensible
- **Clasificar** según OWASP Top 10:2025 y sugerir una prioridad, con nivel de confianza
- **Recomendar** una medida de remediación concreta

Toda respuesta del modelo se valida contra un esquema antes de guardarse; si falla tres veces, el hallazgo queda marcado como no enriquecido. La validación final es siempre humana y queda registrada en la base de datos.

La calidad del modelo se mide contra un golden set etiquetado por una persona sin ver sus respuestas (`docs/evidencias/metricas_golden_set.md`). A partir de esas métricas, la propuesta del equipo es que la prioridad se asigne con una regla por severidad y que la categoría se contraste con una tabla CWE → OWASP (`docs/diseno/IA_MODELO_Y_PROMPT.md`, sección 5).

---

## Marco ético y legal

Las pruebas se ejecutan **únicamente** sobre aplicaciones vulnerables desplegadas en local, en una red sin exposición externa. Nunca se opera sobre infraestructura de terceros no autorizada.

La red del laboratorio usa `internal: true` en Docker, lo que significa que el contenedor objetivo **no tiene ruta de salida a internet**. No es una convención del equipo: es una restricción de infraestructura, verificable con los comandos de la sección de verificación.

La Ley 21.459 sobre delitos informáticos delimita el alcance del proyecto y justifica el uso exclusivo de entornos autorizados. La API rechaza importar reportes de hosts que no pertenezcan al laboratorio, y la base de datos rechaza registrar objetivos fuera de él.

---

## Estructura del repositorio

```
capstone/
├── .github/workflows/    CI: tests, migraciones y restricciones
├── backend/
│   ├── app/
│   │   ├── main.py           API FastAPI
│   │   ├── rutas.py          Endpoints de ingesta y consulta
│   │   ├── ingesta.py        Importación de reportes en una transacción
│   │   ├── models.py         Modelos SQLAlchemy (7 tablas)
│   │   ├── normalizacion.py  Rutas y claves de deduplicación
│   │   ├── parsers/          Conversión de salidas de escáneres
│   │   └── ia/               Cliente de Ollama, prompt, validación y reintentos
│   ├── migrations/           Migraciones de Alembic
│   ├── scripts/
│   │   ├── seed.py                 Datos de prueba sintéticos
│   │   ├── verificar_bd.py         Verifica las restricciones de la base
│   │   └── metricas_golden_set.py  Métricas del modelo contra el golden set
│   └── tests/                Parser, esquema, módulo de IA e ingesta
├── frontend/             Dashboard en Next.js (desde el S5)
├── lab/
│   ├── fixtures/         Escaneos congelados y versionados (insumo de desarrollo)
│   └── salidas/          Resultados de escaneos en curso (no se versiona)
├── docs/
│   ├── diseno/           Esquema del hallazgo, modelo de datos, IA y decisiones técnicas
│   ├── institucional/    Entregables formales que solicita Duoc UC (fase 1 y fase 2)
│   ├── guias/            Instalación, Docker, Ollama
│   └── evidencias/       Logs, mediciones, golden set y planillas de validación
├── docker-compose.yml
└── README.md
```

### Por qué `lab/fixtures/` sí se versiona

Un escaneo completo demora entre 9 y 40 minutos según el equipo y si usa Ajax Spider. Los fixtures son resultados reales congelados que permiten desarrollar y probar en segundos, sin levantar el laboratorio ni re-escanear. Es lo que hace reproducible el desarrollo del pipeline.

`lab/salidas/` no se versiona porque cambia en cada ejecución.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · Alembic |
| Base de datos | PostgreSQL 16 |
| IA | Ollama · Llama 3.1 8B (q4_K_M) · validación con Pydantic |
| Frontend | Next.js · React |
| Laboratorio | Docker Compose |
| Escáner | OWASP ZAP (con Ajax Spider) |
| Objetivo | OWASP Juice Shop |

Nikto, OpenVAS, DVWA y WebGoat quedaron fuera del alcance en la replanificación del 15-10-2026.

---

## Requisitos

- **Docker Engine** — no Docker Desktop, ver nota abajo
- Git
- **En Windows:** WSL2 con Ubuntu
- **Ollama** — solo en el equipo que actúe como nodo de inferencia

Instalación paso a paso: `docs/guias/GUIA_INSTALACION.md`

### Por qué Docker Engine y no Docker Desktop

Docker Desktop presentó inestabilidad bajo carga sostenida en uno de los equipos
del grupo: reinicios del motor, errores 500 en su API y escaneos interrumpidos a
mitad de ejecución. El diagnóstico apuntó a su capa de integración con WSL.
Migrar a Docker Engine nativo dentro de WSL2 resolvió el problema.

Docker Desktop puede funcionar en otros equipos, pero el camino soportado por el
equipo es Docker Engine.

---

## Cómo levantar el proyecto

```bash
git clone https://github.com/monkedevluxo/capstone.git
cd capstone
docker compose up -d
docker compose ps
```

Deben quedar corriendo `sentinel-juiceshop` y `sentinel-db`.

Juice Shop **no responde en `localhost:3000`**, y eso es correcto: vive dentro de `lab_interna` sin puertos publicados. Solo ZAP la alcanza.

### Verificar el aislamiento de red

```bash
# Dentro de lab_interna: debe fallar con "Network unreachable"
docker run --rm --network capstone_lab_interna alpine ping -c 2 -W 2 8.8.8.8

# En la red normal: debe responder
docker run --rm alpine ping -c 2 8.8.8.8
```

Si el nombre de la red no coincide, búsquenlo con `docker network ls`. Docker antepone el nombre de la carpeta del proyecto.

### Ejecutar un escaneo

```bash
# Rápido, solo análisis pasivo (1-2 minutos)
docker compose run --rm zap zap-baseline.py -t http://juiceshop:3000 -J baseline.json -I

# Completo, con escaneo activo (unos 9 minutos)
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -J full.json -I

# Completo con Ajax Spider (más cobertura en Juice Shop; requiere más RAM)
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -j -J ajax.json -I
```

Los resultados quedan en `lab/salidas/`.

**Si aparece `Permission denied` al escribir el JSON:** Docker creó `lab/salidas/` como root. Se corrige con `sudo chown -R $USER:$USER lab/salidas`.

### Levantar el backend y la base de datos

```bash
docker compose up -d db api
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py --reset
curl http://localhost:8000/stats
```

Debe devolver 1 objetivo, 2 escaneos y 40 hallazgos.

Los datos del seed son **sintéticos**, no vienen de un escaneo real. El objetivo
se llama "(datos de prueba)" justamente para no confundirlos en el informe.

### Importar un escaneo real

```bash
curl -X POST localhost:8000/scans/import \
  -H "Content-Type: application/json" \
  --data-binary @lab/fixtures/zap_juiceshop_ajax_v2.json

curl "localhost:8000/findings?severidad=alta"
```

| Endpoint | Qué hace |
|---|---|
| `POST /scans/import` | Importa un reporte de ZAP en una transacción. 403 si el host no es del laboratorio, 409 si el reporte ya se importó, 422 si no es un reporte de ZAP |
| `GET /scans` | Lista los escaneos importados |
| `GET /findings` | Lista hallazgos con filtros por severidad, estado, escaneo, objetivo, categoría OWASP, enriquecimiento y texto |
| `GET /findings/{id}` | Detalle de un hallazgo, con la evidencia original, la capa de IA y las validaciones por separado |

Documentación interactiva de la API: `http://localhost:8000/docs`

<!-- TODO: agregar el levantamiento del frontend (S5) -->
<!-- TODO: documentar las variables de entorno y el archivo .env.ejemplo -->

---

## Presupuesto de memoria

Con 16 GB de RAM no conviene levantar todo simultáneamente. El pipeline es naturalmente por fases:

| Fase | Servicios | RAM aproximada |
|---|---|---|
| Escaneo | `juiceshop` + `zap` | ~9 GB |
| Enriquecimiento | `db` + `api` + Ollama | ~13 GB |
| Dashboard | `db` + `api` + `web` | ~8 GB |

---

## Documentación

| Documento | Ubicación |
|---|---|
| **Instalación del entorno** | `docs/guias/GUIA_INSTALACION.md` |
| Introducción a Docker | `docs/guias/DOCKER_BASICO.md` |
| Esquema del hallazgo normalizado | `docs/diseno/ESQUEMA_HALLAZGO.md` |
| Modelo de datos (DER y tablas) | `docs/diseno/MODELO_DATOS.md` |
| Modelo de IA, prompt y alternativas | `docs/diseno/IA_MODELO_Y_PROMPT.md` |
| Golden set y métricas del modelo | `docs/evidencias/metricas_golden_set.md` |
| Backend y migraciones (S2) | `docs/guias/GUIA_S2.md` |
| Ollama en equipo separado | `docs/guias/ADDENDUM_OLLAMA_REMOTO.md` |
| Entregables institucionales | `docs/institucional/` |
| Rol de Felipe | `docs/README_FELIPE.md` |
| Rol de Joaquín | `docs/README_JOAQUIN.md` |
| Planilla de sprints | `docs/SentinelAI_Plan_Sprints.xlsx` |

---

## Equipo

| Integrante | Rol | Responsabilidades |
|---|---|---|
| Felipe Cayún | Laboratorio y Validación | Escaneos, golden set, informe técnico exportable |
| Joaquín Herrera | Arquitectura, IA y Parser | Parser de ZAP, nodo de inferencia, prompt y métricas |
| Luciano Zambrano | Backend, Datos y Dashboard | Laboratorio, modelo de datos, API, CI y dashboard |

El detalle de cada rol está en `docs/README_FELIPE.md` y `docs/README_JOAQUIN.md`.

**Docente:** Aníbal Sotelo

---

## Integración continua

Cada PR hacia `main` corre automáticamente en GitHub Actions
(`.github/workflows/ci.yml`). Son dos jobs:

| Job | Qué comprueba |
|---|---|
| **Tests** | Los tests del parser de ZAP, del módulo de IA (sin depender de Ollama) y que `ejemplo_hallazgo.json` cumpla `finding.schema.json` |
| **Migraciones y restricciones** | Que la migración aplique, se revierta y se reaplique sobre un PostgreSQL limpio; que modelos y migraciones estén sincronizados (`alembic check`); que la base rechace lo que debe rechazar; y los tests de ingesta y consulta contra la base real |

En total son 72 pruebas automatizadas, más las verificaciones de restricciones.

Las restricciones que se verifican en cada PR:

- solo se aceptan objetivos del laboratorio (Ley 21.459)
- un enriquecimiento fallido no puede traer datos a medias
- un hallazgo no puede tener dos enriquecimientos vigentes
- la confianza del modelo va entre 0 y 1
- no se puede duplicar un hallazgo en el mismo objetivo

La restricción ética del proyecto no depende de que alguien se acuerde de
respetarla: si un cambio la debilita, el CI falla y el PR no se puede mergear.

**No hay CD.** El sistema es deliberadamente local, así que no hay dónde
desplegar. Los escaneos de ZAP y la inferencia con Ollama tampoco corren en el
CI: uno es lento y el otro necesita GPU. Siguen siendo manuales.

### Correr las mismas verificaciones en local

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest tests/ -v
docker compose exec api python scripts/verificar_bd.py
```

`verificar_bd.py` espera los 40 hallazgos del seed. Si tu base tiene otros
datos, recárgala antes con `docker compose exec api python scripts/seed.py --reset`.

Los tests de ingesta (`tests/test_ingesta.py`) se saltan si no hay una base
PostgreSQL disponible, y vacían las tablas antes de cada prueba: no los corras
contra una base con datos que quieras conservar.

---

## Convenciones de trabajo

**Ramas:** `persona/tema`. Por ejemplo `luciano/backend-base`, `joaquin/parser-zap`,
`felipe/lab-escaneos`.

**Commits:** formato `tipo: descripción` — `feat`, `fix`, `docs`, `test`, `lab`, `chore`

**Pull requests:** `main` está protegida. Todo cambio entra por PR, con los dos
checks del CI en verde y una aprobación de otro integrante. Nadie aprueba su
propio PR: la revisión también sirve para que los tres conozcan el código que
van a defender.

---

## Estado del proyecto

El plan parte el 7 de septiembre de 2026 y termina el 13 de diciembre, dentro del semestre. Originalmente eran 9 sprints de 2 semanas; el 15 de octubre se replanificó a 7 porque el plan original terminaba en enero, después del cierre del semestre.

- [x] **S1 · 7 sep – 20 sep** — Laboratorio, aislamiento de red, primer escaneo
- [x] **S2 · 21 sep – 4 oct** — Modelo de datos y migraciones
- [x] **S3 · 5 oct – 18 oct** — Parser, normalización y API de ingesta
- [ ] **S4 · 19 oct – 1 nov** — IA integrada a la API y enriquecimiento por lote *(módulo de IA ya adelantado)*
- [ ] **S5 · 2 nov – 15 nov** — Golden set completo y dashboard *(golden set inicial ya adelantado)*
- [ ] **S6 · 16 nov – 29 nov** — Validación humana, informe técnico y congelamiento (tercera entrega)
- [ ] **S7 · 30 nov – 13 dic** — Documentación, evidencias y defensa

El detalle de las 71 tareas, con su estado y responsable, está en la planilla de sprints.
