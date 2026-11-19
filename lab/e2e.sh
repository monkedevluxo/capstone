#!/usr/bin/env bash
# Prueba de extremo a extremo: de un reporte de ZAP al informe técnico.
# Tarea: T-061 · Responsable: Felipe Cayún
#
# Uso (desde la raíz del repositorio, con el laboratorio arriba):
#   ./lab/e2e.sh                 usa el fixture zap_juiceshop_ajax_v2
#   ./lab/e2e.sh --escanear      escanea Juice Shop primero (baseline) y usa ese resultado
#
# Corre SIEMPRE contra la base de pruebas sentinelai_test, nunca contra la de la
# demo (CONTRIBUTING.md): la vacía al empezar y levanta una API aparte en
# 127.0.0.1:8001 que se detiene al terminar, pase lo que pase.

set -euo pipefail

BASE_PRUEBA="sentinelai_test"
URL_BD="postgresql+psycopg://sentinel:sentinel_local@db:5432/${BASE_PRUEBA}"
API="http://127.0.0.1:8001"
CONTENEDOR="sentinel-api-prueba"
FIXTURE="lab/fixtures/zap_juiceshop_ajax_v2.json"
INFORME="lab/salidas/e2e_informe.html"

FALLAS=0
paso()  { echo; echo "== $*"; }
ok()    { echo "   OK    $*"; }
aviso() { echo "   AVISO $*"; }
falla() { echo "   FALLA $*"; FALLAS=$((FALLAS + 1)); }
error() { echo "ERROR: $*" >&2; exit 1; }

# Lee un campo de un JSON: campo '{"a": 1}' a -> 1
campo() { python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ""))' "$1" "$2"; }

limpiar() { docker stop "${CONTENEDOR}" >/dev/null 2>&1 || true; }
trap limpiar EXIT

# --- 0. Verificaciones previas ------------------------------------------------

[[ -f docker-compose.yml ]] || error "Corre el script desde la raíz del repositorio (cd ~/capstone)."
docker ps --format '{{.Names}}' | grep -qx sentinel-db \
  || error "La base no está arriba. Prueba: docker compose up -d"

REPORTE="${FIXTURE}"
if [[ "${1:-}" == "--escanear" ]]; then
  paso "0. Escaneo baseline de Juice Shop"
  ./lab/escanear.sh baseline
  REPORTE="lab/salidas/$(ls -t lab/salidas | grep '^baseline_.*\.json$' | head -1)"
  ok "reporte: ${REPORTE}"
fi
[[ -f "${REPORTE}" ]] || error "No existe ${REPORTE}."

# --- 1. Base de pruebas limpia ------------------------------------------------

paso "1. Base de pruebas ${BASE_PRUEBA}"
if ! docker compose exec -T db psql -U sentinel -d sentinelai -tAc \
     "SELECT 1 FROM pg_database WHERE datname='${BASE_PRUEBA}'" | grep -q 1; then
  docker compose exec -T db createdb -U sentinel "${BASE_PRUEBA}"
  ok "creada"
fi
docker compose run --rm -T -e DATABASE_URL="${URL_BD}" api alembic upgrade head >/dev/null
docker compose exec -T db psql -U sentinel -d "${BASE_PRUEBA}" -q -c \
  "TRUNCATE validations, ai_enrichments, finding_observations, finding_instances, findings, scans, targets CASCADE"
ok "migrada y vacía"

# --- 2. API de pruebas --------------------------------------------------------

paso "2. API de pruebas en ${API}"
limpiar
docker compose run -d --rm --name "${CONTENEDOR}" -p 127.0.0.1:8001:8000 \
  -e DATABASE_URL="${URL_BD}" api >/dev/null
for _ in $(seq 1 30); do
  curl -sf "${API}/health" >/dev/null && break
  sleep 1
done
curl -sf "${API}/health" >/dev/null || error "La API de pruebas no respondió en 30 segundos."
ok "responde /health"

# --- 3. Importar el reporte ---------------------------------------------------

paso "3. Importar ${REPORTE}"
RESPUESTA="$(curl -s -w '\n%{http_code}' -X POST "${API}/scans/import" \
  -H 'Content-Type: application/json' --data-binary @"${REPORTE}")"
CODIGO="$(tail -1 <<<"${RESPUESTA}")"
CUERPO="$(sed '$d' <<<"${RESPUESTA}")"
if [[ "${CODIGO}" == "201" ]]; then
  SCAN_ID="$(campo "${CUERPO}" scan_id)"
  NUEVOS="$(campo "${CUERPO}" nuevos)"
  ok "201 · ${NUEVOS} hallazgos nuevos · escaneo ${SCAN_ID}"
  [[ "${NUEVOS}" -gt 0 ]] || falla "el reporte no generó hallazgos"
