# Docker en 20 minutos

**SentinelAI · guía introductoria · lectura previa al montaje del laboratorio**

No cubre todo Docker. Cubre lo que van a usar en este proyecto y las cosas que confunden a todo el mundo la primera semana.

---

## 1. La idea

**Una imagen es una plantilla. Un contenedor es una copia corriendo.**

Como una clase y una instancia. La imagen de Juice Shop pesa unos 400 MB y trae la aplicación con todas sus dependencias adentro: Node.js, las librerías, los archivos. Cuando la ejecutan, Docker crea un contenedor a partir de ella.

De la misma imagen pueden crear diez contenedores. Cada uno es independiente: lo que pasa en uno no afecta a los otros.

### Por qué no es una máquina virtual

Una VM lleva su propio sistema operativo completo: pesa gigabytes, arranca en minutos y hay que mantenerla. Un contenedor comparte el núcleo de Linux que ya está debajo y solo empaqueta la aplicación. Pesa megabytes, arranca en segundos y se borra sin dejar rastro.

La consecuencia práctica es la que importa para su proyecto: `docker run` sobre la misma imagen da **exactamente** el mismo resultado en su notebook, en el PC de Joaquín y en el equipo del profesor. Eso es reproducibilidad, y es lo que hace defendible un proyecto de título.

---

## 2. Juice Shop en un comando

Prueben esto antes de leer el resto:

```bash
docker run -d --name juiceshop -p 127.0.0.1:3000:3000 bkimminich/juice-shop
```

Abran `http://localhost:3000`. Ahí está la aplicación completa.

Desglose:

| Parte | Qué hace |
|---|---|
| `docker run` | Crear y arrancar un contenedor |
| `-d` | En segundo plano (*detached*). Sin esto ocupa la terminal. |
| `--name juiceshop` | Ponerle nombre. Si no, Docker inventa uno tipo `sad_einstein`. |
| `-p 127.0.0.1:3000:3000` | Publicar el puerto (ver sección 4) |
| `bkimminich/juice-shop` | La imagen. Si no la tienen, la descarga sola. |

Para borrarlo:

```bash
docker rm -f juiceshop
```

Y no queda nada. Ni carpetas, ni entradas de registro, ni servicios sueltos. Esa es toda la gracia.

---

## 3. Los comandos que van a usar de verdad

```bash
docker ps                      # contenedores corriendo
docker ps -a                   # incluye los detenidos
docker logs juiceshop          # ver su salida
docker logs -f juiceshop       # ídem, siguiendo en vivo (Ctrl+C para salir)
docker exec -it juiceshop sh   # abrir una terminal ADENTRO del contenedor
docker stop juiceshop          # detener (conserva el contenedor)
docker start juiceshop         # volver a arrancar
docker rm -f juiceshop         # eliminar
docker images                  # imágenes descargadas
docker stats                   # cuánta RAM y CPU consume cada uno
```

Con esos diez se defienden todo el proyecto.

**`docker logs` es su mejor herramienta de diagnóstico.** Cuando algo no funciona, ese es el primer comando, siempre. El 80% de los problemas están explicados ahí.

**`docker exec -it <nombre> sh` los mete adentro del contenedor**, como si fuera otra máquina. Útil para revisar si un archivo llegó donde debía. Salen con `exit`.

---

## 4. Las cuatro cosas que confunden

### 4.1 Puertos: `-p afuera:adentro`

```
-p 3000:3000
   ↑    ↑
   |    puerto DENTRO del contenedor
   puerto en SU máquina
```

El número de la izquierda es el que ustedes escriben en el navegador. El de la derecha es donde la aplicación escucha adentro. No tienen que coincidir:

```bash
docker run -d -p 8080:3000 bkimminich/juice-shop
# la app sigue escuchando en 3000 adentro, pero ustedes entran por localhost:8080
```

**Sin `-p`, el contenedor es inalcanzable desde su máquina.** No es un error: es lo que quieren para Juice Shop dentro del laboratorio.

El prefijo `127.0.0.1:` limita la publicación a su propio equipo. Con `-p 3000:3000` a secas, cualquiera en la misma WiFi puede entrar. Para una aplicación deliberadamente vulnerable, eso importa: úsenlo siempre.

### 4.2 Volúmenes: los datos se borran

**Todo lo que un contenedor escribe adentro desaparece cuando lo eliminan.** No es un bug, es el diseño.

Para conservar datos hay dos formas:

```bash
# Volumen con nombre: Docker administra el almacenamiento. Para bases de datos.
-v pgdata:/var/lib/postgresql/data

# Bind mount: una carpeta suya montada adentro. Para código y resultados.
-v ./lab/salidas:/zap/wrk
```

El bind mount es el que usan para que ZAP escriba el JSON en una carpeta que ustedes puedan abrir. Sin él, el archivo se genera adentro del contenedor y se pierde al terminar.

### 4.3 Redes: los contenedores se llaman por nombre

Esta es la que más cuesta.

Cuando dos contenedores están en la misma red de Docker, **se alcanzan por su nombre de servicio**, no por `localhost`:

```
Desde el contenedor zap:
  http://juiceshop:3000     ✓  correcto
  http://localhost:3000     ✗  "localhost" ahí adentro es el propio zap
```

Cada contenedor cree que es una máquina independiente. Su `localhost` es él mismo, no su equipo.

Por eso en el compose el escaneo apunta a `http://juiceshop:3000`, aunque desde el navegador ustedes usen `http://localhost:3000`. Son dos puntos de vista distintos de la misma aplicación.

### 4.4 Etiquetas: `latest` no significa nada estable

