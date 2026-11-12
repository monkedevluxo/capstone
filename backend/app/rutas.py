"""
SentinelAI · Endpoints de ingesta y consulta (tareas T-022, T-023).

    POST /scans/import       importa un reporte JSON de ZAP
    GET  /scans              escaneos importados, del más reciente al más antiguo
    GET  /findings           hallazgos con filtros y paginación
    GET  /findings/{id}      detalle: evidencia original, instancias, IA, validaciones
    POST /findings/{id}/enrich  enriquece un hallazgo con el modelo local (T-032)
    POST /scans/{id}/enrich     enriquece los hallazgos de un escaneo, uno por uno

Cada hallazgo trae además `referencia`: la categoría OWASP según la tabla
CWE -> OWASP 2025, la prioridad por regla y la marca "revisar" de la opción
mixta (app/ia/owasp_por_cwe.py). Se calcula al consultar; no se guarda.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.enriquecimiento import (
    OllamaApagado,
    enriquecer_escaneo,
    enriquecer_hallazgo,
    referencia,
    vigente,
)
from app.ia.cliente import ClienteOllama
from app.ingesta import ErrorIngesta, importar_reporte
from app.models import (
    AiEnrichment,
    EstadoHallazgo,
    Finding,
    FindingInstance,
    FindingObservation,
    Scan,
    Severidad,
    Validation,
)

router = APIRouter()


def get_cliente() -> ClienteOllama:
    """Dependencia: el cliente de Ollama según la configuración. Los tests lo reemplazan."""
    return ClienteOllama.desde_config()


# ── Ingesta ───────────────────────────────────────────────────────────────

@router.post("/scans/import", tags=["ingesta"], status_code=201)
def importar(
    crudo: Annotated[dict, Body(description="El JSON completo que genera ZAP con -J")],
    db: Session = Depends(get_db),
):
    """
    Importa un reporte de ZAP. Respuestas:

    - **201**: importado, con el resumen de nuevos y repetidos
    - **403**: el objetivo no es del laboratorio
    - **409**: ese mismo reporte ya se había importado
    - **422**: el JSON no tiene forma de reporte de ZAP
    """
    try:
        resumen = importar_reporte(db, crudo)
        db.commit()
    except ErrorIngesta as exc:
        db.rollback()
        raise HTTPException(status_code=exc.http, detail={"error": str(exc), **exc.extra})
    return resumen.como_dict()


@router.get("/scans", tags=["consulta"])
def listar_escaneos(db: Session = Depends(get_db)):
    filas = db.scalars(select(Scan).order_by(Scan.started_at.desc())).all()
    return [
        {
            "id": str(s.id),
            "target_id": str(s.target_id),
            "herramienta": s.tool.value,
            "version": s.tool_version,
            "estado": s.status.value,
            "fecha": s.started_at,
            "stats": s.stats,
        }
        for s in filas
    ]


# ── Consulta de hallazgos ─────────────────────────────────────────────────

def _resumen_ia(e: AiEnrichment | None) -> dict | None:
    if e is None:
        return None
    return {
        "estado": e.state.value,
        "owasp": e.owasp_category.value if e.owasp_category else None,
        "prioridad": e.priority.value if e.priority else None,
        "confianza": e.confidence,
        "motivo_fallo": e.failure_reason,
    }


def _detalle_ia(e: AiEnrichment | None) -> dict | None:
    if e is None:
        return None
    return {
        **_resumen_ia(e),
        "explicacion": e.explanation,
        "impacto": e.impact,
        "remediacion": e.remediation_summary,
        "pasos": e.remediation_steps,
        "modelo": e.model,
        "prompt_version": e.prompt_version,
        "prompt_sha256": e.prompt_sha256,
        "intentos": e.attempts,
        "latencia_ms": e.latency_ms,
        "generado": e.generated_at,
    }


@router.get("/findings", tags=["consulta"])
def listar_hallazgos(
    db: Session = Depends(get_db),
    severidad: Annotated[list[Severidad] | None, Query()] = None,
    estado: Annotated[list[EstadoHallazgo] | None, Query()] = None,
    scan_id: uuid.UUID | None = None,
    target_id: uuid.UUID | None = None,
    owasp: str | None = Query(None, description="Ej: A05:2025"),
    con_ia: bool | None = Query(None, description="true: solo enriquecidos; false: solo sin enriquecer"),
    q: str | None = Query(None, min_length=2, description="Busca en título y ruta"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Lista hallazgos ordenados por severidad (crítica primero) y después por
    cantidad de instancias. Los filtros se combinan entre sí.

    Cada hallazgo trae el resumen de su enriquecimiento vigente, o `null` si
    nunca se enriqueció. Un enriquecimiento fallido aparece con
    `estado: "failed"`: el dashboard debe mostrarlo distinto de uno exitoso.
    """
    ia = AiEnrichment
    base = (
        select(Finding, ia)
        .outerjoin(ia, and_(ia.finding_id == Finding.id, ia.is_current.is_(True)))
    )

    filtros = []
    if severidad:
        filtros.append(Finding.severity.in_(severidad))
    if estado:
        filtros.append(Finding.status.in_(estado))
    if target_id:
        filtros.append(Finding.target_id == target_id)
    if scan_id:
        filtros.append(Finding.id.in_(
            select(FindingObservation.finding_id).where(FindingObservation.scan_id == scan_id)
        ))
    if owasp:
        filtros.append(ia.owasp_category == owasp.upper())
    if con_ia is True:
        filtros.append(ia.state == "ok")
    elif con_ia is False:
        filtros.append(or_(ia.id.is_(None), ia.state == "failed"))
    if q:
        patron = f"%{q}%"
        filtros.append(or_(Finding.titulo.ilike(patron), Finding.path_template.ilike(patron)))

    if filtros:
        base = base.where(and_(*filtros))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    filas = db.execute(
        base.order_by(Finding.severity, Finding.occurrences.desc(), Finding.id)
        .limit(limit).offset(offset)
    ).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(f.id),
                "titulo": f.titulo,
                "severidad": f.severity.value,
                "estado": f.status.value,
                "ruta": f.path_template,
                "metodo": f.method,
                "parametro": f.param,
                "cwe": f.cwe_id,
                "ocurrencias": f.occurrences,
                "visto_por_ultima_vez": f.last_seen_at,
                "ia": _resumen_ia(e),
                "referencia": referencia(f, e),
            }
            for f, e in filas
        ],
    }


