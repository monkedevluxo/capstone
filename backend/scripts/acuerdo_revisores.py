"""
Acuerdo entre dos revisores del golden set, a partir de sus archivos de
intercambio (scripts/intercambio.py exportar --que validaciones). Tareas T-043, T-046.

`intercambio.py metricas` calcula el acuerdo solo en «OWASP correcto» y necesita
las dos anotaciones en la misma base. Este script lee los dos archivos tal como
quedan en docs/evidencias/golden_set/ y calcula, para las cuatro preguntas y la
decisión: el porcentaje de cada revisor, el acuerdo y el κ de Cohen. Así
cualquiera puede repetir los números del informe sin levantar el laboratorio.

Mismo criterio que intercambio.py: de cada revisor vale su última validación con
alguna bandera ai_* por hallazgo, y los «no sé» (null) no cuentan.

Uso, desde la raíz del repositorio (solo usa la biblioteca estándar):

    python3 backend/scripts/acuerdo_revisores.py \\
        docs/evidencias/golden_set/ronda1_felipe.json \\
        docs/evidencias/golden_set/ronda1_joaquin.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PREGUNTAS = {
    "ai_owasp_correcto": "Categoría OWASP correcta",
    "ai_prioridad_correcta": "Prioridad correcta",
    "ai_remediacion_util": "Remediación útil",
    "ai_alucinacion": "Inventó algo",
}


def ultimas(datos: dict) -> dict[str, dict]:
    """Última validación con banderas de cada hallazgo, por dedupe_key."""
    items = [i for i in datos["items"] if any(i.get(b) is not None for b in PREGUNTAS)]
    out: dict[str, dict] = {}
    for i in sorted(items, key=lambda i: i["reviewed_at"]):
        out[i["hallazgo"]["dedupe_key"]] = i
    return out


def kappa(pares: list[tuple]) -> float | None:
    """κ de Cohen. None si no hay pares o si el acuerdo esperado es 1."""
    n = len(pares)
    if n == 0:
        return None
    observado = sum(a == b for a, b in pares) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    esperado = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / (n * n)
    if esperado == 1:
        return None
    return (observado - esperado) / (1 - esperado)


def comparar(a: dict, b: dict) -> dict:
    """Porcentajes de cada revisor y acuerdo entre ambos, por pregunta."""
    ua, ub = ultimas(a), ultimas(b)
    comunes = sorted(ua.keys() & ub.keys())
    filas = {}
    for campo in PREGUNTAS:
        ra = [v[campo] for v in ua.values() if v[campo] is not None]
        rb = [v[campo] for v in ub.values() if v[campo] is not None]
        pares = [(ua[k][campo], ub[k][campo]) for k in comunes
                 if ua[k][campo] is not None and ub[k][campo] is not None]
        filas[campo] = {"a": (sum(ra), len(ra)), "b": (sum(rb), len(rb)),
                        "iguales": sum(x == y for x, y in pares), "n": len(pares), "kappa": kappa(pares)}
    decisiones = [(ua[k]["decision"], ub[k]["decision"]) for k in comunes]
    filas["decision"] = {"iguales": sum(x == y for x, y in decisiones), "n": len(decisiones),
                         "kappa": kappa(decisiones)}
    return {"hallazgos": len(comunes), "filas": filas}


def _pct(si: int, n: int) -> str:
    return "—" if n == 0 else f"{si}/{n} ({si / n:.0%})".replace("%", " %")


def _k(k: float | None) -> str:
    return "—" if k is None else f"{k:.2f}".replace(".", ",")


def tabla(a: dict, b: dict) -> str:
    """Tabla en Markdown, lista para pegar en la evidencia."""
    r = comparar(a, b)
    na = ultimas(a)[next(iter(ultimas(a)))]["reviewer"]
    nb = ultimas(b)[next(iter(ultimas(b)))]["reviewer"]
    lineas = [f"Hallazgos anotados por los dos: {r['hallazgos']}", "",
              f"| Pregunta | {na} | {nb} | Acuerdo | κ |", "|---|---|---|---|---|"]
    for campo, nombre in PREGUNTAS.items():
        f = r["filas"][campo]
        lineas.append(f"| {nombre} | {_pct(*f['a'])} | {_pct(*f['b'])} | "
                      f"{_pct(f['iguales'], f['n'])} | {_k(f['kappa'])} |")
    d = r["filas"]["decision"]
    lineas.append(f"| Decisión (confirmado, falso positivo, …) | — | — | "
                  f"{_pct(d['iguales'], d['n'])} | {_k(d['kappa'])} |")
    return "\n".join(lineas) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().split("\n\n")[-1], file=sys.stderr)
        return 2
    a, b = (json.loads(Path(p).read_text(encoding="utf-8")) for p in argv)
    sys.stdout.write(tabla(a, b))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
