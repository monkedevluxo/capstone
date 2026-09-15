"""
SentinelAI · Normalización de rutas y cálculo de claves de deduplicación.

Implementación de referencia de la regla descrita en ESQUEMA_HALLAZGO.md.
Sin dependencias externas: solo biblioteca estándar.

Ejecutar `python normalizacion.py` corre los casos de prueba incluidos.
"""

import hashlib
import re
from urllib.parse import urlsplit, parse_qsl

# ── Normalización de rutas ────────────────────────────────────────────────
# Sin esto, /rest/products/1 y /rest/products/47 se cuentan como dos hallazgos
# distintos y un escaneo de Juice Shop genera decenas de duplicados del mismo problema.

_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_NUM = re.compile(r"^\d+$")
_HEX = re.compile(r"^[0-9a-f]{8,}$", re.I)


def normalizar_segmento(seg: str) -> str:
    # La extensión se separa antes de evaluar: 'a3f91bc2e7d40518.js' es un bundle
    # con hash, no un recurso propio, pero '.js' debe conservarse.
    base, punto, ext = seg.partition(".")
    sufijo = f".{ext.lower()}" if punto else ""

    if _NUM.match(base):
        return "{id}" + sufijo
    if _UUID.match(base):
        return "{uuid}" + sufijo
    if _HEX.match(base):
        return "{hash}" + sufijo
    return seg.lower()


def path_template(url: str) -> str:
    """
    Convierte una URL concreta en su plantilla estable.

    Descarta esquema, host y VALORES de query, pero conserva los NOMBRES de
    los parámetros ordenados: el mismo endpoint atacado por dos parámetros
    distintos son dos hallazgos distintos y no deben colapsarse.

        http://juiceshop:3000/rest/products/47/reviews  ->  /rest/products/{id}/reviews
        http://juiceshop:3000/rest/products/search?q=X  ->  /rest/products/search?q
    """
    partes = urlsplit(url)
    ruta = partes.path or "/"
    segmentos = [normalizar_segmento(s) for s in ruta.split("/") if s]
    base = "/" + "/".join(segmentos)
    if len(base) > 1 and base.endswith("/"):
        base = base[:-1]

    nombres = sorted({k for k, _ in parse_qsl(partes.query, keep_blank_values=True)})
    return f"{base}?{'&'.join(nombres)}" if nombres else base


# ── Claves de agrupación ──────────────────────────────────────────────────

def _hash16(*campos) -> str:
    crudo = "|".join("" if c is None else str(c).strip().lower() for c in campos)
    return hashlib.sha256(crudo.encode("utf-8")).hexdigest()[:16]


def dedupe_key(tool: str, rule_id: str, plantilla: str, param, method) -> str:
    """
    Agrupa repeticiones DENTRO de una misma herramienta. Determinista: el mismo
    hallazgo reimportado produce la misma clave y no crea un registro nuevo.
    Incluye `tool` a propósito: ZAP y Nikto no comparten numeración de reglas.
    """
    return _hash16(tool, rule_id, plantilla, param, method)


def correlation_key(cwe_id, plantilla: str, param) -> str | None:
    """
    Agrupa hallazgos ENTRE herramientas distintas usando el CWE como puente.
    Devuelve None sin CWE. Solo sugiere 'posiblemente el mismo problema':
    nunca fusiona registros ni descarta evidencia.
    """
    if cwe_id is None:
        return None
    return _hash16(cwe_id, plantilla, param)


# ── Severidad ─────────────────────────────────────────────────────────────
# ZAP no emite "critica": su escala llega hasta High. Reservamos ese nivel para
# OpenVAS con CVSS >= 9.0. Inventar criticas a partir de ZAP falsearia el tablero.

_ZAP_RIESGO = {
    "3": "alta", "high": "alta",
    "2": "media", "medium": "media",
    "1": "baja", "low": "baja",
    "0": "informativa", "informational": "informativa", "info": "informativa",
}

_ZAP_CONFIANZA = {
    "0": "false_positive", "1": "low", "2": "medium", "3": "high", "4": "confirmed",
}


def severidad_zap(riskcode) -> str:
    return _ZAP_RIESGO.get(str(riskcode).strip().lower(), "informativa")


def confianza_zap(confidence):
    return _ZAP_CONFIANZA.get(str(confidence).strip())


def severidad_openvas(cvss) -> str:
    if cvss is None:
        return "informativa"
    if cvss >= 9.0:
        return "critica"
    if cvss >= 7.0:
        return "alta"
    if cvss >= 4.0:
        return "media"
    if cvss > 0.0:
        return "baja"
    return "informativa"


# ── Pruebas ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    casos = [
        ("http://juiceshop:3000/rest/products/47/reviews", "/rest/products/{id}/reviews"),
        ("http://juiceshop:3000/rest/products/1/reviews", "/rest/products/{id}/reviews"),
        ("http://juiceshop:3000/rest/products/search?q=%3Cscript%3E", "/rest/products/search?q"),
        ("http://juiceshop:3000/rest/products/search?q=a&sort=z", "/rest/products/search?q&sort"),
        ("http://juiceshop:3000/api/Users/0c5d8e77-3b41-4a92-b6c8-1e07f2a95d10", "/api/users/{uuid}"),
        ("http://juiceshop:3000/assets/a3f91bc2e7d40518.js", "/assets/{hash}.js"),
        ("http://juiceshop:3000/ftp/", "/ftp"),
    ]
    fallos = 0
    for url, esperado in casos:
        obtenido = path_template(url)
        ok = obtenido == esperado
        fallos += not ok
        print(f"{'OK  ' if ok else 'FALLA'} {url}\n      -> {obtenido}")

    # Dos URLs distintas del mismo endpoint deben colapsar en una sola clave.
    a = dedupe_key("zap", "40012", path_template(casos[0][0]), None, "GET")
    b = dedupe_key("zap", "40012", path_template(casos[1][0]), None, "GET")
    print(f"\n{'OK  ' if a == b else 'FALLA'} colapso de instancias: {a} == {b}")
    fallos += a != b

    # Distinto parámetro = distinto hallazgo.
    c = dedupe_key("zap", "40012", "/rest/products/search?q", "q", "GET")
    d = dedupe_key("zap", "40012", "/rest/products/search?q", "sort", "GET")
    print(f"{'OK  ' if c != d else 'FALLA'} parámetros distintos no colapsan")
    fallos += c == d

    print("\n--- Claves del ejemplo (ejemplo_hallazgo.json) ---")
    p = path_template("http://juiceshop:3000/rest/products/search?q=%3Cscript%3Ealert%281%29%3C%2Fscript%3E")
    print("path_template   :", p)
    print("dedupe_key      :", dedupe_key("zap", "40012", p, "q", "GET"))
    print("correlation_key :", correlation_key(79, p, "q"))
    print("severidad ZAP 3 :", severidad_zap("3"))

    raise SystemExit(1 if fallos else 0)
