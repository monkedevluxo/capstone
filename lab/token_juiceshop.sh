#!/usr/bin/env bash
# Crea (si no existe) un usuario de prueba en Juice Shop e imprime su token de sesión.
# Tarea: escaneo autenticado (apoyo a T-041) · Responsable: Felipe Cayún
#
# Uso (desde la raíz del repositorio):
#   ./lab/token_juiceshop.sh
#
# Juice Shop vive en lab_interna, sin puertos publicados, así que las peticiones
# se hacen desde un contenedor conectado a esa misma red.
# Juice Shop borra sus usuarios al reiniciarse: por eso el script intenta crear
# el usuario siempre y, si ya existe, continúa con el login.
#
# El token es una credencial: se imprime por pantalla y NUNCA se guarda en el repo.

set -euo pipefail

RED="capstone_lab_interna"
OBJETIVO="http://juiceshop:3000"
EMAIL="zap@sentinel.lab"
CLAVE="Sentinel123!"     # cuenta de prueba, solo existe en el laboratorio local

curl_lab() {
  docker run --rm --network "${RED}" curlimages/curl -s "$@"
}

error() { echo "ERROR: $*" >&2; exit 1; }

# 1. Crear el usuario (si ya existe, Juice Shop responde con error y seguimos).
curl_lab -X POST "${OBJETIVO}/api/Users" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${CLAVE}\",\"passwordRepeat\":\"${CLAVE}\"}" \
  >/dev/null || true

# 2. Iniciar sesión y extraer el token.
RESPUESTA="$(curl_lab -X POST "${OBJETIVO}/rest/user/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${CLAVE}\"}")"

TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["authentication"]["token"])' \
  <<<"${RESPUESTA}" 2>/dev/null)" \
  || error "No se pudo iniciar sesión. Respuesta de Juice Shop: ${RESPUESTA}"

echo "${TOKEN}"
