# Instalación del entorno

**SentinelAI · Windows 11 · para Felipe y Joaquín**

De "tengo un PC con Windows" a "el laboratorio corre en mi equipo". Una tarde.

---

## Antes de empezar

**No necesitas saber de ciberseguridad.** ZAP hace el trabajo ofensivo y Juice Shop es una aplicación construida a propósito para ser atacada, con documentación oficial de OWASP. Lo que construimos es un pipeline de datos.

**No vas a instalar máquinas virtuales.** Docker las reemplazó. Escribes un archivo de texto que describe unos contenedores y corres un comando. Cada contenedor arranca en segundos y se borra sin dejar rastro.

**Vamos a usar Docker Engine, no Docker Desktop.** Esto es deliberado: Docker Desktop se volvió inestable en el equipo de Luciano y costó un día entero de diagnóstico. Docker Engine es el mismo Docker que corre en los servidores del mundo, sin la capa de traducción que falló. Es más liviano y tiene menos piezas que se rompan.

Lee `docs/guias/DOCKER_BASICO.md` si Docker te es nuevo. Son 20 minutos y te ahorra confusión más adelante.

---

## Paso 1 · WSL2

WSL2 es una máquina Linux liviana integrada a Windows. Ahí va a vivir todo.

PowerShell **como administrador**:

```powershell
wsl --install
```

Reinicia. Al volver, Windows termina de instalar Ubuntu y te pide crear usuario y contraseña de Linux.

**Anota esa contraseña.** No es la de Windows y la vas a necesitar para `sudo`. Si la pierdes: `wsl -d Ubuntu -u root` desde PowerShell y adentro `passwd <tu-usuario>`.

Verifica:

```powershell
wsl -l -v
```

Debe aparecer `Ubuntu` con `VERSION 2`. Si dice `VERSION 1`: `wsl --set-version Ubuntu 2`.

Actualiza el kernel, que evita varios problemas conocidos:

```powershell
wsl --update
wsl --version
```

---

## Paso 2 · Memoria de WSL2

Por defecto WSL2 se reserva hasta la mitad de tu RAM. Conviene fijarlo.

Crea `C:\Users\<tu-usuario>\.wslconfig`:

**Felipe (32 GB):**
```ini
[wsl2]
memory=16GB
processors=4
swap=4GB
```

**Joaquín (16 GB):**
```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
```

Joaquín lleva menos porque Ollama va a correr en Windows, fuera de WSL, y necesita espacio.

Aplica cerrando WSL:

```powershell
wsl --shutdown
```

---

## Paso 3 · Docker Engine

Abre **Ubuntu** desde el menú inicio (no PowerShell).

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

**Cierra la ventana de Ubuntu y ábrela de nuevo.** El cambio de grupo necesita sesión nueva.

```bash
docker ps
docker run --rm hello-world
```

Si `docker ps` dice "permission denied", faltó reabrir la terminal.

Docker Engine no arranca solo al encender el PC. Para que sí lo haga:

```bash
sudo systemctl enable docker
```

---

## Paso 4 · El repositorio

**Importante: va dentro de Linux, no en `C:\`.**

```bash
cd ~
git clone https://github.com/monkedevluxo/capstone.git
cd capstone
git config --global core.autocrlf input
```

Si lo pones en `/mnt/c/`, cada lectura cruza la frontera entre Windows y Linux y todo se vuelve entre 10 y 20 veces más lento. Vas a creer que el proyecto es pesado cuando el problema es dónde está guardado.

**Tampoco lo pongas en OneDrive.** Intenta sincronizar la carpeta `.git` y corrompe repositorios.

Para editar con VS Code: instala la extensión **WSL** y desde la terminal de Ubuntu corre `code .`. Abajo a la izquierda debe decir "WSL: Ubuntu".

---

## Paso 5 · Levantar el laboratorio

```bash
cd ~/capstone
docker compose up -d
docker compose ps
```

La primera vez descarga varios GB de imágenes. Deben quedar corriendo `sentinel-juiceshop`, `sentinel-db` y `sentinel-api`.

**Juice Shop no responde en `localhost:3000`.** No es un error: vive en una red aislada sin puertos publicados. Solo ZAP la alcanza.

Verifica que el aislamiento funciona:

```bash
# Debe fallar con "Network unreachable"
docker run --rm --network capstone_lab_interna alpine ping -c 2 -W 2 8.8.8.8

# Debe responder
docker run --rm alpine ping -c 2 8.8.8.8
```

Si el nombre de la red no coincide, búscalo con `docker network ls`. Docker le antepone el nombre de la carpeta.

---

## Paso 6 · La base de datos

```bash
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py --reset
curl http://localhost:8000/stats
```

Debe devolver 1 objetivo, 2 escaneos y 40 hallazgos.

Abre `http://localhost:8000/docs` en el navegador. Es la documentación interactiva de la API, y es la forma más rápida de entender qué hace el backend.

Los datos del seed son **sintéticos**, no vienen de un escaneo real. El objetivo se llama "(datos de prueba)" justamente para que nadie los confunda en el informe.

---

# Parte específica de cada uno

## Felipe · Escaneos

Tu equipo tiene 32 GB. Es el mejor del grupo para escaneos pesados, y eso importa: el primer escaneo full en el notebook de Luciano encontró solo 3 tipos de hallazgo, porque el spider tradicional no ve el contenido que Juice Shop arma con JavaScript.

