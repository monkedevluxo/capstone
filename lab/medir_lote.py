"""
SentinelAI · Tiempo de enriquecimiento de un escaneo completo (T-039, RNF-15).

Recorre TODOS los hallazgos de la base y los enriquece uno por uno a través de
la API real (POST /findings/{id}/enrich), igual que el botón del dashboard:
prompt v2, validación con Pydantic, reintentos y guardado en PostgreSQL.

Meta de RNF-15: menos de 2 minutos para los 17 hallazgos, con el modelo en GPU.

OJO: cada llamada agrega un enriquecimiento nuevo y lo deja como vigente.
Haz un respaldo de la base antes y restáuralo después (ver instrucciones).

Uso (con la plataforma arriba y Ollama corriendo):
    python3 lab/medir_lote.py                  # 1 corrida
    python3 lab/medir_lote.py --corridas 3

Solo biblioteca estándar. Guarda el detalle en lab/salidas/ (no se versiona).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def pedir(metodo: str, url: str, timeout: int = 300) -> dict:
    req = urllib.request.Request(url, method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--corridas", type=int, default=1)
    args = ap.parse_args()

    hallazgos = pedir("GET", f"{args.api}/findings?limit=200")["items"]
    print(f"{len(hallazgos)} hallazgos · {args.corridas} corrida(s)\n")

    corridas = []
    for n in range(1, args.corridas + 1):
        filas = []
        t0 = time.perf_counter()
        for h in hallazgos:
            t = time.perf_counter()
            try:
                r = pedir("POST", f"{args.api}/findings/{h['id']}/enrich")
            except urllib.error.HTTPError as e:
                print(f"  ERROR {e.code} en {h['titulo']}: Ollama no responde. Se detiene la corrida.")
                return
            seg = time.perf_counter() - t
            ia = r["ia"] or {}
            filas.append({"titulo": h["titulo"], "segundos": round(seg, 2), "estado": ia.get("estado"),
                          "intentos": ia.get("intentos"), "latencia_modelo_ms": ia.get("latencia_ms")})
            print(f"  c{n} {seg:5.1f}s  {ia.get('estado'):6}  intentos={ia.get('intentos')}  {h['titulo'][:55]}")
        total = time.perf_counter() - t0
        c = {
            "corrida": n,
            "hallazgos": len(filas),
            "total_s": round(total, 1),
            "hallazgos_por_minuto": round(len(filas) / total * 60, 1),
            "media_s": round(statistics.mean(f["segundos"] for f in filas), 2),
            "max_s": max(f["segundos"] for f in filas),
            "ok": sum(f["estado"] == "ok" for f in filas),
            "reintentos": sum((f["intentos"] or 1) - 1 for f in filas),
            "cumple_rnf15": total < 120,
            "detalle": filas,
        }
        corridas.append(c)
        print(f"\n  Corrida {n}: {c['total_s']} s · {c['hallazgos_por_minuto']} hallazgos/min · "
              f"{c['ok']}/{c['hallazgos']} ok · {c['reintentos']} reintentos · "
              f"RNF-15 {'cumple' if c['cumple_rnf15'] else 'NO cumple'} (< 120 s)\n")

    salidas = RAIZ / "salidas"
    salidas.mkdir(exist_ok=True)
    archivo = salidas / f"medir_lote_{datetime.now():%Y%m%d_%H%M%S}.json"
    archivo.write_text(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"),
                                   "api": args.api, "corridas": corridas},
                                  ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Detalle en {archivo}")


if __name__ == "__main__":
    main()
