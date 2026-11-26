# Manual técnico

**SentinelAI** · Actualizado: 18-11-2026

Este manual explica cómo instalar, configurar, operar y mantener SentinelAI. Está escrito para alguien con conocimientos de Docker y de la línea de comandos que no participó en el desarrollo.

| Si necesitas | Ver |
|---|---|
| Instalar WSL2 y Docker Engine desde cero | `docs/guias/GUIA_INSTALACION.md` |
| Entender la arquitectura y las decisiones | `docs/diseno/DISENO.md` |
| La lista de endpoints | `README.md`, sección "Importar un escaneo real", y `http://localhost:8000/docs` |
| Ollama en un equipo separado | `docs/guias/ADDENDUM_OLLAMA_REMOTO.md` |

---

## 1. Requisitos

| Recurso | Mínimo | Comentario |
|---|---|---|
| Sistema | Windows 10/11 con WSL2 (Ubuntu), o Linux | Probado en Windows 11 con Ubuntu en WSL2 |
| Docker | Docker Engine con el complemento Compose | Docker Desktop también funciona, con las diferencias de red de la sección 3 |
| RAM | 16 GB | Ver "Presupuesto de memoria" en el `README.md` |
| Disco | 20 GB libres | Imágenes de Docker y el modelo de lenguaje (4,9 GB) |
| Modelo de lenguaje | Ollama con `llama3.1:8b-instruct-q4_K_M` | Con GPU de 8 GB responde en 1 a 2 s por hallazgo. Sin GPU funciona, pero mucho más lento. Es opcional: sin él, el sistema opera y los hallazgos quedan "sin enriquecer" |
| Navegador | Uno actual | Para el dashboard |

## 2. Instalación

```bash
git clone https://github.com/monkedevluxo/capstone.git
cd capstone
cp .env.ejemplo .env               # y ajusta OLLAMA_URL (sección 3)
docker compose up -d --build db api web
docker compose exec api alembic upgrade head
```

Comprobación:

```bash
docker compose ps                   # db, api y web en estado "healthy" o "running"
curl http://localhost:8000/health   # responde con "estado": "ok"
```

El dashboard queda en `http://localhost:3000`. Juice Shop se levanta con `docker compose up -d juiceshop` y **no** responde desde el navegador: vive en una red sin puertos publicados, a propósito.

## 3. Configuración

La configuración se lee de variables de entorno. Hay dos niveles:

**Archivo `.env` en la raíz del repositorio.** Lo lee Docker Compose. Se crea copiando `.env.ejemplo`.

| Variable | Valor por defecto | Para qué sirve |
|---|---|---|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Dirección de Ollama vista desde el contenedor de la API |
| `SQL_ECHO` | `false` | `true` imprime cada consulta SQL en los logs |

**Parámetros de la aplicación.** Tienen valores por defecto en `backend/app/config.py` y normalmente no se cambian. Para cambiarlos, se escriben en un archivo `backend/.env`, que la API lee al iniciar (tampoco se versiona).

| Variable | Valor por defecto | Para qué sirve |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1:8b-instruct-q4_K_M` | Modelo que se usa para enriquecer |
| `OLLAMA_TIMEOUT_S` | `120` | Tiempo límite por llamada al modelo, en segundos |
| `OLLAMA_KEEP_ALIVE` | `10m` | Cuánto tiempo Ollama mantiene el modelo cargado entre llamadas |
| `OLLAMA_SEED` | sin fijar | Fijarla solo para demostraciones reproducibles; oculta la variación real del modelo |
| `LAB_HOSTS` | `juiceshop,dvwa,webgoat` | Equipos del laboratorio. La API rechaza reportes de cualquier otro |

Las variables que define `docker-compose.yml` para cada servicio tienen prioridad sobre ambos archivos:

| Variable | Servicio | Valor |
|---|---|---|
| `DATABASE_URL` | `api` | Conexión a PostgreSQL dentro de la red `lab_datos` |
| `API_URL` | `web` | `http://api:8000`. La lee solo el servidor del dashboard, nunca el navegador |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `db` | Credenciales de la base local. El puerto solo se publica en `127.0.0.1` |

**Dónde está Ollama.** Es lo único que cambia entre equipos:

| Situación | `OLLAMA_URL` |
|---|---|
| Docker Desktop, Ollama en el mismo equipo | `http://host.docker.internal:11434` |
| Docker Engine en WSL2, Ollama en Windows | `http://<ip>:11434`, con la IP que entrega `ip route show \| grep default \| awk '{print $3}'`. Cambia al reiniciar WSL |
| Ollama en otro equipo | `http://<ip-del-equipo>:11434`. Ese equipo debe tener `OLLAMA_HOST=0.0.0.0:11434` y el puerto 11434 abierto solo a la red de confianza |

Después de cambiar el `.env`: `docker compose up -d api`.

## 4. Operación

### Flujo normal

