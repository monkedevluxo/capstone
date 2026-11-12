"""
SentinelAI · Tests del enriquecimiento desde la API (T-032, T-035).

Usan PostgreSQL (como test_ingesta.py) y un cliente de Ollama falso: no
necesitan GPU ni Ollama, así que corren en el CI.

    cd backend
    python -m pytest tests/test_enriquecimiento_api.py -v

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

from app.ia.cliente import OllamaNoDisponible, Respuesta  # noqa: E402
from app.ia.prompt import PROMPT_VERSION  # noqa: E402
from app.main import app  # noqa: E402
from app.rutas import get_cliente  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "lab" / "fixtures"
api = TestClient(app)

VALIDA = {
    "explicacion": "La entrada del usuario llega sin filtrar a la consulta SQL.",
    "impacto": "Un atacante podría leer o modificar datos de la base.",
    "owasp": "A05:2025",
    "prioridad": "p1",
    "confianza": 0.9,
    "remediacion": "Usar consultas parametrizadas.",
}


def _json(**cambios) -> str:
    return json.dumps({**VALIDA, **cambios})


class ClienteFalso:
    """Responde siempre lo mismo, o lanza la excepción que se le pase."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamadas = 0
        self.modelo = "modelo-falso"
        self.url = "http://falso"

    def generar(self, prompt):
        self.llamadas += 1
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return Respuesta(texto=self.respuesta, latencia_ms=120)


def _usar(cliente: ClienteFalso) -> ClienteFalso:
    app.dependency_overrides[get_cliente] = lambda: cliente
    return cliente


@pytest.fixture(autouse=True)
def base_vacia():
    with engine.begin() as c:
        c.execute(text(
            "TRUNCATE validations, ai_enrichments, finding_observations, "
            "finding_instances, findings, scans, targets CASCADE"
        ))
    yield
    app.dependency_overrides.clear()


def _importar(nombre: str = "zap_juiceshop_ajax_v2.json") -> dict:
    crudo = json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))
    r = api.post("/scans/import", json=crudo)
    assert r.status_code == 201, r.text
    return r.json()


def _id(titulo: str) -> str:
    items = api.get("/findings", params={"q": titulo}).json()["items"]
    return next(i["id"] for i in items if i["titulo"] == titulo)


def _filas(finding_id: str) -> list[dict]:
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(
            "SELECT * FROM ai_enrichments WHERE finding_id = :f ORDER BY generated_at, id"
        ), {"f": finding_id})]


# ── Un hallazgo ───────────────────────────────────────────────────────────

def test_enriquece_y_guarda_la_trazabilidad():
    _importar()
    _usar(ClienteFalso(_json()))
    sqli = _id("SQL Injection")

    r = api.post(f"/findings/{sqli}/enrich")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["vigente"] is True
    assert d["ia"]["estado"] == "ok"
    assert d["ia"]["owasp"] == "A05:2025"
    assert d["ia"]["explicacion"].startswith("La entrada")

    (fila,) = _filas(sqli)
    assert fila["model"] == "modelo-falso"
    assert fila["prompt_version"] == PROMPT_VERSION
    assert len(fila["prompt_sha256"]) == 64
    assert fila["attempts"] == 1
    assert fila["latency_ms"] == 120
    assert fila["generated_at"] is not None
    assert fila["is_current"] is True


def test_el_detalle_muestra_la_capa_de_ia_guardada():
    _importar()
    _usar(ClienteFalso(_json()))
    sqli = _id("SQL Injection")
    api.post(f"/findings/{sqli}/enrich")

    d = api.get(f"/findings/{sqli}").json()
    assert d["ia"]["estado"] == "ok"
    assert d["ia"]["modelo"] == "modelo-falso"
    assert d["origen"]["name"] == "SQL Injection", "la evidencia original sigue intacta"


def test_reenriquecer_agrega_historia_y_deja_una_sola_vigente():
    _importar()
    _usar(ClienteFalso(_json()))
    sqli = _id("SQL Injection")
    api.post(f"/findings/{sqli}/enrich")
    api.post(f"/findings/{sqli}/enrich")

    filas = _filas(sqli)
    assert len(filas) == 2
    assert [f["is_current"] for f in filas] == [False, True]


def test_tres_respuestas_invalidas_quedan_como_fallo_sin_datos():
    _importar()
    cliente = _usar(ClienteFalso("esto no es json"))
    sqli = _id("SQL Injection")

    d = api.post(f"/findings/{sqli}/enrich").json()
    assert cliente.llamadas == 3
    assert d["ia"]["estado"] == "failed"
    assert d["ia"]["motivo_fallo"] == "json_invalido"
    assert d["vigente"] is True, "sin un ok previo, el fallo queda vigente: se ve 'sin enriquecer'"

    (fila,) = _filas(sqli)
    assert fila["explanation"] is None and fila["owasp_category"] is None
    item = next(i for i in api.get("/findings", params={"con_ia": "false"}).json()["items"]
                if i["id"] == sqli)
    assert item["ia"]["estado"] == "failed"


