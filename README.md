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

## Arquitectura de la solución

SentinelAI son cinco servicios en Docker Compose, repartidos en dos redes que no se comunican entre sí, más el modelo de lenguaje, que corre fuera de Docker.

```mermaid
flowchart LR
    persona(["Persona<br/>navegador"])

    subgraph interna["Red lab_interna · sin salida a internet"]
        zap["OWASP ZAP<br/>escáner"]
        juice["OWASP Juice Shop<br/>objetivo vulnerable"]
        zap -->|escanea| juice
    end

    archivos[("lab/salidas<br/>reportes JSON")]

    subgraph datos["Red lab_datos"]
        web["Dashboard<br/>Next.js"]
        api["API<br/>FastAPI"]
        db[("PostgreSQL 16")]
        web -->|"HTTP interno"| api
        api -->|SQL| db
    end

    ollama["Ollama · Llama 3.1 8B<br/>equipo local con GPU"]

    zap -->|"escribe el reporte"| archivos
    persona -->|"sube el reporte<br/>127.0.0.1:3000"| web
    archivos -.->|"la persona lo elige"| persona
    api -->|"pide la sugerencia"| ollama
```

| Componente | Responsabilidad | Red |
|---|---|---|
| **Juice Shop** | Aplicación deliberadamente vulnerable: es el único objetivo de los escaneos | `lab_interna` |
| **OWASP ZAP** | Escanea el objetivo y escribe el reporte JSON en `lab/salidas/` | `lab_interna` |
| **API (FastAPI)** | Importa y normaliza los reportes, deduplica, consulta al modelo, registra las decisiones y genera el informe | `lab_datos` |
| **PostgreSQL** | Guarda objetivos, escaneos, hallazgos con su evidencia original, sugerencias de la IA y validaciones | `lab_datos` |
| **Dashboard (Next.js)** | Muestra los hallazgos y recibe las decisiones. Es lo único que usa la persona | `lab_datos` |
| **Ollama** | Ejecuta el modelo de lenguaje en un equipo propio. La API lo alcanza por la dirección configurada en `OLLAMA_URL` | Fuera de Docker |

**Cómo se comunican:**

- **El escáner y la plataforma no comparten red.** Lo único que pasa de un lado al otro es un archivo: ZAP escribe el reporte y una persona lo sube desde el dashboard. La red del objetivo es `internal: true`, sin ruta de salida.
- **El navegador solo habla con el dashboard.** El servidor de Next llama a la API dentro de `lab_datos`; la API no queda expuesta al navegador y no necesita CORS.
- **Todos los puertos se publican en `127.0.0.1`.** Nada queda accesible desde otros equipos de la red.
- **El modelo es opcional para operar.** Si Ollama no responde, la API contesta 503 y los hallazgos quedan "sin enriquecer"; el resto del flujo sigue funcionando.

El detalle del modelo de datos está en `docs/diseno/MODELO_DATOS.md` y el del hallazgo normalizado en `docs/diseno/ESQUEMA_HALLAZGO.md`.

---

## Estructura del repositorio

