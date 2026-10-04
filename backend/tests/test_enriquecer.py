"""
SentinelAI · Tests del enriquecimiento con IA (T-028 a T-031).

No necesitan Ollama: usan un cliente falso que devuelve respuestas guionadas.
Así se prueban justo los casos difíciles (JSON roto, categoría de 2021,
timeouts) que con el modelo real aparecen solo de vez en cuando.

    cd backend
    python -m pytest tests/test_enriquecer.py -v
"""

import json

import pytest

from app.ia.cliente import OllamaNoDisponible, OllamaTimeout, Respuesta
from app.ia.enriquecer import enriquecer
from app.ia.esquema import validar
from app.ia.prompt import PROMPT_VERSION, construir_prompt, datos_para_el_modelo

# ── Datos de prueba ───────────────────────────────────────────────────────

HALLAZGO = {   # forma de la salida de parsear_alerta()
    "rule_id": "10038",
    "titulo": "Content Security Policy (CSP) Header Not Set",
    "descripcion": "<p>Content Security Policy (CSP) is an added layer...</p>",
    "url": "http://juiceshop:3000",
    "param": None,
    "evidence_snippet": None,
    "severity": "media",
    "severity_tool_raw": "Medium",
    "cwe_id": 693,
    "dedupe_key": "0123456789abcdef",
    "source_raw": {"pluginid": "10038"},
}

VALIDA = {
    "explicacion": "El servidor no envia la cabecera Content-Security-Policy.",
    "impacto": "Falta una defensa en profundidad contra XSS.",
    "owasp": "A02:2025",
    "prioridad": "p3",
    "confianza": 0.7,
    "remediacion": "Agregar la cabecera Content-Security-Policy con default-src 'self'.",
}

CAMPOS_CONTENIDO = ("explanation", "impact", "owasp_category", "priority",
                    "confidence", "remediation_summary", "remediation_steps")


def _json(**cambios):
    return json.dumps({**VALIDA, **cambios})


class ClienteFalso:
    """Devuelve, en orden, lo que se le pase: texto o una excepción."""

    def __init__(self, *guion):
        self.guion = list(guion)
        self.prompts = []
        self.modelo = "modelo-falso"
        self.url = "http://falso"

    def generar(self, prompt):
        self.prompts.append(prompt)
        siguiente = self.guion.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return Respuesta(texto=siguiente, latencia_ms=100)


def _enriquecer(*guion):
    cliente = ClienteFalso(*guion)
    return enriquecer(HALLAZGO, cliente, espera_s=0), cliente


# ── Validación (esquema.py) ───────────────────────────────────────────────

def test_valida_acepta_respuesta_correcta():
    salida, errores = validar(_json())
    assert errores == []
    assert salida.owasp == "A02:2025"


@pytest.mark.parametrize("owasp,esperado", [
    ("A02:2025", "A02:2025"),
    ("a02:2025", "A02:2025"),
    ("A02:2025 - Security Misconfiguration", "A02:2025"),
    (" A10:2025", "A10:2025"),
])
def test_valida_normaliza_formato_owasp(owasp, esperado):
    salida, _ = validar(_json(owasp=owasp))
    assert salida.owasp == esperado


@pytest.mark.parametrize("owasp", ["A05:2021", "A11:2025", "A00:2025", "Injection", "", None])
def test_valida_rechaza_owasp_invalido(owasp):
    salida, errores = validar(_json(owasp=owasp))
    assert salida is None
    assert any("owasp" in e for e in errores)


def test_valida_explica_que_uso_la_edicion_2021():
    _, errores = validar(_json(owasp="A05:2021"))
    assert any("2021" in e for e in errores)


def test_valida_normaliza_prioridad():
    salida, _ = validar(_json(prioridad="P2"))
    assert salida.prioridad == "p2"


@pytest.mark.parametrize("prioridad", ["alta", "p5", "1"])
def test_valida_rechaza_prioridad_invalida(prioridad):
    salida, _ = validar(_json(prioridad=prioridad))
    assert salida is None


@pytest.mark.parametrize("confianza", [1.5, -0.1, "mucha"])
def test_valida_rechaza_confianza_fuera_de_rango(confianza):
    salida, _ = validar(_json(confianza=confianza))
    assert salida is None


