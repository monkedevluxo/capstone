"""
SentinelAI · Parser de OWASP ZAP (tarea T-019)

Responsable: rol de Arquitectura, IA y Parser.

CONTRATO
========
Entrada:  el JSON crudo de ZAP, ya cargado con json.load()
Salida:   una lista de diccionarios normalizados

Cada diccionario DEBE tener exactamente estas claves:

    {
      "rule_id":           str        # pluginid de ZAP
      "rule_name":         str | None
      "titulo":            str
      "descripcion":       str | None
      "url":               str        # primera instancia, sin normalizar
      "path_template":     str        # usar path_template() de normalizacion.py
      "method":            str | None # GET, POST, ...
      "param":             str | None
      "evidence_snippet":  str | None
      "severity":          str        # critica|alta|media|baja|informativa
      "severity_tool_raw": str        # "High", "Medium", ... tal cual lo dice ZAP
      "tool_confidence":   str | None # false_positive|low|medium|high|confirmed
      "cwe_id":            int | None # ENTERO, no string
      "wasc_id":           int | None
      "dedupe_key":        str        # 16 hex, usar dedupe_key() de normalizacion.py
      "correlation_key":   str | None # usar correlation_key(), None si no hay CWE
      "occurrences":       int        # cuántas instancias agrupa (>= 1)
      "source_raw":        dict       # el bloque de la alerta SIN MODIFICAR
      "instances":         list[dict] # máximo 50: {"url","method","param"}
    }

REGLAS QUE NO SE NEGOCIAN
=========================
1. `source_raw` va tal cual viene de ZAP. No recortar, no corregir, no traducir.
   Es la evidencia original que respalda todo el proyecto.

2. `cwe_id` es int o None. ZAP lo entrega como string, a veces vacío ("").
   Si viene "" o falta, es None. Nunca 0, nunca "".

3. Si una alerta de ZAP trae N instancias, produce UN solo diccionario con
   occurrences=N. No N diccionarios.

4. Nunca inventar un campo. Si ZAP no lo trae, va None.

5. Usar siempre las funciones de app/normalizacion.py para las claves.
   No reimplementar el hash acá.

CÓMO TRABAJAR
=============
    cd backend
    pytest tests/test_zap_parser.py -v

Los tests fallan hasta que implementes las funciones. Ve uno por uno.
Cuando pasen todos, corre contra el fixture real:

    python -m app.parsers.zap ../lab/fixtures/zap_juiceshop_full_v1.json
"""

from __future__ import annotations

import json
import sys
from typing import Any

from app.normalizacion import (
    confianza_zap,
    correlation_key,
    dedupe_key,
    path_template,
    severidad_zap,
)

MAX_INSTANCIAS = 50


_RIESGO_ZAP_TEXTO = {"0": "Informational", "1": "Low", "2": "Medium", "3": "High"}


def _texto_o_none(valor: Any) -> str | None:
    if valor is None or valor == "":
        return None
    return valor

def _a_entero(valor: Any) -> int | None:
    """
    ZAP entrega cweid y wascid como string, y a veces como "" o "-1".

    Debe devolver:
        "79"  -> 79
        ""    -> None
        None  -> None
        "-1"  -> None
        79    -> 79
    """
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None

    if numero <= 0:
        return None

    return numero


def _extraer_instancias(alerta: dict) -> list[dict]:
    instancias = []
    for inst in alerta.get("instances") or []:
        instancias.append({
            "url": inst.get("uri"),
            "method": _texto_o_none(inst.get("method")),
            "param": _texto_o_none(inst.get("param")),
        })
    return instancias[:MAX_INSTANCIAS]


def parsear_alerta(alerta: dict) -> dict | None:
    instancias = _extraer_instancias(alerta)
    if not instancias:
        return None

    primera = instancias[0]
    url = primera["url"]
    method = primera["method"]
    param = primera["param"]

    rule_id = str(alerta.get("pluginid"))
    plantilla = path_template(url)
    cwe_id = _a_entero(alerta.get("cweid"))

    evidencia = _texto_o_none(alerta["instances"][0].get("evidence"))

    ocurrencias = _a_entero(alerta.get("count")) or len(alerta["instances"])

    return {
        "rule_id": rule_id,
        "rule_name": alerta.get("name"),
        "titulo": alerta.get("alert") or alerta.get("name"),
        "descripcion": alerta.get("desc"),
        "url": url,
        "path_template": plantilla,
        "method": method,
        "param": param,
        "evidence_snippet": evidencia,
        "severity": severidad_zap(alerta.get("riskcode")),
        "severity_tool_raw": _RIESGO_ZAP_TEXTO.get(str(alerta.get("riskcode")), "Informational"),
        "tool_confidence": confianza_zap(alerta.get("confidence")),
        "cwe_id": cwe_id,
        "wasc_id": _a_entero(alerta.get("wascid")),
        "dedupe_key": dedupe_key("zap", rule_id, plantilla, param, method),
        "correlation_key": correlation_key(cwe_id, plantilla, param),
        "occurrences": ocurrencias,
        "source_raw": alerta,
        "instances": instancias,
    }

def parsear_reporte(crudo: dict) -> list[dict]:
    hallazgos = []
    for sitio in crudo.get("site") or []:
        for alerta in sitio.get("alerts") or []:
            hallazgo = parsear_alerta(alerta)
            if hallazgo is not None:
                hallazgos.append(hallazgo)
    return hallazgos

def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__.split("CÓMO TRABAJAR")[1])
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        crudo = json.load(f)

    hallazgos = parsear_reporte(crudo)
    print(f"{len(hallazgos)} hallazgos normalizados\n")

    por_sev: dict[str, int] = {}
    for h in hallazgos:
        por_sev[h["severity"]] = por_sev.get(h["severity"], 0) + 1
    for sev in ("critica", "alta", "media", "baja", "informativa"):
        if sev in por_sev:
            print(f"  {sev:>12}: {por_sev[sev]}")

    claves = {h["dedupe_key"] for h in hallazgos}
    print(f"\n  claves únicas: {len(claves)} de {len(hallazgos)} hallazgos")
    if len(claves) != len(hallazgos):
        print("  AVISO: hay claves repetidas, revisar la deduplicación")


if __name__ == "__main__":
    main()
