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

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.ia.owasp_por_cwe import evaluar

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


def _ia_fallida(enriquecimientos: Iterable[Any]) -> bool:
    """El enriquecimiento vigente existe y falló (cuenta como sin enriquecer)."""
    return any(e.is_current and _valor(e.state) == "failed" for e in enriquecimientos or [])


def _hallazgo(f: Any) -> dict:
    ia = enriquecimiento_vigente(f.enrichments)
    decision = decision_vigente(f.validations)
    # Misma regla que el dashboard: compara la categoría del modelo con la tabla CWE → OWASP.
    referencia = evaluar(f.cwe_id, f.severity_tool_raw, _valor(ia.owasp_category) if ia else None)
    regla = referencia["prioridad_regla"]
    humana = _valor(decision.priority_override) if decision else None
    crudo = f.source_raw or {}

    return {
        "id": str(f.id),
        "ia_fallida": _ia_fallida(f.enrichments),
        "dedupe_key": f.dedupe_key,
        "titulo": f.titulo,
        "estado": _valor(f.status),
        "severidad": _valor(f.severity),
        "severidad_zap": f.severity_tool_raw,
        "confianza_zap": f.tool_confidence,
        "cwe": f.cwe_id,
        "owasp_referencia": referencia["owasp_referencia"],
        "revisar": referencia["requiere_revision"],
        "motivo_revision": referencia["motivo_revision"],
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
            "ia_fallida": sum(1 for h in todos if h["ia_fallida"]),
            "con_decision": sum(1 for h in todos if h["decision"]),
            "por_revisar": sum(1 for h in vigentes if h["revisar"]),
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


# --- Render HTML ---------------------------------------------------------------
#
# Todo texto que viene de ZAP, de la IA o de una persona pasa por html.escape:
# la evidencia trae payloads reales (<script>, comillas), y el informe no puede
# ejecutarlos al abrirse. Las descripciones de ZAP vienen con <p>: se quitan las
# etiquetas antes de escapar.

import html
import re

ETIQUETA_SEVERIDAD = {"critica": "Crítica", "alta": "Alta", "media": "Media",
                      "baja": "Baja", "informativa": "Informativa"}
ETIQUETA_DECISION = {
    "confirmado": "Confirmado", "falso_positivo": "Falso positivo",
    "riesgo_aceptado": "Riesgo aceptado", "duplicado": "Duplicado",
    "requiere_segunda_opinion": "Requiere segunda opinión",
}
ETIQUETA_ESTADO = ETIQUETA_DECISION | {"nuevo": "Nuevo", "en_triage": "En triage",
                                       "remediado": "Remediado"}
MOTIVO_REVISION = {"categoria_distinta": "categoría distinta",
                   "cwe_fuera_de_tabla": "CWE fuera de la tabla"}

# El casco del logo, incrustado como data URI: el informe sigue siendo un solo
# archivo HTML, sin pedir nada afuera.
_CASCO = "data:image/png;base64," + base64.b64encode(
    (Path(__file__).parent / "recursos" / "casco.png").read_bytes()
).decode("ascii")

_CSS = """
:root {
  /* Bronce claro, la misma paleta del dashboard (frontend/src/app/globals.css).
     El informe es siempre claro: es lo que se imprime. */
  --grafito:#1c1f22; --tinta:#1a1c1e; --suave:#5a6067; --borde:#dededb; --fondo:#f4f4f3; --tarjeta:#fff;
  --cobre:#c08666; --cobre-claro:#eaac86;
  --escaner:#4b5058; --escaner-suave:#ededeb; --ia:#0e6a78; --ia-suave:#e3f1f3;
  --persona:#c08666; --persona-suave:#f6eae2; --persona-texto:#8c4a26; --persona-borde:#e4c4ae;
  --exito:#065f46; --exito-fondo:#ecfdf5;
  --critica:#8a1c1c; --alta:#9b1c1c; --alta-fondo:#fbe3e1; --media:#5c5a00; --media-fondo:#f3f1c8;
  --baja:#4b5058; --baja-fondo:#e9e9e6; --info:#5a6067;
}
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; background: #fff; color: var(--tinta);
       font: 14px/1.55 "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif; }
code, pre, .mono { font-family: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Consolas, monospace; font-size: 12px; }
a { color: var(--ia); }
/* Portada en la misma hoja blanca del documento: el único color es el logo. */
.portada .contenido { max-width: 1000px; margin: 0 auto; padding: 32px 24px 4px; }
.marca { margin: 0; display: flex; align-items: center; gap: 10px; color: var(--persona-texto); font-size: 13px;
         letter-spacing: .06em; text-transform: uppercase; }
.marca img { height: 30px; width: auto; }
.portada h1 { margin: 10px 0 10px; font-size: 30px; line-height: 1.2; }
.portada .meta { margin: 0; color: var(--suave); font-size: 13px; }
.portada .meta code { color: var(--tinta); }
main { max-width: 1000px; margin: 0 auto; padding: 24px; }
h2 { font-size: 20px; margin: 40px 0 14px; display: flex; align-items: baseline; gap: 10px; }
h2 .num { color: var(--suave); font-weight: 500; }
h3 { font-size: 14px; margin: 0 0 10px; color: var(--suave); font-weight: 600; }
p { margin: 0 0 8px; }
.suave { color: var(--suave); }
.aviso { background: var(--ia-suave); border: 1px solid #c6e2e6; border-radius: 8px; padding: 12px 16px; margin: 0; }
.tarjeta { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 10px; padding: 16px 18px; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 0 0 14px; }
.kpi { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 10px; padding: 14px 16px; }
.kpi .valor { font-size: 28px; font-weight: 700; line-height: 1.1; }
.kpi .rotulo { color: var(--suave); font-size: 12.5px; }
/* El color va en el número, no en una franja: así se lee también en blanco y negro. */
.kpi.alerta .valor { color: var(--alta); }
.kpi.revisar .valor, .kpi.persona .valor { color: var(--persona-texto); }
.kpi.base .valor { color: var(--ia); }
.tres { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.barra { display: grid; grid-template-columns: 110px 1fr 28px; align-items: center; gap: 8px; margin: 6px 0; font-size: 13px; }
.barra .pista { background: var(--fondo); border-radius: 4px; height: 10px; overflow: hidden; }
.barra .relleno { display: block; height: 100%; border-radius: 4px; background: var(--ia); }
.barra .n { text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }
.r-critica { background: var(--critica) !important; } .r-alta { background: var(--alta) !important; }
.r-media { background: #8f8a16 !important; } .r-baja { background: #6b7178 !important; } .r-informativa { background: #8a8f96 !important; }
table { width: 100%; border-collapse: collapse; background: var(--tarjeta); }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--borde); vertical-align: top; }
th { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: var(--suave); background: var(--escaner-suave); }
.tabla { border: 1px solid var(--borde); border-radius: 10px; overflow: hidden; }
.tabla table td:first-child, .tabla table th:first-child { padding-left: 14px; }
.tabla tr:last-child td { border-bottom: 0; }
.hash { word-break: break-all; color: var(--suave); }
.etiqueta { display: inline-block; padding: 1px 9px; border-radius: 999px; font-size: 12px; font-weight: 600;
            white-space: nowrap; border: 1px solid transparent; }
.sev-critica { background: var(--critica); color: #fff; }
.sev-alta { background: var(--alta-fondo); color: var(--alta); border-color: #f1c4c0; }
.sev-media { background: var(--media-fondo); color: var(--media); border-color: #dedb93; }
.sev-baja { background: var(--baja-fondo); color: var(--baja); border-color: #d3d3cf; }
.sev-informativa { background: #fff; color: var(--info); border-color: var(--borde); }
.prio { display: inline-block; min-width: 28px; text-align: center; padding: 1px 7px; border-radius: 6px;
        font: 600 12px "IBM Plex Mono", ui-monospace, monospace; background: var(--grafito); color: #fff; }
.prio-p2 { background: #3d434a; } .prio-p3 { background: #5a6067; } .prio-p4 { background: #e9e9e6; color: var(--tinta); }
.chip { display: inline-block; padding: 1px 8px; border-radius: 6px; background: var(--escaner-suave);
        color: var(--escaner); font-size: 12px; margin: 0 4px 4px 0; }
.chip-ok { background: var(--exito-fondo); color: var(--exito); } .chip-dif { background: var(--persona-suave); color: var(--persona-texto); }
.indice td { font-size: 13px; } .indice a { color: var(--tinta); text-decoration: none; font-weight: 600; }
.hallazgo { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 12px; margin: 0 0 18px;
            overflow: hidden; break-inside: avoid-page; }
.hallazgo.revisar { border-color: var(--persona-borde); }
.hallazgo .cabecera { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;
                      padding: 16px 18px 12px; border-bottom: 1px solid var(--borde); cursor: pointer; list-style: none; }
.hallazgo .cabecera::-webkit-details-marker { display: none; }
.hallazgo .cabecera:hover { background: #fafaf9; }
.hallazgo .cabecera:focus-visible { outline: 2px solid var(--grafito); outline-offset: -2px; }
.ficha:not([open]) > .cabecera { border-bottom: 0; }
.abrir { font-size: 12px; color: var(--suave); white-space: nowrap; margin-left: 4px; }
.abrir::after { content: "Ver capas ▸"; }
.ficha[open] .abrir::after { content: "Ocultar ▾"; }
.controles-fichas { display: flex; gap: 8px; justify-content: flex-end; margin: 14px 0 10px; }
.controles-fichas button { font: inherit; font-size: 13px; color: var(--tinta); background: var(--tarjeta);
                           border: 1px solid #8a8f96; border-radius: 6px; padding: 4px 12px; cursor: pointer; }
.controles-fichas button:hover { background: var(--escaner-suave); }
.controles-fichas button:focus-visible { outline: 2px solid var(--grafito); outline-offset: 2px; }
.hallazgo h3 { margin: 0 0 6px; font-size: 17px; color: var(--tinta); }
.hallazgo h3 .n { color: var(--suave); font-weight: 500; margin-right: 4px; }
.insignias { display: flex; gap: 6px; align-items: center; flex-shrink: 0; }
.revisar-marca { color: var(--persona-texto); font-weight: 600; font-size: 13px; margin: 6px 0 0; }
.capas { padding: 4px 18px 16px; }
/* Cada capa con su tinte y un borde del mismo tono, sin franja lateral. */
.capa { margin-top: 12px; padding: 10px 14px; border-radius: 8px; border: 1px solid #dcdcd8; background: var(--escaner-suave); }
.capa.ia { border-color: #c6e2e6; background: var(--ia-suave); }
.capa.persona { border-color: var(--persona-borde); background: var(--persona-suave); }
.capa h4 { margin: 0 0 6px; font-size: 11.5px; letter-spacing: .08em; text-transform: uppercase; color: var(--escaner); }
.capa.ia h4 { color: var(--ia); } .capa.persona h4 { color: var(--persona-texto); }
dl { display: grid; grid-template-columns: 120px 1fr; gap: 4px 12px; margin: 0; }
dt { color: var(--suave); font-size: 13px; } dd { margin: 0; }
pre { background: #fff; border: 1px solid var(--borde); border-radius: 6px; padding: 8px 10px;
      white-space: pre-wrap; word-break: break-all; margin: 0; max-height: 160px; overflow: auto; }
.capa table { margin-top: 8px; border: 1px solid var(--borde); border-radius: 6px; font-size: 12.5px; }
.capa table td code { word-break: break-all; }
.solo-impresion { display: none; }
details { margin-top: 8px; } summary { cursor: pointer; color: var(--ia); font-size: 13px; }
details .texto-zap { margin-top: 6px; font-size: 13px; color: #3d434a; }
.metricas { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.metrica .valor { font-size: 24px; font-weight: 700; } .metrica .rotulo { font-size: 12.5px; color: var(--suave); }
.metrica .pista { background: var(--fondo); border-radius: 4px; height: 8px; margin-top: 8px; overflow: hidden; }
.metrica .relleno { display: block; height: 100%; background: var(--ia); }
footer { max-width: 1000px; margin: 32px auto 0; padding: 16px 24px 40px; color: var(--suave); font-size: 12px;
         border-top: 1px solid var(--borde); }
@media (max-width: 760px) {
  .kpis, .metricas { grid-template-columns: repeat(2, 1fr); } .tres { grid-template-columns: 1fr; }
  .hallazgo .cabecera { flex-direction: column; } dl { grid-template-columns: 1fr; }
  .indice .opcional { display: none; }
}
/* Hoja impresa: la misma para "Imprimir" del navegador y para el PDF que arma
   la API (WeasyPrint, app/informe_export.a_pdf). Chrome ignora los márgenes
   con el número de página; WeasyPrint los dibuja. */
@page { size: A4; margin: 14mm 13mm 16mm;
  @bottom-left { content: "SentinelAI · Informe técnico"; font: 8.5px "IBM Plex Sans", sans-serif; color: #5a6067; }
  @bottom-right { content: "Página " counter(page) " de " counter(pages); font: 8.5px "IBM Plex Sans", sans-serif; color: #5a6067; } }
@media print {
  body { background: #fff; font-size: 11px; line-height: 1.45; }
  main, .portada .contenido { max-width: none; padding-left: 0; padding-right: 0; }
  main { padding-top: 14px; } .portada .contenido { padding-top: 0; }
  .portada h1 { font-size: 24px; margin: 6px 0; }
  h2 { font-size: 15px; margin: 22px 0 10px; break-after: avoid; }
  code, pre, .mono { font-size: 10px; }
  .abrir, .controles-fichas { display: none; }
  .aviso { padding: 8px 12px; }
  /* Una hoja A4 o Carta mide ~720 px: sin esto se aplicaría el diseño de celular
     (etiqueta y valor en líneas separadas), que casi duplica el largo. */
  .kpis, .metricas { grid-template-columns: repeat(4, 1fr); } .tres { grid-template-columns: repeat(3, 1fr); }
  .indice .opcional { display: table-cell; }
  .kpi, .tarjeta { padding: 10px 12px; } .kpi .valor { font-size: 22px; } .kpi .rotulo, .barra { font-size: 11px; }
  th, td { padding: 4px 8px; } th { font-size: 9.5px; } .indice td { font-size: 11px; }
  .tabla, .kpi, .tarjeta { break-inside: avoid; } .tabla.indice { break-inside: auto; margin-bottom: 18px; }

  /* Fichas compactas: sin cajas de color, una línea fina sobre cada capa, y las
     capas del escáner y de la IA lado a lado. La de la persona va debajo, a lo
     ancho. Una ficha puede seguir en la hoja siguiente; una capa no se corta. */
  .hallazgo, .hallazgo.revisar { border: 0; border-top: 1.5px solid var(--tinta); border-radius: 0; overflow: visible;
              margin: 0 0 16px; break-inside: auto; }
  .hallazgo .cabecera { flex-direction: row; padding: 6px 0 4px; border-bottom: 0; break-after: avoid; }
  .hallazgo h3 { font-size: 13.5px; margin: 0 0 3px; }
  .chip { font-size: 9.5px; padding: 0 6px; margin: 0 3px 3px 0; }
  .etiqueta, .prio { font-size: 10px; }
  .revisar-marca { font-size: 10.5px; margin: 1px 0 0; }
  /* Tabla y no grilla ni columnas: WeasyPrint no corta una grilla entre hojas
     y equilibrar columnas lo hace muy lento. La capa de la persona es el pie. */
  .capas { padding: 0; display: table; width: 100%; table-layout: fixed; border-collapse: collapse; }
  .capa:not(.persona) { display: table-cell; width: 50%; }
  .capa:first-child { padding-right: 18px; }
  .capa, .capa.ia, .capa.persona { background: none; border: 0; border-top: 1px solid var(--borde); border-radius: 0;
                                   margin: 0; padding: 5px 0 4px; break-inside: avoid; }
  .capa.persona { display: table-caption; caption-side: bottom; }
  .capa h4 { font-size: 9px; margin: 0 0 3px; }
  .capa.persona h4, .capa.persona p { display: inline; margin: 0 10px 0 0; }
  dl { display: block; } dt { float: left; clear: left; width: 72px; font-size: 10px; }
  dd { margin: 0 0 2px 80px; }
  dd ol { margin: 2px 0 0; padding-left: 16px; }
  pre { max-height: none; padding: 3px 6px; }
  .capa table { font-size: 10px; margin-top: 5px; } .capa th, .capa td { padding: 2px 5px; }
  a { text-decoration: none; }
  /* La descripción y la solución genéricas de ZAP (en inglés) y las URLs
     después de las primeras quedan solo en el informe en línea. Con una sola
     URL, la tabla repite la ubicación de arriba. */
  .capa details, .capa tr.extra, .capa table.una-url { display: none; }
  .solo-impresion { display: table-row; }
  /* Respaldo si se imprime sin que corra el script: el contenido de una ficha
     cerrada también sale (navegadores con ::details-content). */
  .ficha::details-content { content-visibility: visible; display: contents; }
}
"""

# IBM Plex, la tipografía del dashboard (licencia OFL, ver recursos/fuentes/OFL.txt).
# Solo las usa el PDF: el contenedor de la API no tiene fuentes del sistema.
_DIR_FUENTES = Path(__file__).parent / "recursos" / "fuentes"
_FUENTES = "".join(
    f'@font-face {{ font-family: "{familia}"; font-weight: {peso}; '
    f'src: url("{(_DIR_FUENTES / archivo).as_uri()}") format("woff2"); }}'
    for familia, peso, archivo in (
        ("IBM Plex Sans", "100 700", "ibm-plex-sans-latin-wght-normal.woff2"),
        ("IBM Plex Mono", "400", "ibm-plex-mono-latin-400-normal.woff2"),
        ("IBM Plex Mono", "600", "ibm-plex-mono-latin-600-normal.woff2"),
    )
)

_CONTROLES_FICHAS = (
    '<div class="controles-fichas"><button type="button" data-fichas="abrir">Abrir todas</button>'
    '<button type="button" data-fichas="cerrar">Cerrar todas</button></div>'
)

# Sin dependencias: abre las fichas al imprimir y las deja como estaban después; abre
# la ficha a la que se salta desde el índice; botones para abrir o cerrar todas.
_SCRIPT = """
(function () {
  var guardado = null;
  addEventListener('beforeprint', function () {
    var todos = document.querySelectorAll('details.ficha');
    guardado = Array.prototype.map.call(todos, function (d) { return d.open; });
    todos.forEach(function (d) { d.open = true; });
  });
  addEventListener('afterprint', function () {
    if (!guardado) return;
    document.querySelectorAll('details.ficha').forEach(function (d, i) { d.open = guardado[i]; });
    guardado = null;
  });
  function abrirDestino() {
    var id = decodeURIComponent(location.hash.slice(1));
    var art = id && document.getElementById(id);
    var ficha = art && art.querySelector('details.ficha');
    if (ficha) ficha.open = true;
  }
  addEventListener('hashchange', abrirDestino);
  document.addEventListener('DOMContentLoaded', function () {
    abrirDestino();
    document.querySelectorAll('[data-fichas]').forEach(function (b) {
      b.addEventListener('click', function () {
        var abrir = b.getAttribute('data-fichas') === 'abrir';
        document.querySelectorAll('details.ficha').forEach(function (d) { d.open = abrir; });
      });
    });
  });
})();
""".strip()


def _e(valor: Any) -> str:
    """Escapa para HTML. None se muestra como guion."""
    return "—" if valor is None or valor == "" else html.escape(str(valor))


def _fecha(iso: str | None) -> str:
    """'2026-11-18T22:00:00+00:00' -> '18-11-2026 22:00 UTC'. Lo que no se entiende queda igual."""
    if not iso:
        return "—"
    try:
        f = datetime.fromisoformat(iso).astimezone(timezone.utc)
    except ValueError:
        return _e(iso)
    return f.strftime("%d-%m-%Y %H:%M UTC")


def _texto_zap(valor: str | None) -> str:
    """Descripción de ZAP sin etiquetas, escapada y con saltos de párrafo."""
    if not valor:
        return "—"
    limpio = re.sub(r"<[^>]+>", "\n", valor)
    parrafos = [p.strip() for p in limpio.split("\n") if p.strip()]
    return "<br>".join(html.escape(p) for p in parrafos)


def _proporcion(m: dict) -> str:
    if not m["n"]:
        return "sin respuestas"
    return f"{m['si']}/{m['n']} ({m['si'] / m['n']:.0%})"


def _sev(clave: str | None) -> str:
    return (f'<span class="etiqueta sev-{_e(clave)}">'
            f"{_e(ETIQUETA_SEVERIDAD.get(clave, clave))}</span>")


def _prio(clave: str | None) -> str:
    return f'<span class="prio prio-{_e(clave)}">{_e(clave)}</span>'


def _barras(conteo: dict, etiquetas: dict | None = None, clase: bool = False) -> str:
    if not conteo:
        return '<p class="suave">—</p>'
    maximo = max(conteo.values()) or 1
    return "".join(
        f'<div class="barra"><span>{_e((etiquetas or {}).get(k, k))}</span>'
        f'<span class="pista"><span class="relleno{f" r-{_e(k)}" if clase else ""}" '
        f'style="width:{v / maximo * 100:.0f}%"></span></span><span class="n">{v}</span></div>'
        for k, v in conteo.items()
    )


def _indice(hallazgos: list[dict]) -> str:
    if not hallazgos:
        return ""
    filas = "".join(
        f'<tr{" class=\"revisar\"" if h["revisar"] else ""}><td class="suave">{n}</td>'
        f'<td><a href="#h-{_e(h["dedupe_key"])}">{_e(h["titulo"])}</a>'
        f'{" ⚠" if h["revisar"] else ""}<br><code class="suave">{_e(h["ubicacion"]["ruta"])}</code></td>'
        f"<td>{_sev(h['severidad'])}</td><td>{_prio(h['prioridad'])}</td>"
        f'<td class="opcional">{_e(h["owasp_referencia"] or (h["ia"] or {}).get("owasp"))}</td>'
        f'<td class="opcional">{_e(ETIQUETA_ESTADO.get(h["estado"], h["estado"]))}</td></tr>'
        for n, h in enumerate(hallazgos, 1)
    )
    return (
        '<div class="tabla indice"><table><thead><tr><th>#</th><th>Hallazgo</th><th>Severidad</th>'
        '<th>Prioridad</th><th class="opcional">OWASP</th><th class="opcional">Estado</th></tr></thead>'
        f"<tbody>{filas}</tbody></table></div>"
    )


# URLs de cada hallazgo que entran en el PDF.
_URLS_IMPRESAS = 5
_EXTRA = ' class="extra"'
_UNA_URL = ' class="una-url"'


def _seccion_hallazgo(h: dict, n: int, pdf: bool = False) -> str:
    ub = h["ubicacion"]
    ev = h["evidencia"]
    origen = {"persona": "decidida por una persona", "regla": "según la regla",
              "ia": "sugerida por la IA"}.get(h["prioridad_origen"], h["prioridad_origen"])
    fragmento = f"<pre>{_e(ev['fragmento'])}</pre>" if ev["fragmento"] else "—"
    # En pantalla se ven todas las URLs; en el PDF solo las primeras (ver _CSS).
    instancias = "".join(
        f"<tr{_EXTRA if n_i >= _URLS_IMPRESAS else ''}><td>{_e(i['metodo'])}</td>"
        f"<td><code>{_e(i['url'])}</code></td><td>{_e(i['parametro'])}</td></tr>"
        for n_i, i in enumerate(ev["instancias"])
    )
    resto = len(ev["instancias"]) - _URLS_IMPRESAS
    if resto > 0:
        instancias += (f'<tr class="solo-impresion"><td colspan="3" class="suave">… y {resto} '
                       f'{"URL" if resto == 1 else "URLs"} más en el informe en línea.</td></tr>')
    partes = [
        f'<article class="hallazgo{" revisar" if h["revisar"] else ""}" id="h-{_e(h["dedupe_key"])}">',
        # Cerrada por defecto: se ve la cabecera y las capas se abren con un clic.
        # Al imprimir se abren todas (ver _SCRIPT); la descripción de ZAP no entra al PDF.
        # En el PDF de la API no hay clics: la ficha es un bloque abierto.
        '<div class="ficha"><div class="cabecera"><div>' if pdf
        else '<details class="ficha"><summary class="cabecera"><div>',
        f'<h3><span class="n">{n}.</span>{_e(h["titulo"])}</h3>',
        f'<span class="chip">CWE {_e(h["cwe"])}</span>'
        f'<span class="chip">OWASP de referencia {_e(h["owasp_referencia"])}</span>'
        f'<span class="chip">Estado: {_e(ETIQUETA_ESTADO.get(h["estado"], h["estado"]))}</span>'
        f'<span class="chip">Prioridad {_e(origen)}</span>',
        (f'<p class="revisar-marca">⚠ Revisar · {_e(MOTIVO_REVISION.get(h["motivo_revision"], h["motivo_revision"]))}</p>'
         if h["revisar"] else ""),
        f'</div><div class="insignias">{_sev(h["severidad"])} {_prio(h["prioridad"])}'
        '<span class="abrir" aria-hidden="true"></span></div>' + ("</div>" if pdf else "</summary>"),
        '<div class="capas">',
        '<div class="capa"><h4>Evidencia original (ZAP)</h4><dl>',
        f"<dt>Ubicación</dt><dd><code>{_e(ub['metodo'])} {_e(ub['ruta'])}</code></dd>",
        f"<dt>Parámetro</dt><dd>{_e(ub['parametro'])}</dd>",
        f"<dt>Ocurrencias</dt><dd>{_e(ub['ocurrencias'])} · confianza de ZAP {_e(h['confianza_zap'])}</dd>",
        f"<dt>Fragmento</dt><dd>{fragmento}</dd>",
        f"<dt>Clave</dt><dd><code class=\"suave\">{_e(h['dedupe_key'])}</code></dd>",
        "</dl>",
    ]
    if instancias:
        partes.append(
            f"<table{_UNA_URL if len(ev['instancias']) == 1 else ''}>"
            "<thead><tr><th>Método</th><th>URL</th><th>Parámetro</th></tr></thead>"
            f"<tbody>{instancias}</tbody></table>"
        )
    if not pdf:
        partes.append(
            "<details><summary>Descripción y solución que entrega ZAP (en inglés)</summary>"
            f'<div class="texto-zap"><p><strong>Descripción:</strong> {_texto_zap(ev["descripcion"])}</p>'
            f'<p><strong>Solución propuesta por ZAP:</strong> {_texto_zap(ev["solucion"])}</p></div></details>'
        )
    partes.append("</div>")

    ia = h["ia"]
    if ia:
        pasos = "".join(f"<li>{_e(p)}</li>" for p in ia["pasos"])
        coincide = ia["owasp"] and h["owasp_referencia"] and ia["owasp"] == h["owasp_referencia"]
        comparacion = (
            '<span class="chip chip-ok">coincide con la tabla CWE</span>' if coincide
            else f'<span class="chip chip-dif">la tabla CWE dice {_e(h["owasp_referencia"])}</span>'
            if h["owasp_referencia"] else '<span class="chip">sin referencia en la tabla</span>'
        )
        partes += [
            '<div class="capa ia"><h4>Sugerencia de la IA</h4><dl>',
            f"<dt>Explicación</dt><dd>{_e(ia['explicacion'])}</dd>",
            f"<dt>Impacto</dt><dd>{_e(ia['impacto'])}</dd>",
            f"<dt>Categoría</dt><dd>{_e(ia['owasp'])} {comparacion}</dd>",
            f"<dt>Prioridad</dt><dd>{_prio(ia['prioridad'])} · confianza declarada {_e(ia['confianza'])}</dd>",
            f"<dt>Remediación</dt><dd>{_e(ia['remediacion'])}"
            f"{f'<ol>{pasos}</ol>' if pasos else ''}</dd>",
            f'<dt>Modelo</dt><dd class="suave">{_e(ia["modelo"])} · prompt {_e(ia["version_prompt"])}'
            f" · {_fecha(ia['generado'])}</dd>",
            "</dl></div>",
        ]
    else:
        partes.append('<div class="capa ia"><h4>Sugerencia de la IA</h4><p>Sin enriquecer.</p></div>')

    d = h["decision"]
    if d:
        partes += [
            '<div class="capa persona"><h4>Decisión humana</h4>',
            f"<p><strong>{_e(ETIQUETA_DECISION.get(d['decision'], d['decision']))}</strong>"
            f" · {_e(d['revisor'])} · {_fecha(d['fecha'])}</p>",
            f"<p>{_e(d['comentario'])}</p>" if d["comentario"] else "",
            "</div>",
        ]
    else:
        partes.append('<div class="capa persona"><h4>Decisión humana</h4><p>Pendiente de revisión.</p></div>')

    partes.append("</div></div></article>" if pdf else "</div></details></article>")
    return "".join(partes)


def _seccion_metricas(m: dict) -> str:
    if not m["revisores"]:
        return ('<p class="aviso">Todavía no hay validaciones con las banderas del golden set. '
                "Las métricas aparecen cuando una persona revisa la sugerencia de la IA desde el dashboard.</p>")

    def tarjeta(rotulo: str, valor: dict) -> str:
        pct = valor["si"] / valor["n"] * 100 if valor["n"] else 0
        return (f'<div class="tarjeta metrica"><div class="valor">{_proporcion(valor)}</div>'
                f'<div class="rotulo">{rotulo}</div>'
                f'<div class="pista"><span class="relleno" style="width:{pct:.0f}%"></span></div></div>')

    return (
        f"<p>Revisores: {_e(', '.join(r.title() for r in m['revisores']))}. Se cuenta la última respuesta de cada "
        "revisor por hallazgo; las banderas sin responder no entran en el denominador.</p>"
        '<div class="metricas">'
        + tarjeta("Acierto de categoría OWASP", m["acierto_owasp"])
        + tarjeta("Acierto de prioridad", m["acierto_prioridad"])
        + tarjeta("Remediación útil", m["remediacion_util"])
        + tarjeta("Tasa de alucinación", m["alucinacion"])
        + "</div>"
    )


def renderizar_html(datos: dict, pdf: bool = False) -> str:
    """El informe completo como una página HTML autocontenida e imprimible.

    Con pdf=True es la versión que convierte WeasyPrint: sin script ni botones,
    las fichas abiertas y las fuentes IBM Plex del propio backend.
    """
    obj = datos["objetivo"]
    res = datos["resumen"]
    escaneos = "".join(
        f"<tr><td>{_e(s['herramienta'])} {_e(s['version'])}</td><td>{_fecha(s['inicio'])}</td>"
        f'<td><code class="hash">{_e(s["sha256"])}</code></td></tr>'
        for s in datos["escaneos"]
    )
    vigentes = "".join(_seccion_hallazgo(h, i, pdf) for i, h in enumerate(datos["hallazgos"], 1))
    cabeza = f"<style>{_FUENTES}</style>" if pdf else f"<script>{_SCRIPT}</script>"
    como_se_ven = "" if pdf else " Las fichas se abren con un clic; al imprimir salen todas abiertas."
    descartados = "".join(
        f"<tr><td>{_e(h['titulo'])}</td><td><code>{_e(h['ubicacion']['ruta'])}</code></td>"
        f"<td>{_e(ETIQUETA_ESTADO.get(h['estado'], h['estado']))}</td>"
        f"<td>{_e(h['decision']['revisor'] if h['decision'] else None)}</td></tr>"
        for h in datos["descartados"]
    )
    p1 = res["por_prioridad"].get("p1", 0)

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe técnico · {_e(obj['nombre'])}</title>
<style>{_CSS}</style>
{cabeza}
</head>
<body>
<header class="portada"><div class="contenido">
  <p class="marca"><img src="{_CASCO}" alt=""> SentinelAI · Informe técnico de hallazgos</p>
  <h1>{_e(obj['nombre'])}</h1>
  <p class="meta"><code>{_e(obj['url'])}</code> · entorno {_e(obj['entorno'])} · {len(datos['escaneos'])} escaneos · generado {_fecha(datos['generado_en'])}</p>
</div></header>
<main>
<p class="aviso">La evidencia de cada hallazgo se muestra tal como la entregó la herramienta.
La salida de la IA es una sugerencia; la decisión final la toma una persona.</p>

<h2>1. Resumen</h2>
<div class="kpis">
  <div class="kpi base"><div class="valor">{res['vigentes']}</div><div class="rotulo">hallazgos vigentes, de {res['total']}</div></div>
  <div class="kpi alerta"><div class="valor">{p1}</div><div class="rotulo">con prioridad p1</div></div>
  <div class="kpi revisar"><div class="valor">{res['por_revisar']}</div><div class="rotulo">para revisar primero</div></div>
  <div class="kpi persona"><div class="valor">{res['con_decision']}</div><div class="rotulo">con decisión humana</div></div>
</div>
<p><strong>{res['vigentes']}</strong> hallazgos vigentes y <strong>{res['descartados']}</strong>
descartados (falsos positivos o duplicados), de {res['total']} en total.
Con sugerencia de la IA: {res['con_ia']}; con el enriquecimiento fallido: {res['ia_fallida']}. Con decisión humana: {res['con_decision']}.
Hallazgos marcados para revisar primero: {res['por_revisar']}, porque la categoría del modelo no
coincide con la tabla CWE → OWASP o el CWE no está en ella.</p>
<div class="tres">
  <div class="tarjeta"><h3>Por severidad</h3>{_barras(res['por_severidad'], ETIQUETA_SEVERIDAD, clase=True)}</div>
  <div class="tarjeta"><h3>Por prioridad</h3>{_barras(res['por_prioridad'])}</div>
  <div class="tarjeta"><h3>Por estado</h3>{_barras(res['por_estado'], ETIQUETA_ESTADO)}</div>
</div>

<h2>2. Escaneos de origen</h2>
<p class="suave">El hash SHA-256 de cada reporte permite verificar que la evidencia no se modificó después de importarla.</p>
<div class="tabla"><table><thead><tr><th>Herramienta</th><th>Inicio</th><th>SHA-256 del reporte</th></tr></thead>
<tbody>{escaneos or '<tr><td colspan="3">—</td></tr>'}</tbody></table></div>

<h2>3. Hallazgos</h2>
<p class="suave">Ordenados por prioridad y severidad. Cada ficha muestra tres capas: lo que entregó el escáner,
lo que sugiere la IA y lo que decidió una persona.{como_se_ven}</p>
{_indice(datos['hallazgos'])}
{_CONTROLES_FICHAS if datos['hallazgos'] and not pdf else ''}
{vigentes or '<p>No hay hallazgos vigentes.</p>'}

<h2>4. Descartados</h2>
<div class="tabla"><table><thead><tr><th>Hallazgo</th><th>Ruta</th><th>Motivo</th><th>Revisor</th></tr></thead>
<tbody>{descartados or '<tr><td colspan="4">—</td></tr>'}</tbody></table></div>

<h2>5. Calidad de la IA (golden set)</h2>
{_seccion_metricas(datos['metricas'])}
</main>
<footer>Generado por SentinelAI a partir de la base del laboratorio. Proyecto de título · Duoc UC · Grupo 3.</footer>
</body>
</html>
"""
