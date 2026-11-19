"""
SentinelAI · Reglas de la validación humana (T-057).

El estado de un hallazgo lo fija su validación más reciente
(docs/diseno/ESQUEMA_HALLAZGO.md, sección 7). Lo usan la ruta
POST /findings/{id}/validaciones y la importación entre equipos
(scripts/intercambio.py), para que la regla viva en un solo lugar.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DecisionValidacion, EstadoHallazgo, Finding, Validation

ESTADO_POR_DECISION: dict[DecisionValidacion, EstadoHallazgo] = {
    DecisionValidacion.confirmado: EstadoHallazgo.confirmado,
    DecisionValidacion.falso_positivo: EstadoHallazgo.falso_positivo,
    DecisionValidacion.riesgo_aceptado: EstadoHallazgo.riesgo_aceptado,
    DecisionValidacion.duplicado: EstadoHallazgo.duplicado,
    DecisionValidacion.requiere_segunda_opinion: EstadoHallazgo.en_triage,
}


def recalcular_estado(db: Session, f: Finding) -> EstadoHallazgo | None:
    """Deja f.status según la validación más reciente. No hace commit.

    Más reciente = mayor reviewed_at; si dos empatan, el mayor id, para que el
    resultado no dependa del orden en que la base devuelva las filas.
    Sin validaciones no toca el estado y devuelve None.
    """
    db.flush()
    decision = db.scalar(
        select(Validation.decision)
        .where(Validation.finding_id == f.id)
        .order_by(Validation.reviewed_at.desc(), Validation.id.desc())
        .limit(1)
    )
    if decision is None:
        return None
    f.status = ESTADO_POR_DECISION[decision]
    return f.status
