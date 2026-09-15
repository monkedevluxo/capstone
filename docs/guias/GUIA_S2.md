# Sprint 2 · Modelo de datos y backend base

**Tareas T-010, T-012, T-013, T-015, T-016 · rol Backend, Datos y Dashboard**

---

## Dónde va cada archivo

```
capstone/
├── docker-compose.yml          ← reemplaza el actual (agrega el servicio api)
└── backend/
    ├── Dockerfile
    ├── .dockerignore
    ├── requirements.txt
    ├── alembic.ini
    ├── app/
    │   ├── __init__.py         ← archivo vacío, necesario
    │   ├── config.py
    │   ├── db.py
    │   ├── models.py           ← ya lo tenías, va acá
    │   ├── normalizacion.py    ← ya lo tenías, va acá
    │   └── main.py
    ├── migrations/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/           ← carpeta vacía, la llena Alembic
    └── scripts/
        └── seed.py
```

`migrations/versions/` debe existir aunque esté vacía. Como Git no versiona carpetas vacías:

```bash
touch backend/migrations/versions/.gitkeep
```

---

## Puesta en marcha

```bash
cd ~/sentinelai
git checkout -b luciano/backend-base

# 1. Levantar base y API
docker compose up -d db api
docker compose logs -f api        # Ctrl+C cuando diga "Application startup complete"

# 2. Generar la migración inicial
docker compose exec api alembic revision --autogenerate -m "esquema inicial"
```

**Revisa la migración generada antes de aplicarla.** Está en `backend/migrations/versions/`. Alembic no siempre acierta con lo específico de PostgreSQL:

```bash
cat backend/migrations/versions/*_esquema_inicial.py
```

Tres cosas que verificar:

1. **Los `CREATE TYPE` de los enums** aparecen antes de las tablas que los usan
2. **El índice parcial** `uq_enrichment_vigente` incluye su cláusula `postgresql_where`
3. **El `downgrade()`** elimina los tipos enum, no solo las tablas. Alembic suele olvidarlo y entonces `downgrade` + `upgrade` falla con "type already exists". Si falta, agrégalo a mano:

```python
def downgrade():
    # ... op.drop_table(...) generados por Alembic ...
    for tipo in ("herramienta", "severidad", "prioridad", "estado_hallazgo",
                 "estado_escaneo", "estado_ia", "categoria_owasp",
                 "decision_validacion"):
        op.execute(f"DROP TYPE IF EXISTS {tipo}")
```

Luego:

```bash
# 3. Aplicar
docker compose exec api alembic upgrade head

# 4. Cargar datos de prueba
docker compose exec api python scripts/seed.py --reset

# 5. Verificar
curl http://localhost:8000/health
curl http://localhost:8000/stats
```

`/stats` debe devolver 1 objetivo, 2 escaneos y unos 40 hallazgos repartidos por severidad.

Documentación interactiva de la API en `http://localhost:8000/docs`.

---

## Criterio de aceptación del sprint (T-013)

La prueba real es que funcione sobre una base vacía, no sobre la tuya que ya tiene datos:

```bash
docker compose down -v          # borra el volumen: base desde cero
docker compose up -d db api
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
curl http://localhost:8000/stats
```

Si eso funciona de corrido, T-013 está cumplida.

Prueba también la reversión, que casi nadie verifica y siempre falla:

```bash
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
```

---

## Sobre el seed: qué es y qué no es

**Genera hallazgos sintéticos, no parsea ZAP.** El parser es la tarea T-019 y corresponde al rol de Arquitectura e IA. Mezclarlos ahora te haría escribir el trabajo de Joaquín.

Lo que el seed te da es lo que necesitas para no depender de nadie:

- ~40 hallazgos repartidos en las cinco severidades
- Unos 70% con enriquecimiento de IA, y de esos ~10% en estado `failed`
- Unos 40% con validación humana registrada
- Todos los estados del ciclo de vida representados

Con eso puedes construir el dashboard completo del S7 sin esperar el parser ni volver a escanear.

El objetivo se llama **"OWASP Juice Shop (datos de prueba)"** y cada registro lleva `_nota: "REGISTRO SINTETICO"` en su `source_raw`. Es deliberado: en la semana 15, cuando estén armando el informe, nadie va a confundir estos números con resultados reales.

El seed usa semilla fija (`Random(42)`), así que dos ejecuciones producen exactamente los mismos datos.

---

## Detalles que conviene entender

**El healthcheck consulta la base.** Un `/health` que solo devuelve 200 sin tocar la base miente: la API puede estar viva con la base caída. El de acá ejecuta un `SELECT 1` y responde 503 si falla.

**Las credenciales no están en `alembic.ini`.** La URL se lee de `DATABASE_URL` en `migrations/env.py`, igual que la aplicación. Una sola fuente de verdad y nada versionado.

**`compare_type=True` en env.py.** Sin eso, cambiar un `String(100)` a `String(300)` no genera migración y la base queda desincronizada del código sin avisar.

**El contenedor corre como usuario sin privilegios (uid 1000).** Es lo que evita el `Permission denied` que te pasó con ZAP: los archivos que el contenedor escriba en volúmenes montados quedan a tu nombre, no de root.

**`pool_pre_ping=True`.** Descarta conexiones muertas antes de usarlas. Sin esto, cada reinicio del contenedor de Postgres te deja errores de conexión hasta que reinicias la API también.

---

## Qué falta para cerrar el sprint

- [ ] T-011 · DER en `docs/diseno/` (ya está en MODELO_DATOS.md)
- [ ] T-012 · Modelos SQLAlchemy — hecho
- [ ] T-013 · `alembic upgrade head` sobre base vacía
- [ ] T-015 · Índices — están en los modelos, verifica que aparezcan en la migración
- [ ] T-016 · Seed — hecho
- [ ] T-017 · Documentación del modelo — hecha
- [ ] Medir el listado con 500 hallazgos: `python scripts/seed.py --reset -n 130`

Ese último punto está en la planilla como criterio y conviene hacerlo ahora, no en la semana 14. Con 130 hallazgos (el máximo que permiten las combinaciones del seed) puedes cronometrar `/stats` y detectar si falta algún índice.

---

## Siguiente

Con esto cerrado, el S3 son los endpoints: `POST /scans/import` y `GET /findings` con filtros. Puedes escribirlos contra los datos del seed, sin esperar el parser de Joaquín, siempre que acuerden antes la firma de la interfaz: él entrega objetos conformes a `finding.schema.json`, tú los persistes.
