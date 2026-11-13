"""
SentinelAI · Tests del resumen de hallazgos y del filtro "revisar".

GET /findings/resumen y GET /findings?revisar=... calculan la marca
`requiere_revision` en SQL, mientras que cada hallazgo la trae calculada en
Python por evaluar() (app/ia/owasp_por_cwe.py). Estos tests comprueban que las
dos coinciden, que total y paginación son correctos y el orden del listado.

Usan PostgreSQL (como test_ingesta.py) y un cliente de Ollama falso.

    cd backend
    python -m pytest tests/test_resumen_filtros_api.py -v

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

from app.ia.cliente import Respuesta  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EstadoHallazgo, Severidad  # noqa: E402
from app.rutas import get_cliente  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "lab" / "fixtures"
TODOS = [
    "zap_juiceshop_baseline_v1.json",
    "zap_juiceshop_full_v1.json",
    "zap_juiceshop_ajax_v1.json",
    "zap_juiceshop_ajax_v2.json",
    "zap_juiceshop_ajax_auth_v1.json",
]
api = TestClient(app)

VALIDA = {
    "explicacion": "Explicación de prueba.",
    "impacto": "Impacto de prueba.",
    "owasp": "A05:2025",
    "prioridad": "p1",
    "confianza": 0.9,
    "remediacion": "Remediación de prueba.",
}
ORDEN_SEVERIDAD = [s.value for s in Severidad]


class ClienteFalso:
    """Responde siempre lo mismo."""

    def __init__(self, texto: str):
        self.texto = texto
        self.modelo = "modelo-falso"
        self.url = "http://falso"

    def generar(self, prompt):
        return Respuesta(texto=self.texto, latencia_ms=50)


@pytest.fixture(autouse=True)
def base_vacia():
    with engine.begin() as c:
        c.execute(text(
            "TRUNCATE validations, ai_enrichments, finding_observations, "
            "finding_instances, findings, scans, targets CASCADE"
        ))
    yield
    app.dependency_overrides.clear()


def _importar(*nombres: str) -> list[dict]:
    resultados = []
    for nombre in nombres or TODOS:
        crudo = json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))
        r = api.post("/scans/import", json=crudo)
        assert r.status_code == 201, r.text
        resultados.append(r.json())
    return resultados


def _id(titulo: str) -> str:
    items = api.get("/findings", params={"q": titulo, "limit": 200}).json()["items"]
    (encontrado,) = [i["id"] for i in items if i["titulo"] == titulo]
    return encontrado


def _enriquecer(titulo: str, owasp: str | None) -> None:
    """owasp=None simula tres respuestas inválidas: queda un fallo."""
    texto = "esto no es json" if owasp is None else json.dumps({**VALIDA, "owasp": owasp})
    app.dependency_overrides[get_cliente] = lambda: ClienteFalso(texto)
    r = api.post(f"/findings/{_id(titulo)}/enrich")
    assert r.status_code == 200, r.text


def _todos(**params) -> list[dict]:
    """Recorre el listado completo página por página."""
    items, offset = [], 0
    while True:
        d = api.get("/findings", params={**params, "limit": 5, "offset": offset}).json()
        items += d["items"]
        offset += 5
        if offset >= d["total"]:
            return items


def _escenario_completo() -> None:
    """Hallazgos en todos los estados que importan para la regla "revisar"."""
    _importar()
    _enriquecer("SQL Injection", "A05:2025")                  # CWE-89: igual a la tabla
    _enriquecer("External Redirect", "A05:2025")              # CWE-601 es A01: distinta
    _enriquecer("Off-site Redirect", None)                    # fallido, CWE en la tabla
    _enriquecer("Cross-Domain Misconfiguration", None)        # fallido, CWE fuera de la tabla
    _enriquecer("Modern Web Application", "A05:2025")         # sin CWE: nunca se marca
    _enriquecer("Missing Anti-clickjacking Header", "A02:2025")  # CWE-1021 es A06: distinta...
    _enriquecer("Missing Anti-clickjacking Header", None)     # ...y un fallo no la reemplaza
    # "Session ID in URL Rewrite" y el resto quedan sin enriquecer.


# ── Equivalencia SQL vs evaluar() ─────────────────────────────────────────

def test_el_filtro_sql_coincide_con_evaluar_en_todos_los_casos():
    _escenario_completo()

    todos = _todos()
    marcados = {i["id"] for i in _todos(revisar="true")}
    no_marcados = {i["id"] for i in _todos(revisar="false")}

    assert len(todos) == 18
    assert marcados.isdisjoint(no_marcados)
    assert marcados | no_marcados == {i["id"] for i in todos}
    for i in todos:
        esperado = i["referencia"]["requiere_revision"]  # calculado por evaluar()
        assert (i["id"] in marcados) is esperado, i["titulo"]

    # El escenario cubre los casos que se quieren comparar.
    por_titulo = {i["titulo"]: i for i in todos}

    def marcado(titulo):
        return por_titulo[titulo]["id"] in marcados

    assert not marcado("SQL Injection")
    assert marcado("External Redirect")
    assert not marcado("Off-site Redirect")
    assert marcado("Cross-Domain Misconfiguration")
    assert not marcado("Modern Web Application")
    assert marcado("Missing Anti-clickjacking Header")
    assert not marcado("Session ID in URL Rewrite")
    assert por_titulo["Off-site Redirect"]["ia"]["estado"] == "failed"
    assert por_titulo["Missing Anti-clickjacking Header"]["ia"]["estado"] == "ok"
    assert por_titulo["Session ID in URL Rewrite"]["ia"] is None


# ── Filtro revisar: total y paginación ────────────────────────────────────

def test_revisar_true_y_false_se_reparten_el_total():
    _escenario_completo()
    total = api.get("/findings").json()["total"]
    si = api.get("/findings", params={"revisar": "true"}).json()
    no = api.get("/findings", params={"revisar": "false"}).json()

    assert si["total"] == 3
    assert si["total"] + no["total"] == total
    assert all(i["referencia"]["requiere_revision"] for i in si["items"])
    assert not any(i["referencia"]["requiere_revision"] for i in no["items"])


def test_la_paginacion_de_revisar_no_repite_ni_pierde_hallazgos():
    _escenario_completo()
    total = api.get("/findings", params={"revisar": "true"}).json()["total"]

    vistos = []
    for offset in range(total + 1):
        d = api.get("/findings", params={"revisar": "true", "limit": 1, "offset": offset}).json()
        assert d["total"] == total
        vistos += [i["id"] for i in d["items"]]

    assert len(vistos) == total == len(set(vistos))


def test_revisar_se_combina_con_otros_filtros():
    _escenario_completo()
    d = api.get("/findings", params={"revisar": "true", "severidad": "alta"}).json()
    assert [i["titulo"] for i in d["items"]] == ["External Redirect"]
    assert d["total"] == 1


def test_revisar_invalido_da_422():
    assert api.get("/findings", params={"revisar": "quizas"}).status_code == 422


# ── Orden del listado ─────────────────────────────────────────────────────

def test_orden_severidad_despues_revisar_despues_ocurrencias():
    _importar()
    # Informativo con 1 ocurrencia y categoría distinta de la tabla (CWE-359 es A01).
    _enriquecer("Information Disclosure - Information in Browser localStorage", "A05:2025")

    items = _todos()
    claves = [
        (
            ORDEN_SEVERIDAD.index(i["severidad"]),
            not i["referencia"]["requiere_revision"],
            -i["ocurrencias"],
        )
        for i in items
    ]
    assert claves == sorted(claves)

    informativos = [i for i in items if i["severidad"] == "informativa"]
    primero = informativos[0]
    assert primero["titulo"] == "Information Disclosure - Information in Browser localStorage"
    assert primero["ocurrencias"] == 1
    assert max(i["ocurrencias"] for i in informativos) > 1, "pasa antes que otros con más ocurrencias"


# ── Resumen ───────────────────────────────────────────────────────────────

def test_resumen_con_la_base_vacia_trae_todas_las_claves_en_cero():
    r = api.get("/findings/resumen")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "total": 0,
        "por_severidad": {s.value: 0 for s in Severidad},
        "por_estado": {e.value: 0 for e in EstadoHallazgo},
        "revisar": 0,
        "sin_enriquecer": 0,
    }


def test_resumen_despues_de_importar():
    _importar()
    d = api.get("/findings/resumen").json()

    assert d["total"] == api.get("/findings").json()["total"] == 18
    assert sum(d["por_severidad"].values()) == d["total"]
    assert sum(d["por_estado"].values()) == d["total"]
    assert d["por_severidad"]["alta"] == 3
    assert d["por_estado"]["nuevo"] == 18
    assert d["sin_enriquecer"] == 18
    assert d["revisar"] == 1, "sin IA solo se marca el CWE fuera de la tabla (Cross-Domain)"


def test_resumen_cuenta_revisar_y_sin_enriquecer():
    _escenario_completo()
    d = api.get("/findings/resumen").json()

    # Enriquecidos ok: SQL Injection, External Redirect, Modern Web Application
    # y Anti-clickjacking (su fallo posterior no reemplaza al ok).
    assert d["sin_enriquecer"] == 18 - 4, "un fallido sigue contando como sin enriquecer"
    assert d["revisar"] == 3


@pytest.mark.parametrize("filtros", [
    {},
    {"severidad": "media"},
    {"severidad": ["alta", "baja"]},
    {"con_ia": "true"},
    {"con_ia": "false"},
    {"revisar": "true"},
    {"revisar": "false", "severidad": "media"},
    {"q": "Disclosure"},
    {"owasp": "A05:2025"},
    {"estado": "nuevo"},
])
def test_resumen_y_listado_cuentan_lo_mismo_con_los_mismos_filtros(filtros):
    escaneos = _importar()
    _enriquecer("SQL Injection", "A05:2025")
    _enriquecer("External Redirect", "A05:2025")
    _enriquecer("Off-site Redirect", None)

    for extra in ({}, {"scan_id": escaneos[0]["scan_id"]}):
        params = {**filtros, **extra}
        resumen = api.get("/findings/resumen", params=params).json()
        listado = _todos(**params)

        assert resumen["total"] == len(listado)
        assert resumen["revisar"] == sum(i["referencia"]["requiere_revision"] for i in listado)
        assert resumen["sin_enriquecer"] == sum(
            i["ia"] is None or i["ia"]["estado"] == "failed" for i in listado
        )
        for s in Severidad:
            assert resumen["por_severidad"][s.value] == sum(
                i["severidad"] == s.value for i in listado
            )


def test_resumen_no_choca_con_el_detalle_de_un_hallazgo():
    _importar("zap_juiceshop_ajax_v2.json")
    assert api.get("/findings/resumen").status_code == 200
    sqli = _id("SQL Injection")
    assert api.get(f"/findings/{sqli}").json()["titulo"] == "SQL Injection"