```bash
# Rápido, solo pasivo (1-2 minutos)
docker compose run --rm zap zap-baseline.py -t http://juiceshop:3000 -J baseline.json -I

# Completo (unos 9 minutos)
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -J full.json -I

# Completo + Ajax Spider: el que puede cambiar las cosas
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -J full_ajax.json -I -j
```

Ese último levanta un navegador headless dentro del contenedor para recorrer la aplicación Angular. Es pesado — en el notebook falló por falta de recursos. Con 32 GB deberías poder.

Si sale `Permission denied` al escribir el JSON:

```bash
sudo chown -R $USER:$USER lab/salidas
```

Congela el resultado como fixture, que es lo que desbloquea a los demás:

```bash
cp lab/salidas/full_ajax.json lab/fixtures/zap_juiceshop_ajax_v2.json
git add lab/fixtures/ && git commit -m "lab: fixture con ajax spider" && git push
```

Compara cuánto ganaste:

```bash
python3 -c "import json;d=json.load(open('lab/salidas/full.json'));print(sum(len(s['alerts']) for s in d['site']),'alertas')"
python3 -c "import json;d=json.load(open('lab/salidas/full_ajax.json'));print(sum(len(s['alerts']) for s in d['site']),'alertas')"
```

Tu rol completo está en `docs/README_FELIPE.md`.

---

## Joaquín · Ollama

**Ollama va instalado en Windows, no dentro de WSL ni en un contenedor.** Es lo que le da acceso directo a tu GPU.

Con 8 GB de VRAM te alcanza cómodo para un modelo de 8B cuantizado, que ocupa unos 5 GB.

Descarga de `ollama.com` e instala. Después, **antes de usarlo**, configura una variable de entorno de Windows:

1. Buscar "variables de entorno" en el menú inicio
2. Variables de usuario → Nueva
3. Nombre: `OLLAMA_HOST` · Valor: `0.0.0.0:11434`
4. **Cerrar sesión de Windows y volver a entrar**

Sin esto, Ollama escucha solo en localhost y nada lo alcanza desde WSL. El error que da no explica nada.

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama run llama3.1:8b-instruct-q4_K_M "responde solo: ok"
```

Mientras responde, abre otra ventana y corre `nvidia-smi`. Debe aparecer `ollama` usando memoria de GPU. Si no aparece, está calculando por CPU y hay que revisar los drivers.

### Alcanzar Ollama desde los contenedores

Con Docker Engine en WSL2, `host.docker.internal` **no** apunta a Windows como sí lo hace con Docker Desktop. Hay que encontrar la IP del host:

```bash
ip route show | grep default | awk '{print $3}'
```

Eso devuelve algo como `172.20.144.1`. Pruébala:

```bash
curl http://172.20.144.1:11434/api/tags
```

Si devuelve un JSON con la lista de modelos, funciona. Guárdala en un `.env` en la raíz del repo (que no se versiona):

```
OLLAMA_URL=http://172.20.144.1:11434
```

**Ojo: esa IP cambia cuando reinicias WSL.** Si un día deja de funcionar, vuelve a correr el comando del `ip route`.

Alternativa más estable, si te molesta: en `.wslconfig` agrega `networkingMode=mirrored` bajo `[wsl2]`, corre `wsl --shutdown`, y después `localhost:11434` funciona directo desde WSL. Es una función de Windows 11; si no te resulta, quédate con la IP.

Si el firewall bloquea, PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "Ollama SentinelAI" -Direction Inbound `
  -LocalPort 11434 -Protocol TCP -Action Allow -Profile Private
```

### El parser

Es tu otra tarea y no depende de Ollama:

```bash
cd ~/capstone/backend
pip install pytest
python -m pytest tests/test_zap_parser.py -v
```

Vas a ver 25 tests fallando. Eso es correcto: son la especificación y pasan cuando el parser esté implementado.

Tu rol completo está en `docs/README_JOAQUIN.md`.

---

## Problemas frecuentes

**`docker: permission denied`**
Faltó cerrar y reabrir la terminal de Ubuntu después del `usermod`.

**`Cannot connect to the Docker daemon`**
El servicio no arrancó: `sudo systemctl start docker`.

**Todo va lentísimo**
El repositorio está en `/mnt/c/`. Muévelo a `~/`.

**El contenedor arranca y se muere**
`docker compose logs <servicio>` lo explica en la primera línea, casi siempre.

**`no space left on device`**
`docker system prune -a` libera imágenes viejas. En Windows el disco de WSL no se encoge solo; hay que compactarlo aparte.

**El nombre de la red no coincide**
Docker antepone el nombre de la carpeta. Si clonaste como `capstone`, la red es `capstone_lab_interna`. Confirma con `docker network ls`.

---

## Checklist

- [ ] `wsl -l -v` muestra Ubuntu en VERSION 2
- [ ] `.wslconfig` creado con la memoria de tu equipo
- [ ] `docker run --rm hello-world` funciona
- [ ] Repositorio clonado en `~/capstone`
- [ ] `docker compose up -d` deja tres contenedores arriba
- [ ] El ping dentro de `lab_interna` falla, el normal responde
- [ ] `curl http://localhost:8000/stats` devuelve 40 hallazgos
- [ ] `http://localhost:8000/docs` abre en el navegador

**Felipe además:** un escaneo ejecutado y su fixture commiteado.
**Joaquín además:** Ollama respondiendo y alcanzable desde un contenedor.

---

Si algo falla, pega el mensaje de error completo en el grupo. Docker da errores largos pero la causa suele estar en la primera línea.
