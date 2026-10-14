"""
SentinelAI · Validación de la salida del modelo (tarea T-030).

Toda respuesta del modelo pasa por aquí antes de tocar la base. Lo que no
cumple se rechaza con un motivo legible, y ese motivo se le devuelve al
modelo para que corrija (ver enriquecer.py).

Criterio: se normaliza el FORMATO (mayúsculas, espacios, texto sobrante
después del código OWASP), nunca el CONTENIDO. Si el modelo dice A05:2021,
no se "traduce" a 2025: se rechaza.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

_OWASP_2025 = re.compile(r"^\s*(A(?:0[1-9]|10):2025)\b")
_OWASP_OTRA_EDICION = re.compile(r"^\s*A\d{1,2}:(\d{4})")


class SalidaIA(BaseModel):
    """Los seis campos que pide el prompt. Campos extra se ignoran."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    explicacion: str = Field(min_length=10)
    impacto: str = Field(min_length=5)
    owasp: str
    prioridad: Literal["p1", "p2", "p3", "p4"]
    confianza: float = Field(ge=0.0, le=1.0)
    remediacion: str = Field(min_length=10)

    @field_validator("owasp", mode="before")
    @classmethod
    def _owasp_2025(cls, v):
        texto = str(v or "").upper()
        m = _OWASP_2025.match(texto)
        if m:
            return m.group(1)            # "A02:2025 - Security Misc." -> "A02:2025"
        otra = _OWASP_OTRA_EDICION.match(texto)
        if otra:
            raise ValueError(f"usa la edicion {otra.group(1)}; debe ser del Top 10:2025")
        raise ValueError("debe tener el formato AXX:2025, de A01 a A10")

    @field_validator("prioridad", mode="before")
    @classmethod
    def _prioridad_minuscula(cls, v):
        return str(v or "").strip().lower()


def validar(texto: str) -> tuple[SalidaIA | None, list[str]]:
    """
    Devuelve (salida, []) si es válida, o (None, [motivos]) si no.

    Los motivos están en español y son cortos: se reenvían tal cual al modelo
    en el intento de reparación.
    """
    try:
        return SalidaIA.model_validate_json(texto), []
    except ValidationError as exc:
        errores = []
        for e in exc.errors():
            campo = ".".join(str(p) for p in e["loc"]) or "respuesta"
            if e["type"] == "json_invalid":
                errores.append("la respuesta no es un JSON valido")
            elif e["type"] == "missing":
                errores.append(f"falta el campo '{campo}'")
            else:
                mensaje = e["msg"].removeprefix("Value error, ")
                errores.append(f"'{campo}': {mensaje}")
        return None, errores
