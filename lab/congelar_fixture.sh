#!/usr/bin/env bash
# Copia un resultado de escaneo de lab/salidas/ a lab/fixtures/ para versionarlo.
# Tarea: T-018 · Responsable: Felipe Cayún
#
# Uso (desde la raíz del repositorio):
#   ./lab/congelar_fixture.sh <archivo_en_salidas> <nombre_fixture>
#
# Ejemplo:
#   ./lab/congelar_fixture.sh ajax_20261109_2130.json zap_juiceshop_ajax_v3
#   → lab/fixtures/zap_juiceshop_ajax_v3.json
#
# Nunca sobrescribe un fixture existente: los tests y las métricas dependen de ellos.

set -euo pipefail

error() { echo "ERROR: $*" >&2; exit 1; }

[[ $# -eq 2 ]] || error "Uso: $0 <archivo_en_salidas> <nombre_fixture>"

ORIGEN="lab/salidas/$1"
DESTINO="lab/fixtures/${2%.json}.json"

[[ -f "${ORIGEN}" ]]   || error "No existe ${ORIGEN}. Revisa con: ls lab/salidas"
[[ ! -e "${DESTINO}" ]] || error "${DESTINO} ya existe. Usa otro nombre (por ejemplo, sube la versión: _v3)."

python3 -c "import json,sys; json.load(open(sys.argv[1]))" "${ORIGEN}" 2>/dev/null \
  || error "${ORIGEN} no es un JSON válido. ¿El escaneo terminó bien?"

cp "${ORIGEN}" "${DESTINO}"
echo "Fixture creado: ${DESTINO}"
echo "Siguiente paso: git add ${DESTINO} && git commit -m \"lab: fixture $(basename "${DESTINO}" .json)\""
