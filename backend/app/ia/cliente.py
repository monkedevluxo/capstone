"""
SentinelAI · Cliente de Ollama (tarea T-028).

Un módulo aislado que solo sabe hablar con Ollama. No conoce la base de datos
ni el esquema: recibe un prompt y devuelve texto, o lanza un error tipado.

Solo usa la biblioteca estándar, así que no agrega dependencias al backend.
Toda la configuración sale de variables de entorno (app/config.py).
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class ErrorOllama(Exception):
    """Base. `motivo` es corto porque va a la columna failure_reason (40 caracteres)."""
    motivo = "error_ollama"


class OllamaTimeout(ErrorOllama):
    motivo = "timeout"


class OllamaNoDisponible(ErrorOllama):
    motivo = "ollama_no_disponible"


class OllamaRespuestaInvalida(ErrorOllama):
    motivo = "respuesta_http_invalida"


@dataclass
class Respuesta:
    texto: str
    latencia_ms: int


class ClienteOllama:
    def __init__(
        self,
        url: str,
        modelo: str,
        timeout_s: float = 120.0,
        keep_alive: str = "10m",
        seed: int | None = None,
        temperatura: float = 0.1,
    ):
        self.url = url.rstrip("/")
        self.modelo = modelo
        self.timeout_s = timeout_s
        self.keep_alive = keep_alive
        self.seed = seed
        self.temperatura = temperatura

    @classmethod
    def desde_config(cls) -> "ClienteOllama":
        from app.config import settings
        return cls(
            url=settings.OLLAMA_URL,
            modelo=settings.OLLAMA_MODEL,
            timeout_s=settings.OLLAMA_TIMEOUT_S,
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            seed=settings.OLLAMA_SEED,
        )

    def generar(self, prompt: str) -> Respuesta:
        """Una llamada a /api/generate en modo JSON. No reintenta: eso lo decide quien llama."""
        opciones: dict = {"temperature": self.temperatura}
        if self.seed is not None:
            opciones["seed"] = self.seed

        cuerpo = json.dumps({
            "model": self.modelo,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": self.keep_alive,
            "options": opciones,
        }).encode()
        req = urllib.request.Request(
            f"{self.url}/api/generate", data=cuerpo,
            headers={"Content-Type": "application/json"},
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                datos = json.loads(r.read())
        except (TimeoutError, socket.timeout) as exc:
            raise OllamaTimeout(f"sin respuesta en {self.timeout_s:.0f}s") from exc
        except urllib.error.HTTPError as exc:
            raise OllamaRespuestaInvalida(f"HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise OllamaTimeout(f"sin respuesta en {self.timeout_s:.0f}s") from exc
            raise OllamaNoDisponible(f"no se pudo conectar a {self.url}: {exc.reason}") from exc
        except (json.JSONDecodeError, ValueError) as exc:
            raise OllamaRespuestaInvalida("Ollama no devolvio JSON") from exc

        if "response" not in datos:
            raise OllamaRespuestaInvalida("falta el campo 'response'")
        latencia = int((time.perf_counter() - t0) * 1000)
        return Respuesta(texto=datos["response"], latencia_ms=latencia)

    def disponible(self) -> bool:
        """Para healthchecks: ¿Ollama contesta en /api/tags?"""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=5) as r:
                return r.status == 200
        except (urllib.error.URLError, TimeoutError, socket.timeout, OSError):
            return False
