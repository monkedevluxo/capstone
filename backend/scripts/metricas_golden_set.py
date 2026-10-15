"""
SentinelAI · Métricas del modelo contra el golden set (tarea T-045).

Cruza la anotación humana de Felipe (docs/evidencias/validacion_manual.csv)
con lo que responde el modelo para los MISMOS hallazgos, y calcula:

  - acierto de categoría OWASP 2025
  - acierto de prioridad (exacto y a un tramo de distancia)
  - la misma prioridad calculada con una REGLA FIJA por severidad de ZAP,
    para comparar modelo contra regla (insumo de la decisión A / B / mixta)
  - consistencia entre corridas y si la confianza del modelo distingue
    aciertos de errores
  - tasa de alucinación, a partir de una planilla de revisión humana

Uso (desde backend/, con el .venv activo y Ollama abierto):

    $env:OLLAMA_URL = "http://localhost:11434"
    python scripts/metricas_golden_set.py                 # consulta al modelo (2 corridas)
    python scripts/metricas_golden_set.py --corridas 3
    python scripts/metricas_golden_set.py --desde ..\\docs\\evidencias\\respuestas_modelo\\golden_set_XXXX.json
                                                          # recalcula SIN Ollama

Reproducible: cada corrida queda guardada en docs/evidencias/respuestas_modelo/,
y con --desde se recalculan exactamente las mismas métricas a partir de ese archivo.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
RAIZ = BACKEND.parent
sys.path.insert(0, str(BACKEND))

CSV_GOLDEN = RAIZ / "docs" / "evidencias" / "validacion_manual.csv"
CSV_REVISION = RAIZ / "docs" / "evidencias" / "revision_alucinaciones.csv"
REPORTE = RAIZ / "docs" / "evidencias" / "metricas_golden_set.md"
DIR_RESPUESTAS = RAIZ / "docs" / "evidencias" / "respuestas_modelo"
FIXTURES = ["zap_juiceshop_ajax_v2.json", "zap_juiceshop_full_v1.json"]

# Regla fija de comparación: el tramo "más urgente" que permite el prompt v2
# para cada severidad de ZAP. No usa IA: siempre da lo mismo.
REGLA_PRIORIDAD = {"High": "p1", "Medium": "p2", "Low": "p3", "Informational": "p4"}

SI = {"si", "sí", "s", "x", "true", "verdadero", "1", "yes", "y"}


# ── Lectura del golden set ────────────────────────────────────────────────

def _normalizar(texto) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


def _owasp(valor) -> list[str]:
    """'A02:2025', 'a02', 'A01 / A02' -> ['A02:2025', ...]. Vacío o N/A -> [] (no se puntúa)."""
    numeros = {int(m) for m in re.findall(r"A\s*(\d{1,2})", str(valor or "").upper())}
    return [f"A{n:02d}:2025" for n in sorted(numeros) if 1 <= n <= 10]


def _prioridad(valor) -> str | None:
    m = re.search(r"p\s*([1-4])", str(valor or "").lower())
    return f"p{m.group(1)}" if m else None


def leer_golden(ruta: Path) -> list[dict]:
    texto = ruta.read_text(encoding="utf-8-sig")
    dialecto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=",;\t")
    filas = []
    for i, f in enumerate(csv.DictReader(texto.splitlines(), dialect=dialecto), start=1):
        f = {_normalizar(k).replace(" ", "_"): (v or "").strip() for k, v in f.items() if k}
        hallazgo = f.get("hallazgo") or f.get("titulo") or ""
        if not hallazgo:
            continue
        filas.append({
            "fila": f.get("id_hallazgo") or f.get("id") or str(i),
            "hallazgo": hallazgo,
            "fixture": f.get("fixture", ""),
            "cwe": f.get("cwe", ""),
            "owasp_humano": _owasp(f.get("owasp_2025") or f.get("owasp")),
            "prioridad_humana": _prioridad(f.get("prioridad")),
            "falso_positivo": _normalizar(f.get("es_falso_positivo")) in SI,
            "comentario": f.get("comentario", ""),
        })
    return filas


# ── Cruce con los hallazgos reales ────────────────────────────────────────

def cargar_hallazgos() -> list[tuple[str, dict]]:
    from app.parsers.zap import parsear_reporte
    todos = []
    for nombre in FIXTURES:
        ruta = RAIZ / "lab" / "fixtures" / nombre
        if ruta.exists():
            with open(ruta, encoding="utf-8") as fh:
                todos += [(nombre, h) for h in parsear_reporte(json.load(fh))]
    return todos


def emparejar(fila: dict, hallazgos: list[tuple[str, dict]]) -> dict | None:
    """Busca el hallazgo del fixture que corresponde a una fila del CSV, por título."""
    buscado = _normalizar(fila["hallazgo"])
    candidatos = hallazgos
    if fila["fixture"]:
        candidatos = [(n, h) for n, h in hallazgos if _normalizar(fila["fixture"]) in _normalizar(n)] or hallazgos

    for criterio in (
        lambda t: t == buscado,
        lambda t: t.startswith(buscado) or buscado.startswith(t),
        lambda t: buscado in t or t in buscado,
    ):
        hits = [h for _, h in candidatos if criterio(_normalizar(h["titulo"]))]
        if hits:
            return hits[0]          # mismo título en dos fixtures = mismo problema
    return None


# ── Consulta al modelo ────────────────────────────────────────────────────

def consultar_modelo(filas: list[dict], corridas: int) -> dict:
    from app.ia.cliente import ClienteOllama
    from app.ia.enriquecer import enriquecer
    from app.ia.prompt import PROMPT_VERSION

    cliente = ClienteOllama.desde_config()
    if not cliente.disponible():
        sys.exit(f"Ollama no responde en {cliente.url}. Ábrelo o revisa OLLAMA_URL.")

    hallazgos = cargar_hallazgos()
    print(f"Modelo {cliente.modelo} · prompt {PROMPT_VERSION} · {len(filas)} filas × {corridas} corridas\n")

    for f in filas:
        h = emparejar(f, hallazgos)
        f["encontrado"] = h is not None
        f["respuestas"] = []
        if h is None:
            print(f"  SIN PAREJA en los fixtures: {f['hallazgo']}")
            continue
        f["titulo_fixture"] = h["titulo"]
        f["severidad_zap"] = h["severity_tool_raw"]
        f["cwe_fixture"] = h["cwe_id"]
        f["evidencia_zap"] = h["evidence_snippet"]
        for c in range(1, corridas + 1):
            r = enriquecer(h, cliente)
            f["respuestas"].append({"corrida": c, **r})
            print(f"  [{c}] {h['titulo'][:45]:45} {r['owasp_category'] or 'FALLA'}  {r['priority'] or ''}")

    return {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "modelo": cliente.modelo,
        "prompt_version": PROMPT_VERSION,
        "corridas": corridas,
        "filas": filas,
    }


# ── Métricas ──────────────────────────────────────────────────────────────

def _distancia(a: str | None, b: str | None) -> int | None:
    return abs(int(a[1]) - int(b[1])) if a and b else None


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.0%})" if d else "sin datos"


def leer_marcas_alucinacion() -> dict:
    if not CSV_REVISION.exists():
        return {}
    texto = CSV_REVISION.read_text(encoding="utf-8-sig")
    dialecto = csv.Sniffer().sniff(texto.splitlines()[0], delimiters=",;\t")
    marcas = {}
    for f in csv.DictReader(texto.splitlines(), dialect=dialecto):
        valor = _normalizar(f.get("alucinacion"))
        if valor:
            marcas[(f.get("fila"), f.get("corrida"))] = valor in SI
    return marcas


def calcular(datos: dict, ambiguos: set[str] = frozenset()) -> dict:
    filas = [f for f in datos["filas"] if f.get("encontrado")]
    resp = [(f, r) for f in filas for r in f["respuestas"]]
    ok = [(f, r) for f, r in resp if r["state"] == "ok"]

    owasp = [(f, r) for f, r in ok if f["owasp_humano"]]
    owasp_ok = [(f, r) for f, r in owasp if r["owasp_category"] in f["owasp_humano"]]
    claros = [(f, r) for f, r in owasp if str(f["fila"]) not in ambiguos]
    claros_ok = [(f, r) for f, r in claros if (f, r) in owasp_ok]

    prio = [(f, r) for f, r in ok if f["prioridad_humana"]]
    prio_exacta = sum(r["priority"] == f["prioridad_humana"] for f, r in prio)
    prio_cerca = sum(_distancia(r["priority"], f["prioridad_humana"]) <= 1 for f, r in prio)

    regla = [(f, REGLA_PRIORIDAD.get(f["severidad_zap"])) for f in filas if f["prioridad_humana"]]
    regla_exacta = sum(p == f["prioridad_humana"] for f, p in regla)
    regla_cerca = sum(_distancia(p, f["prioridad_humana"]) <= 1 for f, p in regla if p)

    fp = [(f, r) for f, r in ok if f["falso_positivo"]]
    fp_urgente = sum(r["priority"] in ("p1", "p2") for f, r in fp)

    cambia_owasp = [f for f in filas if len({r["owasp_category"] for r in f["respuestas"]}) > 1]
    cambia_prio = [f for f in filas if len({r["priority"] for r in f["respuestas"]}) > 1]

    conf_ok = [r["confidence"] for f, r in owasp_ok]
    conf_mal = [r["confidence"] for f, r in owasp if (f, r) not in owasp_ok]

    marcas = leer_marcas_alucinacion()
    alucina = [v for (fila, corr), v in marcas.items()]

    return {
        "filas_csv": len(datos["filas"]),
        "filas_cruzadas": len(filas),
        "sin_pareja": [f["hallazgo"] for f in datos["filas"] if not f.get("encontrado")],
        "respuestas": len(resp),
        "fallidas": len(resp) - len(ok),
        "owasp": (len(owasp_ok), len(owasp)),
        "owasp_claros": (len(claros_ok), len(claros)),
        "ambiguos": sorted(ambiguos),
        "prio_exacta": (prio_exacta, len(prio)),
        "prio_cerca": (prio_cerca, len(prio)),
        "regla_exacta": (regla_exacta, len(regla)),
        "regla_cerca": (regla_cerca, len(regla)),
        "fp": (fp_urgente, len(fp)),
        "cambia_owasp": cambia_owasp,
        "cambia_prio": cambia_prio,
        "conf_ok": statistics.mean(conf_ok) if conf_ok else None,
        "conf_mal": statistics.mean(conf_mal) if conf_mal else None,
        "n_conf": (len(conf_ok), len(conf_mal)),
        "alucinacion": (sum(alucina), len(alucina)),
    }


# ── Salidas ───────────────────────────────────────────────────────────────

def escribir_revision(datos: dict) -> None:
    """Planilla para que una persona marque alucinaciones. Nunca pisa marcas existentes."""
    if CSV_REVISION.exists():
        print(f"\n{CSV_REVISION.name} ya existe: no se sobrescribe (puede tener marcas humanas).")
        return
    with open(CSV_REVISION, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["fila", "corrida", "hallazgo", "evidencia_zap", "owasp_modelo", "prioridad_modelo",
                    "explicacion", "impacto", "remediacion", "alucinacion", "nota"])
        for f in datos["filas"]:
            for r in f.get("respuestas", []):
                if r["state"] == "ok":
                    w.writerow([f["fila"], r["corrida"], f["hallazgo"], f.get("evidencia_zap") or "",
                                r["owasp_category"], r["priority"], r["explanation"], r["impact"],
                                r["remediation_summary"], "", ""])
    print(f"\nPlanilla para marcar alucinaciones: {CSV_REVISION}")


def escribir_reporte(datos: dict, m: dict, origen: str, args_extra: str = "") -> None:
    def fmt_conf(v):
        return f"{v:.2f}" if v is not None else "—"

    filas_tabla = []
    for f in datos["filas"]:
        if not f.get("encontrado"):
            continue
        modelo = " · ".join(f"{r['owasp_category'] or 'falla'} {r['priority'] or ''}".strip()
                            for r in f["respuestas"])
        humano = f"{' o '.join(c[:3] for c in f['owasp_humano']) or '—'} {f['prioridad_humana'] or ''}"
        regla = REGLA_PRIORIDAD.get(f["severidad_zap"], "—")
        fp = "sí" if f["falso_positivo"] else ""
        filas_tabla.append(f"| {f['fila']} | {f['hallazgo']} | {f['severidad_zap']} | {humano.strip()} | {modelo} | {regla} | {fp} |")

    alu_n, alu_d = m["alucinacion"]
    fila_claros = (f"| Acierto OWASP 2025 sin los casos ambiguos ({', '.join(m['ambiguos'])}) | {_pct(*m['owasp_claros'])} |"
                   if m["ambiguos"] else "")
    alucinacion = (_pct(alu_n, alu_d) if alu_d else
                   "pendiente: falta marcar `revision_alucinaciones.csv`")

    texto = f"""# Métricas del modelo contra el golden set (T-045)

