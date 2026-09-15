# Montar el laboratorio desde cero

**SentinelAI · Windows 11/10 · 16 GB RAM · sprint S1 (tareas T-003, T-005, T-006, T-007, T-008, T-010)**

Esta guía va de "tengo un notebook con Windows" a "tengo un JSON de ZAP en el disco y una medición real de cuánto demora el modelo". Ese es el objetivo del sprint 1 completo.

Tiempo estimado: una tarde para los pasos 1 a 6, otra para los pasos 7 a 9.

---

## Lo que hay que entender antes de empezar

**No van a hacer pentesting.** ZAP hace el trabajo ofensivo, solo hay que saber invocarlo. Juice Shop está construida para ser atacada: es material didáctico oficial de OWASP, con documentación que explica cada vulnerabilidad. Lo que ustedes construyen es un pipeline de datos.

**Docker reemplazó las máquinas virtuales.** No van a instalar ni administrar sistemas operativos. Van a escribir un archivo de texto que describe cinco contenedores y correr un comando. Un contenedor arranca en segundos, no en minutos, y se borra sin dejar rastro.

**El laboratorio tiene dos redes, y la separación es deliberada.** `lab_interna` no tiene salida a internet: ahí viven la aplicación vulnerable y el escáner. `lab_datos` tiene la base, el backend y el dashboard. Esa separación es la implementación concreta de lo que su propuesta promete sobre la Ley 21.459, y es demostrable con un comando.

---

## Paso 1 · WSL2

Docker en Windows funciona sobre WSL2 (una máquina Linux liviana integrada al sistema). Sin esto no hay nada.

Abran PowerShell **como administrador** y corran:

```powershell
wsl --install
```

Reinicien. Al volver, Windows termina de instalar Ubuntu y les pide crear un usuario y contraseña de Linux. Anótenla: no es la contraseña de Windows y la van a necesitar para `sudo`.

Verifiquen:

```powershell
wsl --status
wsl -l -v
```

Deben ver `Ubuntu` con `VERSION 2`. Si dice `VERSION 1`, corran `wsl --set-version Ubuntu 2`.

### Limitar la memoria de WSL2 (importante con 16 GB)

Por defecto WSL2 se reserva hasta la mitad de la RAM (8 GB). Como Ollama va a correr fuera de WSL, hay que dejarle espacio.

Creen el archivo `C:\Users\<su-usuario>\.wslconfig` con este contenido:

```ini
[wsl2]
memory=6GB
processors=4
swap=2GB
```

Aplíquenlo cerrando WSL por completo:

```powershell
wsl --shutdown
```

Sin este archivo, WSL y Ollama se pelean la memoria y el sistema empieza a usar disco como RAM. Eso convierte 8 segundos por hallazgo en 90.

---

## Paso 2 · Docker Desktop

Descárguenlo del sitio oficial de Docker e instálenlo. Durante la instalación, dejen marcada la opción de usar el backend WSL2.

Una vez instalado, abran Docker Desktop → **Settings → Resources → WSL Integration** y activen la integración con `Ubuntu`.

Verifiquen desde una terminal de Ubuntu (búsquenla en el menú inicio como "Ubuntu"):

```bash
docker --version
docker compose version
docker run --rm hello-world
```

Si el último comando imprime un mensaje de bienvenida, están listos.

---

## Paso 3 · La regla que más gente rompe

