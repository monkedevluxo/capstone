"""
SentinelAI · Categoría OWASP de referencia y prioridad por regla (decisión mixta).

Implementa la opción "mixta" de docs/diseno/IA_MODELO_Y_PROMPT.md (sección 5):

- La **categoría de referencia** sale del CWE del hallazgo, usando el mapeo
  oficial CWE -> OWASP Top 10:2025 ("List of Mapped CWEs" de cada categoría,
  https://top10.owasp.org/2025/, consultado el 02-11-2026).
- La **prioridad** sale de una regla fija según la severidad de ZAP.
- El modelo sigue proponiendo su categoría. Si no coincide con la de
  referencia, el hallazgo queda marcado para revisión y va primero en la
  cola de validación humana.

Nada de esto se guarda en la base: se calcula al consultar (ver 5.2, fila
"Cambios en la base de datos"). Lo que devuelve el modelo queda intacto en
ai_enrichments como sugerencia, para seguir midiéndolo contra el golden set.

Uso típico (endpoint de consulta, T-032):

    from app.ia.owasp_por_cwe import evaluar
    extra = evaluar(cwe_id=f.cwe_id,
                    severidad_zap=f.severity_tool_raw,
                    owasp_modelo=e.owasp_category if e else None)
    # extra == {"owasp_referencia": "A05:2025", "prioridad_regla": "p1",
    #           "requiere_revision": False, "motivo_revision": None}
"""

from __future__ import annotations

from typing import Any

EDICION = "2025"
FUENTE = "https://top10.owasp.org/2025/ (List of Mapped CWEs, consultado 02-11-2026)"

# ---------------------------------------------------------------------------
# Mapeo oficial OWASP Top 10:2025. Se copia la lista completa de cada
# categoría, no solo los CWE de los fixtures, para que un escaneo nuevo no
# caiga en "fuera de tabla" por un CWE que OWASP sí mapea.
# Cantidades según la tabla de cada página: 40, 16, 6, 32, 37, 39, 36, 14, 5, 24.
# ---------------------------------------------------------------------------
_CWES_POR_CATEGORIA: dict[str, tuple[int, ...]] = {
    # A01 Broken Access Control (absorbe SSRF)
    "A01:2025": (
        22, 23, 36, 59, 61, 65, 200, 201, 219, 276, 281, 282, 283, 284, 285,
        352, 359, 377, 379, 402, 424, 425, 441, 497, 538, 540, 548, 552, 566,
        601, 615, 639, 668, 732, 749, 862, 863, 918, 922, 1275,
    ),
    # A02 Security Misconfiguration
    "A02:2025": (
        5, 11, 13, 15, 16, 260, 315, 489, 526, 547, 611, 614, 776, 942, 1004,
        1174,
    ),
    # A03 Software Supply Chain Failures
    "A03:2025": (447, 1035, 1104, 1329, 1357, 1395),
    # A04 Cryptographic Failures
    "A04:2025": (
        261, 296, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330,
        331, 332, 334, 335, 336, 337, 338, 340, 342, 347, 523, 757, 759, 760,
        780, 916, 1240, 1241,
    ),
    # A05 Injection (incluye XSS)
    "A05:2025": (
        20, 74, 76, 77, 78, 79, 80, 83, 86, 88, 89, 90, 91, 93, 94, 95, 96,
        97, 98, 99, 103, 104, 112, 113, 114, 115, 116, 129, 159, 470, 493,
        500, 564, 610, 643, 644, 917,
    ),
    # A06 Insecure Design
    "A06:2025": (
        73, 183, 256, 266, 269, 286, 311, 312, 313, 316, 362, 382, 419, 434,
        436, 444, 451, 454, 472, 501, 522, 525, 539, 598, 602, 628, 642, 646,
        653, 656, 657, 676, 693, 799, 807, 841, 1021, 1022, 1125,
    ),
    # A07 Authentication Failures
    "A07:2025": (
        258, 259, 287, 288, 289, 290, 291, 293, 294, 295, 297, 298, 299, 300,
        302, 303, 304, 305, 306, 307, 308, 309, 346, 350, 384, 521, 613, 620,
        640, 798, 940, 941, 1390, 1391, 1392, 1393,
    ),
    # A08 Software or Data Integrity Failures
    "A08:2025": (
        345, 353, 426, 427, 494, 502, 506, 509, 565, 784, 829, 830, 915, 926,
    ),
    # A09 Security Logging & Alerting Failures
    "A09:2025": (117, 221, 223, 532, 778),
    # A10 Mishandling of Exceptional Conditions
    "A10:2025": (
        209, 215, 234, 235, 248, 252, 274, 280, 369, 390, 391, 394, 396, 397,
        460, 476, 478, 484, 550, 636, 703, 754, 755, 756,
    ),
}

