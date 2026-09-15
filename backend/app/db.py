"""
SentinelAI · Motor de base de datos y gestión de sesiones.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_pre_ping=True,   # descarta conexiones muertas antes de usarlas;
                          # evita errores cuando el contenedor de la base se reinicia
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI. Una sesión por request, cerrada siempre."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
