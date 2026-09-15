"""
SentinelAI · Tests del parser de ZAP

Estos tests SON la especificación. Cuando todos pasen, el parser está listo.

    cd backend
    pytest tests/test_zap_parser.py -v

Sugerencia: ve de a uno. Corre un solo test con
    pytest tests/test_zap_parser.py::test_a_entero_convierte -v
"""

import pytest

from app.parsers.zap import (
    _a_entero,
    _extraer_instancias,
    parsear_alerta,
    parsear_reporte,
)

# ── Datos de prueba con forma real de ZAP ─────────────────────────────────

ALERTA_XSS = {
    "pluginid": "40012",
    "alertRef": "40012",
    "alert": "Cross Site Scripting (Reflected)",
    "name": "Cross Site Scripting (Reflected)",
    "riskcode": "3",
    "confidence": "2",
    "riskdesc": "High (Medium)",
    "desc": "<p>Cross-site Scripting (XSS) es una tecnica de ataque...</p>",
    "instances": [
        {
            "uri": "http://juiceshop:3000/rest/products/search?q=%3Cscript%3E",
            "method": "GET",
            "param": "q",
            "attack": "<script>alert(1)</script>",
            "evidence": "<script>alert(1)</script>",
        },
        {
            "uri": "http://juiceshop:3000/rest/products/search?q=%3Cimg%3E",
            "method": "GET",
            "param": "q",
            "attack": "<img src=x onerror=alert(1)>",
            "evidence": "<img src=x onerror=alert(1)>",
        },
    ],
    "count": "2",
    "solution": "<p>Usar una libreria probada...</p>",
    "cweid": "79",
    "wascid": "8",
    "sourceid": "1",
}

ALERTA_SIN_CWE = {
    "pluginid": "10109",
    "alert": "Modern Web Application",
    "riskcode": "0",
    "confidence": "3",
    "desc": "La aplicacion parece ser una aplicacion web moderna.",
    "instances": [
        {"uri": "http://juiceshop:3000/", "method": "GET", "param": "", "evidence": ""}
    ],
    "count": "1",
    "cweid": "",
    "wascid": "",
}

ALERTA_SIN_INSTANCIAS = {
    "pluginid": "99999",
    "alert": "Alerta rota",
    "riskcode": "2",
    "confidence": "1",
    "instances": [],
    "count": "0",
    "cweid": "200",
}

REPORTE = {
    "@version": "2.17.0",
    "@generated": "Thu, 11 Sep 2026 20:42:24",
    "site": [
        {
            "@name": "http://juiceshop:3000",
            "@host": "juiceshop",
            "@port": "3000",
            "alerts": [ALERTA_XSS, ALERTA_SIN_CWE, ALERTA_SIN_INSTANCIAS],
        }
    ],
}

CLAVES_OBLIGATORIAS = {
    "rule_id", "rule_name", "titulo", "descripcion", "url", "path_template",
    "method", "param", "evidence_snippet", "severity", "severity_tool_raw",
    "tool_confidence", "cwe_id", "wasc_id", "dedupe_key", "correlation_key",
    "occurrences", "source_raw", "instances",
}


# ── _a_entero ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("entrada,esperado", [
    ("79", 79),
    (79, 79),
    ("", None),
    (None, None),
    ("-1", None),
    ("0", None),
])
def test_a_entero_convierte(entrada, esperado):
    assert _a_entero(entrada) == esperado


# ── _extraer_instancias ───────────────────────────────────────────────────

def test_extraer_instancias_renombra_uri_a_url():
    inst = _extraer_instancias(ALERTA_XSS)
    assert len(inst) == 2
    assert inst[0]["url"] == "http://juiceshop:3000/rest/products/search?q=%3Cscript%3E"
    assert inst[0]["method"] == "GET"
    assert inst[0]["param"] == "q"
    assert "uri" not in inst[0], "la clave debe ser 'url', no 'uri'"


def test_extraer_instancias_lista_vacia_si_no_hay():
    assert _extraer_instancias(ALERTA_SIN_INSTANCIAS) == []


