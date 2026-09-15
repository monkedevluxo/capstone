"""
SentinelAI · Aplicación FastAPI.

Por ahora solo el esqueleto y el healthcheck (tarea T-010). Los endpoints de
ingesta y consulta llegan en el S3.
"""

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Finding, Scan, Target

app = FastAPI(
    title="SentinelAI",
    description="Hallazgos de seguridad web priorizados con IA local",
    version="0.1.0",
)


@app.get("/health", tags=["sistema"])
def health(db: Session = Depends(get_db)):
    """
    Verifica que la aplicación responde Y que la base contesta.

    Un healthcheck que solo devuelve 200 sin tocar la base miente: la API puede
    estar viva con la base caída. Por eso ejecuta una consulta real.
    """
    try:
        db.execute(text("SELECT 1"))
        base = "ok"
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"estado": "degradado", "base_datos": f"error: {type(exc).__name__}"},
        )

    return {
        "estado": "ok",
        "base_datos": base,
        "schema_version": settings.SCHEMA_VERSION,
    }


@app.get("/stats", tags=["sistema"])
def stats(db: Session = Depends(get_db)):
    """Conteos básicos. Sirve para confirmar que el seed cargó bien."""
    por_severidad = dict(
        db.execute(
            select(Finding.severity, func.count()).group_by(Finding.severity)
        ).all()
    )
    return {
        "objetivos": db.scalar(select(func.count()).select_from(Target)),
        "escaneos": db.scalar(select(func.count()).select_from(Scan)),
        "hallazgos": db.scalar(select(func.count()).select_from(Finding)),
        "por_severidad": {k.value: v for k, v in por_severidad.items()},
    }
