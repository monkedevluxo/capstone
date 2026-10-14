"""
SentinelAI · Endpoints de ingesta y consulta (tareas T-022, T-023).

    POST /scans/import       importa un reporte JSON de ZAP
    GET  /scans              escaneos importados, del más reciente al más antiguo
    GET  /findings           hallazgos con filtros y paginación
    GET  /findings/{id}      detalle: evidencia original, instancias, IA, validaciones
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
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

    ia_vigente = db.scalar(
        select(AiEnrichment).where(
            AiEnrichment.finding_id == f.id, AiEnrichment.is_current.is_(True)
        )
    )
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

    ia = None
    if ia_vigente is not None:
        ia = {
            **_resumen_ia(ia_vigente),
            "explicacion": ia_vigente.explanation,
            "impacto": ia_vigente.impact,
            "remediacion": ia_vigente.remediation_summary,
            "pasos": ia_vigente.remediation_steps,
            "modelo": ia_vigente.model,
            "prompt_version": ia_vigente.prompt_version,
            "intentos": ia_vigente.attempts,
            "generado": ia_vigente.generated_at,
        }

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
        "ia": ia,
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
