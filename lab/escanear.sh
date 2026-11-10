#!/usr/bin/env bash
# Ejecuta un escaneo de OWASP ZAP contra Juice Shop dentro del laboratorio aislado.
# Tarea: T-018 · Responsable: Felipe Cayún
#
# Uso (desde la raíz del repositorio):
#   ./lab/escanear.sh
#
# El resultado queda en lab/salidas/<nombre>.json

set -euo pipefail

OBJETIVO="http://juiceshop:3000"
FECHA="$(date +%Y%m%d_%H%M)"
SALIDA="baseline_${FECHA}.json"

echo "Escaneo baseline contra ${OBJETIVO}"
echo "Resultado: lab/salidas/${SALIDA}"

# -I: no tratar las advertencias como error (ZAP devuelve código 2 si hay WARN).
docker compose run --rm zap zap-baseline.py -t "${OBJETIVO}" -J "${SALIDA}" -I

echo "Listo: lab/salidas/${SALIDA}"