```
capstone/
├── .github/              CI (workflows/) y plantilla de PR
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
│   │   ├── metricas_golden_set.py  Métricas del modelo contra el golden set
│   │   └── intercambio.py          Intercambio entre equipos y acuerdo entre revisores
│   └── tests/                Parser, esquema, módulo de IA e ingesta
├── frontend/             Dashboard en Next.js (desde el S5)
├── api/                  Colección de Bruno para probar la API
├── lab/
│   ├── fixtures/         Escaneos congelados y versionados (insumo de desarrollo)
│   └── salidas/          Resultados de escaneos en curso (no se versiona)
├── docs/
│   ├── diseno/           Esquema del hallazgo, modelo de datos, IA y decisiones técnicas
│   ├── institucional/    Entregables formales que solicita Duoc UC (fase 1 y fase 2)
│   ├── guias/            Instalación, Docker, Ollama
│   └── evidencias/       Logs, mediciones, golden set y planillas de validación
├── docker-compose.yml
├── CONTRIBUTING.md
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
| Frontend | Next.js 16 (App Router) · React · TypeScript · Tailwind CSS · shadcn/ui · bun |
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
| `GET /scans` | Lista los escaneos importados, del más reciente al más antiguo, con su objetivo |
| `GET /findings` | Lista hallazgos con filtros por severidad, estado, escaneo, objetivo, categoría OWASP del modelo (`owasp`) o de la tabla CWE (`owasp_ref`), enriquecimiento, `revisar` y texto. Orden: severidad, después los marcados para revisar, después ocurrencias |
| `GET /findings/resumen` | Total y conteos por severidad, por estado, para revisar, sin enriquecer y con el enriquecimiento fallido (`fallidos`), con los mismos filtros que `GET /findings`. Con `?scan_id=` da las métricas de un escaneo |
| `GET /findings/{id}` | Detalle de un hallazgo, con la evidencia original, la capa de IA y las validaciones por separado |
| `POST /findings/{id}/enrich` | Enriquece un hallazgo con el modelo local y guarda el resultado con modelo, versión y hash del prompt. 503 si Ollama no responde |
| `POST /scans/{id}/enrich` | Enriquece uno por uno los hallazgos de un escaneo; por defecto se salta los que ya tienen un enriquecimiento válido |
| `GET /informe` | Informe técnico de un objetivo en HTML autocontenido (`?objetivo=<base_url>`; sin él, el objetivo con más hallazgos). 404 si no hay escaneos o el objetivo no existe |
| `GET /informe.xlsx` | El mismo informe como libro de Excel: hojas Resumen, Hallazgos (con filtros) y Escaneos. Mismos parámetros y 404 que `GET /informe` |
| `GET /informe.csv` | El mismo informe como CSV, un hallazgo por fila, UTF-8 con BOM. Mismos parámetros y 404 que `GET /informe` |
| `GET /health` | Comprueba que la API responde y que la base contesta una consulta real. 503 si la base no responde |
| `GET /stats` | Conteos de objetivos, escaneos y hallazgos por severidad, para confirmar que una carga quedó bien |
| `POST /findings/{id}/validaciones` | Registra la decisión de una persona (confirmado, falso positivo, riesgo aceptado, duplicado o requiere segunda opinión) y actualiza el estado del hallazgo en la misma transacción: cada decisión deja su estado homónimo, `duplicado` incluido (estado propio desde la migración `7c2e9d41b3a5`), y "requiere segunda opinión" lo deja `en_triage` (ciclo de vida en `docs/diseno/ESQUEMA_HALLAZGO.md`, sección 7). Guarda qué sugerencia del modelo se juzgó y las banderas del golden set. 409 si la sugerencia cambió mientras se decidía |

Cada hallazgo del listado y del detalle trae `referencia`: la categoría OWASP según la tabla CWE → OWASP 2025, la prioridad por regla y la marca `requiere_revision` de la opción mixta. Se calcula al consultar; no se guarda.

Documentación interactiva de la API: `http://localhost:8000/docs`

### Levantar el dashboard

```bash
docker compose up -d web
```

Queda en `http://localhost:3000` y lista los hallazgos de `GET /findings`. El
servidor de Next lee la API en `http://api:8000` dentro de la red `lab_datos`;
el navegador nunca habla con la API directo, por eso no hay CORS. El servicio
`web` no está en `lab_interna`: no alcanza al objetivo.

El código de `frontend/` está montado en vivo y Next recarga al guardar. Si
cambian las dependencias (`package.json` o `bun.lock`), reconstruye y renueva
el volumen de `node_modules`:

```bash
docker compose up -d --build -V web
```

