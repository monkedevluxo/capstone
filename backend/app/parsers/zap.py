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
    raise NotImplementedError("TODO: implementar _a_entero")


def _extraer_instancias(alerta: dict) -> list[dict]:
    """
    Saca la lista de instancias de una alerta de ZAP.

    En el JSON de ZAP cada instancia se ve así:
        {"uri": "...", "method": "GET", "param": "q",
         "attack": "...", "evidence": "..."}

    Devuelve una lista de diccionarios con las claves url, method y param.
    Recorta a MAX_INSTANCIAS. Si la alerta no trae instancias, lista vacía.

    OJO: la clave en ZAP es "uri", pero nuestro esquema usa "url".
    """
    raise NotImplementedError("TODO: implementar _extraer_instancias")


def parsear_alerta(alerta: dict) -> dict | None:
    """
    Convierte UNA alerta de ZAP en UN hallazgo normalizado.

    Devuelve None si la alerta no tiene instancias utilizables
    (sin URL no hay hallazgo que registrar).

    Pasos sugeridos:
      1. Sacar las instancias con _extraer_instancias
      2. Si no hay ninguna, devolver None
      3. Tomar la primera instancia como representativa (url, method, param)
      4. Calcular path_template a partir de esa url
      5. Calcular dedupe_key y correlation_key
      6. Mapear severidad con severidad_zap(alerta["riskcode"])
      7. occurrences: usar alerta.get("count") si viene, si no len(instancias)
      8. Armar el diccionario del contrato
    """
    raise NotImplementedError("TODO: implementar parsear_alerta")


def parsear_reporte(crudo: dict) -> list[dict]:
    """
    Recorre el JSON completo de ZAP y devuelve todos los hallazgos normalizados.

    Estructura del JSON de ZAP:
        {
          "@version": "2.17.0",
          "site": [
            {
              "@name": "http://juiceshop:3000",
              "alerts": [ {...}, {...} ]
            }
          ]
        }

    OJO: "site" es una LISTA, aunque casi siempre traiga un solo elemento.
    Hay que recorrerla igual.

    Las alertas que parsear_alerta devuelve como None se descartan.
    """
    raise NotImplementedError("TODO: implementar parsear_reporte")


def main() -> None:
    """Uso: python -m app.parsers.zap <archivo.json>"""
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
