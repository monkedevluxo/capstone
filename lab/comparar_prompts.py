"""
SentinelAI · Comparación v1 contra v2 sobre los 17 hallazgos del golden set (T-047).

Misma muestra, mismo modelo, mismas repeticiones: lo único que cambia es el
prompt. La "respuesta correcta" no la decide una persona, sale de reglas fijas:

- Categoría: tabla oficial CWE -> OWASP 2025 (backend/app/ia/owasp_por_cwe.py).
  Solo cuentan los hallazgos que tienen referencia (13 de 17).
- Prioridad: regla por severidad de ZAP (High p1, Medium p2, Low p3, Info p4).

Por eso cualquiera puede repetir la medición y comparar (T-048).

Uso (desde la raíz del repo, con Ollama corriendo y el modelo cargado):
    python lab/comparar_prompts.py                    # v1 y v2, 2 repeticiones
    python lab/comparar_prompts.py --repeticiones 3

Guarda el detalle en lab/salidas/ (no se versiona).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent / "backend"))
sys.path.insert(0, str(RAIZ))

from app.ia.owasp_por_cwe import evaluar as referencia  # noqa: E402
from app.ia.prompt import datos_para_el_modelo  # noqa: E402
from app.parsers.zap import parsear_reporte  # noqa: E402
from prueba_prompt import CAMPOS, PROMPTS, consultar  # noqa: E402

# Los tres escaneos del golden set: juntos dan 17 hallazgos únicos
FIXTURES = ["zap_juiceshop_ajax_v2.json", "zap_juiceshop_full_v1.json", "zap_juiceshop_ajax_auth_v1.json"]


def cargar_golden_set() -> list[dict]:
    unicos: dict[str, dict] = {}
    for nombre in FIXTURES:
        crudo = json.loads((RAIZ / "fixtures" / nombre).read_text(encoding="utf-8"))
        for h in parsear_reporte(crudo):
            unicos.setdefault(h["dedupe_key"], h)
    return list(unicos.values())


def puntuar(salida: str, ref: dict) -> dict:
    """Describe una respuesta. No corrige nada."""
    r = {"json_ok": False, "owasp": None, "prioridad": None,
         "owasp_ok": None, "prioridad_ok": None, "numeracion_2021": False}
    try:
        d = json.loads(salida)
    except json.JSONDecodeError:
        return r
    r["json_ok"] = isinstance(d, dict) and CAMPOS <= set(d)
    if not isinstance(d, dict):
        return r
    owasp = str(d.get("owasp") or "").strip().upper()[:8]
    prioridad = str(d.get("prioridad") or "").strip().lower()
    r["owasp"], r["prioridad"] = owasp or None, prioridad or None
    r["numeracion_2021"] = owasp.endswith("2021")
    if ref["owasp_referencia"]:
        r["owasp_ok"] = owasp == ref["owasp_referencia"]
    if ref["prioridad_regla"]:
        r["prioridad_ok"] = prioridad == ref["prioridad_regla"]
    return r


def _cuenta(filas: list[dict], campo: str) -> str:
    validas = [f[campo] for f in filas if f[campo] is not None]
    return f"{sum(validas)}/{len(validas)}" if validas else "-"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repeticiones", type=int, default=2)
    ap.add_argument("--prompts", nargs="+", default=["v1", "v2"], choices=sorted(PROMPTS))
    args = ap.parse_args()

    hallazgos = cargar_golden_set()
    print(f"{len(hallazgos)} hallazgos · prompts {args.prompts} · {args.repeticiones} repeticiones\n")

    detalle = []
    resumen = {}
    for version in args.prompts:
        filas, latencias = [], []
        t0 = time.perf_counter()
        for rep in range(1, args.repeticiones + 1):
            for h in hallazgos:
                ref = referencia(h["cwe_id"], h["severity_tool_raw"], None)
                hallazgo = datos_para_el_modelo(h)
                seg, salida = consultar(hallazgo, PROMPTS[version])
                p = puntuar(salida, ref)
                latencias.append(seg)
                filas.append(p)
                detalle.append({"prompt": version, "repeticion": rep, "dedupe_key": h["dedupe_key"],
                                "titulo": h["titulo"], "cwe": h["cwe_id"], "segundos": round(seg, 2),
                                "referencia": ref, **p, "respuesta": salida})
                marca = {True: "ok", False: "x ", None: "--"}[p["owasp_ok"]]
                print(f"  {version} r{rep} [{marca}] {seg:5.1f}s  {p['owasp'] or '?':9} {h['titulo'][:50]}")
        total = time.perf_counter() - t0
        resumen[version] = {
            "json_valido": f"{sum(f['json_ok'] for f in filas)}/{len(filas)}",
            "owasp_igual_a_tabla": _cuenta(filas, "owasp_ok"),
            "prioridad_igual_a_regla": _cuenta(filas, "prioridad_ok"),
            "numeracion_2021": sum(f["numeracion_2021"] for f in filas),
            "latencia_media_s": round(statistics.mean(latencias), 2),
            "hallazgos_por_minuto": round(len(filas) / total * 60, 1),
        }
        print()

    print("Resumen")
    for version, r in resumen.items():
        print(f"  {version}: {r}")

    salidas = RAIZ / "salidas"
    salidas.mkdir(exist_ok=True)
    archivo = salidas / f"comparar_prompts_{datetime.now():%Y%m%d_%H%M%S}.json"
    archivo.write_text(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"),
                                   "repeticiones": args.repeticiones, "resumen": resumen,
                                   "detalle": detalle}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalle en {archivo}")


if __name__ == "__main__":
    main()
