"""Tests de la tabla CWE -> OWASP 2025 y la regla de prioridad (decisión mixta)."""

import json
from pathlib import Path

import pytest

from app.ia.owasp_por_cwe import (
    CATEGORIA_DISTINTA,
    CWE_FUERA_DE_TABLA,
    REGLA_PRIORIDAD,
    TABLA,
    _CWES_POR_CATEGORIA,
    evaluar,
    owasp_por_cwe,
    prioridad_por_severidad,
)
from app.models import CategoriaOwasp, Prioridad
from app.parsers.zap import parsear_reporte

FIXTURES = Path(__file__).resolve().parents[2] / "lab" / "fixtures"


# --- La tabla ---------------------------------------------------------------

def test_cantidades_por_categoria_segun_owasp():
    # "CWEs Mapped" de cada página de top10.owasp.org/2025
    esperado = {"A01:2025": 40, "A02:2025": 16, "A03:2025": 6, "A04:2025": 32,
                "A05:2025": 37, "A06:2025": 39, "A07:2025": 36, "A08:2025": 14,
                "A09:2025": 5, "A10:2025": 24}
    assert {k: len(v) for k, v in _CWES_POR_CATEGORIA.items()} == esperado


def test_ningun_cwe_en_dos_categorias():
    todos = [c for cwes in _CWES_POR_CATEGORIA.values() for c in cwes]
    assert len(todos) == len(set(todos)) == len(TABLA)


def test_categorias_validas_para_la_base():
    validas = {c.value for c in CategoriaOwasp}
    assert set(TABLA.values()) <= validas


@pytest.mark.parametrize("cwe, categoria", [
    (89, "A05:2025"),    # SQL Injection
    (79, "A05:2025"),    # XSS
    (601, "A01:2025"),   # External / Off-site Redirect
    (359, "A01:2025"),   # Information Disclosure - sessionStorage
    (497, "A01:2025"),   # Private IP / Timestamp Disclosure
    (598, "A06:2025"),   # Session ID in URL Rewrite
    (693, "A06:2025"),   # CSP Header Not Set, X-Content-Type-Options
    (1021, "A06:2025"),  # Missing Anti-clickjacking Header
])
def test_cwes_de_los_fixtures(cwe, categoria):
    assert owasp_por_cwe(cwe) == categoria


def test_cwe_264_no_esta_mapeado_en_2025():
    # Cross-Domain Misconfiguration (CORS). CWE-264 es una categoría antigua
    # de MITRE y OWASP 2025 no la incluye en ninguna lista.
    assert owasp_por_cwe(264) is None


@pytest.mark.parametrize("valor", [None, "", "0", 0, -1, "-1", "abc", True])
def test_sin_cwe(valor):
    assert owasp_por_cwe(valor) is None


def test_cwe_como_texto():
    assert owasp_por_cwe("89") == owasp_por_cwe(" 89 ") == "A05:2025"


# --- La regla de prioridad --------------------------------------------------

@pytest.mark.parametrize("severidad, prioridad", [
    ("High", "p1"), ("Medium", "p2"), ("Low", "p3"), ("Informational", "p4"),
    ("high", "p1"), (" MEDIUM ", "p2"),
])
def test_prioridad_por_severidad(severidad, prioridad):
    assert prioridad_por_severidad(severidad) == prioridad


@pytest.mark.parametrize("severidad", [None, "", "Critical", "3"])
def test_severidad_desconocida(severidad):
    assert prioridad_por_severidad(severidad) is None


def test_prioridades_validas_para_la_base():
    assert set(REGLA_PRIORIDAD.values()) == {p.value for p in Prioridad}


# --- La comparación regla / modelo ------------------------------------------

def test_coinciden_no_se_marca():
    r = evaluar(89, "High", "A05:2025")
    assert r == {"owasp_referencia": "A05:2025", "prioridad_regla": "p1",
                 "requiere_revision": False, "motivo_revision": None}


def test_distintos_se_marca():
    # El error típico del modelo: CSP en A05 (ver IA_MODELO_Y_PROMPT.md 5.3)
    r = evaluar(693, "Medium", "A05:2025")
    assert r["owasp_referencia"] == "A06:2025"
    assert r["requiere_revision"] is True
    assert r["motivo_revision"] == CATEGORIA_DISTINTA


def test_cwe_fuera_de_tabla_se_marca_aunque_el_modelo_responda():
    r = evaluar(264, "Medium", "A02:2025")
    assert r["owasp_referencia"] is None
    assert r["requiere_revision"] is True
    assert r["motivo_revision"] == CWE_FUERA_DE_TABLA


def test_sin_cwe_no_aplica_y_no_se_marca():
    r = evaluar(-1, "Informational", "A05:2025")
    assert r["owasp_referencia"] is None
    assert r["prioridad_regla"] == "p4"
    assert r["requiere_revision"] is False


def test_sin_enriquecer_no_se_marca():
    r = evaluar(89, "High", None)
    assert r["owasp_referencia"] == "A05:2025"
    assert r["requiere_revision"] is False


def test_acepta_el_enum_y_texto_sobrante():
    assert evaluar(89, "High", CategoriaOwasp.a05)["requiere_revision"] is False
    assert evaluar(89, "High", "a05:2025 Injection")["requiere_revision"] is False


# --- Los fixtures reales ----------------------------------------------------

@pytest.mark.parametrize("fixture", sorted(p.name for p in FIXTURES.glob("zap_*.json")))
def test_todos_los_hallazgos_de_los_fixtures(fixture):
    """Cada hallazgo obtiene prioridad, y solo CWE-264 queda fuera de tabla."""
    reporte = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    for h in parsear_reporte(reporte):
        r = evaluar(h["cwe_id"], h["severity_tool_raw"], None)
        assert r["prioridad_regla"] is not None, h["titulo"]
        if h["cwe_id"] and h["cwe_id"] > 0 and h["cwe_id"] != 264:
            assert r["owasp_referencia"] is not None, (h["cwe_id"], h["titulo"])
