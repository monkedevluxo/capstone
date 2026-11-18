"""
Comparte los enriquecimientos del modelo entre las bases locales del equipo,
para anotar el golden set sin que cada uno tenga que correr Ollama.

Quien tiene Ollama importa los fixtures, enriquece y EXPORTA a un JSON. El resto
importa los mismos fixtures y CARGA ese JSON. Así todos anotan exactamente las
mismas respuestas del modelo.

Cada hallazgo se busca por (objetivo, dedupe_key), no por id: los ids cambian en
cada máquina, pero la dedupe_key es el mismo hash en todas (normalizacion.py).

Uso (docs/ no está montado en el contenedor, por eso el archivo va por
stdout/stdin; -T evita que Docker mezcle la salida con la terminal):

    # 1. Quien tiene Ollama, después de importar y enriquecer:
    docker compose exec -T api python scripts/compartir_enriquecimientos.py exportar \\
        > docs/evidencias/respuestas_modelo/enriquecimientos_AAAAMMDD.json

    # 2. El resto, después de importar los mismos fixtures:
    docker compose exec -T api python scripts/compartir_enriquecimientos.py cargar - \\
        < docs/evidencias/respuestas_modelo/enriquecimientos_AAAAMMDD.json

`exportar` acepta --escaneo ID (repetible) para exportar solo los hallazgos
vistos en esos escaneos. Sin filtro exporta todos los enriquecimientos vigentes.

`cargar` es solo para desarrollo local: se niega a correr si encuentra la
variable CI. Correrlo dos veces no duplica nada. Si un hallazgo ya tenía otro
enriquecimiento vigente, lo deja como histórico (is_current = false), igual que
un reenriquecimiento normal.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FORMATO = "sentinelai-enriquecimientos/1"

# Columnas de ai_enrichments que viajan en el archivo. id, finding_id e
# is_current no: dependen de cada base.
CAMPOS = (
    "state", "model", "prompt_version", "prompt_sha256", "attempts",
    "latency_ms", "failure_reason", "explanation", "impact", "owasp_version",
    "owasp_category", "priority", "confidence", "remediation_summary",
    "remediation_steps",
)


# --- Partes puras (sin base de datos; las prueba test_compartir_enriquecimientos)

def _valor(v):
    """Enum -> su valor; datetime -> ISO 8601; el resto tal cual."""
    if isinstance(v, datetime):
        return v.isoformat()
    return getattr(v, "value", v)


def enriquecimiento_a_dict(e) -> dict:
    """Fila de ai_enrichments (o cualquier objeto con esos atributos) -> dict JSON."""
    d = {c: _valor(getattr(e, c)) for c in CAMPOS}
    d["generated_at"] = _valor(getattr(e, "generated_at", None))
    return d


def misma_respuesta(a: dict, b: dict) -> bool:
    """True si dos enriquecimientos son la misma respuesta del modelo.

    No compara generated_at: es metadato de la corrida y su formato puede
    variar entre bases sin que cambie la respuesta.
    """
    return all(a.get(c) == b.get(c) for c in CAMPOS)


def validar_archivo(datos) -> list[str]:
    """Errores de forma del archivo. Lista vacía si se puede cargar."""
    if not isinstance(datos, dict):
        return ["el archivo no es un objeto JSON"]
    if datos.get("formato") != FORMATO:
        return [f"formato {datos.get('formato')!r}, se esperaba {FORMATO!r}"]
    filas = datos.get("enriquecimientos")
    if not isinstance(filas, list):
        return ["falta la lista 'enriquecimientos'"]
    errores = []
    for i, f in enumerate(filas):
        faltan = [k for k in ("objetivo", "dedupe_key", "enriquecimiento") if not f.get(k)]
        if faltan:
            errores.append(f"fila {i}: faltan {', '.join(faltan)}")
            continue
        e = f["enriquecimiento"]
        faltan = [c for c in ("state", "model", "prompt_version", "attempts") if e.get(c) in (None, "")]
        if faltan:
            errores.append(f"fila {i} ({f['dedupe_key']}): faltan {', '.join(faltan)}")
    return errores


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    fecha = datetime.fromisoformat(valor)
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


# --- Exportar -----------------------------------------------------------------

def exportar(escaneos: list[uuid.UUID]) -> dict:
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import AiEnrichment, Finding, FindingObservation, Target

    consulta = (
        select(AiEnrichment, Finding, Target.base_url)
        .join(Finding, AiEnrichment.finding_id == Finding.id)
        .join(Target, Finding.target_id == Target.id)
        .where(AiEnrichment.is_current.is_(True))
        .order_by(Target.base_url, Finding.dedupe_key)
    )
    if escaneos:
        vistos = select(FindingObservation.finding_id).where(
            FindingObservation.scan_id.in_(escaneos)
        )
        consulta = consulta.where(Finding.id.in_(vistos))

    with SessionLocal() as db:
        filas = [
            {
                "objetivo": base_url,
                "dedupe_key": f.dedupe_key,
                # Solo para que una persona sepa de qué hallazgo se trata.
                "titulo": f.titulo,
                "param": f.param,
                "enriquecimiento": enriquecimiento_a_dict(e),
            }
            for e, f, base_url in db.execute(consulta).all()
        ]

    return {
        "formato": FORMATO,
        "exportado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "escaneos": [str(s) for s in escaneos] or "todos",
        "total": len(filas),
        "enriquecimientos": filas,
    }


# --- Cargar -------------------------------------------------------------------

def cargar(datos: dict) -> int:
    errores = validar_archivo(datos)
    if errores:
        for err in errores:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    from sqlalchemy import select, update

    from app.db import SessionLocal
    from app.models import AiEnrichment, CategoriaOwasp, EstadoIA, Finding, Prioridad, Target

    cargados = sin_cambios = omitidos = 0

    with SessionLocal() as db:
        for fila in datos["enriquecimientos"]:
            r = fila["enriquecimiento"]
            etiqueta = f"{fila['dedupe_key']} {fila.get('titulo') or ''}".strip()
            if fila.get("param"):
                etiqueta += f" [{fila['param']}]"

            f = db.scalar(
                select(Finding)
                .join(Target, Finding.target_id == Target.id)
                .where(Target.base_url == fila["objetivo"], Finding.dedupe_key == fila["dedupe_key"])
            )
            if f is None:
                print(f"  omitido   {etiqueta}: no está en tu base (¿importaste el mismo fixture?)")
                omitidos += 1
                continue

            vigente = db.scalar(
                select(AiEnrichment).where(
                    AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True)
                )
            )
            if vigente is not None and misma_respuesta(enriquecimiento_a_dict(vigente), r):
                print(f"  igual     {etiqueta}: ya estaba cargado")
                sin_cambios += 1
                continue

            db.execute(
                update(AiEnrichment)
                .where(AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True))
                .values(is_current=False)
            )
            nueva = AiEnrichment(
                finding_id=f.id,
                is_current=True,
                **{c: r.get(c) for c in CAMPOS},
            )
            nueva.state = EstadoIA(r["state"])
            nueva.owasp_category = CategoriaOwasp(r["owasp_category"]) if r.get("owasp_category") else None
            nueva.priority = Prioridad(r["priority"]) if r.get("priority") else None
            generado = _fecha(r.get("generated_at"))
            if generado is not None:
                nueva.generated_at = generado
            db.add(nueva)
            print(
                f"  cargado   {etiqueta}: {r['state']} {r.get('owasp_category')} "
                f"{r.get('priority')}"
            )
            cargados += 1

        db.commit()

    print(f"\n{cargados} cargados, {sin_cambios} sin cambios, {omitidos} omitidos")
    return 0


# --- Línea de comandos --------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="accion", required=True)

    ex = sub.add_parser("exportar", help="escribe los enriquecimientos vigentes en stdout")
    ex.add_argument("--escaneo", action="append", default=[], metavar="ID", type=uuid.UUID,
                    help="solo hallazgos vistos en este escaneo (repetible)")

    ca = sub.add_parser("cargar", help="carga un archivo exportado en la base local")
    ca.add_argument("archivo", help="JSON exportado, o - para leer de stdin")

    args = ap.parse_args(argv)

    if args.accion == "exportar":
        datos = exportar(args.escaneo)
        json.dump(datos, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        print(f"{datos['total']} enriquecimientos exportados", file=sys.stderr)
        return 0

    if os.environ.get("CI"):
        print("cargar es solo para desarrollo local; no corre en el CI.", file=sys.stderr)
        return 2
    if args.archivo == "-":
        datos = json.load(sys.stdin)
    else:
        with open(args.archivo, encoding="utf-8") as fh:
            datos = json.load(fh)
    return cargar(datos)


if __name__ == "__main__":
    sys.exit(main())
