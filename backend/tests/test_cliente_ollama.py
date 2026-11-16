"""
SentinelAI · Tests del cliente de Ollama (app/ia/cliente.py).

No necesitan Ollama ni base de datos: simulan las fallas de red con un
servidor HTTP local de una sola conexión o reemplazando urlopen.

    cd backend
    python -m pytest tests/test_cliente_ollama.py -v
"""

import http.client
import socket
import struct
import threading
import urllib.error
import urllib.request

import pytest

from app.ia.cliente import ClienteOllama, OllamaNoDisponible


def _cliente(url: str = "http://ollama.invalid") -> ClienteOllama:
    return ClienteOllama(url=url, modelo="modelo-de-prueba", timeout_s=5)


def _servidor_que_corta(modo: str) -> str:
    """Acepta una conexión, lee el pedido y la corta sin responder bien.

    modo "cierra": cierra limpio (el cliente ve RemoteDisconnected).
    modo "reset":  SO_LINGER 0, el cliente recibe un RST (ConnectionResetError).
    modo "a_medias": manda cabeceras con Content-Length y solo parte del cuerpo.
    """
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def atender():
        conn, _ = srv.accept()
        conn.recv(65536)
        if modo == "reset":
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        elif modo == "a_medias":
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Content-Length: 100\r\n\r\n{\"response\": \"{"
            )
        conn.close()
        srv.close()

    threading.Thread(target=atender, daemon=True).start()
    return f"http://127.0.0.1:{srv.getsockname()[1]}"


@pytest.mark.parametrize("modo", ["cierra", "reset", "a_medias"])
def test_ollama_que_corta_la_conexion_cuenta_como_no_disponible(modo):
    # Antes de la corrección, estas fallas no eran URLError y se escapaban:
    # POST /scans/{id}/enrich respondía 500 en vez de detenido_por.
    with pytest.raises(OllamaNoDisponible):
        _cliente(_servidor_que_corta(modo)).generar("hola")


@pytest.mark.parametrize(
    "error",
    [
        ConnectionResetError(104, "Connection reset by peer"),
        http.client.RemoteDisconnected("Remote end closed connection without response"),
        ConnectionAbortedError(103, "Software caused connection abort"),
        BrokenPipeError(32, "Broken pipe"),
    ],
    ids=lambda e: type(e).__name__,
)
def test_errores_de_conexion_de_urlopen_son_no_disponible(monkeypatch, error):
    def urlopen_que_falla(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_que_falla)
    with pytest.raises(OllamaNoDisponible):
        _cliente().generar("hola")


def test_conexion_rechazada_sigue_siendo_no_disponible(monkeypatch):
    def urlopen_rechazado(*_args, **_kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_rechazado)
    with pytest.raises(OllamaNoDisponible):
        _cliente().generar("hola")
