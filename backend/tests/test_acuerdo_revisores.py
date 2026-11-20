"""Tests de scripts/acuerdo_revisores.py (sin base de datos)."""

import importlib.util
import json
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "acuerdo_revisores", _RAIZ / "backend" / "scripts" / "acuerdo_revisores.py")
ar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ar)


def _item(clave, revisor, fecha, decision="confirmado", **banderas):
    base = {b: None for b in ar.PREGUNTAS}
    base.update(banderas)
    return {"hallazgo": {"dedupe_key": clave}, "reviewer": revisor, "reviewed_at": fecha,
            "decision": decision, **base}


def test_kappa_coincide_con_la_revision_de_alucinaciones_de_octubre():
    # acuerdo_alucinaciones.md: 20 respuestas, 18 iguales, κ = 0,74
    pares = [(True, True)] * 4 + [(True, False)] * 2 + [(False, False)] * 14
    assert ar.kappa(pares) == pytest.approx(0.74, abs=0.01)


def test_kappa_sin_variacion_o_sin_pares_no_se_calcula():
    assert ar.kappa([(True, True), (True, True)]) is None
    assert ar.kappa([]) is None


def test_vale_la_ultima_validacion_con_banderas():
    datos = {"items": [
        _item("k1", "F", "2026-11-19T01:00", ai_alucinacion=True),
        _item("k1", "F", "2026-11-19T02:00", ai_alucinacion=False),
        _item("k1", "F", "2026-11-19T03:00"),  # sin banderas: no reemplaza
    ]}
    assert ar.ultimas(datos)["k1"]["ai_alucinacion"] is False


def test_los_no_se_no_entran_en_el_acuerdo():
    a = {"items": [_item("k1", "F", "t1", ai_owasp_correcto=True),
                   _item("k2", "F", "t1", ai_owasp_correcto=None, ai_alucinacion=False)]}
    b = {"items": [_item("k1", "J", "t1", ai_owasp_correcto=True),
                   _item("k2", "J", "t1", ai_owasp_correcto=False, ai_alucinacion=False)]}
    fila = ar.comparar(a, b)["filas"]["ai_owasp_correcto"]
    assert (fila["iguales"], fila["n"]) == (1, 1)
    assert fila["a"] == (1, 1) and fila["b"] == (1, 2)


def test_la_ronda_1_del_repo_da_los_numeros_documentados():
    carpeta = _RAIZ / "docs" / "evidencias" / "golden_set"
    if not (carpeta / "ronda1_felipe.json").exists():
        pytest.skip("sin los archivos del golden set")
    a, b = (json.loads((carpeta / f"ronda1_{n}.json").read_text(encoding="utf-8"))
            for n in ("felipe", "joaquin"))
    r = ar.comparar(a, b)
    assert r["hallazgos"] == 17
    assert r["filas"]["ai_owasp_correcto"]["a"] == (5, 14)
    assert r["filas"]["ai_alucinacion"]["iguales"] == 14
    assert "| Inventó algo |" in ar.tabla(a, b)
