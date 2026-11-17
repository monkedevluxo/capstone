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

_CSS = """
:root { --tinta:#1a2433; --suave:#5b6675; --borde:#d9dee5; --fondo:#f5f7fa;
        --alta:#b42318; --media:#b54708; --baja:#1d4ed8; --info:#475467; }
* { box-sizing: border-box; }
body { font: 14px/1.5 system-ui, sans-serif; color: var(--tinta); margin: 0; background: #fff; }
main { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
h1 { font-size: 28px; margin: 0 0 4px; }
h2 { font-size: 20px; margin: 32px 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--tinta); }
h3 { font-size: 16px; margin: 0; }
.suave { color: var(--suave); }
table { width: 100%; border-collapse: collapse; margin: 8px 0 16px; }
table.conteo { width: auto; min-width: 240px; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--borde); vertical-align: top; }
th { background: var(--fondo); font-weight: 600; }
code, pre { font: 12px/1.4 ui-monospace, monospace; }
pre { background: var(--fondo); padding: 8px; white-space: pre-wrap; word-break: break-all; margin: 4px 0; }
.hallazgo { border: 1px solid var(--borde); border-radius: 6px; padding: 16px; margin: 0 0 16px;
            break-inside: avoid; }
.cabecera { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.etiqueta { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 12px;
            font-weight: 600; color: #fff; background: var(--info); white-space: nowrap; }
.sev-critica, .sev-alta { background: var(--alta); }
.sev-media { background: var(--media); }
.sev-baja { background: var(--baja); }
.capa { margin-top: 12px; padding-left: 12px; border-left: 3px solid var(--borde); }
.capa h4 { margin: 0 0 4px; font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
           color: var(--suave); }
.ia { border-left-color: #7c3aed; }
.persona { border-left-color: #059669; }
.aviso { background: var(--fondo); padding: 8px 12px; border-radius: 4px; }
.hallazgo.revisar { background: #fffbf7; border-color: #f2c48d; }
.revisar-marca { color: #9a3412; font-weight: 600; font-size: 13px; margin: 2px 0 0; }
@media print {
  main { padding: 0; }
  h2 { break-after: avoid; }
  a { color: inherit; text-decoration: none; }
}
"""


def _e(valor: Any) -> str:
    """Escapa para HTML. None se muestra como guion."""
    return "—" if valor is None or valor == "" else html.escape(str(valor))


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


def _tabla_conteo(conteo: dict, etiquetas: dict | None = None) -> str:
    filas = "".join(
        f"<tr><td>{_e((etiquetas or {}).get(k, k))}</td><td>{v}</td></tr>"
        for k, v in conteo.items()
    )
    return f"<table class=\"conteo\"><tbody>{filas or '<tr><td>—</td></tr>'}</tbody></table>"


def _seccion_hallazgo(h: dict, n: int) -> str:
    ub = h["ubicacion"]
    ev = h["evidencia"]
    instancias = "".join(
        f"<tr><td>{_e(i['metodo'])}</td><td><code>{_e(i['url'])}</code></td>"
        f"<td>{_e(i['parametro'])}</td></tr>"
        for i in ev["instancias"]
    )
    partes = [
        f'<article class="hallazgo{" revisar" if h["revisar"] else ""}" id="h-{_e(h["dedupe_key"])}">',
        '<div class="cabecera">',
        f"<h3>{n}. {_e(h['titulo'])}</h3>",
        f'<span><span class="etiqueta sev-{_e(h["severidad"])}">'
        f"{_e(ETIQUETA_SEVERIDAD.get(h['severidad'], h['severidad']))}</span> "
        f"<strong>{_e(h['prioridad'])}</strong></span>",
        "</div>",
        (f'<p class="revisar-marca">⚠ Revisar · {_e(MOTIVO_REVISION.get(h["motivo_revision"], h["motivo_revision"]))}</p>'
         if h["revisar"] else ""),
        f'<p class="suave">CWE {_e(h["cwe"])} · OWASP de referencia {_e(h["owasp_referencia"])} · '
        f"prioridad según {_e(h['prioridad_origen'])} · estado {_e(ETIQUETA_ESTADO.get(h['estado'], h['estado']))} · "
        f"clave <code>{_e(h['dedupe_key'])}</code></p>",
        '<div class="capa"><h4>Evidencia original (ZAP)</h4>',
        f"<p><strong>Ubicación:</strong> <code>{_e(ub['metodo'])} {_e(ub['ruta'])}</code>"
        f" · parámetro {_e(ub['parametro'])} · {_e(ub['ocurrencias'])} ocurrencias"
        f" · confianza de ZAP {_e(h['confianza_zap'])}</p>",
        f"<p><strong>Fragmento:</strong></p><pre>{_e(ev['fragmento'])}</pre>",
        f"<p><strong>Descripción:</strong> {_texto_zap(ev['descripcion'])}</p>",
        f"<p><strong>Solución propuesta por ZAP:</strong> {_texto_zap(ev['solucion'])}</p>",
    ]
    if instancias:
        partes.append(
            "<table><thead><tr><th>Método</th><th>URL</th><th>Parámetro</th></tr></thead>"
            f"<tbody>{instancias}</tbody></table>"
        )
    partes.append("</div>")

    ia = h["ia"]
    if ia:
        pasos = "".join(f"<li>{_e(p)}</li>" for p in ia["pasos"])
        partes += [
            '<div class="capa ia"><h4>Sugerencia de la IA</h4>',
            f'<p class="suave">{_e(ia["modelo"])} · prompt {_e(ia["version_prompt"])} · '
            f"{_e(ia['generado'])} · confianza declarada {_e(ia['confianza'])}</p>",
            f"<p><strong>Explicación:</strong> {_e(ia['explicacion'])}</p>",
            f"<p><strong>Impacto:</strong> {_e(ia['impacto'])}</p>",
            f"<p><strong>Categoría sugerida:</strong> {_e(ia['owasp'])} "
            f"(referencia según CWE: {_e(h['owasp_referencia'])}) · "
            f"<strong>prioridad sugerida:</strong> {_e(ia['prioridad'])}</p>",
            f"<p><strong>Remediación:</strong> {_e(ia['remediacion'])}</p>",
            f"<ol>{pasos}</ol>" if pasos else "",
            "</div>",
        ]
    else:
        partes.append('<div class="capa ia"><h4>Sugerencia de la IA</h4><p>Sin enriquecer.</p></div>')

    d = h["decision"]
    if d:
        partes += [
            '<div class="capa persona"><h4>Decisión humana</h4>',
            f"<p><strong>{_e(ETIQUETA_DECISION.get(d['decision'], d['decision']))}</strong>"
            f" · {_e(d['revisor'])} · {_e(d['fecha'])}</p>",
            f"<p>{_e(d['comentario'])}</p>" if d["comentario"] else "",
            "</div>",
        ]
    else:
        partes.append('<div class="capa persona"><h4>Decisión humana</h4><p>Pendiente de revisión.</p></div>')

    partes.append("</article>")
    return "".join(partes)


