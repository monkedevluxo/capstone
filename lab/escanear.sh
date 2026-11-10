#!/usr/bin/env bash
# Ejecuta un escaneo de OWASP ZAP contra Juice Shop dentro del laboratorio aislado.
# Tarea: T-018 · Responsable: Felipe Cayún
#
# Uso (desde la raíz del repositorio):
#   ./lab/escanear.sh [baseline|full|ajax]
#
#   baseline  Solo pasivo, 1-2 minutos (por defecto)
#   full      Escaneo activo con el spider tradicional, unos 6-9 minutos
#   ajax      Escaneo activo con Ajax Spider y límites de tiempo, unos 15 minutos
#
# El resultado queda en lab/salidas/<modo>_<fecha>.json

set -euo pipefail

MODO="${1:-baseline}"
OBJETIVO="http://juiceshop:3000"
FECHA="$(date +%Y%m%d_%H%M)"
SALIDA="${MODO}_${FECHA}.json"
DIR_SALIDAS="lab/salidas"

# Límites para el Ajax Spider. Sin ellos, el escaneo quedó colgado más de 3 horas
# abriendo navegadores headless sin cerrarlos (regla de DOM XSS).
AJAX_MINUTOS=5          # tiempo que explora el Ajax Spider
MAX_MIN_POR_REGLA=5     # ninguna regla de ataque puede durar más
MAX_MIN_ESCANEO=60      # tope del escaneo activo completo

error() { echo "ERROR: $*" >&2; exit 1; }

# --- Verificaciones previas -------------------------------------------------

[[ -f docker-compose.yml ]] \
  || error "Corre el script desde la raíz del repositorio (cd ~/capstone)."

docker info >/dev/null 2>&1 \
  || error "Docker no está corriendo. Prueba: sudo systemctl start docker"

docker ps --format '{{.Names}}' | grep -qx sentinel-juiceshop \
  || error "Juice Shop no está arriba. Prueba: docker compose up -d"

mkdir -p "${DIR_SALIDAS}"
[[ -w "${DIR_SALIDAS}" ]] \
  || error "Sin permiso de escritura en ${DIR_SALIDAS}. Prueba: sudo chown -R \$USER:\$USER ${DIR_SALIDAS}"

# --- Escaneo ----------------------------------------------------------------

case "${MODO}" in
  baseline)
    COMANDO=(zap-baseline.py -t "${OBJETIVO}" -J "${SALIDA}" -I)
    ;;
  full)
    COMANDO=(zap-full-scan.py -t "${OBJETIVO}" -J "${SALIDA}" -I)
    ;;
  ajax)
    COMANDO=(zap-full-scan.py -t "${OBJETIVO}" -J "${SALIDA}" -I -j -m "${AJAX_MINUTOS}"
             -z "-config scanner.maxScanDurationInMins=${MAX_MIN_ESCANEO} -config scanner.maxRuleDurationInMins=${MAX_MIN_POR_REGLA}")
    ;;
  *)
    error "Modo no válido: ${MODO}. Usa baseline, full o ajax."
    ;;
esac

echo "Escaneo ${MODO} contra ${OBJETIVO}"
echo "Resultado: ${DIR_SALIDAS}/${SALIDA}"

# -I: no tratar las advertencias como error (ZAP devuelve código 2 si hay WARN).
docker compose run --rm zap "${COMANDO[@]}"

echo "Listo: ${DIR_SALIDAS}/${SALIDA}"
