"""
SentinelAI · Tests de GET /informe (T-058, T-059).

El informe en sí (secciones, orden, marca "Revisar", escape HTML) se prueba en
test_informe.py sin base. Acá se prueba que la API lo entrega: que elige el
objetivo, responde HTML y avisa con 404 cuando no hay qué informar.

Usan PostgreSQL (como test_ingesta.py).

    cd backend
    python -m pytest tests/test_informe_api.py -v

OJO: vacían las tablas. No los corras contra una base con datos que te importen.
"""

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

FIXTURE = Path(__file__).resolve().parents[2] / "lab" / "fixtures" / "zap_juiceshop_ajax_v2.json"
OBJETIVO = "http://juiceshop:3000"
SECCIONES = ("1. Resumen", "2. Escaneos de origen", "3. Hallazgos", "4. Descartados",
             "5. Calidad de la IA")
api = TestClient(app)


@pytest.fixture(autouse=True)
def base_vacia():
    with engine.begin() as c:
        c.execute(text(
            "TRUNCATE validations, ai_enrichments, finding_observations, "
            "finding_instances, findings, scans, targets CASCADE"
        ))
    yield


def _importar() -> dict:
    r = api.post("/scans/import", json=json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert r.status_code == 201, r.text
    return r.json()


def test_sin_escaneos_responde_404_con_un_mensaje_claro():
    r = api.get("/informe")
    assert r.status_code == 404
    assert "importa uno primero" in r.json()["detail"]


def test_entrega_el_informe_en_html_con_una_ficha_por_hallazgo():
    nuevos = _importar()["nuevos"]
    r = api.get("/informe")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    pagina = r.text
    for seccion in SECCIONES:
        assert seccion in pagina
    # Sin la comilla de cierre: las marcadas para revisar son class="hallazgo revisar".
    assert pagina.count('<article class="hallazgo') == nuevos


def test_objetivo_explicito_y_objetivo_que_no_existe():
    _importar()
    assert api.get("/informe", params={"objetivo": OBJETIVO}).status_code == 200
    r = api.get("/informe", params={"objetivo": "http://otro:8080"})
    assert r.status_code == 404
    assert "http://otro:8080" in r.json()["detail"]


def test_muestra_la_decision_humana_registrada():
    _importar()
    hallazgo = api.get("/findings", params={"limit": 1}).json()["items"][0]["id"]
    r = api.post(f"/findings/{hallazgo}/validaciones",
                 json={"decision": "confirmado", "revisor": "Revisora de prueba"})
    assert r.status_code == 201, r.text
    pagina = api.get("/informe").text
    assert "Revisora de prueba" in pagina


def test_es_el_mismo_informe_que_genera_la_linea_de_comandos():
    from app.db import SessionLocal
    from app.informe_consulta import elegir_objetivo, generar

    _importar()
    with SessionLocal() as db:
        html_script, _ = generar(db, elegir_objetivo(db))
    pagina = api.get("/informe").text
    # La fecha de generación cambia entre las dos llamadas; el resto debe ser igual.
    sin_fecha = lambda h: h.split("generado", 1)[1].split("</p>", 1)[1]  # noqa: E731
    assert sin_fecha(pagina) == sin_fecha(html_script)


def test_exporta_el_informe_en_csv_con_un_hallazgo_por_fila():
    nuevos = _importar()["nuevos"]
    r = api.get("/informe.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="informe_juiceshop-3000_' in r.headers["content-disposition"]
    lineas = r.content.decode("utf-8-sig").splitlines()
    assert lineas[0].startswith("N°,Sección,Título")
    import csv
    assert len(list(csv.reader(lineas))) == nuevos + 1


def test_exporta_el_informe_en_xlsx_con_tres_hojas():
    import io

    from openpyxl import load_workbook

    nuevos = _importar()["nuevos"]
    r = api.get("/informe.xlsx", params={"objetivo": OBJETIVO})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert r.headers["content-disposition"].endswith('.xlsx"')
    libro = load_workbook(io.BytesIO(r.content))
    assert libro.sheetnames == ["Resumen", "Hallazgos", "Escaneos"]
    assert libro["Hallazgos"].max_row == nuevos + 1


def test_exportar_sin_escaneos_responde_404():
    assert api.get("/informe.csv").status_code == 404
    assert api.get("/informe.xlsx").status_code == 404
