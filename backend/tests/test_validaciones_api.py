"""
SentinelAI · Tests de la validación humana (T-057).

POST /findings/{id}/validaciones guarda la decisión de una persona y deja el
estado del hallazgo en la misma transacción. Usan PostgreSQL y un cliente de
Ollama falso (como test_enriquecimiento_api.py).

    cd backend
    python -m pytest tests/test_validaciones_api.py -v

OJO: vacían las tablas. No los corras contra una base con datos que te importen.
"""

import json
import uuid
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

from app.ia.cliente import Respuesta  # noqa: E402
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


class ClienteFalso:
    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.modelo = "modelo-falso"
        self.url = "http://falso"

    def generar(self, prompt):
        return Respuesta(texto=self.respuesta, latencia_ms=100)


@pytest.fixture(autouse=True)
def base_vacia():
    with engine.begin() as c:
        c.execute(text(
            "TRUNCATE validations, ai_enrichments, finding_observations, "
            "finding_instances, findings, scans, targets CASCADE"
        ))
    crudo = json.loads((FIXTURES / "zap_juiceshop_ajax_v2.json").read_text(encoding="utf-8"))
    assert api.post("/scans/import", json=crudo).status_code == 201
    yield
    app.dependency_overrides.clear()


def _id(titulo: str) -> str:
    items = api.get("/findings", params={"q": titulo}).json()["items"]
    return next(i["id"] for i in items if i["titulo"] == titulo)


def _enriquecer(finding_id: str, respuesta: str | None = None) -> dict:
    app.dependency_overrides[get_cliente] = lambda: ClienteFalso(respuesta or json.dumps(VALIDA))
    r = api.post(f"/findings/{finding_id}/enrich")
    assert r.status_code == 200, r.text
    return r.json()


def _id_sugerencia(finding_id: str) -> str:
    with engine.connect() as c:
        return str(c.scalar(text(
            "SELECT id FROM ai_enrichments WHERE finding_id = :f AND is_current"
        ), {"f": finding_id}))


def _estado(finding_id: str) -> str:
    with engine.connect() as c:
        return c.scalar(text("SELECT status FROM findings WHERE id = :f"), {"f": finding_id})


def _validar(finding_id: str, **cuerpo):
    return api.post(
        f"/findings/{finding_id}/validaciones",
        json={"decision": "confirmado", "revisor": "Felipe", **cuerpo},
    )


# ── Caso feliz ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("decision", "estado"),
    [
        ("confirmado", "confirmado"),
        ("falso_positivo", "falso_positivo"),
        ("riesgo_aceptado", "riesgo_aceptado"),
        ("duplicado", "duplicado"),
        ("requiere_segunda_opinion", "en_triage"),
    ],
)
def test_cada_decision_crea_la_validacion_y_cambia_el_estado(decision, estado):
    f = _id("SQL Injection")
    assert _estado(f) == "nuevo"

    r = _validar(f, decision=decision, comentario="Revisado a mano.")
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["estado"] == estado
    assert d["validacion"]["decision"] == decision
    assert d["validacion"]["revisor"] == "Felipe"
    assert d["validacion"]["comentario"] == "Revisado a mano."
    assert _estado(f) == estado

    detalle = api.get(f"/findings/{f}").json()
    assert detalle["estado"] == estado
    assert [v["decision"] for v in detalle["validaciones"]] == [decision]


def test_guarda_la_sugerencia_juzgada_y_las_banderas():
    f = _id("SQL Injection")
    _enriquecer(f)
    sugerencia = _id_sugerencia(f)

    r = _validar(
        f,
        enrichment_id=sugerencia,
        prioridad_corregida="p2",
        ai_owasp_correcto=True,
        ai_prioridad_correcta=False,
        ai_remediacion_util=None,
        ai_alucinacion=False,
        ai_nota="  La prioridad es alta, no crítica.  ",
    )
    assert r.status_code == 201, r.text
    v = r.json()["validacion"]
    assert v["enrichment_id"] == sugerencia
    assert v["prioridad_corregida"] == "p2"
    assert (v["ai_owasp_correcto"], v["ai_prioridad_correcta"]) == (True, False)
    assert v["ai_remediacion_util"] is None  # "no sé"
    assert v["ai_alucinacion"] is False
    assert v["ai_nota"] == "La prioridad es alta, no crítica."


def test_el_revisor_se_guarda_sin_espacios_al_borde_y_el_comentario_vacio_es_null():
    f = _id("SQL Injection")
    r = _validar(f, revisor="  Joaquín  ", comentario="   ")
    assert r.status_code == 201, r.text
    assert r.json()["validacion"]["revisor"] == "Joaquín"
    assert r.json()["validacion"]["comentario"] is None


