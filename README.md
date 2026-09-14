# SentinelAI

**Hallazgos de seguridad web priorizados con IA local**

Proyecto de Título · Capstone · Duoc UC · Grupo 3

---

## Qué es

Una plataforma web que centraliza los resultados de herramientas de análisis de seguridad ejecutadas sobre una aplicación deliberadamente vulnerable en un laboratorio aislado. Normaliza los hallazgos, los enriquece con un modelo de lenguaje ejecutado localmente y los presenta priorizados.

El flujo es: **escaneo → normalización → enriquecimiento con IA → validación humana → informe**.

### Qué hace la IA, y qué no

El modelo corre localmente con Ollama e **interpreta evidencia ya recolectada**. No escanea, no ataca y no descubre vulnerabilidades por sí mismo. Su trabajo es:

- **Explicar** el hallazgo técnico en lenguaje comprensible
- **Clasificar** según OWASP Top 10 y sugerir una prioridad, con nivel de confianza
- **Recomendar** una medida de remediación concreta

La validación final es siempre humana y queda registrada en la base de datos.

---

## Marco ético y legal

Las pruebas se ejecutan **únicamente** sobre aplicaciones vulnerables desplegadas en local, en una red sin exposición externa. Nunca se opera sobre infraestructura de terceros no autorizada.

La red del laboratorio usa `internal: true` en Docker, lo que significa que el contenedor objetivo **no tiene ruta de salida a internet**. No es una convención del equipo: es una restricción de infraestructura, verificable con los comandos de la sección de verificación.

La Ley 21.459 sobre delitos informáticos delimita el alcance del proyecto y justifica el uso exclusivo de entornos autorizados.

---

## Estructura del repositorio

```
capstone/
├── backend/              API FastAPI, modelos de datos, parser de hallazgos
├── frontend/             Dashboard en Next.js
├── lab/
│   ├── fixtures/         Escaneos congelados y versionados (insumo de desarrollo)
│   └── salidas/          Resultados de escaneos en curso (no se versiona)
├── docs/
│   ├── diseno/           Esquema del hallazgo, modelo de datos, decisiones técnicas
│   ├── institucional/    Entregables formales que solicita Duoc UC
│   ├── guias/            Montaje del laboratorio, uso de Docker
│   └── evidencias/       Capturas, logs y planillas de validación
├── docker-compose.yml
└── README.md
```

### Por qué `lab/fixtures/` sí se versiona

Un escaneo completo demora unos 9 minutos. Los fixtures son resultados reales congelados que permiten desarrollar y probar el parser en segundos, sin levantar el laboratorio ni re-escanear. Es lo que hace reproducible el desarrollo del pipeline.

`lab/salidas/` no se versiona porque cambia en cada ejecución.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| Backend | Python · FastAPI |
| Base de datos | PostgreSQL 16 |
| IA | Ollama (modelo local) |
| Frontend | Next.js · React |
| Laboratorio | Docker Compose |
| Escáner | OWASP ZAP |
| Objetivo | OWASP Juice Shop |

Nikto y OpenVAS quedan como herramientas de apoyo opcionales. DVWA y WebGoat, como objetivos secundarios, solo si el flujo principal está estable.

---

## Requisitos

- Docker Engine o Docker Desktop
- Git
- **En Windows:** WSL2. Se recomienda Docker Engine nativo dentro de WSL en lugar de Docker Desktop (ver `docs/guias/`)
- Ollama, en el equipo que actúe como nodo de inferencia

<!-- TODO: fijar versiones mínimas una vez estabilizado el entorno -->

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
```

Los resultados quedan en `lab/salidas/`.

**Si aparece `Permission denied` al escribir el JSON:** Docker creó `lab/salidas/` como root. Se corrige con `sudo chown -R $USER:$USER lab/salidas`.

<!-- TODO: agregar el levantamiento del backend cuando exista el Dockerfile (S3) -->
<!-- TODO: agregar el levantamiento del frontend (S7) -->
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
| Esquema del hallazgo normalizado | `docs/diseno/ESQUEMA_HALLAZGO.md` |
| Modelo de datos (DER y tablas) | `docs/diseno/MODELO_DATOS.md` |
| Montaje del laboratorio | `docs/guias/GUIA_MONTAJE_LABORATORIO.md` |
| Introducción a Docker | `docs/guias/DOCKER_BASICO.md` |
| Planilla de sprints | `docs/SentinelAI_Plan_Sprints.xlsx` |

---

## Equipo

| Integrante | Rol |
|---|---|
| Felipe Cayún | Laboratorio y Validación* |
| Joaquín Herrera | Arquitectura, IA y Parser* |
| Luciano Zambrano | Backend, Datos, Dashboard* |

*Roles por confirmar

**Docente:** Aníbal Sotelo

---

## Convenciones de trabajo

<!-- TODO: acordar en reunión de equipo -->

**Ramas:** <!-- por persona (felipe/...) o por tema (backend/parser)? -->

**Commits:** formato `tipo: descripción` — `feat`, `fix`, `docs`, `chore`, `lab`

**Pull requests:** `main` solo se modifica por PR, con al menos un revisor.

---

## Estado del proyecto

Proyecto de 18 semanas dividido en 9 sprints de 2 semanas.

- [x] **S1 · Semanas 1-2** — Laboratorio, aislamiento de red, primer escaneo
- [ ] **S2 · Semanas 3-4** — Modelo de datos y migraciones
- [ ] **S3 · Semanas 5-6** — Parser, normalización y API de ingesta
- [ ] **S4 · Semanas 7-8** — Integración con Ollama
- [ ] **S5 · Semanas 9-10** — Enriquecimiento asíncrono y trazabilidad
- [ ] **S6 · Semanas 11-12** — Golden set y métricas de calidad
- [ ] **S7 · Semanas 13-14** — Dashboard
- [ ] **S8 · Semanas 15-16** — Validación humana e informe
- [ ] **S9 · Semanas 17-18** — Documentación y defensa

El detalle de las 71 tareas está en la planilla de sprints.