# CWE -> categoría. Se construye una sola vez al importar.
TABLA: dict[int, str] = {
    cwe: categoria
    for categoria, cwes in _CWES_POR_CATEGORIA.items()
    for cwe in cwes
}

# Regla fija de prioridad (5.3, punto 1). La persona que valida puede ajustarla.
REGLA_PRIORIDAD: dict[str, str] = {
    "High": "p1",
    "Medium": "p2",
    "Low": "p3",
    "Informational": "p4",
}

# Motivos de revisión, legibles para el dashboard.
CWE_FUERA_DE_TABLA = "cwe_fuera_de_tabla"  # trae CWE, pero OWASP 2025 no lo mapea
CATEGORIA_DISTINTA = "categoria_distinta"  # regla y modelo no coinciden


def owasp_por_cwe(cwe_id: Any) -> str | None:
    """Categoría OWASP 2025 de referencia para un CWE, o None si no hay.

    Acepta int o str ("89"), porque ZAP entrega el CWE como texto. None, "",
    0 y -1 (cómo ZAP marca "sin CWE") devuelven None.
    """
    cwe = _cwe_entero(cwe_id)
    if cwe is None:
        return None
    return TABLA.get(cwe)


def prioridad_por_severidad(severidad_zap: Any) -> str | None:
    """p1..p4 según la severidad de ZAP. None si la severidad no se reconoce."""
    if severidad_zap is None:
        return None
    texto = str(severidad_zap).strip().capitalize()
    return REGLA_PRIORIDAD.get(texto)


def evaluar(cwe_id: Any, severidad_zap: Any, owasp_modelo: str | None) -> dict:
    """Los campos calculados que la API agrega a cada hallazgo.

    Devuelve:
        owasp_referencia   categoría según la tabla, o None
        prioridad_regla    p1..p4 según la severidad de ZAP, o None
        requiere_revision  True si la persona debería mirar primero este hallazgo
        motivo_revision    por qué (constantes de arriba), o None

    Criterios (tabla de 5.2):
        - Sin CWE: la referencia es "no aplica" y no se marca. Es lo esperable
          en hallazgos informativos como "Modern Web Application".
        - CWE fuera de la tabla: se usa la categoría del modelo, marcada "revisar".
        - Regla y modelo distintos: "revisar".
        - Sin categoría del modelo (hallazgo "sin enriquecer"): no hay con qué
          comparar; ese estado ya se muestra aparte, así que no se marca.
    """
    referencia = owasp_por_cwe(cwe_id)
    modelo = _normalizar_categoria(owasp_modelo)

    if _cwe_entero(cwe_id) is None:
        motivo = None  # sin CWE: la referencia "no aplica", no es discrepancia
    elif referencia is None:
        motivo = CWE_FUERA_DE_TABLA
    elif modelo is not None and modelo != referencia:
        motivo = CATEGORIA_DISTINTA
    else:
        motivo = None

    return {
        "owasp_referencia": referencia,
        "prioridad_regla": prioridad_por_severidad(severidad_zap),
        "requiere_revision": motivo is not None,
        "motivo_revision": motivo,
    }


def _cwe_entero(valor: Any) -> int | None:
    """int positivo o None. ZAP usa "", "0" y "-1" para decir "sin CWE"."""
    if valor is None or isinstance(valor, bool):
        return None
    try:
        cwe = int(str(valor).strip())
    except ValueError:
        return None
    return cwe if cwe > 0 else None


def _normalizar_categoria(valor: str | None) -> str | None:
    """Acepta "A05:2025" o un enum CategoriaOwasp; compara solo el código."""
    if valor is None:
        return None
    texto = str(getattr(valor, "value", valor)).strip().upper()
    return texto[:8] or None
