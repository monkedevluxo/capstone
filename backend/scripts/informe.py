"""
Genera el informe técnico de un objetivo como una página HTML autocontenida
(tareas T-058 y T-059). Para PDF: abrir el HTML en el navegador e imprimir.

Uso (desde la raíz del repositorio, con el laboratorio arriba):

    docker compose exec -T api python scripts/informe.py --listar
    docker compose exec -T api python scripts/informe.py > informe.html
    docker compose exec -T api python scripts/informe.py --objetivo http://juiceshop:3000 > informe.html

Sin --objetivo usa el objetivo con más hallazgos. El HTML sale por stdout y los
avisos por stderr, así la redirección `>` deja solo el informe en el archivo.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.informe import armar_datos, renderizar_html  # noqa: E402
from app.models import Finding, Scan, Target  # noqa: E402


def _objetivos(db) -> list[tuple[Target, int]]:
    """Objetivos con su cantidad de hallazgos, de más a menos."""
    filas = db.execute(
        select(Target, func.count(Finding.id))
        .outerjoin(Finding, Finding.target_id == Target.id)
        .group_by(Target.id)
        .order_by(func.count(Finding.id).desc())
    ).all()
    return [(t, n) for t, n in filas]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--objetivo", help="base_url del objetivo (por defecto, el que tiene más hallazgos)")
    p.add_argument("--listar", action="store_true", help="lista los objetivos disponibles y sale")
    args = p.parse_args()

    with SessionLocal() as db:
        objetivos = _objetivos(db)
        if not objetivos:
            print("No hay objetivos en la base. Importa un escaneo primero.", file=sys.stderr)
            return 1

        if args.listar:
            for t, n in objetivos:
                print(f"{n:4d} hallazgos  {t.base_url}  ({t.nombre})")
            return 0

        if args.objetivo:
            elegido = next((t for t, _ in objetivos if t.base_url == args.objetivo), None)
            if elegido is None:
                print(f"No existe el objetivo {args.objetivo}. Usa --listar.", file=sys.stderr)
                return 1
        else:
            elegido = objetivos[0][0]
            if len(objetivos) > 1:
                print(f"Usando {elegido.base_url} (el de más hallazgos). Cambia con --objetivo.",
                      file=sys.stderr)

        escaneos = db.scalars(select(Scan).where(Scan.target_id == elegido.id)).all()
        hallazgos = db.scalars(
            select(Finding)
            .where(Finding.target_id == elegido.id)
            .options(
                selectinload(Finding.instances),
                selectinload(Finding.enrichments),
                selectinload(Finding.validations),
            )
        ).all()

        datos = armar_datos(elegido, escaneos, hallazgos)
        sys.stdout.write(renderizar_html(datos))
        r = datos["resumen"]
        print(f"Informe generado: {r['total']} hallazgos ({r['vigentes']} vigentes, "
              f"{r['descartados']} descartados).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
