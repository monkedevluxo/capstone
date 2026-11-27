"""
Genera el informe técnico de un objetivo como una página HTML autocontenida
(tareas T-058 y T-059). En PDF: GET /informe.pdf o el botón "Exportar informe".
El dashboard muestra el mismo informe con el botón "Informe" (GET /informe).

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

from app.db import SessionLocal  # noqa: E402
from app.informe_consulta import generar, objetivos  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--objetivo", help="base_url del objetivo (por defecto, el que tiene más hallazgos)")
    p.add_argument("--listar", action="store_true", help="lista los objetivos disponibles y sale")
    args = p.parse_args()

    with SessionLocal() as db:
        lista = objetivos(db)
        if not lista:
            print("No hay objetivos en la base. Importa un escaneo primero.", file=sys.stderr)
            return 1

        if args.listar:
            for t, n in lista:
                print(f"{n:4d} hallazgos  {t.base_url}  ({t.nombre})")
            return 0

        if args.objetivo:
            elegido = next((t for t, _ in lista if t.base_url == args.objetivo), None)
            if elegido is None:
                print(f"No existe el objetivo {args.objetivo}. Usa --listar.", file=sys.stderr)
                return 1
        else:
            elegido = lista[0][0]
            if len(lista) > 1:
                print(f"Usando {elegido.base_url} (el de más hallazgos). Cambia con --objetivo.",
                      file=sys.stderr)

        html, datos = generar(db, elegido)
        sys.stdout.write(html)
        r = datos["resumen"]
        print(f"Informe generado: {r['total']} hallazgos ({r['vigentes']} vigentes, "
              f"{r['descartados']} descartados).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