else
  error "Se esperaba 201 y llegó ${CODIGO}: ${CUERPO}"
fi

paso "4. Importar el mismo reporte otra vez"
CODIGO="$(curl -s -o /dev/null -w '%{http_code}' -X POST "${API}/scans/import" \
  -H 'Content-Type: application/json' --data-binary @"${REPORTE}")"
[[ "${CODIGO}" == "409" ]] && ok "409 · el reporte repetido se rechaza" \
  || falla "se esperaba 409 y llegó ${CODIGO}"

paso "5. Consultar el resumen"
RESUMEN="$(curl -sf "${API}/findings/resumen")"
TOTAL="$(campo "${RESUMEN}" total)"
[[ "${TOTAL}" == "${NUEVOS}" ]] && ok "${TOTAL} hallazgos, igual que los importados" \
  || falla "el resumen dice ${TOTAL} y se importaron ${NUEVOS}"

paso "6. Enriquecer el escaneo con la IA"
RESPUESTA="$(curl -s -w '\n%{http_code}' -X POST "${API}/scans/${SCAN_ID}/enrich")"
CODIGO="$(tail -1 <<<"${RESPUESTA}")"
CUERPO="$(sed '$d' <<<"${RESPUESTA}")"
case "${CODIGO}" in
  200) ok "200 · $(campo "${CUERPO}" procesados) hallazgos procesados" ;;
  503) aviso "Ollama no responde: los hallazgos quedan 'sin enriquecer' y el flujo sigue" ;;
  *)   falla "se esperaba 200 o 503 y llegó ${CODIGO}: ${CUERPO}" ;;
esac

paso "7. Registrar una decisión humana"
REVISOR="Prueba E2E"
HALLAZGO="$(curl -sf "${API}/findings?limit=1" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["items"][0]["id"])')"
RESPUESTA="$(curl -s -w '\n%{http_code}' -X POST "${API}/findings/${HALLAZGO}/validaciones" \
  -H 'Content-Type: application/json' \
  -d "{\"decision\": \"confirmado\", \"revisor\": \"${REVISOR}\", \"comentario\": \"Registrada por lab/e2e.sh\"}")"
CODIGO="$(tail -1 <<<"${RESPUESTA}")"
CUERPO="$(sed '$d' <<<"${RESPUESTA}")"
if [[ "${CODIGO}" == "201" ]]; then
  ESTADO="$(campo "${CUERPO}" estado)"
  [[ "${ESTADO}" == "confirmado" ]] && ok "201 · el hallazgo pasó a 'confirmado'" \
    || falla "la decisión se guardó, pero el hallazgo quedó en '${ESTADO}'"
else
  falla "se esperaba 201 y llegó ${CODIGO}: ${CUERPO}"
fi

paso "8. Generar el informe técnico"
mkdir -p lab/salidas
docker exec "${CONTENEDOR}" python scripts/informe.py > "${INFORME}" 2>/dev/null \
  || falla "scripts/informe.py terminó con error"
FALTAN=0
for seccion in "1. Resumen" "2. Escaneos de origen" "3. Hallazgos" "4. Descartados" "5. Calidad de la IA"; do
  grep -q "${seccion}" "${INFORME}" || { falla "al informe le falta la sección '${seccion}'"; FALTAN=1; }
done
# Sin la comilla de cierre: las fichas marcadas para revisar traen class="hallazgo revisar".
FICHAS="$(grep -o '<article class="hallazgo' "${INFORME}" | wc -l)"
[[ "${FALTAN}" -eq 0 ]] && ok "${INFORME} · 5 secciones · ${FICHAS} fichas de hallazgo"
[[ "${FICHAS}" == "${TOTAL}" ]] && ok "una ficha por hallazgo" \
  || falla "el informe trae ${FICHAS} fichas y la base tiene ${TOTAL} hallazgos"
grep -q "${REVISOR}" "${INFORME}" && grep -q "Con decisión humana: 1\." "${INFORME}" \
  && ok "el informe muestra la decisión humana registrada en el paso 7" \
  || falla "el informe no muestra la decisión humana del paso 7"

# --- Resultado ----------------------------------------------------------------

echo
if [[ "${FALLAS}" -eq 0 ]]; then
  echo "E2E OK: todos los pasos pasaron."
else
  echo "E2E con ${FALLAS} falla(s). Revisa los pasos marcados FALLA."
  exit 1
fi