def _seccion_metricas(m: dict) -> str:
    if not m["revisores"]:
        return ('<p class="aviso">Todavía no hay validaciones con las banderas del golden set. '
                "Las métricas aparecen cuando una persona revisa la sugerencia de la IA desde el dashboard.</p>")
    return (
        f"<p>Revisores: {_e(', '.join(m['revisores']))}. Se cuenta la última respuesta de cada "
        "revisor por hallazgo; las banderas sin responder no entran en el denominador.</p>"
        "<table><thead><tr><th>Métrica</th><th>Resultado</th></tr></thead><tbody>"
        f"<tr><td>Acierto de categoría OWASP</td><td>{_proporcion(m['acierto_owasp'])}</td></tr>"
        f"<tr><td>Acierto de prioridad</td><td>{_proporcion(m['acierto_prioridad'])}</td></tr>"
        f"<tr><td>Remediación útil</td><td>{_proporcion(m['remediacion_util'])}</td></tr>"
        f"<tr><td>Tasa de alucinación</td><td>{_proporcion(m['alucinacion'])}</td></tr>"
        "</tbody></table>"
    )


def renderizar_html(datos: dict) -> str:
    """El informe completo como una página HTML autocontenida e imprimible."""
    obj = datos["objetivo"]
    res = datos["resumen"]
    escaneos = "".join(
        f"<tr><td>{_e(s['herramienta'])} {_e(s['version'])}</td><td>{_e(s['inicio'])}</td>"
        f"<td><code>{_e(s['sha256'])}</code></td></tr>"
        for s in datos["escaneos"]
    )
    vigentes = "".join(_seccion_hallazgo(h, i) for i, h in enumerate(datos["hallazgos"], 1))
    descartados = "".join(
        f"<tr><td>{_e(h['titulo'])}</td><td><code>{_e(h['ubicacion']['ruta'])}</code></td>"
        f"<td>{_e(ETIQUETA_ESTADO.get(h['estado'], h['estado']))}</td>"
        f"<td>{_e(h['decision']['revisor'] if h['decision'] else None)}</td></tr>"
        for h in datos["descartados"]
    )

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe técnico · {_e(obj['nombre'])}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<header>
  <p class="suave">SentinelAI · Informe técnico de hallazgos</p>
  <h1>{_e(obj['nombre'])}</h1>
  <p class="suave"><code>{_e(obj['url'])}</code> · entorno {_e(obj['entorno'])} · generado {_e(datos['generado_en'])}</p>
</header>

<p class="aviso">La evidencia de cada hallazgo se muestra tal como la entregó la herramienta.
La salida de la IA es una sugerencia; la decisión final la toma una persona.</p>

<h2>1. Resumen</h2>
<p><strong>{res['vigentes']}</strong> hallazgos vigentes y <strong>{res['descartados']}</strong>
descartados (falsos positivos o duplicados), de {res['total']} en total.
{res['con_ia']} tienen sugerencia de la IA y {res['con_decision']} tienen decisión humana.
Hallazgos marcados para revisar primero: {res['por_revisar']}, porque la categoría del modelo no
coincide con la tabla CWE → OWASP o el CWE no está en ella.</p>
<h3>Por severidad</h3>
{_tabla_conteo(res['por_severidad'], ETIQUETA_SEVERIDAD)}
<h3>Por prioridad</h3>
{_tabla_conteo(res['por_prioridad'])}
<h3>Por estado</h3>
{_tabla_conteo(res['por_estado'], ETIQUETA_ESTADO)}

<h2>2. Escaneos de origen</h2>
<p>El hash SHA-256 de cada reporte permite verificar que la evidencia no se modificó después de importarla.</p>
<table><thead><tr><th>Herramienta</th><th>Inicio</th><th>SHA-256 del reporte</th></tr></thead>
<tbody>{escaneos or '<tr><td colspan="3">—</td></tr>'}</tbody></table>

<h2>3. Hallazgos</h2>
<p class="suave">Ordenados por prioridad y severidad.</p>
{vigentes or '<p>No hay hallazgos vigentes.</p>'}

<h2>4. Descartados</h2>
<table><thead><tr><th>Hallazgo</th><th>Ruta</th><th>Motivo</th><th>Revisor</th></tr></thead>
<tbody>{descartados or '<tr><td colspan="4">—</td></tr>'}</tbody></table>

<h2>5. Calidad de la IA (golden set)</h2>
{_seccion_metricas(datos['metricas'])}
</main>
</body>
</html>
"""