```bash
bkimminich/juice-shop           # equivale a :latest, cambia con el tiempo
bkimminich/juice-shop:v17.1.1   # fijo, reproducible
```

`latest` es simplemente la etiqueta por defecto, no "la última versión estable". Puede cambiar entre hoy y su defensa, y con ella cambiarían los hallazgos.

**Para el proyecto: fijen versiones y anótenlas en el README.** Es parte de la reproducibilidad que les van a exigir.

---

## 5. Compose: lo mismo, pero para varios contenedores

Levantar cinco contenedores a mano, con sus puertos, redes y volúmenes, es un comando gigante que nadie recuerda. Docker Compose es ese comando escrito en un archivo.

Cada opción del `docker run` tiene su equivalente en YAML:

| En `docker run` | En `docker-compose.yml` |
|---|---|
| `-p 3000:3000` | `ports: ["3000:3000"]` |
| `-v ./salidas:/zap/wrk` | `volumes: ["./salidas:/zap/wrk"]` |
| `--name juiceshop` | `container_name: juiceshop` |
| `-e VAR=valor` | `environment: {VAR: valor}` |

Los comandos equivalentes:

```bash
docker compose up -d           # levantar todo
docker compose up -d db api    # levantar solo dos servicios
docker compose ps              # ver el estado
docker compose logs -f api     # logs de un servicio
docker compose exec api sh     # entrar a un servicio
docker compose stop            # detener sin borrar
docker compose down            # detener y eliminar los contenedores
```

**Cuidado con `docker compose down -v`.** La `-v` borra también los volúmenes, o sea la base de datos completa. Es recuperable en desarrollo, pero pierde todo el trabajo de validación manual que hayan hecho. Sin `-v` los datos sobreviven.

---

## 6. Juice Shop: qué es y cómo usarlo

Es una aplicación web de tienda en línea **construida a propósito con vulnerabilidades**. Es un proyecto oficial de OWASP y probablemente la aplicación insegura más usada del mundo para enseñar seguridad web. No es un juguete: es una aplicación real, moderna (Angular + Node.js), con más de cien vulnerabilidades deliberadas.

Para su proyecto es el objetivo ideal porque genera muchos hallazgos de tipos variados, que es exactamente lo que necesitan para que la priorización tenga algo que priorizar.

### Reiniciarla

Guarda su estado en memoria. Reiniciar el contenedor la deja como nueva:

```bash
docker restart juiceshop
```

Útil entre escaneos, para que los resultados sean comparables.

### El tablero de puntajes

Entren a `http://localhost:3000/#/score-board`. Ahí está la lista de todos los desafíos con su dificultad. Explórenlo un rato: es la forma más rápida de entender qué tipo de fallas van a aparecer en sus escaneos.

Hay un libro compañero gratuito, *Pwning OWASP Juice Shop*, que explica cada vulnerabilidad y por qué está ahí. Para el marco teórico de su informe es material de primera.

### Una advertencia que va en serio

**Juice Shop es genuinamente vulnerable.** No es una simulación: tiene inyección SQL real, XSS real, autenticación rota real.

- Publíquenla solo en `127.0.0.1`, nunca en `0.0.0.0`
- No la expongan a la red del campus ni a internet
- Dentro del laboratorio, con `internal: true`, no tiene ni salida ni entrada

Esto no es paranoia académica: es exactamente lo que su diapositiva de marco ético promete, y es la diferencia entre un laboratorio y un incidente.

---

## 7. Errores que van a ver

**`port is already allocated`**
Otro proceso ocupa ese puerto. Usen otro (`-p 3001:3000`) o encuentren al culpable con `docker ps`.

**`Cannot connect to the Docker daemon`**
Docker Desktop no está abierto, o falta activar la integración con WSL.

**`dial tcp: lookup juiceshop: no such host`**
Un contenedor intenta alcanzar a otro que no está en su misma red, o está detenido. Revisen con `docker compose ps` y verifiquen la sección `networks`.

**El contenedor arranca y se muere de inmediato**
`docker logs <nombre>` casi siempre lo explica en la primera línea. Suele ser una variable de entorno faltante o un error de sintaxis en el comando.

**`no space left on device`**
Docker acumula imágenes viejas. Ver sección 8.

---

## 8. Higiene: Docker acumula basura

Después de unas semanas, las imágenes descartadas ocupan varios gigabytes.

```bash
docker system df        # cuánto espacio está usando
docker system prune     # borrar lo no usado (pregunta antes)
docker system prune -a  # más agresivo: borra imágenes sin contenedor
```

**En Windows hay un detalle adicional:** el disco virtual de WSL2 no se encoge solo. Aunque borren todo con `prune`, el archivo sigue ocupando el espacio máximo que llegó a usar. Para recuperarlo:

```powershell
wsl --shutdown
Optimize-VHD -Path "$env:LOCALAPPDATA\Docker\wsl\disk\docker_data.vhdx" -Mode Full
```

`Optimize-VHD` requiere Hyper-V habilitado. Si no lo tienen, la alternativa es `diskpart` con `compact vdisk`. Háganlo cada tantas semanas, o cuando el disco empiece a apretar.

---

## 9. Lo mínimo que hay que retener

1. Imagen = plantilla, contenedor = copia corriendo
2. `docker logs` primero, siempre, ante cualquier problema
3. `-p afuera:adentro`, y usen `127.0.0.1:` para no exponer nada
4. Sin volumen, los datos se borran al eliminar el contenedor
5. Entre contenedores se llaman por nombre, no por `localhost`
6. Fijen versiones, `latest` cambia
7. `down -v` borra la base de datos

Con eso pueden seguir la guía de montaje sin ir a ciegas.
