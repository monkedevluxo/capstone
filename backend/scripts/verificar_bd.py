"""
SentinelAI · Verificación de la base de datos

Comprueba que el esquema aplicado hace cumplir las reglas del proyecto.
Lo corre el CI después de migrar y cargar el seed, pero sirve también local:

    python scripts/verificar_bd.py

Cada verificación intenta algo que la base DEBE rechazar. Si lo acepta,
el script falla: significa que alguien debilitó una restricción.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.db import engine  # noqa: E402
from app.models import Finding  # noqa: E402

fallos = 0


def debe_rechazar(nombre: str, sql: str, params: dict | None = None) -> None:
    """Ejecuta un INSERT que la base debe rechazar, y revierte siempre."""
    global fallos
    with engine.connect() as c:
        tx = c.begin()
        try:
            c.execute(text(sql), params or {})
            print(f"  FALLA  {nombre}: la base lo aceptó")
            fallos += 1
        except IntegrityError:
            print(f"  OK     {nombre}")
        finally:
            tx.rollback()


print("Datos del seed")
with engine.connect() as c:
    n = c.scalar(select(func.count()).select_from(Finding))
    if n == 40:
        print("  OK     40 hallazgos cargados")
    else:
        print(f"  FALLA  se esperaban 40 hallazgos, hay {n}")
        fallos += 1
    un_hallazgo = c.scalar(select(Finding.id).limit(1))

print("\nRestricciones del proyecto")

debe_rechazar(
    "solo se aceptan objetivos del laboratorio (Ley 21.459)",
    "INSERT INTO targets (nombre, base_url, environment) "
    "VALUES ('externo', 'http://ejemplo.com', 'prod')",
)

debe_rechazar(
    "un enriquecimiento fallido no puede traer datos a medias",
    "INSERT INTO ai_enrichments (finding_id, state, model, prompt_version, "
    "owasp_category, failure_reason, is_current) "
    "VALUES (:f, 'failed', 'm', 'p', 'A05:2025', 'timeout', false)",
    {"f": un_hallazgo},
)

debe_rechazar(
    "un hallazgo no puede tener dos enriquecimientos vigentes",
    "INSERT INTO ai_enrichments (finding_id, state, model, prompt_version, is_current) "
    "VALUES (:f, 'ok', 'm', 'p', true), (:f, 'ok', 'm', 'p', true)",
    {"f": un_hallazgo},
)

debe_rechazar(
    "la confianza del modelo va entre 0 y 1",
    "INSERT INTO ai_enrichments (finding_id, state, model, prompt_version, "
    "confidence, is_current) VALUES (:f, 'ok', 'm', 'p', 1.7, false)",
    {"f": un_hallazgo},
)

debe_rechazar(
    "no se puede duplicar un hallazgo en el mismo objetivo",
    "INSERT INTO findings (target_id, tool, rule_id, source_raw, titulo, url, "
    "path_template, severity, dedupe_key) "
    "SELECT target_id, tool, rule_id, source_raw, titulo, url, path_template, "
    "severity, dedupe_key FROM findings LIMIT 1",
)

print()
if fallos:
    print(f"{fallos} verificación(es) fallaron.")
    sys.exit(1)
print("Todas las verificaciones pasaron.")
