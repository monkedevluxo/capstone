"""
SentinelAI · El ejemplo de hallazgo debe cumplir el esquema.

Si alguien cambia finding.schema.json sin actualizar el ejemplo, o al revés,
este test lo detecta. El esquema es el contrato de datos de todo el proyecto.
"""

import json
from pathlib import Path

import pytest

jsonschema = pytest.importorskip("jsonschema")

DISENO = Path(__file__).resolve().parents[2] / "docs" / "diseno"


def _cargar(nombre: str) -> dict:
    return json.loads((DISENO / nombre).read_text(encoding="utf-8"))


def test_el_esquema_es_json_schema_valido():
    jsonschema.Draft202012Validator.check_schema(_cargar("finding.schema.json"))


def test_el_ejemplo_cumple_el_esquema():
    validador = jsonschema.Draft202012Validator(
        _cargar("finding.schema.json"),
        format_checker=jsonschema.FormatChecker(),
    )
    errores = [f"{list(e.path)}: {e.message}" for e in validador.iter_errors(_cargar("ejemplo_hallazgo.json"))]
    assert not errores, "\n".join(errores)
