# Addendum · Ollama en un equipo separado

**SentinelAI · complemento de GUIA_INSTALACION.md**


> **Nota:** este documento asume Docker Desktop. Con Docker Engine en WSL2,
> `host.docker.internal` no apunta a Windows. Ver la sección de Joaquín en
> `GUIA_INSTALACION.md` para la forma correcta.
Reemplaza al paso 8 de la guía principal cuando Ollama corre en otro equipo.

| Equipo | Rol | Hardware |
|---|---|---|
| Notebook (T14 Gen 1) | Docker, WSL2, backend, dashboard | Ryzen 7 PRO 4000, 16 GB, sin GPU dedicada |
| Escritorio de Joaquín | Nodo de inferencia | 16 GB, GPU dedicada |

---

## Paso 0 · Averiguar la VRAM antes de decidir el modelo

En el PC de Joaquín, PowerShell:

```powershell
nvidia-smi
```

Si el comando no existe, la tarjeta no es NVIDIA. Vayan a Administrador de tareas → Rendimiento → GPU y lean **"Memoria de GPU dedicada"**.

| VRAM | Modelo recomendado | Qué esperar |
|---|---|---|
| 12 GB o más | 8B q4 o superior | Cómodo, 30+ tokens/s |
| 8 GB | `llama3.1:8b-instruct-q4_K_M` | Entra completo, buena velocidad |
| 6 GB | 8B q4 | Entra justo. Cierren juegos y navegador. |
| 4 GB | 3B q4, o 8B con descarga parcial | Midan antes de comprometerse |

**Si la GPU es AMD:** el soporte de Ollama en Windows existe pero es más nuevo que el de NVIDIA. Corran la prueba de humo del paso 4 antes de dar por hecho que acelera. Si no acelera, sigue siendo útil: el escritorio libera la RAM del notebook aunque calcule por CPU.

---

## Paso 1 · Configurar Ollama en el equipo de Joaquín

Instalar desde `ollama.com`, y luego:

1. Buscar "variables de entorno" en el menú inicio
2. Variables de usuario → Nueva
3. Nombre: `OLLAMA_HOST` · Valor: `0.0.0.0:11434`
4. **Cerrar sesión de Windows y volver a entrar** (no basta con reiniciar Ollama)

Bajar el modelo:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama run llama3.1:8b-instruct-q4_K_M "responde solo: ok"
```

Verificar que efectivamente usa la GPU: mientras el modelo responde, abran otra ventana y corran `nvidia-smi`. Debe aparecer `ollama` en la lista de procesos con memoria asignada. Si no aparece, está calculando por CPU y hay que revisar los drivers.

---

## Paso 2 · Abrir el puerto en el firewall de Windows

Este es el paso que falta casi siempre. Windows bloquea el puerto 11434 por defecto y el error que da desde el otro equipo es un "connection timeout" que no explica nada.

En el PC de Joaquín, PowerShell **como administrador**:

```powershell
New-NetFirewallRule -DisplayName "Ollama SentinelAI" `
  -Direction Inbound -LocalPort 11434 -Protocol TCP -Action Allow `
  -Profile Private
