"""
SentinelAI · Tests de la ingesta y la consulta de hallazgos.

Necesitan PostgreSQL con las migraciones aplicadas (los corre el job
"Migraciones y restricciones" del CI). Sin base disponible, se saltan.

    cd backend
    python -m pytest tests/test_ingesta.py -v

OJO: vacían las tablas. No los corras contra una base con datos que te importen.
"""

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db import engine

try:
    with engine.connect() as _c:
        _c.execute(text("SELECT 1 FROM findings LIMIT 1"))
except Exception:  # noqa: BLE001
    pytest.skip("sin PostgreSQL migrado disponible", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "lab" / "fixtures"
cliente = TestClient(app)


def _cargar(nombre: str) -> dict:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def base_vacia():
    with engine.begin() as c:
        c.execute(text(
            "TRUNCATE validations, ai_enrichments, finding_observations, "
            "finding_instances, findings, scans, targets CASCADE"
        ))
    yield


def _contar(tabla: str) -> int:
    with engine.connect() as c:
        return c.scalar(text(f"SELECT count(*) FROM {tabla}"))


# ── Ingesta ───────────────────────────────────────────────────────────────

def test_importa_un_reporte_real():
    r = cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["objetivo"] == "http://juiceshop:3000"
    assert d["nuevos"] == 13
    assert d["repetidos"] == 0
    assert _contar("findings") == 13
    assert _contar("scans") == 1


def test_el_mismo_reporte_no_se_importa_dos_veces():
    crudo = _cargar("zap_juiceshop_ajax_v2.json")
    primero = cliente.post("/scans/import", json=crudo).json()
    r = cliente.post("/scans/import", json=crudo)
    assert r.status_code == 409
    assert r.json()["detail"]["scan_id"] == primero["scan_id"]
    assert _contar("scans") == 1


def test_un_segundo_escaneo_no_duplica_hallazgos():
    a = cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json")).json()
    b = cliente.post("/scans/import", json=_cargar("zap_juiceshop_full_v1.json")).json()
    assert b["repetidos"] > 0, "los escaneos comparten hallazgos y deben reconocerse"
    assert _contar("findings") == a["nuevos"] + b["nuevos"]
    assert _contar("scans") == 2
    assert _contar("targets") == 1, "mismo objetivo, un solo registro"


def test_rechaza_objetivos_fuera_del_laboratorio():
    crudo = copy.deepcopy(_cargar("zap_juiceshop_ajax_v2.json"))
    crudo["site"][0]["@name"] = "https://www.ejemplo.cl"
    r = cliente.post("/scans/import", json=crudo)
    assert r.status_code == 403
    assert _contar("scans") == 0
    assert _contar("findings") == 0


def test_rechaza_un_json_que_no_es_de_zap():
    r = cliente.post("/scans/import", json={"hola": "mundo"})
    assert r.status_code == 422
    assert _contar("scans") == 0


def test_la_evidencia_original_se_guarda_intacta():
    crudo = _cargar("zap_juiceshop_ajax_v2.json")
    cliente.post("/scans/import", json=crudo)
    sqli = cliente.get("/findings", params={"q": "SQL"}).json()["items"][0]
    detalle = cliente.get(f"/findings/{sqli['id']}").json()
    original = next(a for a in crudo["site"][0]["alerts"] if a["pluginid"] == "40018")
    assert detalle["origen"] == original
    assert len(detalle["instancias"]) <= 50


# ── Consulta ──────────────────────────────────────────────────────────────

def test_ordena_por_severidad():
    cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    items = cliente.get("/findings").json()["items"]
    orden = {"critica": 0, "alta": 1, "media": 2, "baja": 3, "informativa": 4}
    rangos = [orden[i["severidad"]] for i in items]
    assert rangos == sorted(rangos)


def test_filtra_por_severidad():
    cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    d = cliente.get("/findings", params={"severidad": "alta"}).json()
    assert d["total"] == 3
    assert {i["severidad"] for i in d["items"]} == {"alta"}


def test_filtra_por_escaneo():
    cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    b = cliente.post("/scans/import", json=_cargar("zap_juiceshop_full_v1.json")).json()
    d = cliente.get("/findings", params={"scan_id": b["scan_id"]}).json()
    assert d["total"] == b["nuevos"] + b["repetidos"]


def test_sin_enriquecer_aparece_sin_ia():
    cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    d = cliente.get("/findings", params={"con_ia": "false"}).json()
    assert d["total"] == 13
    assert all(i["ia"] is None for i in d["items"])


def test_paginacion():
    cliente.post("/scans/import", json=_cargar("zap_juiceshop_ajax_v2.json"))
    p1 = cliente.get("/findings", params={"limit": 5}).json()
    p2 = cliente.get("/findings", params={"limit": 5, "offset": 5}).json()
    assert p1["total"] == p2["total"] == 13
    assert not {i["id"] for i in p1["items"]} & {i["id"] for i in p2["items"]}


def test_hallazgo_inexistente_da_404():
    r = cliente.get("/findings/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
