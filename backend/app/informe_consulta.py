"""
Consultas a la base para el informe técnico (T-058, T-059).

app/informe.py arma y dibuja el informe sin tocar la base; acá se elige el
objetivo y se cargan sus escaneos y hallazgos. Lo usan la línea de comandos
(scripts/informe.py) y la API (GET /informe), así los dos generan lo mismo.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.informe import armar_datos, renderizar_html
from app.models import Finding, Scan, Target


def objetivos(db: Session) -> list[tuple[Target, int]]:
    """Objetivos con su cantidad de hallazgos, de más a menos."""
    filas = db.execute(
        select(Target, func.count(Finding.id))
        .outerjoin(Finding, Finding.target_id == Target.id)
        .group_by(Target.id)
        .order_by(func.count(Finding.id).desc(), Target.base_url)
    ).all()
    return [(t, n) for t, n in filas]


def elegir_objetivo(db: Session, base_url: str | None = None) -> Target | None:
    """El objetivo pedido, o el que tiene más hallazgos. None si no hay."""
    lista = objetivos(db)
    if base_url:
        return next((t for t, _ in lista if t.base_url == base_url), None)
    return lista[0][0] if lista else None


def generar(db: Session, objetivo: Target) -> tuple[str, dict]:
    """El informe de un objetivo: la página HTML y los datos con que se armó."""
    escaneos = db.scalars(select(Scan).where(Scan.target_id == objetivo.id)).all()
    hallazgos = db.scalars(
        select(Finding)
        .where(Finding.target_id == objetivo.id)
        .options(
            selectinload(Finding.instances),
            selectinload(Finding.enrichments),
            selectinload(Finding.validations),
        )
    ).all()
    datos = armar_datos(objetivo, escaneos, hallazgos)
    return renderizar_html(datos), datos
