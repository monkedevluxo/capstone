"""
Carga en la base local las respuestas del modelo guardadas en una corrida del
golden set, para trabajar el dashboard sin tener Ollama a mano.

SOLO PARA DESARROLLO LOCAL. No lo usa el CI y se niega a correr si encuentra
la variable CI (GitHub Actions la define siempre).

Para cada fila del archivo busca el hallazgo con el mismo título y guarda la
primera respuesta (corrida 1) como enriquecimiento vigente, con los campos tal
cual vienen: modelo, versión y hash del prompt, intentos, latencia, estado y la
salida completa. `generated_at` toma la fecha de la corrida, no la de la carga.

- Si un título calza con más de un hallazgo (mismo tipo de alerta con distinto
  parámetro), el archivo no trae ruta ni parámetro para saber a cuál
  corresponde. Se usa el parámetro de PARAMETRO_POR_FILA; si la fila no está
  ahí, se omite: el script no adivina.
- Si el hallazgo ya tiene como vigente una respuesta con el mismo hash de
  prompt y la misma explicación, no hace nada. Correrlo dos veces no duplica.
- Si tiene otro enriquecimiento vigente, lo deja como histórico (is_current =
  false), igual que un reenriquecimiento normal.

Uso (docs/ no está montado en el contenedor, por eso el archivo va por stdin):

    docker compose exec -T api python scripts/cargar_respuestas_golden.py - \\
        < docs/evidencias/respuestas_modelo/golden_set_20261014_234209.json

    # o desde backend/, con DATABASE_URL apuntando a la base local:
    python scripts/cargar_respuestas_golden.py \\
        ../docs/evidencias/respuestas_modelo/golden_set_20261014_234209.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AiEnrichment,
    CategoriaOwasp,
    EstadoIA,
    Finding,
    Prioridad,
)


# Filas cuyo título calza con más de un hallazgo, y el parámetro del que
# corresponde. Lo confirma el equipo, no se deduce del archivo.
PARAMETRO_POR_FILA = {
    # El golden set salió de ajax_v2, donde el hallazgo es el de itemTotal.
    # El de bid aparece recién en el escaneo autenticado (ajax_auth_v1).
    "H10": "itemTotal",
}


def _leer(origen: str) -> dict:
    if origen == "-":
        return json.load(sys.stdin)
    with open(origen, encoding="utf-8") as fh:
        return json.load(fh)


def _fecha_corrida(datos: dict) -> datetime | None:
    """La fecha del archivo viene sin zona; las corridas se hicieron en Chile."""
    fecha = datos.get("fecha")
    if not fecha:
        return None
    valor = datetime.fromisoformat(fecha)
    if valor.tzinfo is None:
        from zoneinfo import ZoneInfo

        valor = valor.replace(tzinfo=ZoneInfo("America/Santiago"))
    return valor.astimezone(timezone.utc)


def _fila_enriquecimiento(finding_id, r: dict, generado: datetime | None) -> AiEnrichment:
    fila = AiEnrichment(
        finding_id=finding_id,
        state=EstadoIA(r["state"]),
        model=r["model"],
        prompt_version=r["prompt_version"],
        prompt_sha256=r.get("prompt_sha256"),
        attempts=r["attempts"],
        latency_ms=r.get("latency_ms"),
        failure_reason=r.get("failure_reason"),
        explanation=r.get("explanation"),
        impact=r.get("impact"),
        owasp_version=r.get("owasp_version"),
        owasp_category=CategoriaOwasp(r["owasp_category"]) if r.get("owasp_category") else None,
        priority=Prioridad(r["priority"]) if r.get("priority") else None,
        confidence=r.get("confidence"),
        remediation_summary=r.get("remediation_summary"),
        remediation_steps=r.get("remediation_steps"),
        is_current=True,
    )
    if generado is not None:
        fila.generated_at = generado
    return fila


def cargar(datos: dict) -> int:
    generado = _fecha_corrida(datos)
    cargados = omitidos = sin_cambios = 0

    with SessionLocal() as db:
        for fila in datos["filas"]:
            etiqueta = f"{fila.get('fila', '?')} {fila['hallazgo']}"
            respuestas = sorted(fila.get("respuestas") or [], key=lambda r: r.get("corrida", 0))
            if not respuestas:
                print(f"  omitido   {etiqueta}: sin respuestas del modelo")
                omitidos += 1
                continue
            r = respuestas[0]

            candidatos = db.scalars(
                select(Finding).where(Finding.titulo == fila["hallazgo"])
            ).all()
            if not candidatos:
                print(f"  omitido   {etiqueta}: no hay un hallazgo con ese título")
                omitidos += 1
                continue
            if len(candidatos) > 1:
                parametro = PARAMETRO_POR_FILA.get(fila.get("fila"))
                elegidos = [c for c in candidatos if parametro is not None and c.param == parametro]
                if len(elegidos) != 1:
                    detalle = (
                        f"ninguno o varios con parámetro {parametro!r}"
                        if parametro is not None
                        else "falta en PARAMETRO_POR_FILA"
                    )
                    print(
                        f"  omitido   {etiqueta}: {len(candidatos)} hallazgos con ese título, "
                        f"{detalle}; no se adivina"
                    )
                    omitidos += 1
                    continue
                candidatos = elegidos
                etiqueta += f" [{parametro}]"
            f = candidatos[0]

            vigente = db.scalar(
                select(AiEnrichment).where(
                    AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True)
                )
            )
            if (
                vigente is not None
                and vigente.prompt_sha256 == r.get("prompt_sha256")
                and vigente.explanation == r.get("explanation")
            ):
                print(f"  igual     {etiqueta}: ya estaba cargado")
                sin_cambios += 1
                continue

            db.execute(
                update(AiEnrichment)
                .where(AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True))
                .values(is_current=False)
            )
            db.add(_fila_enriquecimiento(f.id, r, generado))
            print(
                f"  cargado   {etiqueta}: {r['state']} {r.get('owasp_category')} "
                f"{r.get('priority')} confianza {r.get('confidence')}"
            )
            cargados += 1

        db.commit()

    print(f"\n{cargados} cargados, {sin_cambios} sin cambios, {omitidos} omitidos")
    return 0


def main() -> int:
    if os.environ.get("CI"):
        print("Este script es solo para desarrollo local; no corre en el CI.", file=sys.stderr)
        return 2

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("archivo", help="JSON de respuestas del golden set, o - para leer de stdin")
    args = ap.parse_args()
    return cargar(_leer(args.archivo))


if __name__ == "__main__":
    sys.exit(main())