**Todo el proyecto vive dentro del sistema de archivos de Linux, no en `C:\`.**

```bash
cd ~
mkdir sentinelai
cd sentinelai
pwd    # debe decir /home/<usuario>/sentinelai
```

Si ponen el repositorio en `/mnt/c/Users/...`, cada lectura de archivo cruza la frontera entre Windows y Linux. Docker, npm y las recargas en caliente se vuelven entre 10 y 20 veces más lentos, y van a pasar semanas creyendo que su código es pesado cuando el problema es dónde está guardado.

Para editar con VS Code desde Windows sobre esos archivos, instalen la extensión **WSL** y abran la carpeta con:

```bash
code .
```

VS Code se conecta a Linux y trabaja allí directamente. Es la forma correcta.

---

## Paso 4 · Estructura del repositorio (T-003)

```bash
mkdir -p backend frontend lab/salidas lab/fixtures docs
git init
```

```
sentinelai/
├── backend/          # FastAPI, modelos, parser
├── frontend/         # Next.js
├── lab/
│   ├── salidas/      # donde ZAP escribe sus JSON
│   └── fixtures/     # JSON congelados para desarrollar sin re-escanear
├── docs/             # esquema, modelo de datos, esta guía
├── docker-compose.yml
└── .gitignore
```

En `.gitignore`:

```
lab/salidas/
__pycache__/
node_modules/
.env
*.pyc
```

`lab/salidas/` no se versiona porque cambia en cada escaneo. `lab/fixtures/` **sí se versiona**: son los JSON de referencia con los que van a desarrollar el parser sin levantar el laboratorio entero.

---

## Paso 5 · docker-compose.yml (T-005, T-010)

Creen `docker-compose.yml` en la raíz:

```yaml
services:
  juiceshop:
    image: bkimminich/juice-shop:latest
    container_name: sentinel-juiceshop
    networks: [lab_interna]
    restart: unless-stopped
    # Sin "ports": nadie fuera de lab_interna puede alcanzarlo.

  zap:
    image: zaproxy/zap-stable
    container_name: sentinel-zap
    networks: [lab_interna]
    volumes:
      - ./lab/salidas:/zap/wrk:rw
    profiles: ["scan"]
    # El perfil evita que arranque con "up": se invoca a demanda.

  db:
    image: postgres:16-alpine
    container_name: sentinel-db
    environment:
      POSTGRES_USER: sentinel
      POSTGRES_PASSWORD: sentinel_local
      POSTGRES_DB: sentinelai
    networks: [lab_datos]
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U sentinel"]
      interval: 5s
      retries: 10

  api:
    build: ./backend
    container_name: sentinel-api
    environment:
      DATABASE_URL: postgresql+psycopg://sentinel:sentinel_local@db:5432/sentinelai
      OLLAMA_URL: http://host.docker.internal:11434
    networks: [lab_datos]
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./lab/salidas:/data/salidas:ro
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
    extra_hosts:
      - "host.docker.internal:host-gateway"

networks:
  lab_interna:
    internal: true      # ← sin NAT hacia afuera. Esta línea es el aislamiento.
  lab_datos:

volumes:
  pgdata:
```

**Tres cosas que conviene entender de este archivo:**

`internal: true` es lo que impide que Juice Shop alcance internet. No es una convención ni una promesa: Docker no crea la ruta de salida. Es el respaldo técnico de su marco ético.

`127.0.0.1:5432:5432` publica Postgres solo hacia el propio equipo, no hacia la red del campus. Si escribieran `5432:5432` a secas, cualquiera en la misma WiFi podría conectarse.

`host.docker.internal` es cómo el contenedor `api` alcanza Ollama, que corre en Windows. La línea `extra_hosts` es la que hace que ese nombre resuelva.

**Antes de seguir, fijen las versiones.** Los tags `latest` cambian y su proyecto tiene que ser reproducible en enero. Levanten una vez, averigüen qué versión bajaron, y reemplacen `latest` por ese número:

```bash
docker compose up -d juiceshop
docker compose exec juiceshop cat package.json | grep '"version"'
```

Anoten también la versión de ZAP (paso 7) y déjenlas escritas en el README.

---

## Paso 6 · Levantar y demostrar el aislamiento (T-006)

```bash
docker compose up -d juiceshop db
docker compose ps
```

Ahora la prueba que convierte "está aislado" en evidencia. Lancen un contenedor auxiliar dentro de `lab_interna` y verifiquen que no sale:

```bash
docker run --rm --network sentinelai_lab_interna alpine \
  sh -c "ping -c 2 -W 2 8.8.8.8 || echo 'SIN SALIDA A INTERNET — correcto'"
```

Debe imprimir el mensaje de correcto. Comparen con la red normal:

```bash
docker run --rm alpine ping -c 2 8.8.8.8
```

Esta sí responde. **Guarden las dos capturas de pantalla**: son la evidencia de la tarea T-006 y el respaldo directo de lo que afirman en la diapositiva de marco ético.

Si el nombre de la red no coincide, búsquenlo con `docker network ls` (Docker le antepone el nombre de la carpeta).

Verifiquen también que Juice Shop responde desde adentro de la red:

```bash
docker run --rm --network sentinelai_lab_interna alpine \
  sh -c "apk add -q curl && curl -s -o /dev/null -w '%{http_code}\n' http://juiceshop:3000"
```

Debe devolver `200`.

---

## Paso 7 · Primer escaneo (T-007)

Empiecen con el escaneo rápido, solo para confirmar que la cañería funciona:

```bash
docker compose run --rm zap zap-baseline.py \
  -t http://juiceshop:3000 -J baseline.json -I