**Generado:** {datetime.now():%d-%m-%Y %H:%M} · **Modelo:** `{datos['modelo']}` · **Prompt:** {datos['prompt_version']} · **Corridas por hallazgo:** {datos['corridas']}

**Anotación humana:** `docs/evidencias/validacion_manual.csv` (Felipe, sin ver las respuestas del modelo).
**Respuestas del modelo:** `{origen}`

Reproducir sin Ollama:
```powershell
cd backend
python scripts/metricas_golden_set.py --desde ..\\{origen.replace('/', chr(92))}{args_extra}
```

## Resultados

| Métrica | Resultado |
|---|---|
| Hallazgos del golden set cruzados con los fixtures | {m['filas_cruzadas']}/{m['filas_csv']} |
| Respuestas del modelo con formato válido | {_pct(m['respuestas'] - m['fallidas'], m['respuestas'])} |
| **Acierto OWASP 2025** (todos los hallazgos) | **{_pct(*m['owasp'])}** |
{fila_claros}
| **Acierto de prioridad (exacta), modelo** | **{_pct(*m['prio_exacta'])}** |
| Acierto de prioridad (a un tramo o menos), modelo | {_pct(*m['prio_cerca'])} |
| **Acierto de prioridad (exacta), regla fija por severidad** | **{_pct(*m['regla_exacta'])}** |
| Acierto de prioridad (a un tramo o menos), regla fija | {_pct(*m['regla_cerca'])} |
| Falsos positivos que el modelo trató como urgentes (p1 o p2) | {_pct(*m['fp'])} |
| Hallazgos con categoría distinta entre corridas | {len(m['cambia_owasp'])}/{m['filas_cruzadas']} |
| Hallazgos con prioridad distinta entre corridas | {len(m['cambia_prio'])}/{m['filas_cruzadas']} |
| Confianza media cuando acierta / cuando falla | {fmt_conf(m['conf_ok'])} (n={m['n_conf'][0]}) / {fmt_conf(m['conf_mal'])} (n={m['n_conf'][1]}) |
| **Tasa de alucinación** | **{alucinacion}** |

