"""
SentinelAI · Informe técnico exportable (tareas T-058 y T-059).

Arma el informe a partir de lo que ya está en la base: cada hallazgo con su
evidencia original de ZAP, la sugerencia vigente de la IA y la última decisión
humana. Este módulo no consulta la base: recibe los objetos ya cargados
(scripts/informe.py hace la consulta), así la lógica se prueba sin PostgreSQL.

Reglas del informe:
  - La evidencia de ZAP se muestra tal cual viene (source_raw). Nunca se edita.
  - La salida de la IA se presenta siempre como sugerencia, nunca como verdad.
  - La prioridad final es la que decidió una persona; si nadie decidió, la de la
    regla por severidad (decisión mixta, IA_MODELO_Y_PROMPT.md sección 5).
  - Falsos positivos y duplicados van en una sección aparte, no se borran.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from app.ia.owasp_por_cwe import owasp_por_cwe, prioridad_por_severidad

ORDEN_SEVERIDAD = ["critica", "alta", "media", "baja", "informativa"]
ORDEN_PRIORIDAD = ["p1", "p2", "p3", "p4"]
ESTADOS_DESCARTADOS = {"falso_positivo", "duplicado"}
MAX_INSTANCIAS_INFORME = 10


def _valor(x: Any) -> Any:
    """El .value de un enum, o el valor tal cual."""
    return getattr(x, "value", x)


def _iso(fecha: datetime | None) -> str | None:
    return fecha.isoformat(timespec="minutes") if fecha else None


def enriquecimiento_vigente(enriquecimientos: Iterable[Any]) -> Any | None:
    """El enriquecimiento vigente y válido, o None si no hay."""
    for e in enriquecimientos or []:
        if e.is_current and _valor(e.state) == "ok":
            return e
    return None


def decision_vigente(validaciones: Iterable[Any]) -> Any | None:
    """La validación más reciente: es la que fija el estado del hallazgo."""
    validaciones = list(validaciones or [])
    return max(validaciones, key=lambda v: v.reviewed_at) if validaciones else None


def _hallazgo(f: Any) -> dict:
    ia = enriquecimiento_vigente(f.enrichments)
    decision = decision_vigente(f.validations)
    regla = prioridad_por_severidad(f.severity_tool_raw)
    humana = _valor(decision.priority_override) if decision else None
    crudo = f.source_raw or {}

    return {
        "id": str(f.id),
        "dedupe_key": f.dedupe_key,
        "titulo": f.titulo,
        "estado": _valor(f.status),
        "severidad": _valor(f.severity),
        "severidad_zap": f.severity_tool_raw,
        "confianza_zap": f.tool_confidence,
        "cwe": f.cwe_id,
        "owasp_referencia": owasp_por_cwe(f.cwe_id),
        "prioridad": humana or regla or "p4",
        "prioridad_origen": "persona" if humana else "regla",
        "ubicacion": {
            "metodo": f.method,
            "ruta": f.path_template,
            "parametro": f.param,
            "ocurrencias": f.occurrences,
        },
        "evidencia": {
            "fragmento": f.evidence_snippet,
            "descripcion": crudo.get("desc"),
            "solucion": crudo.get("solution"),
            "referencias": crudo.get("reference"),
            "instancias": [
                {"metodo": i.method, "url": i.url, "parametro": i.param}
                for i in list(f.instances or [])[:MAX_INSTANCIAS_INFORME]
            ],
        },
        "ia": None if ia is None else {
            "modelo": ia.model,
            "version_prompt": ia.prompt_version,
            "explicacion": ia.explanation,
            "impacto": ia.impact,
            "owasp": _valor(ia.owasp_category),
            "prioridad": _valor(ia.priority),
            "confianza": ia.confidence,
            "remediacion": ia.remediation_summary,
            "pasos": list(ia.remediation_steps or []),
            "generado": _iso(ia.generated_at),
        },
        "decision": None if decision is None else {
            "decision": _valor(decision.decision),
            "revisor": decision.reviewer,
            "fecha": _iso(decision.reviewed_at),
            "comentario": decision.comment,
        },
    }


def _clave_orden(h: dict) -> tuple:
    return (
        ORDEN_PRIORIDAD.index(h["prioridad"]) if h["prioridad"] in ORDEN_PRIORIDAD else 99,
        ORDEN_SEVERIDAD.index(h["severidad"]) if h["severidad"] in ORDEN_SEVERIDAD else 99,
        h["titulo"] or "",
    )


def _contar(items: Iterable[dict], campo: str, orden: list[str] | None = None) -> dict:
    conteo: dict = {}
    for h in items:
        conteo[h[campo]] = conteo.get(h[campo], 0) + 1
    if orden:
        return {k: conteo[k] for k in orden if k in conteo} | {
            k: v for k, v in conteo.items() if k not in orden
        }
    return dict(sorted(conteo.items(), key=lambda kv: str(kv[0])))


def armar_datos(objetivo: Any, escaneos: Iterable[Any], hallazgos: Iterable[Any],
                generado_en: datetime | None = None) -> dict:
    """Todo lo que lleva el informe, como diccionario listo para renderizar."""
    todos = sorted((_hallazgo(f) for f in hallazgos), key=_clave_orden)
    vigentes = [h for h in todos if h["estado"] not in ESTADOS_DESCARTADOS]
    descartados = [h for h in todos if h["estado"] in ESTADOS_DESCARTADOS]

    return {
        "generado_en": _iso(generado_en or datetime.now(timezone.utc)),
        "objetivo": {"nombre": objetivo.nombre, "url": objetivo.base_url,
                     "entorno": objetivo.environment},
        "escaneos": [
            {
                "herramienta": _valor(s.tool),
                "version": s.tool_version,
                "inicio": _iso(s.started_at),
                "sha256": s.report_sha256,
            }
            for s in sorted(escaneos, key=lambda s: s.started_at)
        ],
        "resumen": {
            "total": len(todos),
            "vigentes": len(vigentes),
            "descartados": len(descartados),
            "por_severidad": _contar(vigentes, "severidad", ORDEN_SEVERIDAD),
            "por_prioridad": _contar(vigentes, "prioridad", ORDEN_PRIORIDAD),
            "por_estado": _contar(todos, "estado"),
            "con_ia": sum(1 for h in todos if h["ia"]),
            "con_decision": sum(1 for h in todos if h["decision"]),
        },
        "hallazgos": vigentes,
        "descartados": descartados,
        "metricas": metricas_golden_set(v for f in hallazgos for v in (f.validations or [])),
    }


def metricas_golden_set(validaciones: Iterable[Any]) -> dict:
    """Las tres métricas del golden set, con su denominador.

    Cuenta la última respuesta de cada revisor por hallazgo (agrupando nombres
    sin distinguir mayúsculas ni espacios) e ignora las banderas sin responder.
    """
    ultimas: dict = {}
    for v in validaciones:
        clave = (str(v.finding_id), " ".join(str(v.reviewer).lower().split()))
        if clave not in ultimas or v.reviewed_at > ultimas[clave].reviewed_at:
            ultimas[clave] = v

    def proporcion(campo: str) -> dict:
        respuestas = [getattr(v, campo) for v in ultimas.values() if getattr(v, campo) is not None]
        return {"si": sum(1 for r in respuestas if r), "n": len(respuestas)}

    return {
        "revisores": sorted({k[1] for k in ultimas}),
        "acierto_owasp": proporcion("ai_owasp_correcto"),
        "acierto_prioridad": proporcion("ai_prioridad_correcta"),
        "remediacion_util": proporcion("ai_remediacion_util"),
        "alucinacion": proporcion("ai_alucinacion"),
    }
