"""
SentinelAI · Configuración leída desde variables de entorno.

Nada de credenciales en el código. El .env no se versiona; sí se versiona
.env.ejemplo para que cualquiera pueda levantar el proyecto (tarea T-065).
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = (
        "postgresql+psycopg://sentinel:sentinel_local@db:5432/sentinelai"
    )
    OLLAMA_URL: str = "http://host.docker.internal:11434"
    # Parámetros del enriquecimiento (app/ia). Ver docs/diseno/IA_MODELO_Y_PROMPT.md
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    OLLAMA_TIMEOUT_S: float = 120.0
    OLLAMA_KEEP_ALIVE: str = "10m"
    OLLAMA_SEED: int | None = None   # fijarla solo para demos reproducibles
    SCHEMA_VERSION: str = "1.0.0"

    # echo=True imprime cada consulta SQL. Útil mientras se arma el modelo,
    # insoportable después. Se activa con SQL_ECHO=true en el .env.
    SQL_ECHO: bool = False


settings = Settings()
