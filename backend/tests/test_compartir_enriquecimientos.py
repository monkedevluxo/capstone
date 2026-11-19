"""Tests de las partes puras de scripts/compartir_enriquecimientos.py (sin base)."""

import importlib.util
import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

_RUTA = Path(__file__).resolve().parents[1] / "scripts" / "compartir_enriquecimientos.py"
_spec = importlib.util.spec_from_file_location("compartir_enriquecimientos", _RUTA)
ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ce)


class _Cat(str, Enum):
    a05 = "A05:2025"


def _fila_bd(**cambios):
    """Imita una fila de ai_enrichments: enums y datetime, como los entrega SQLAlchemy."""
    base = dict(
        state=SimpleNamespace(value="ok"), model="llama3.1:8b-instruct-q4_K_M",
        prompt_version="v2", prompt_sha256="abc123", attempts=1, latency_ms=1800,
        failure_reason=None, explanation="La entrada llega sin filtrar a la consulta.",
        impact="Lectura de datos.", owasp_version="2025", owasp_category=_Cat.a05,
        priority=SimpleNamespace(value="p1"), confidence=0.9,
        remediation_summary="Consultas parametrizadas.", remediation_steps=["Paso 1"],
        generated_at=datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc),
    )
    base.update(cambios)
    return SimpleNamespace(**base)


def _archivo(*filas):
    return {"formato": ce.FORMATO, "enriquecimientos": list(filas)}


def _fila_archivo(**cambios):
    fila = {"objetivo": "http://juiceshop:3000", "dedupe_key": "0123456789abcdef",
            "titulo": "SQL Injection", "param": "q",
            "enriquecimiento": ce.enriquecimiento_a_dict(_fila_bd())}
    fila.update(cambios)
    return fila


def test_a_dict_convierte_enums_y_fechas_a_json():
    d = ce.enriquecimiento_a_dict(_fila_bd())
    assert d["state"] == "ok"
    assert d["owasp_category"] == "A05:2025"
    assert d["priority"] == "p1"
    assert d["generated_at"] == "2026-11-18T15:00:00+00:00"
    json.dumps(d)  # no debe lanzar


def test_a_dict_trae_todas_las_columnas_y_nada_de_la_base_local():
    d = ce.enriquecimiento_a_dict(_fila_bd())
    assert set(d) == set(ce.CAMPOS) | {"generated_at"}
    assert not {"id", "finding_id", "is_current"} & set(d)


def test_fallido_viaja_con_nulos():
    d = ce.enriquecimiento_a_dict(_fila_bd(
        state=SimpleNamespace(value="failed"), failure_reason="timeout",
        explanation=None, owasp_category=None, priority=None, confidence=None))
    assert d["state"] == "failed" and d["owasp_category"] is None


def test_misma_respuesta_ignora_generated_at():
    a = ce.enriquecimiento_a_dict(_fila_bd())
    b = dict(a, generated_at="2026-11-18T12:00:00-03:00")
    assert ce.misma_respuesta(a, b)


def test_misma_respuesta_detecta_cambios():
    a = ce.enriquecimiento_a_dict(_fila_bd())
    assert not ce.misma_respuesta(a, dict(a, explanation="Otra explicación."))
    assert not ce.misma_respuesta(a, dict(a, owasp_category="A02:2025"))


def test_archivo_valido():
    assert ce.validar_archivo(_archivo(_fila_archivo())) == []


def test_archivo_de_otro_formato():
    # El JSON del golden set (cargar_respuestas_golden.py) no se confunde con este
    assert ce.validar_archivo({"fecha": "2026-10-14", "filas": []})


def test_fila_sin_dedupe_key():
    errores = ce.validar_archivo(_archivo(_fila_archivo(dedupe_key="")))
    assert errores and "dedupe_key" in errores[0]


def test_enriquecimiento_incompleto():
    fila = _fila_archivo()
    fila["enriquecimiento"] = dict(fila["enriquecimiento"], model=None)
    errores = ce.validar_archivo(_archivo(fila))
    assert errores and "model" in errores[0]


def test_ida_y_vuelta_por_json():
    original = _archivo(_fila_archivo())
    leido = json.loads(json.dumps(original, ensure_ascii=False))
    assert ce.validar_archivo(leido) == []
    assert ce.misma_respuesta(leido["enriquecimientos"][0]["enriquecimiento"],
                              original["enriquecimientos"][0]["enriquecimiento"])


def test_fecha_sin_zona_se_toma_como_utc():
    assert ce._fecha("2026-11-18T15:00:00").tzinfo is not None
    assert ce._fecha(None) is None


def test_cargar_rechaza_archivo_invalido_sin_tocar_la_base(capsys):
    # Falla en la validación, antes de importar SQLAlchemy o abrir la base
    assert ce.cargar({"formato": "otro"}) == 1
    assert "ERROR" in capsys.readouterr().err