Los denominadores cuentan **respuestas** (hallazgos × corridas), salvo la regla fija, que es determinista y se cuenta una vez por hallazgo.

## Detalle por hallazgo

| ID | Hallazgo | Sev. ZAP | Humano (OWASP, prioridad) | Modelo (por corrida) | Regla fija | Falso positivo |
|---|---|---|---|---|---|---|
{chr(10).join(filas_tabla)}

## Método

- **OWASP:** acierto si la categoría del modelo está entre las que el anotador aceptó. Las filas sin categoría humana (no aplica) no se puntúan. Los casos que la rúbrica declara ambiguos (admiten más de una categoría razonable) se reportan también por separado.
- **Prioridad:** exacta, o a un tramo de distancia (p2 contra p3 cuenta como cercana).
- **Regla fija:** High → p1, Medium → p2, Low → p3, Informational → p4. Es la línea base contra la que se compara el modelo.
- **Alucinación:** una persona revisa cada respuesta en `revision_alucinaciones.csv` y marca `si` cuando el modelo afirma algo que la evidencia de ZAP no respalda. La tasa es marcas `si` sobre respuestas revisadas.

## Limitaciones

- Muestra inicial del golden set ({m['filas_csv']} hallazgos, un anotador). El golden set completo, con dos revisores por hallazgo, corresponde al S6 (T-041 a T-044).
- Temperatura 0.1 sin seed: los resultados varían entre corridas. Por eso se reporta más de una corrida.
"""
    if m["sin_pareja"]:
        texto += "- Filas del CSV sin pareja en los fixtures (no puntuadas): " + ", ".join(m["sin_pareja"]) + ".\n"
    REPORTE.write_text(texto, encoding="utf-8")
    print(f"Reporte: {REPORTE}")


def main() -> None:
    p = argparse.ArgumentParser(description="Métricas del modelo contra el golden set (T-045)")
    p.add_argument("--csv", type=Path, default=CSV_GOLDEN)
    p.add_argument("--corridas", type=int, default=2)
    p.add_argument("--desde", type=Path, help="JSON de una corrida anterior: recalcula sin Ollama")
    p.add_argument("--ambiguos", default="", help="IDs que la rúbrica declara ambiguos, separados por coma (ej. H02,H05)")
    args = p.parse_args()

    if args.desde:
        datos = json.loads(args.desde.read_text(encoding="utf-8"))
        origen = args.desde.resolve().relative_to(RAIZ).as_posix()
    else:
        if not args.csv.exists():
            sys.exit(f"No encuentro {args.csv}. ¿Ya trajiste el CSV de Felipe (git pull)?")
        datos = consultar_modelo(leer_golden(args.csv), args.corridas)
        DIR_RESPUESTAS.mkdir(parents=True, exist_ok=True)
        ruta = DIR_RESPUESTAS / f"golden_set_{datetime.now():%Y%m%d_%H%M%S}.json"
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        origen = ruta.relative_to(RAIZ).as_posix()
        print(f"\nRespuestas guardadas: {ruta}")
        escribir_revision(datos)

    ambiguos = {x.strip() for x in args.ambiguos.split(",") if x.strip()}
    m = calcular(datos, ambiguos)
    escribir_reporte(datos, m, origen, f" --ambiguos {args.ambiguos}" if ambiguos else "")
    print(f"\nOWASP {_pct(*m['owasp'])} (sin ambiguos {_pct(*m['owasp_claros'])}) · prioridad modelo {_pct(*m['prio_exacta'])} "
          f"· prioridad regla {_pct(*m['regla_exacta'])} · alucinación {_pct(*m['alucinacion'])}")


if __name__ == "__main__":
    main()