```

Tarda uno o dos minutos. El resultado queda en `lab/salidas/baseline.json`.

Reviven que el archivo tiene contenido:

```bash
python3 -c "import json; d=json.load(open('lab/salidas/baseline.json')); print(sum(len(s['alerts']) for s in d['site']), 'alertas')"
```

El baseline solo hace análisis pasivo y devuelve pocas alertas. Para tener material de verdad, corran el escaneo completo:

```bash
docker compose run --rm zap zap-full-scan.py \
  -t http://juiceshop:3000 -J full.json -I
```

**Este demora entre 20 y 60 minutos.** Déjenlo corriendo mientras hacen otra cosa. El resultado es el que van a usar como fixture durante todo el proyecto:

```bash
cp lab/salidas/full.json lab/fixtures/zap_juiceshop_full_v1.json
git add lab/fixtures/ && git commit -m "fixture: escaneo full de ZAP sobre Juice Shop"
```

Con ese archivo versionado pueden desarrollar el parser sin volver a escanear nunca. Es la diferencia entre iterar en segundos o en media hora.

---

## Paso 8 · Ollama en Windows (T-008)

**Ollama va instalado en Windows, no en un contenedor.** En un contenedor no accede a la GPU y pierde la poca aceleración que puedan tener.

Descárguenlo de `ollama.com` e instálenlo. Luego, **antes de usarlo**, configuren una variable de entorno de Windows para que acepte conexiones desde Docker:

1. Buscar "variables de entorno" en el menú inicio
2. Variables de usuario → Nueva
3. Nombre: `OLLAMA_HOST` · Valor: `0.0.0.0:11434`
4. Cerrar sesión de Windows y volver a entrar

Sin esto, Ollama escucha solo en `localhost` y el contenedor `api` no lo alcanza. Es el error más común de este montaje y da un mensaje de "conexión rechazada" que no explica nada.

Bajen un modelo. Con 16 GB, empiecen por uno de 7-8B cuantizado:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama run llama3.1:8b-instruct-q4_K_M "responde solo: ok"
```

Ocupa unos 5 GB en memoria mientras corre. Revisen el catálogo actual en `ollama.com/library` por si hay opciones mejores; los nombres cambian.

Verifiquen que Docker lo alcanza:

```bash
docker run --rm --add-host=host.docker.internal:host-gateway alpine \
  sh -c "apk add -q curl && curl -s http://host.docker.internal:11434/api/tags"
```

Si devuelve un JSON con la lista de modelos, la conexión funciona.

---

## Paso 9 · La medición que decide la arquitectura (T-008)

Esta es la tarea más importante del sprint 1. Guarden esto como `lab/prueba_humo.py` y córranlo **desde Windows**, no desde WSL:

```python
import json, time, urllib.request

MODELO = "llama3.1:8b-instruct-q4_K_M"
HALLAZGO = {
    "titulo": "Cross Site Scripting (Reflected)",
    "url": "http://juiceshop:3000/rest/products/search?q=<script>alert(1)</script>",
    "param": "q",
    "evidencia": "<script>alert(1)</script>",
    "severidad_zap": "High",
    "cwe": 79,
}

PROMPT = f"""Eres un analista de seguridad. Analiza este hallazgo y responde
UNICAMENTE con un objeto JSON, sin texto adicional ni markdown.

Hallazgo: {json.dumps(HALLAZGO, ensure_ascii=False)}

Formato exacto:
{{"explicacion": "...", "owasp": "A05:2025", "prioridad": "p1", "confianza": 0.0}}

La categoria debe ser del OWASP Top 10 EDICION 2025: A01 Broken Access Control,
A02 Security Misconfiguration, A03 Software Supply Chain Failures,
A04 Cryptographic Failures, A05 Injection, A06 Insecure Design,
A07 Authentication Failures, A08 Software or Data Integrity Failures,
A09 Security Logging and Alerting Failures,
A10 Mishandling of Exceptional Conditions."""

cuerpo = json.dumps({
    "model": MODELO,
    "prompt": PROMPT,
    "stream": False,
    "format": "json",          # obliga a Ollama a devolver JSON válido
    "options": {"temperature": 0.1},
}).encode()

tiempos, validos = [], 0
for i in range(5):
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=cuerpo,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        salida = json.loads(r.read())["response"]
    dt = time.perf_counter() - t0
    tiempos.append(dt)
    try:
        d = json.loads(salida)
        ok = d.get("owasp", "").endswith(":2025")
        validos += ok
        print(f"  {i+1}. {dt:6.1f}s  owasp={d.get('owasp')}  prioridad={d.get('prioridad')}")
    except json.JSONDecodeError:
        print(f"  {i+1}. {dt:6.1f}s  JSON INVALIDO")

print(f"\nMediana: {sorted(tiempos)[2]:.1f}s por hallazgo")
print(f"JSON valido con edicion 2025: {validos}/5")
print(f"Proyeccion para 300 hallazgos: {sorted(tiempos)[2]*300/60:.0f} minutos")
```

