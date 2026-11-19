# Cómo trabajamos en SentinelAI

Guía corta para cualquier cambio al repo. Si algo de aquí no calza con lo que
hacemos en la práctica, se corrige aquí, por PR como todo lo demás.

## Ramas

- Formato `persona/tema`, siempre desde `main` actualizado:
  `luciano/enriquecimiento`, `joaquin/tabla-cwe-owasp`, `felipe/escaneo-autenticado`.
- Una rama por tarea o grupo de tareas relacionadas. Los ID de la planilla
  (`T-0xx`) van en la descripción del PR, y si se puede también en el título.
- Si tu rama depende de otra que aún no se mergea, dilo en el PR.

## Commits

Formato `tipo: descripción`, en español, en presente o imperativo, sin punto final.

| Tipo | Para qué |
|---|---|
| `feat` | algo nuevo que hace el sistema |
| `fix` | corrige un comportamiento |
| `docs` | README, guías, diseño, evidencias |
| `test` | pruebas, sin cambiar el comportamiento |
| `lab` | laboratorio: escaneos, scripts de ZAP, fixtures |
| `chore` | mantenimiento: dependencias, configuración, limpieza |

Ejemplos reales del repo:

```
feat: enriquecimiento con IA desde la API (T-032, T-035)
fix: el lote cortado por Ollama dice "Enriquecimiento detenido"
docs: el README explica el estado duplicado y el ciclo de vida de las decisiones
lab: agregar modo ajax-auth con sesion iniciada al escaner
```

Un commit, un cambio que se entienda solo. Si el mensaje necesita un "y además",
probablemente son dos commits.

## Pull requests

- `main` está protegida: todo entra por PR, nadie hace push directo.
- Usa la plantilla (se carga sola al abrir el PR): qué hace, tareas, cómo se probó y checklist.
- Checks obligatorios: **Tests** y **Migraciones y restricciones**. El job
  **Frontend** (lint, tipos y build) también corre, pero todavía no es obligatorio:
  si falla, arréglalo igual.
- Hace falta **1 aprobación de otro integrante**. Nadie aprueba su propio PR: la
  revisión también sirve para que los tres conozcan el código que van a defender.
- El CI corre en PRs hacia `main` (y en cada push a `main`). Si cambias la base de
  un PR a `main` después de abrirlo, los checks no se disparan solos: sube un
  commit nuevo para que corran.

## Probar en local

Corre lo mismo que el CI antes de abrir el PR: ver
[Correr las mismas verificaciones en local](README.md#correr-las-mismas-verificaciones-en-local).

Los tests que usan PostgreSQL **vacían las tablas**. Córrelos siempre contra
`sentinelai_test`, nunca contra la base de la demo:

```bash
DATABASE_URL=postgresql+psycopg://sentinel:sentinel_local@localhost:5432/sentinelai_test python -m pytest tests/
```

## Base de datos

- `sentinelai` es la base de la **demo**: sus datos (escaneos, enriquecimientos de
  Ollama real, validaciones del golden set) cuestan rehacerlos. No escribas datos de prueba
  ahí, y no uses `docker compose down -v` ni `docker volume prune`.
- `sentinelai_test` es la de **pruebas**: se puede vaciar cuando quieras.
- El esquema cambia solo con migraciones de Alembic. Si tocas `models.py`, genera la
  migración (`alembic revision --autogenerate -m "..."`), revísala a mano y verifica
  que `alembic check` diga "No new upgrade operations detected". El CI lo exige.
- Antes de migrar la base de la demo, respáldala fuera del repo y comprueba el respaldo:

  ```bash
  docker compose exec -T db pg_dump -U sentinel -Fc sentinelai > ~/sentinelai-respaldos/sentinelai_$(date +%Y%m%d-%H%M).dump
  docker compose exec -T db pg_restore --list < ~/sentinelai-respaldos/sentinelai_<fecha-hora>.dump | head
  ```

## Ética

Solo se escanean objetivos del laboratorio propio, en la red aislada `lab_interna`.
La API y la base lo hacen cumplir, pero la responsabilidad es nuestra: ver
[Marco ético y legal](README.md#marco-ético-y-legal) (Ley 21.459).

## Secretos

Nada de secretos en el repo: ni tokens, ni contraseñas reales, ni `.env` con datos
propios. El token de GitHub (PAT) va en el credential helper de git, no en archivos
ni en la URL del remoto. Las credenciales de `docker-compose.yml` son de bases
locales desechables, no secretos.