def test_valida_rechaza_campo_faltante():
    incompleta = {k: v for k, v in VALIDA.items() if k != "remediacion"}
    salida, errores = validar(json.dumps(incompleta))
    assert salida is None
    assert any("remediacion" in e for e in errores)


def test_valida_rechaza_json_roto():
    salida, errores = validar('{"explicacion": "corta')
    assert salida is None
    assert any("JSON" in e for e in errores)


# ── Prompt (prompt.py) ────────────────────────────────────────────────────

def test_prompt_solo_lleva_evidencia():
    datos = datos_para_el_modelo(HALLAZGO)
    assert "dedupe_key" not in datos and "source_raw" not in datos
    assert datos["cwe"] == 693
    assert datos["severidad_zap"] == "Medium"
    assert "<p>" not in datos["descripcion"], "el HTML de ZAP se limpia"


def test_prompt_es_determinista():
    assert construir_prompt(HALLAZGO) == construir_prompt(HALLAZGO)


# ── Enriquecimiento (enriquecer.py) ───────────────────────────────────────

def test_enriquece_al_primer_intento():
    r, _ = _enriquecer(_json())
    assert r["state"] == "ok"
    assert r["attempts"] == 1
    assert r["owasp_category"] == "A02:2025"
    assert r["owasp_version"] == "2025"
    assert r["priority"] == "p3"
    assert r["remediation_summary"].startswith("Agregar")
    assert r["failure_reason"] is None
    assert r["prompt_version"] == PROMPT_VERSION
    assert r["model"] == "modelo-falso"


def test_repara_categoria_2021_en_el_segundo_intento():
    r, cliente = _enriquecer(_json(owasp="A05:2021"), _json())
    assert r["state"] == "ok"
    assert r["attempts"] == 2
    assert "2021" in cliente.prompts[1], "el reintento le explica al modelo qué corregir"
    assert cliente.prompts[1].startswith(cliente.prompts[0])


def test_tres_respuestas_invalidas_dejan_el_hallazgo_sin_enriquecer():
    r, _ = _enriquecer("no es json", "tampoco", "{}")
    assert r["state"] == "failed"
    assert r["attempts"] == 3
    assert r["failure_reason"] in ("json_invalido", "esquema_invalido")


def test_un_fallo_no_deja_campos_a_medias():
    """Refleja la restricción ck_enrichment_fallo_sin_datos de la base."""
    r, _ = _enriquecer("x", "x", "x")
    for campo in CAMPOS_CONTENIDO:
        assert r[campo] is None, f"{campo} debería ser None en un fallo"


def test_timeout_se_reintenta():
    r, _ = _enriquecer(OllamaTimeout("lento"), _json())
    assert r["state"] == "ok"
    assert r["attempts"] == 2


def test_tres_timeouts_marcan_fallo_por_timeout():
    r, _ = _enriquecer(OllamaTimeout("1"), OllamaTimeout("2"), OllamaTimeout("3"))
    assert r["state"] == "failed"
    assert r["failure_reason"] == "timeout"


def test_ollama_apagado_no_reintenta():
    r, cliente = _enriquecer(OllamaNoDisponible("apagado"), _json())
    assert r["state"] == "failed"
    assert r["failure_reason"] == "ollama_no_disponible"
    assert len(cliente.prompts) == 1


def test_hash_del_prompt_es_reproducible():
    a, _ = _enriquecer(_json())
    b, _ = _enriquecer(_json(owasp="A05:2021"), _json())
    assert len(a["prompt_sha256"]) == 64
    assert a["prompt_sha256"] == b["prompt_sha256"], "el hash es del prompt base, no del de reparación"


def test_motivo_de_fallo_cabe_en_la_columna():
    r, _ = _enriquecer("x", "x", "x")
    assert len(r["failure_reason"]) <= 40


def test_salida_tiene_las_columnas_de_ai_enrichments():
    columnas = {"state", "model", "prompt_version", "prompt_sha256", "attempts",
                "latency_ms", "failure_reason", "explanation", "impact",
                "owasp_version", "owasp_category", "priority", "confidence",
                "remediation_summary", "remediation_steps"}
    ok, _ = _enriquecer(_json())
    falla, _ = _enriquecer("x", "x", "x")
    assert set(ok) == columnas
    assert set(falla) == columnas