```powershell
python lab\prueba_humo.py
```

**Cómo leer el resultado:**

| Mediana | Qué significa | Qué hacer |
|---|---|---|
| Menos de 15 s | Cómodo | Sigan con el plan tal cual |
| 15 a 40 s | Viable | Enriquecimiento por lotes en segundo plano (ya está en el S5) |
| Más de 40 s | Problema | Modelo de 3B, o enriquecer solo severidad alta y crítica |

Ese último caso no es un fracaso: **"enriquecemos por niveles según severidad porque medimos el costo por hallazgo"** es una decisión de ingeniería defendible y mucho mejor que descubrirlo en la semana 15.

Anoten también cuántas veces el modelo respondió con categorías de **2021** en vez de 2025. Va a pasar, porque su entrenamiento es mayormente anterior. Ese número es material directo para su sección de resultados y justifica la validación con Pydantic de la tarea T-030.

---

## El presupuesto de memoria: no corran todo junto

Con 16 GB no alcanza para tener todo arriba al mismo tiempo. Tampoco hace falta: el pipeline es naturalmente por fases.

| Fase | Qué levantan | RAM aproximada |
|---|---|---|
| Escaneo | `juiceshop` + `zap` | ~9 GB |
| Enriquecimiento | `db` + `api` + Ollama | ~13 GB |
| Dashboard | `db` + `api` + `web` | ~8 GB |
| Todo junto | — | ~17 GB, **no cabe** |

En la práctica:

```bash
docker compose stop juiceshop        # después de escanear
docker compose up -d db api          # antes de enriquecer
```

Y cierren Ollama desde la bandeja del sistema cuando trabajen en el frontend. Cuando toque la demo de la defensa, ensayen la secuencia completa de encendido y apagado: es parte del guion.

---

## Problemas frecuentes

**`docker: command not found` en Ubuntu.** Falta activar WSL Integration en Docker Desktop (paso 2).

**Todo va lentísimo.** El repositorio está en `/mnt/c/`. Muévanlo a `~/` (paso 3).

**`connection refused` hacia Ollama.** Falta `OLLAMA_HOST=0.0.0.0:11434` o falta cerrar y reabrir sesión de Windows (paso 8).

**ZAP no escribe el JSON.** Verifiquen que `lab/salidas/` existe y que el volumen apunta a `/zap/wrk`. ZAP corre como usuario `zap` y solo escribe ahí.

**El equipo se congela durante el escaneo full.** ZAP con Java consume 2 GB o más. Cierren Ollama y el navegador antes de lanzarlo.

**El nombre de la red no coincide.** Docker antepone el nombre de la carpeta. Si su carpeta se llama distinto, la red será `<carpeta>_lab_interna`. Confirmen con `docker network ls`.

---

## Qué queda cerrado al terminar

| Tarea | Evidencia |
|---|---|
| T-003 | Repositorio con estructura y primer commit |
| T-005 | `docker compose up` levanta el laboratorio |
| T-006 | Las dos capturas del ping bloqueado y permitido |
| T-007 | `lab/fixtures/zap_juiceshop_full_v1.json` versionado |
| T-008 | Latencia mediana medida y anotada |
| T-009 | Modelo elegido, con la medición que lo justifica |

Marquen esas seis como "Hecho" en la planilla y el sprint 1 queda al 60%. Lo que falta (T-001, T-002, T-004, T-010) es diseño y convenciones, que ya tienen resuelto con los documentos del esquema y el modelo de datos.

---

## Para aprender lo justo de seguridad

No estudien seguridad en general. Estudien estas cuatro cosas, en este orden:

1. **Qué reporta ZAP.** Abran el JSON del escaneo full y lean diez alertas distintas. En dos horas van a reconocer los patrones.
2. **El OWASP Top 10:2025.** Las diez categorías, una página cada una. `owasp.org/Top10/2025/`
3. **Juice Shop.** Tiene un libro compañero gratuito que explica cada vulnerabilidad plantada y por qué existe.
4. **CWE.** Solo el concepto: es un catálogo numerado de tipos de debilidad. Su campo `cwe_id` viene de ahí.

Con eso alcanza para defender el proyecto. Su aporte no es descubrir vulnerabilidades: es construir el sistema que las ordena, las explica y las prioriza.
