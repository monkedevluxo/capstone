"""
Intercambia enriquecimientos y validaciones entre las bases de cada equipo,
para anotar el golden set entre varios revisores. La lógica vive en
app/intercambio.py; esto es solo la línea de comandos.

Uso (dentro del contenedor api; el archivo va por stdin/stdout):

    docker compose exec -T api python scripts/intercambio.py exportar --que enriquecimientos > enr.json
    docker compose exec -T api python scripts/intercambio.py exportar --que validaciones --revisor "Felipe" > val.json
    docker compose exec -T api python scripts/intercambio.py importar --simular < enr.json
    docker compose exec -T api python scripts/intercambio.py importar < enr.json
    docker compose exec -T api python scripts/intercambio.py metricas [--json]

Exportar y metricas abren una transacción de solo lectura. Importar hace todo
en una transacción: --simular la deshace y muestra el mismo reporte.

Códigos de salida: 0 bien, 2 archivo inválido (no se importó nada).
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.intercambio import (  # noqa: E402
    TIPOS, ArchivoInvalido, exportar, importar, metricas, metricas_texto,
)


def _solo_lectura(db) -> None:
    db.execute(text("SET TRANSACTION READ ONLY"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)
    e = sub.add_parser("exportar", help="escribe el archivo de intercambio en stdout")
    e.add_argument("--que", choices=TIPOS, required=True)
    e.add_argument("--revisor", help="solo las validaciones de este revisor")
    i = sub.add_parser("importar", help="lee el archivo de intercambio desde stdin")
    i.add_argument("--simular", action="store_true", help="muestra el reporte y deshace todo")
    m = sub.add_parser("metricas", help="métricas del golden set y acuerdo entre revisores")
    m.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    if args.comando == "exportar" and args.revisor and args.que != "validaciones":
        p.error("--revisor solo aplica a --que validaciones")

    with SessionLocal() as db:
        if args.comando == "exportar":
            _solo_lectura(db)
            json.dump(exportar(db, args.que, revisor=args.revisor), sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
            return 0

        if args.comando == "metricas":
            _solo_lectura(db)
            m = metricas(db)
            print(json.dumps(m, ensure_ascii=False, indent=2) if args.json else metricas_texto(m))
            return 0

        try:
            archivo = json.load(sys.stdin)
        except json.JSONDecodeError as err:
            print(f"Archivo inválido, no se importó nada: no es JSON ({err})", file=sys.stderr)
            return 2
        try:
            reporte = importar(db, archivo)
        except ArchivoInvalido as err:
            db.rollback()
            print("Archivo inválido, no se importó nada:", file=sys.stderr)
            for x in err.errores:
                print(f"  - {x}", file=sys.stderr)
            return 2
        if args.simular:
            db.rollback()
        else:
            db.commit()
        print(reporte.texto(simulado=args.simular))
        return 0


if __name__ == "__main__":
    sys.exit(main())