def test_un_fallo_no_borra_un_enriquecimiento_valido():
    _importar()
    sqli = _id("SQL Injection")
    _usar(ClienteFalso(_json()))
    api.post(f"/findings/{sqli}/enrich")

    _usar(ClienteFalso("esto no es json"))
    d = api.post(f"/findings/{sqli}/enrich").json()
    assert d["ia"]["estado"] == "failed"
    assert d["vigente"] is False

    filas = _filas(sqli)
    assert len(filas) == 2, "el intento fallido igual queda en el historial"
    vigentes = [f for f in filas if f["is_current"]]
    assert len(vigentes) == 1 and vigentes[0]["state"] == "ok"
    assert api.get(f"/findings/{sqli}").json()["ia"]["estado"] == "ok"


def test_ollama_apagado_da_503_y_no_guarda_nada():
    _importar()
    _usar(ClienteFalso(OllamaNoDisponible("sin conexión")))
    sqli = _id("SQL Injection")

    r = api.post(f"/findings/{sqli}/enrich")
    assert r.status_code == 503
    assert r.json()["detail"]["motivo"] == "ollama_no_disponible"
    assert _filas(sqli) == []


def test_hallazgo_inexistente_da_404():
    _usar(ClienteFalso(_json()))
    r = api.post("/findings/00000000-0000-0000-0000-000000000000/enrich")
    assert r.status_code == 404


# ── Opción mixta ──────────────────────────────────────────────────────────

def test_referencia_por_tabla_y_prioridad_por_regla():
    _importar()
    _usar(ClienteFalso(_json()))
    sqli = _id("SQL Injection")

    ref = api.post(f"/findings/{sqli}/enrich").json()["referencia"]
    assert ref["owasp_referencia"] == "A05:2025"
    assert ref["prioridad_regla"] == "p1"
    assert ref["requiere_revision"] is False


def test_si_el_modelo_discrepa_de_la_tabla_se_marca_para_revisar():
    _importar()
    _usar(ClienteFalso(_json(owasp="A01:2025")))
    sqli = _id("SQL Injection")
    api.post(f"/findings/{sqli}/enrich")

    ref = api.get(f"/findings/{sqli}").json()["referencia"]
    assert ref["requiere_revision"] is True
    assert ref["motivo_revision"] == "categoria_distinta"


def test_el_listado_trae_la_referencia_aunque_no_haya_ia():
    _importar()
    items = api.get("/findings").json()["items"]
    assert all("referencia" in i for i in items)
    sqli = next(i for i in items if i["titulo"] == "SQL Injection")
    assert sqli["ia"] is None
    assert sqli["referencia"]["prioridad_regla"] == "p1"
    assert sqli["referencia"]["requiere_revision"] is False


# ── Un escaneo completo ───────────────────────────────────────────────────

def test_enriquece_todos_los_hallazgos_de_un_escaneo():
    escaneo = _importar()
    cliente = _usar(ClienteFalso(_json()))

    d = api.post(f"/scans/{escaneo['scan_id']}/enrich").json()
    assert d["procesados"] == 13
    assert d["enriquecidos"] == 13
    assert d["detenido_por"] is None
    assert cliente.llamadas == 13
    assert api.get("/findings", params={"con_ia": "false"}).json()["total"] == 0


def test_un_segundo_lote_se_salta_los_ya_enriquecidos():
    escaneo = _importar()
    _usar(ClienteFalso(_json()))
    api.post(f"/scans/{escaneo['scan_id']}/enrich")

    cliente = _usar(ClienteFalso(_json()))
    d = api.post(f"/scans/{escaneo['scan_id']}/enrich").json()
    assert d["procesados"] == 0
    assert d["omitidos"] == 13
    assert cliente.llamadas == 0


def test_lote_con_ollama_apagado_da_503():
    escaneo = _importar()
    _usar(ClienteFalso(OllamaNoDisponible("sin conexión")))
    r = api.post(f"/scans/{escaneo['scan_id']}/enrich")
    assert r.status_code == 503
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM ai_enrichments")) == 0


def test_lote_de_escaneo_inexistente_da_404():
    _usar(ClienteFalso(_json()))
    r = api.post("/scans/00000000-0000-0000-0000-000000000000/enrich")
    assert r.status_code == 404