```

`-Profile Private` limita la regla a redes marcadas como privadas. Si la red del campus está marcada como pública en Windows, la regla no aplica: o cambian el perfil de esa red a privada, o agregan `-Profile Private,Public` asumiendo que entienden que eso expone el puerto a toda la red.

Averiguar la IP de Joaquín:

```powershell
ipconfig
```

Busquen "Dirección IPv4" del adaptador activo. Algo como `192.168.1.42`.

---

## Paso 3 · Probar la conexión desde el notebook

Desde WSL en el notebook:

```bash
curl -s http://192.168.1.42:11434/api/tags
```

Si devuelve un JSON con la lista de modelos, funciona. Si se queda colgado o da timeout:

1. ¿Están los dos en la misma red? (`ipconfig` en ambos, comparar los primeros tres números)
2. ¿La regla de firewall aplica al perfil de red correcto?
3. ¿La red tiene aislamiento de clientes? → sigan al paso 3b

### Paso 3b · Si la red del campus los aísla

Muchas redes universitarias impiden que dos equipos conectados se vean entre sí. No es un problema de configuración de ustedes y no hay regla de firewall que lo arregle.

**La solución es Tailscale.** Es gratis para uso personal, se instala en ambos equipos, y crea una red privada cifrada que atraviesa NAT y aislamiento de clientes. Entrega IPs fijas del rango `100.x.x.x` que **no cambian nunca**, lo que además resuelve el problema de que el DHCP del campus le asigne otra IP a Joaquín cada día.

1. Crear una cuenta en `tailscale.com` (sirve la de Google o GitHub)
2. Instalar Tailscale en ambos equipos e iniciar sesión con la misma cuenta
3. En el panel de Tailscale aparecen los dos equipos con su IP `100.x.x.x`
4. Usar esa IP en lugar de la de la red local

Con Tailscale funciona incluso desde sus casas, en redes distintas. Para un proyecto de tres personas que trabajan en horarios distintos, eso vale bastante.

Prueben esto **la primera semana**, no cuando lo necesiten.

---

## Paso 4 · Apuntar el backend al equipo remoto

En `docker-compose.yml`, cambien la variable del servicio `api`:

```yaml
  api:
    environment:
      DATABASE_URL: postgresql+psycopg://sentinel:sentinel_local@db:5432/sentinelai
      OLLAMA_URL: ${OLLAMA_URL:-http://host.docker.internal:11434}
```

Y creen un archivo `.env` en la raíz (que **no** se versiona):

```
OLLAMA_URL=http://100.101.102.103:11434
```

El valor por defecto después de `:-` hace que si alguien levanta el proyecto sin `.env`, caiga a la máquina local en vez de fallar. Eso importa para el criterio de "cualquiera puede levantar el proyecto siguiendo el README" de la tarea T-065.

Agreguen un `.env.ejemplo` **sí versionado**, con la variable documentada pero sin la IP real.

Ya no necesitan `extra_hosts` para esto, aunque dejarlo no molesta.

Verifiquen desde el contenedor:

```bash
docker compose up -d api
docker compose exec api python -c "import os,urllib.request,json; print(json.loads(urllib.request.urlopen(os.environ['OLLAMA_URL']+'/api/tags').read())['models'][0]['name'])"
```

---

## Paso 5 · Correr la prueba de humo contra el nodo remoto

Usen el mismo `lab/prueba_humo.py` del paso 9 de la guía principal, cambiando una línea:

```python
"http://100.101.102.103:11434/api/generate"
```

Corran la medición **desde el notebook**, no desde el PC de Joaquín. Lo que importa es la latencia que va a ver el backend, con la red incluida. Suele agregar entre 20 y 100 ms, despreciable frente al tiempo de inferencia, pero mídanlo igual.

---

## Lo que hay que acordar como equipo

**El PC de Joaquín pasa a ser infraestructura.** Si está jugando, el modelo compite por la GPU y las mediciones dejan de ser comparables. Acuerden cuándo está disponible y anótenlo, sobre todo antes de cualquier corrida de medición para el informe.

**Definan un plan B por escrito.** Si el equipo de Joaquín no está disponible, el notebook puede correr un modelo de 3B por CPU. Más lento y peor, pero el proyecto no se detiene. Que esté en el README, no en la memoria de alguien.

---

## Por qué esto no compromete la demo de la defensa

Vale la pena que lo tengan claro, porque suena a riesgo y no lo es tanto.

Las salidas del modelo viven en la tabla `ai_enrichments`. **El dashboard lee de la base de datos, no de Ollama.** Para demostrar el sistema no necesitan el nodo de inferencia encendido: los hallazgos ya están enriquecidos y persistidos.

Solo necesitan Ollama arriba si van a enriquecer en vivo durante la defensa. Si lo hacen, que sea un extra opcional al final, nunca la parte central de la demo. Y el video de respaldo de la tarea T-068 cubre el caso de que falle igual.

---

## Cambios respecto de la guía principal

| Sección | Qué cambia |
|---|---|
| Paso 8 | Ollama se instala en el equipo de Joaquín, no en el notebook |
| Paso 9 | La prueba de humo apunta a la IP remota |
| Presupuesto de RAM | La fila "Enriquecimiento" baja de ~13 GB a ~7 GB en el notebook |
| Problemas frecuentes | Se agrega: firewall, aislamiento de clientes, IP cambiante |

El resto de la guía queda igual.