Para trabajar fuera del contenedor hace falta [bun](https://bun.sh). bun solo
instala y corre scripts; en el contenedor Next se ejecuta con Node:

```bash
cd frontend
bun install
bun --bun run lint        # --bun: usa el runtime de bun si no tienes Node
bun --bun run typecheck   # tsc de TypeScript 7
```

Las fuentes (IBM Plex) vienen empaquetadas, no de Google Fonts: el dashboard
compila y se ve igual sin internet.

### Probar la API con Bruno

`api/` es una colección de [Bruno](https://www.usebruno.com) en texto plano (`.bru`):
cada request trae asserts sobre el código HTTP y la forma del cuerpo. Se abre con la
app de Bruno (*Open Collection* → `api/`) o se corre por consola, sin instalar nada:

```bash
cd api
bunx @usebruno/cli@4.3.0 run "1 · Consulta" --env local     # solo GET: segura contra la demo
```

| Carpeta | Qué hace | Contra qué |
|---|---|---|
| `1 · Consulta` | health, escaneos, listado con filtros, resumen, detalle, 404 y 422 | cualquier API, incluida la demo (`local`, :8000) |
| `2 · Escritura (solo entorno prueba)` | importa un fixture (201, 409, 403, 422), enriquece, valida (201, 409, 422) y enriquece un lote | **solo** el entorno `prueba` (:8001), con `sentinelai_test` vacía |

La carpeta de escritura se niega a correr (falla en el *pre-request*, sin enviar
nada) si el entorno no es `prueba` o si la URL es la de la demo. Para usarla,
levanta una API apuntada a la base de pruebas y, para los enrich, un Ollama
(`OLLAMA_URL`, real o uno falso):

```bash
docker compose exec -T db psql -U sentinel -d sentinelai_test -c \
  "TRUNCATE validations, ai_enrichments, finding_observations, finding_instances, findings, scans, targets CASCADE"
docker compose run -d --rm --name sentinel-api-prueba -p 127.0.0.1:8001:8000 \
  -e DATABASE_URL=postgresql+psycopg://sentinel:sentinel_local@db:5432/sentinelai_test api
cd api && bunx @usebruno/cli@4.3.0 run "2 · Escritura (solo entorno prueba)" "1 · Consulta" --env prueba
docker stop sentinel-api-prueba
```

### Anotar el golden set entre varios equipos

Cada integrante tiene su propia base y los ids no coinciden entre bases.
`backend/scripts/intercambio.py` identifica cada hallazgo por el objetivo
(`base_url`) y su `dedupe_key`, y conserva el uuid de cada enriquecimiento y
validación. Importar es idempotente: lo que ya está se omite, un uuid con
contenido distinto se reporta como conflicto y no se pisa, y nunca se crean
hallazgos. Todos deben tener importados los mismos fixtures.

```bash
# 1. Joaquín enriquece con Ollama real y exporta
docker compose exec -T api python scripts/intercambio.py exportar --que enriquecimientos > enriquecimientos_joaquin.json

# 2. Cada uno los importa (primero --simular para ver el reporte sin guardar)
docker compose exec -T api python scripts/intercambio.py importar --simular < enriquecimientos_joaquin.json
docker compose exec -T api python scripts/intercambio.py importar < enriquecimientos_joaquin.json

# 3. Cada uno anota en su dashboard y exporta sus validaciones
docker compose exec -T api python scripts/intercambio.py exportar --que validaciones --revisor "Felipe" > validaciones_felipe.json

# 4. Luciano importa todas y calcula las métricas
docker compose exec -T api python scripts/intercambio.py importar < validaciones_felipe.json
docker compose exec -T api python scripts/intercambio.py metricas          # o --json
```

- Si el enriquecimiento importado es vigente, el local pasa a histórico. La
  excepción es la misma regla del enriquecimiento con Ollama: uno fallido no
  desplaza a uno válido, entra como histórico y el reporte lo avisa.
- Una validación cuyo enriquecimiento no está en tu base se omite ("importa
  primero los enriquecimientos de …"). Al reimportarla después, entra.
- El estado de cada hallazgo lo vuelve a fijar su validación más reciente.
- Si el archivo no es válido no se importa nada (código de salida 2).
- Una validación con fecha más de 10 minutos en el futuro (respecto de la base)
  se omite como conflicto: revisa el reloj de la máquina que la exportó. Con
  menos desfase, o en un enriquecimiento, se importa con un aviso.
- Las métricas agrupan a cada revisor por su nombre sin importar mayúsculas ni
  espacios ("felipe  cayún" = "Felipe Cayún"), y cuentan su última respuesta por hallazgo y
  sugerencia, sin los "no sé". El κ va con su n y el % de acuerdo simple: con
  n chico, el κ solo no dice nada.

### Variables de entorno

La configuración se lee de variables de entorno; no hay credenciales en el código. Antes del primer arranque:

```bash
cp .env.ejemplo .env
```

| Variable | Para qué sirve |
|---|---|
| `OLLAMA_URL` | Dirección de Ollama vista desde el contenedor de la API. Es lo único que normalmente hay que ajustar |
| `SQL_ECHO` | `true` imprime cada consulta SQL en los logs de la API |

El `.env` no se versiona. El resto de los parámetros (modelo, tiempos límite, equipos del laboratorio) y cómo cambiarlos están en `docs/guias/MANUAL_TECNICO.md`, sección "Configuración".

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
| Visión del producto | `docs/producto/PRODUCT_VISION.md` |
| Definición de terminado | `docs/producto/DEFINITION_OF_DONE.md` |
| Product Backlog (historias de usuario) | `docs/producto/PRODUCT_BACKLOG.md` |
| Requisitos no funcionales | `docs/producto/REQUISITOS_NO_FUNCIONALES.md` |
| Innovación | `docs/producto/INNOVACION.md` |
| Retrospectivas por sprint | `docs/producto/RETROSPECTIVAS.md` |
| **Documento de diseño** (arquitectura, UML, decisiones) | `docs/diseno/DISENO.md` |
| **Manual técnico** (configuración, operación, respaldo) | `docs/guias/MANUAL_TECNICO.md` |
| Plan de pruebas y resultados | `docs/evidencias/plan_pruebas.md` |
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

## Metodología de trabajo

El equipo trabaja con una **metodología ágil e incremental basada en Scrum**, adaptada a un equipo de tres personas con horarios distintos.

| Elemento | Cómo lo aplicamos |
|---|---|
| **Sprints** | 7 sprints de 2 semanas, del 7 de septiembre al 13 de diciembre de 2026. Cada uno tiene un objetivo y un hito verificable |
| **Backlog** | 71 tareas en `docs/SentinelAI_Plan_Sprints.xlsx`, cada una con criterio de aceptación, responsable, estimación, dependencias y estado |
| **Definición de terminado** | `docs/producto/DEFINITION_OF_DONE.md`. Una tarea está terminada cuando su cambio está integrado en `main` |
| **Revisión** | Todo cambio entra por pull request, con la integración continua en verde y la aprobación de otro integrante |
| **Coordinación** | Asíncrona, por mensajería y en los propios pull requests, más la clase presencial de los viernes |
| **Riesgos** | Registro con probabilidad, impacto, mitigación y señal de alerta temprana, en la misma planilla |

Sobre esa base aplicamos cuatro prácticas de ingeniería:

- **Contrato de datos primero.** El esquema del hallazgo normalizado se definió antes de programar, para que cada integrante avanzara en paralelo.
- **Pruebas como especificación.** El comportamiento esperado se escribe como pruebas automáticas, que corren en cada pull request.
- **Fixtures versionados.** Los resultados reales de los escaneos se guardan en el repositorio, para desarrollar sin repetir escaneos de hasta 40 minutos.
- **Decisiones con datos.** Las decisiones sobre la IA se toman a partir de mediciones contra el golden set y quedan documentadas.

El plan original era de 9 sprints. El 15 de octubre se replanificó a 7, porque terminaba después del cierre del semestre. La visión del producto está en `docs/producto/PRODUCT_VISION.md`.

---

## Integración continua

Cada PR hacia `main` corre automáticamente en GitHub Actions
(`.github/workflows/ci.yml`). Son tres jobs:

| Job | Qué comprueba |
|---|---|
| **Tests** | Los tests del parser de ZAP, del módulo de IA (sin depender de Ollama) y que `ejemplo_hallazgo.json` cumpla `finding.schema.json` |
| **Migraciones y restricciones** | Que la migración aplique, se revierta y se reaplique sobre un PostgreSQL limpio; que modelos y migraciones estén sincronizados (`alembic check`); que la base rechace lo que debe rechazar; y los tests de ingesta y consulta contra la base real |
| **Frontend** | Que el dashboard pase ESLint, el chequeo de tipos con TypeScript 7 y `next build` |

En total son 253 pruebas automatizadas, más las verificaciones de restricciones.

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

Los tests de ingesta, enriquecimiento, resumen y validaciones (`tests/test_ingesta.py`, `tests/test_enriquecimiento_api.py`, `tests/test_resumen_filtros_api.py`, `tests/test_validaciones_api.py`, `tests/test_intercambio.py`) se saltan si no hay una base
PostgreSQL disponible, y vacían las tablas antes de cada prueba: no los corras
contra una base con datos que quieras conservar.

---

## Convenciones de trabajo

Ramas `persona/tema` desde `main`, commits `tipo: descripción` (`feat`, `fix`, `docs`, `test`, `lab`, `chore`).
Todo entra por PR con los checks del CI en verde y la aprobación de otro integrante; nadie aprueba lo propio.
El detalle (plantilla de PR, bases de datos, migraciones y secretos) está en [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Estado del proyecto

El plan parte el 7 de septiembre de 2026 y termina el 13 de diciembre, dentro del semestre. Originalmente eran 9 sprints de 2 semanas; el 15 de octubre se replanificó a 7 porque el plan original terminaba en enero, después del cierre del semestre.

- [x] **S1 · 7 sep – 20 sep** — Laboratorio, aislamiento de red, primer escaneo
- [x] **S2 · 21 sep – 4 oct** — Modelo de datos y migraciones
- [x] **S3 · 5 oct – 18 oct** — Parser, normalización y API de ingesta
- [x] **S4 · 19 oct – 1 nov** — IA integrada a la API y enriquecimiento por lote
- [x] **S5 · 2 nov – 15 nov** — Golden set completo y dashboard *(el golden set de 17 hallazgos con dos revisores se cerró el 20-11, con una ronda de calibración)*
- [ ] **S6 · 16 nov – 29 nov** — Validación humana, informe técnico y congelamiento (tercera entrega) *(validación humana, informe técnico con el botón Informe y golden set hechos; falta el congelamiento del código del 29-11)*
- [ ] **S7 · 30 nov – 13 dic** — Documentación, evidencias y defensa

El detalle de las 71 tareas, con su estado y responsable, está en la planilla de sprints.