@router.get("/findings/{finding_id}", tags=["consulta"])
def detalle_hallazgo(finding_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Todo lo que se sabe de un hallazgo, separado por capas para que el
    dashboard las muestre lado a lado: lo que dijo la herramienta (`origen`),
    lo que interpretó el modelo (`ia`) y lo que decidió una persona
    (`validaciones`).
    """
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="hallazgo no encontrado")

    ia_vigente = vigente(db, f.id)
    instancias = db.scalars(
        select(FindingInstance).where(FindingInstance.finding_id == f.id)
    ).all()
    validaciones = db.scalars(
        select(Validation).where(Validation.finding_id == f.id)
        .order_by(Validation.reviewed_at.desc())
    ).all()
    escaneos = db.scalars(
        select(FindingObservation.scan_id).where(FindingObservation.finding_id == f.id)
    ).all()

    return {
        "id": str(f.id),
        "titulo": f.titulo,
        "descripcion": f.descripcion,
        "severidad": f.severity.value,
        "severidad_herramienta": f.severity_tool_raw,
        "confianza_herramienta": f.tool_confidence,
        "estado": f.status.value,
        "cwe": f.cwe_id,
        "url": f.url,
        "ruta": f.path_template,
        "metodo": f.method,
        "parametro": f.param,
        "evidencia": f.evidence_snippet,
        "ocurrencias": f.occurrences,
        "primera_vez": f.first_seen_at,
        "ultima_vez": f.last_seen_at,
        "escaneos": [str(s) for s in escaneos],
        "instancias": [{"url": i.url, "metodo": i.method, "parametro": i.param} for i in instancias],
        "origen": f.source_raw,
        "ia": _detalle_ia(ia_vigente),
        "referencia": referencia(f, ia_vigente),
        "validaciones": [
            {
                "decision": v.decision.value,
                "revisor": v.reviewer,
                "fecha": v.reviewed_at,
                "comentario": v.comment,
                "prioridad_corregida": v.priority_override.value if v.priority_override else None,
            }
            for v in validaciones
        ],
    }


# ── Enriquecimiento con IA ────────────────────────────────────────────────

_OLLAMA_APAGADO = {
    "error": "Ollama no responde: no se registró ningún intento",
    "motivo": "ollama_no_disponible",
}


@router.post("/findings/{finding_id}/enrich", tags=["ia"])
def enriquecer_uno(
    finding_id: uuid.UUID,
    db: Session = Depends(get_db),
    cliente: ClienteOllama = Depends(get_cliente),
):
    """
    Enriquece un hallazgo con el modelo local y guarda el resultado, con el
    modelo, la versión y el hash del prompt, los intentos y la latencia.

    - **200**: el modelo respondió. `ia.estado` es `ok` o `failed` (tras 3
      intentos inválidos), con `motivo_fallo`. `vigente: false` indica que el
      intento falló y se conservó el enriquecimiento válido anterior.
    - **404**: el hallazgo no existe
    - **503**: Ollama no responde; no se guardó nada
    """
    f = db.get(Finding, finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="hallazgo no encontrado")
    try:
        nueva = enriquecer_hallazgo(db, f, cliente)
        db.commit()
    except OllamaApagado:
        db.rollback()
        raise HTTPException(status_code=503, detail=_OLLAMA_APAGADO)

    return {
        "id": str(f.id),
        "titulo": f.titulo,
        "vigente": nueva.is_current,
        "ia": _detalle_ia(nueva),
        "referencia": referencia(f, vigente(db, f.id)),
    }


@router.post("/scans/{scan_id}/enrich", tags=["ia"])
def enriquecer_lote(
    scan_id: uuid.UUID,
    solo_pendientes: bool = Query(
        True, description="true: se salta los hallazgos que ya tienen un enriquecimiento válido"
    ),
    db: Session = Depends(get_db),
    cliente: ClienteOllama = Depends(get_cliente),
):
    """
    Enriquece, uno por uno, los hallazgos que vio un escaneo. Cada resultado
    se guarda al terminar, así que si se corta, una segunda llamada sigue
    donde quedó. Con el modelo cargado toma 1-2 s por hallazgo; la primera
    llamada puede tardar más mientras Ollama carga el modelo en la GPU.

    - **200**: resumen del lote. Si Ollama se cae a la mitad, `detenido_por`
      lo indica y lo ya procesado queda guardado.
    - **404**: el escaneo no existe
    - **503**: Ollama no responde y no se alcanzó a procesar ningún hallazgo
    """
    if db.get(Scan, scan_id) is None:
        raise HTTPException(status_code=404, detail="escaneo no encontrado")
    resumen = enriquecer_escaneo(db, scan_id, cliente, solo_pendientes=solo_pendientes)
    if resumen.detenido_por and resumen.procesados == 0:
        raise HTTPException(status_code=503, detail=_OLLAMA_APAGADO)
    return resumen.como_dict()
