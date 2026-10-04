"""
SentinelAI · Enriquecimiento de un hallazgo con el modelo local (T-028 a T-031).

Flujo de UN hallazgo:

    hallazgo normalizado (parser)
        -> prompt v2
        -> Ollama (cliente.py)
        -> validación (esquema.py)
             ├─ válida   -> state="ok" con los campos
             └─ inválida -> se reenvía el prompt con los motivos del rechazo
                            (máximo 3 intentos en total)
        -> tras 3 fallos: state="failed", TODOS los campos de contenido en None

La salida es un diccionario con los nombres EXACTOS de las columnas de
`ai_enrichments` (app/models.py, clase AiEnrichment). Quien persiste solo hace:

    AiEnrichment(finding_id=..., **enriquecer(hallazgo))

Regla que no se negocia: nunca se inventa un campo. Si el modelo no entregó
algo válido, el hallazgo queda visiblemente "sin enriquecer".

Probar contra Ollama real (desde backend/, con el .venv activo):

    python -m app.ia.enriquecer ..\\lab\\fixtures\\zap_juiceshop_baseline_v1.json
"""

from __future__ import annotations

import hashlib
import logging
import time

from app.ia.cliente import ClienteOllama, ErrorOllama, OllamaNoDisponible
from app.ia.esquema import validar
from app.ia.prompt import PROMPT_VERSION, construir_prompt, construir_reparacion

log = logging.getLogger(__name__)

MAX_INTENTOS = 3


def _fila(cliente: ClienteOllama, sha: str, intentos: int, latencia_ms: int) -> dict:
    """Columnas comunes a un resultado ok y a uno fallido."""
    return {
        "model": cliente.modelo,
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": sha,
        "attempts": intentos,
        "latency_ms": latencia_ms,
    }


def _fallido(base: dict, motivo: str) -> dict:
    # La base de datos exige (ck_enrichment_fallo_sin_datos) que un fallo no
    # deje campos de contenido rellenados a medias.
    return {
        **base,
        "state": "failed",
        "failure_reason": motivo[:40],
        "explanation": None,
        "impact": None,
        "owasp_version": None,
        "owasp_category": None,
        "priority": None,
        "confidence": None,
        "remediation_summary": None,
        "remediation_steps": None,
    }


def enriquecer(
    hallazgo: dict,
    cliente: ClienteOllama | None = None,
    max_intentos: int = MAX_INTENTOS,
    espera_s: float = 1.0,
) -> dict:
    """
    Enriquece un hallazgo normalizado (la salida de parsear_alerta).

    Nunca lanza excepción por culpa del modelo o de Ollama: cualquier falla
    termina en un resultado con state="failed" y su failure_reason.
    """
    cliente = cliente or ClienteOllama.desde_config()
    prompt_base = construir_prompt(hallazgo)
    # El hash es del prompt base (intento 1): con él se reproduce la corrida.
    sha = hashlib.sha256(prompt_base.encode("utf-8")).hexdigest()

    prompt = prompt_base
    latencia_total = 0
    motivo = "sin_intentos"

    for intento in range(1, max_intentos + 1):
        try:
            respuesta = cliente.generar(prompt)
        except OllamaNoDisponible as exc:
            # Si Ollama está apagado, reintentar no sirve: se marca y se sigue.
            log.warning("Ollama no disponible: %s", exc)
            return _fallido(_fila(cliente, sha, intento, latencia_total), exc.motivo)
        except ErrorOllama as exc:
            log.warning("intento %d/%d: %s", intento, max_intentos, exc)
            motivo = exc.motivo
            if intento < max_intentos and espera_s:
                time.sleep(espera_s)
            continue

        latencia_total += respuesta.latencia_ms
        salida, errores = validar(respuesta.texto)

        if salida is not None:
            return {
                **_fila(cliente, sha, intento, latencia_total),
                "state": "ok",
                "failure_reason": None,
                "explanation": salida.explicacion,
                "impact": salida.impacto,
                "owasp_version": "2025",
                "owasp_category": salida.owasp,
                "priority": salida.prioridad,
                "confidence": salida.confianza,
                "remediation_summary": salida.remediacion,
                "remediation_steps": None,   # el prompt v2 no pide pasos separados
            }

        log.info("intento %d/%d rechazado: %s", intento, max_intentos, "; ".join(errores))
        motivo = "json_invalido" if any("JSON" in e for e in errores) else "esquema_invalido"
        prompt = construir_reparacion(prompt_base, errores)

    return _fallido(_fila(cliente, sha, max_intentos, latencia_total), motivo)


# ── Prueba de extremo a extremo: fixture -> parser -> modelo -> validación ──

def main() -> None:
    import argparse
    import json

    from app.parsers.zap import parsear_reporte

    p = argparse.ArgumentParser(description="Enriquece los hallazgos de un fixture de ZAP")
    p.add_argument("fixture")
    p.add_argument("--max", type=int, default=10, help="cuántos hallazgos procesar")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="   %(message)s")

    with open(args.fixture, encoding="utf-8") as f:
        hallazgos = parsear_reporte(json.load(f))[: args.max]

    cliente = ClienteOllama.desde_config()
    print(f"Ollama: {cliente.url}  ·  modelo {cliente.modelo}  ·  prompt {PROMPT_VERSION}")
    if not cliente.disponible():
        print("\nOllama no responde. Revisa que esté abierto y la variable OLLAMA_URL.")
        raise SystemExit(1)
    print(f"{len(hallazgos)} hallazgos\n")

    ok = fallidos = reparados = 0
    for h in hallazgos:
        r = enriquecer(h, cliente)
        if r["state"] == "ok":
            ok += 1
            reparados += r["attempts"] > 1
            print(f"OK   {h['titulo'][:45]:45}  {r['owasp_category']}  {r['priority']}  "
                  f"conf={r['confidence']:.2f}  intentos={r['attempts']}  {r['latency_ms']}ms")
        else:
            fallidos += 1
            print(f"FALLA {h['titulo'][:44]:44}  motivo={r['failure_reason']}  intentos={r['attempts']}")

    print(f"\nEnriquecidos: {ok}/{len(hallazgos)}  ·  reparados en reintento: {reparados}  "
          f"·  sin enriquecer: {fallidos}")


if __name__ == "__main__":
    main()
