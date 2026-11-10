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

# Límites para el Ajax Spider. Sin ellos, el escaneo quedó colgado más de 3 horas
# abriendo navegadores headless sin cerrarlos (regla de DOM XSS).
AJAX_MINUTOS=5          # tiempo que explora el Ajax Spider
MAX_MIN_POR_REGLA=5     # ninguna regla de ataque puede durar más
MAX_MIN_ESCANEO=60      # tope del escaneo activo completo

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
    echo "Modo no válido: ${MODO}. Usa baseline, full o ajax." >&2
    exit 1
    ;;
esac

echo "Escaneo ${MODO} contra ${OBJETIVO}"
echo "Resultado: lab/salidas/${SALIDA}"

# -I: no tratar las advertencias como error (ZAP devuelve código 2 si hay WARN).
docker compose run --rm zap "${COMANDO[@]}"

echo "Listo: lab/salidas/${SALIDA}"
