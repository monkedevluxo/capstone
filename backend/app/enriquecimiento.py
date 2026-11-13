"""
SentinelAI · Enriquecimiento de hallazgos guardados en la base (T-032, T-035).

Une tres piezas que ya existían:

    app/ia/enriquecer.py     llama a Ollama, valida y reintenta (Joaquín)
    app/ia/owasp_por_cwe.py  categoría de referencia y prioridad por regla (Joaquín)
    app/models.py            tabla ai_enrichments, histórica

Flujo de UN hallazgo:

    hallazgo en la base
      -> mismo diccionario que entrega el parser (lo que ve el modelo)
      -> enriquecer()  ── Ollama apagado ──> OllamaApagado (no se guarda nada)
      -> fila nueva en ai_enrichments, con modelo, prompt_version,
         prompt_sha256, intentos, latencia y fecha (T-035)

Qué fila queda vigente (is_current):

    resultado ok                         -> la nueva, la anterior pasa a histórica
    resultado fallido, sin ok vigente    -> la nueva (el hallazgo se ve "sin enriquecer")
    resultado fallido, con un ok vigente -> se queda el ok; la nueva se guarda
                                            solo como historial

Así un reintento que falla nunca borra una explicación válida, y aun así
queda registro de que se intentó.

La llamada a Ollama ocurre ANTES de tocar la base: no se mantiene una
transacción abierta mientras el modelo piensa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ia.cliente import ClienteOllama
from app.ia.enriquecer import enriquecer
from app.ia.owasp_por_cwe import evaluar
from app.models import (
    AiEnrichment,
    CategoriaOwasp,
    EstadoIA,
    Finding,
    FindingObservation,
    Prioridad,
)

MOTIVO_OLLAMA_APAGADO = "ollama_no_disponible"


class OllamaApagado(Exception):
    """Ollama no responde. No es culpa del hallazgo: no se registra nada."""


def para_el_modelo(f: Finding) -> dict:
    """El hallazgo con las mismas claves que entrega el parser de ZAP.

    El prompt (app/ia/prompt.py) se construye a partir de este diccionario,
    así que el modelo ve exactamente la misma evidencia que en las pruebas
    hechas sobre los fixtures.
    """
    return {
        "titulo": f.titulo,
        "url": f.url,
        "param": f.param,
        "evidence_snippet": f.evidence_snippet,
        "severity_tool_raw": f.severity_tool_raw,
        "cwe_id": f.cwe_id,
        "descripcion": f.descripcion,
    }


def vigente(db: Session, finding_id) -> AiEnrichment | None:
    """El enriquecimiento vigente de un hallazgo, o None si nunca se enriqueció."""
    return db.scalar(
        select(AiEnrichment).where(
            AiEnrichment.finding_id == finding_id, AiEnrichment.is_current.is_(True)
        )
    )


def referencia(f: Finding, e: AiEnrichment | None) -> dict:
    """Campos de la opción mixta: se calculan al consultar, no se guardan."""
    owasp_modelo = e.owasp_category if e is not None and e.state == EstadoIA.ok else None
    return evaluar(cwe_id=f.cwe_id, severidad_zap=f.severity_tool_raw, owasp_modelo=owasp_modelo)


def _fila(finding_id, r: dict) -> AiEnrichment:
    """Convierte la salida de enriquecer() en una fila, con los enums del modelo."""
    return AiEnrichment(
        finding_id=finding_id,
        state=EstadoIA(r["state"]),
        model=r["model"],
        prompt_version=r["prompt_version"],
        prompt_sha256=r["prompt_sha256"],
        attempts=r["attempts"],
        latency_ms=r["latency_ms"],
        failure_reason=r["failure_reason"],
        explanation=r["explanation"],
        impact=r["impact"],
        owasp_version=r["owasp_version"],
        owasp_category=CategoriaOwasp(r["owasp_category"]) if r["owasp_category"] else None,
        priority=Prioridad(r["priority"]) if r["priority"] else None,
        confidence=r["confidence"],
        remediation_summary=r["remediation_summary"],
        remediation_steps=r["remediation_steps"],
    )


def enriquecer_hallazgo(db: Session, f: Finding, cliente: ClienteOllama) -> AiEnrichment:
    """Enriquece un hallazgo y guarda el resultado. No hace commit.

    Devuelve la fila nueva. Para saber si quedó vigente, mirar `is_current`.
    Lanza OllamaApagado si Ollama no responde.
    """
    resultado = enriquecer(para_el_modelo(f), cliente)
    if resultado["state"] == "failed" and resultado["failure_reason"] == MOTIVO_OLLAMA_APAGADO:
        raise OllamaApagado(cliente.url)

    # Bloquea el hallazgo hasta el commit: dos enriquecimientos simultáneos del
    # mismo hallazgo se ordenan en vez de chocar con uq_enrichment_vigente.
    db.execute(select(Finding.id).where(Finding.id == f.id).with_for_update())

    actual = vigente(db, f.id)
    nueva = _fila(f.id, resultado)

    conservar_vigente = (
        nueva.state == EstadoIA.failed
        and actual is not None
        and actual.state == EstadoIA.ok
    )
    if conservar_vigente:
        nueva.is_current = False
    else:
        db.execute(
            update(AiEnrichment)
            .where(AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True))
            .values(is_current=False)
        )
        nueva.is_current = True

    db.add(nueva)
    db.flush()
    return nueva


@dataclass
class ResumenLote:
    scan_id: str
    procesados: int = 0
    enriquecidos: int = 0
    fallidos: int = 0
    omitidos: int = 0
    detenido_por: str | None = None
    hallazgos: list[dict] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {
            "scan_id": self.scan_id,
            "procesados": self.procesados,
            "enriquecidos": self.enriquecidos,
            "fallidos": self.fallidos,
            "omitidos": self.omitidos,
            "detenido_por": self.detenido_por,
            "hallazgos": self.hallazgos,
        }


def enriquecer_escaneo(
    db: Session, scan_id, cliente: ClienteOllama, solo_pendientes: bool = True
) -> ResumenLote:
    """Enriquece, uno por uno, los hallazgos que vio un escaneo.

    Hace commit después de cada hallazgo: si se corta a la mitad, lo ya
    enriquecido queda guardado y una segunda llamada sigue donde quedó
    (con solo_pendientes=True se saltan los que ya tienen un ok vigente).

    Reemplaza la cola de trabajos de T-036: con 1-2 s por hallazgo y menos
    de 20 hallazgos únicos por escaneo, el lote cabe en una sola petición.
    """
    resumen = ResumenLote(scan_id=str(scan_id))
    hallazgos = db.scalars(
        select(Finding)
        .join(FindingObservation, FindingObservation.finding_id == Finding.id)
        .where(FindingObservation.scan_id == scan_id)
        .order_by(Finding.severity, Finding.occurrences.desc(), Finding.id)
    ).all()

    for f in hallazgos:
        if solo_pendientes:
            ya_ok = db.scalar(
                select(AiEnrichment.id).where(
                    AiEnrichment.finding_id == f.id,
                    AiEnrichment.is_current.is_(True),
                    AiEnrichment.state == EstadoIA.ok,
                )
            )
            if ya_ok is not None:
                resumen.omitidos += 1
                continue
        try:
            fila = enriquecer_hallazgo(db, f, cliente)
            db.commit()
        except OllamaApagado:
            db.rollback()
            resumen.detenido_por = MOTIVO_OLLAMA_APAGADO
            break

        resumen.procesados += 1
        if fila.state == EstadoIA.ok:
            resumen.enriquecidos += 1
        else:
            resumen.fallidos += 1
        resumen.hallazgos.append({
            "id": str(f.id),
            "titulo": f.titulo,
            "estado": fila.state.value,
            "motivo_fallo": fila.failure_reason,
            **referencia(f, vigente(db, f.id)),
        })
    return resumen