def test_extraer_instancias_recorta_a_50():
    alerta = {"instances": [
        {"uri": f"http://juiceshop:3000/p/{i}", "method": "GET", "param": ""}
        for i in range(120)
    ]}
    assert len(_extraer_instancias(alerta)) == 50


# ── parsear_alerta ────────────────────────────────────────────────────────

def test_parsear_alerta_devuelve_todas_las_claves():
    h = parsear_alerta(ALERTA_XSS)
    assert set(h.keys()) == CLAVES_OBLIGATORIAS, (
        f"faltan: {CLAVES_OBLIGATORIAS - set(h.keys())} | "
        f"sobran: {set(h.keys()) - CLAVES_OBLIGATORIAS}"
    )


def test_parsear_alerta_mapea_severidad():
    h = parsear_alerta(ALERTA_XSS)
    assert h["severity"] == "alta"
    assert h["severity_tool_raw"] == "High"


def test_parsear_alerta_informativa():
    h = parsear_alerta(ALERTA_SIN_CWE)
    assert h["severity"] == "informativa"


def test_parsear_alerta_cwe_es_entero():
    h = parsear_alerta(ALERTA_XSS)
    assert h["cwe_id"] == 79
    assert isinstance(h["cwe_id"], int)


def test_parsear_alerta_sin_cwe_es_none():
    h = parsear_alerta(ALERTA_SIN_CWE)
    assert h["cwe_id"] is None
    assert h["correlation_key"] is None, "sin CWE no hay clave de correlación"


def test_parsear_alerta_agrupa_instancias():
    """Dos instancias del mismo problema = UN hallazgo con occurrences=2."""
    h = parsear_alerta(ALERTA_XSS)
    assert h["occurrences"] == 2
    assert len(h["instances"]) == 2


def test_parsear_alerta_conserva_source_raw_intacto():
    h = parsear_alerta(ALERTA_XSS)
    assert h["source_raw"] == ALERTA_XSS, "source_raw no se modifica, jamás"


def test_parsear_alerta_sin_instancias_devuelve_none():
    assert parsear_alerta(ALERTA_SIN_INSTANCIAS) is None


def test_parsear_alerta_dedupe_key_tiene_formato():
    h = parsear_alerta(ALERTA_XSS)
    assert len(h["dedupe_key"]) == 16
    assert all(c in "0123456789abcdef" for c in h["dedupe_key"])


def test_parsear_alerta_dedupe_key_es_determinista():
    a = parsear_alerta(ALERTA_XSS)
    b = parsear_alerta(ALERTA_XSS)
    assert a["dedupe_key"] == b["dedupe_key"]


def test_parsear_alerta_normaliza_la_ruta():
    h = parsear_alerta(ALERTA_XSS)
    assert h["path_template"] == "/rest/products/search?q"


def test_parsear_alerta_confianza():
    h = parsear_alerta(ALERTA_XSS)
    assert h["tool_confidence"] == "medium"   # confidence "2" en ZAP


# ── parsear_reporte ───────────────────────────────────────────────────────

def test_parsear_reporte_descarta_alertas_sin_instancias():
    hallazgos = parsear_reporte(REPORTE)
    assert len(hallazgos) == 2, "la alerta sin instancias no debe aparecer"


def test_parsear_reporte_recorre_varios_sites():
    reporte = {
        "site": [
            {"@name": "http://a:3000", "alerts": [ALERTA_XSS]},
            {"@name": "http://b:3000", "alerts": [ALERTA_SIN_CWE]},
        ]
    }
    assert len(parsear_reporte(reporte)) == 2


def test_parsear_reporte_sin_alertas():
    assert parsear_reporte({"site": [{"@name": "http://a", "alerts": []}]}) == []


def test_parsear_reporte_claves_unicas():
    """Dos hallazgos distintos no pueden compartir dedupe_key."""
    hallazgos = parsear_reporte(REPORTE)
    claves = [h["dedupe_key"] for h in hallazgos]
    assert len(claves) == len(set(claves))