def test_decidir_sin_ia_no_necesita_enrichment_id():
    f = _id("SQL Injection")
    r = _validar(f, decision="falso_positivo")
    assert r.status_code == 201, r.text
    assert r.json()["validacion"]["enrichment_id"] is None


def test_dos_validaciones_dejan_el_estado_de_la_mas_reciente():
    f = _id("SQL Injection")
    assert _validar(f, decision="requiere_segunda_opinion", revisor="Felipe").status_code == 201
    assert _estado(f) == "en_triage"
    assert _validar(f, decision="confirmado", revisor="Joaquín").status_code == 201
    assert _estado(f) == "confirmado"

    historial = api.get(f"/findings/{f}").json()["validaciones"]
    # El detalle las trae de la más reciente a la más antigua.
    assert [(v["decision"], v["revisor"]) for v in historial] == [
        ("confirmado", "Joaquín"),
        ("requiere_segunda_opinion", "Felipe"),
    ]


# ── Errores ───────────────────────────────────────────────────────────────

def test_hallazgo_inexistente_da_404():
    r = _validar(str(uuid.uuid4()))
    assert r.status_code == 404
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM validations")) == 0


def test_sugerencia_vieja_da_409_y_no_guarda_nada():
    f = _id("SQL Injection")
    _enriquecer(f)
    vieja = _id_sugerencia(f)
    _enriquecer(f)  # alguien vuelve a enriquecer mientras la persona decide
    nueva = _id_sugerencia(f)
    assert nueva != vieja

    r = _validar(f, enrichment_id=vieja, ai_owasp_correcto=True)
    assert r.status_code == 409, r.text
    assert "recarga" in r.json()["detail"]["error"]
    assert r.json()["detail"]["enrichment_vigente"] == nueva
    assert _estado(f) == "nuevo"
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM validations")) == 0


@pytest.mark.parametrize("revisor", ["", "   ", "x" * 121])
def test_revisor_vacio_o_muy_largo_da_422(revisor):
    f = _id("SQL Injection")
    r = _validar(f, revisor=revisor)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == "revisor"
    assert _estado(f) == "nuevo"


def test_revisor_es_obligatorio():
    f = _id("SQL Injection")
    r = api.post(f"/findings/{f}/validaciones", json={"decision": "confirmado"})
    assert r.status_code == 422


def test_sugerencia_de_otro_hallazgo_da_422():
    f = _id("SQL Injection")
    otro = _id("Private IP Disclosure")
    _enriquecer(otro)

    r = _validar(f, enrichment_id=_id_sugerencia(otro))
    assert r.status_code == 422
    assert r.json()["detail"]["campo"] == "enrichment_id"


def test_sugerencia_inexistente_da_422():
    f = _id("SQL Injection")
    r = _validar(f, enrichment_id=str(uuid.uuid4()))
    assert r.status_code == 422


@pytest.mark.parametrize(
    "bandera",
    [
        {"ai_owasp_correcto": True},
        {"ai_prioridad_correcta": False},
        {"ai_remediacion_util": True},
        {"ai_alucinacion": False},
        {"ai_nota": "El modelo inventó un parámetro."},
    ],
)
def test_banderas_ai_sin_ia_dan_422(bandera):
    f = _id("SQL Injection")  # sin enriquecer
    r = _validar(f, **bandera)
    assert r.status_code == 422
    assert r.json()["detail"]["campo"] == "ai_owasp_correcto"
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM validations")) == 0


def test_banderas_ai_sobre_un_intento_fallido_dan_422():
    f = _id("SQL Injection")
    _enriquecer(f, respuesta="esto no es JSON")  # 3 intentos inválidos: queda failed
    fallida = _id_sugerencia(f)

    r = _validar(f, enrichment_id=fallida, ai_alucinacion=True)
    assert r.status_code == 422
    # Decidir sobre el hallazgo, sin opinar de la IA, sí se puede.
    assert _validar(f, enrichment_id=fallida).status_code == 201


def test_banderas_ai_sin_enrichment_id_dan_422_aunque_haya_ia():
    f = _id("SQL Injection")
    _enriquecer(f)
    r = _validar(f, ai_owasp_correcto=True)
    assert r.status_code == 422


def test_campos_desconocidos_dan_422():
    f = _id("SQL Injection")
    r = _validar(f, estado="remediado")
    assert r.status_code == 422