| Paso | Cómo |
|---|---|
| 1. Escanear | `./lab/escanear.sh`, o los comandos de ZAP del `README.md`. El reporte queda en `lab/salidas/` |
| 2. Importar | Dashboard, pantalla **Inicio**: arrastrar el JSON. O `POST /scans/import` |
| 3. Enriquecer | Dashboard, botón **Enriquecer pendientes**. O `POST /scans/{id}/enrich` |
| 4. Revisar | Dashboard, pantalla **Hallazgos**: filtros y "Revisar primero" |
| 5. Decidir | Detalle del hallazgo, sección **Tu decisión** *(pull request #28)* |
| 6. Informe | En el dashboard, módulo Informe → Exportar informe (PDF, XLSX o CSV). Desde la terminal: `docker compose exec -T api python scripts/informe.py > informe.html` |

### Servicios

```bash
docker compose up -d db api web        # levantar la plataforma
docker compose stop                     # detener sin borrar datos
docker compose logs -f api              # ver los logs de un servicio
docker compose restart web              # reiniciar un servicio
```

**Nunca** usar `docker compose down -v` ni `docker volume prune` sobre una base con datos que importen: borran el volumen de PostgreSQL.

## 5. Respaldo y restauración

Respaldo de la base, fuera del repositorio:

```bash
mkdir -p ~/sentinelai-respaldos
docker compose exec -T db pg_dump -U sentinel -Fc sentinelai \
  > ~/sentinelai-respaldos/sentinelai_$(date +%Y%m%d-%H%M).dump

# Comprobar que el respaldo se puede leer
docker compose exec -T db pg_restore --list < ~/sentinelai-respaldos/<archivo>.dump | head
```

Restauración, que **reemplaza** el contenido actual de la base:

```bash
docker compose stop api web
docker compose exec -T db pg_restore -U sentinel -d sentinelai --clean --if-exists \
  < ~/sentinelai-respaldos/<archivo>.dump
docker compose start api web
```

Se hace un respaldo antes de cada migración de la base de la demostración y antes de presentar.

## 6. Actualización

Después de traer cambios del repositorio:

```bash
git pull
docker compose exec api alembic upgrade head       # si hay migraciones nuevas
docker compose up -d --build -V web                # si cambiaron las dependencias del dashboard
docker compose up -d --build api                   # si cambió backend/requirements.txt
```

El código de la API y del dashboard está montado en vivo: los cambios de código se aplican solos, sin reconstruir.

## 7. Pruebas

| Qué | Comando | Base de datos |
|---|---|---|
| Pruebas unitarias | `cd backend && python -m pytest tests/ -v` | No necesita |
| Pruebas de integración | Las mismas, con PostgreSQL disponible | `sentinelai_test`; se saltan si no hay base |
| Extremo a extremo | `./lab/e2e.sh` | `sentinelai_test`, con una API aparte en el puerto 8001 |
| Dashboard | `cd frontend && bun --bun run lint && bun --bun run typecheck` | No necesita |

Las pruebas **nunca** se corren contra la base de la demostración (`sentinelai`).

## 8. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| El dashboard dice "No se pudo conectar con la API" | La API no está arriba, o el dashboard corre fuera de Docker | `docker compose up -d api`. Si el dashboard corre con `bun dev` fuera de Docker, definir `API_URL=http://localhost:8000` antes de iniciarlo |
| "Ollama no está disponible" al enriquecer (503) | Ollama apagado o `OLLAMA_URL` incorrecta | Probar `curl <OLLAMA_URL>/api/tags` desde WSL. Con Docker Engine, revisar la IP del host (cambia al reiniciar WSL) |
| Al importar: "ya estaba importado" (409) | Ese reporte ya está en la base | Es el comportamiento esperado: un reporte no se importa dos veces |
| Al importar: objetivo fuera del laboratorio (403) | El reporte apunta a un equipo que no está en `LAB_HOSTS` | Solo se importan resultados del laboratorio |
| El dashboard abre, pero los botones no responden | Se abrió con una dirección que el servidor de desarrollo no reconoce | Abrir `http://localhost:3000` |
| El dashboard deja de recargar al guardar | Se compiló el dashboard en la misma carpeta mientras el contenedor corría | `docker compose restart web`. Compilar siempre en otra copia del repositorio |
| ZAP no puede escribir el reporte | `lab/salidas/` pertenece a `root` | `sudo chown -R $USER:$USER lab/salidas` |
| Todo va muy lento | El repositorio está en `/mnt/c/` | Clonarlo dentro de WSL, en `~/` |

## 9. Seguridad operacional

- Todos los puertos se publican solo en `127.0.0.1`. No cambiarlo a `0.0.0.0`.
- La red `lab_interna` debe seguir con `internal: true`. Se comprueba con el ping de la sección "Verificar el aislamiento de red" del `README.md`.
- Las credenciales de PostgreSQL son de desarrollo local. Si el sistema se despliega en una red compartida, hay que cambiarlas, agregar autenticación al dashboard y no exponer la API.
- Ollama en otro equipo: abrir el puerto 11434 solo a la red de confianza, nunca a internet.
