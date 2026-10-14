# Evidencia · Un contenedor alcanza Ollama (y uno aislado no)

**Responsable:** Joaquín Herrera · **Fecha:** 14-10-2026 · **Checklist:** "Un contenedor alcanza Ollama por la IP del host"

## Entorno

| Elemento | Valor |
|---|---|
| Nodo de inferencia | Windows · Ollama con `OLLAMA_HOST=0.0.0.0:11434` · `llama3.1:8b-instruct-q4_K_M` |
| WSL | WSL2 · Ubuntu 26.04.1 LTS · `.wslconfig` con `memory=8GB`, `processors=4`, `swap=2GB` |
| Docker | Docker Engine 29.9.0 · Docker Compose v5.6.0 (no Docker Desktop) |

## 1. IP de Windows vista desde WSL

```bash
$ ip route show | grep default | awk '{print $3}'
172.31.32.1
```

## 2. WSL alcanza Ollama

```bash
$ curl -m 5 http://172.31.32.1:11434/api/tags
{"models":[{"name":"llama3.1:8b-instruct-q4_K_M", ...}]}
```

No hizo falta abrir el firewall: bastó con `OLLAMA_HOST=0.0.0.0:11434`.

## 3. Un contenedor alcanza Ollama ✅

```bash
$ docker run --rm curlimages/curl -s -m 5 http://172.31.32.1:11434/api/tags
{"models":[{"name":"llama3.1:8b-instruct-q4_K_M", ... "parameter_size":"8.0B","quantization_level":"Q4_K_M" ...}]}
```

Es el mismo camino que usará el contenedor `api` (red `lab_datos`) para enriquecer hallazgos.

## 4. Un contenedor en red aislada NO alcanza Ollama ✅

Se crea una red con la misma opción que `lab_interna` en `docker-compose.yml` (`internal: true`):

```bash
$ docker network create --internal prueba_aislada
$ docker run --rm --network prueba_aislada curlimages/curl -s -m 5 http://172.31.32.1:11434/api/tags; echo "codigo de salida: $?"
codigo de salida: 7
$ docker network rm prueba_aislada
```

`curl` termina con el código **7** (*Failed to connect to host*) y sin ninguna respuesta. Un contenedor en la red del laboratorio, donde vive Juice Shop, **no tiene ruta hacia el nodo de inferencia**. Esto complementa `T006_aislamiento.txt`: la aplicación vulnerable no puede salir a internet ni alcanzar el modelo de IA.

## Configuración para el backend

En el `.env` de la raíz del repo, que no se versiona:

```
OLLAMA_URL=http://172.31.32.1:11434
```

**Ojo:** esa IP la asigna WSL y **puede cambiar al reiniciar WSL o Windows**. Si el backend deja de alcanzar Ollama, hay que repetir el paso 1 y actualizar el `.env`. Alternativa estable (Windows 11): `networkingMode=mirrored` en `.wslconfig` (ver `GUIA_INSTALACION.md`).
