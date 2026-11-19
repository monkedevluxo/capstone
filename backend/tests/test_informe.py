"""Tests del informe técnico (app/informe.py). No necesitan base de datos:
usan objetos simples con los mismos atributos que los modelos."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as O

from app.informe import armar_datos, metricas_golden_set, renderizar_html

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
OBJETIVO = O(nombre="Juice Shop", base_url="http://juiceshop:3000", environment="lab")
ESCANEO = O(tool="zap", tool_version="2.16.0", started_at=T0, report_sha256="ab" * 32)


def ia(**cambios):
    base = dict(is_current=True, state="ok", model="llama3.1:8b", prompt_version="v2",
                explanation="Explicación", impact="Impacto", owasp_category="A05:2025",
                priority="p1", confidence=0.9, remediation_summary="Usar consultas parametrizadas",
                remediation_steps=["Paso 1"], generated_at=T0)
    return O(**(base | cambios))


def validacion(fid, revisor="Felipe", minutos=0, **cambios):
    base = dict(finding_id=fid, reviewer=revisor, reviewed_at=T0 + timedelta(minutes=minutos),
                decision="confirmado", priority_override=None, comment=None,
                ai_owasp_correcto=None, ai_prioridad_correcta=None,
                ai_remediacion_util=None, ai_alucinacion=None)
    return O(**(base | cambios))


def hallazgo(fid, titulo="SQL Injection", severidad="alta", sev_zap="High", estado="nuevo",
             evidencia=None, enriquecimientos=(), validaciones=(), cwe=89):
    return O(
        id=fid, dedupe_key=f"k{fid}", titulo=titulo, status=estado, severity=severidad,
        severity_tool_raw=sev_zap, tool_confidence="low", cwe_id=cwe, method="GET",
        path_template="/rest/products/search", param="q", occurrences=2,
        evidence_snippet=evidencia, source_raw={"desc": "<p>Descripción</p>", "solution": "<p>Arreglo</p>"},
        instances=[O(method="GET", url="http://juiceshop:3000/rest/products/search?q=%27", param="q")],
        enrichments=list(enriquecimientos), validations=list(validaciones),
    )


def test_prioridad_de_la_regla_si_nadie_decidio():
    datos = armar_datos(OBJETIVO, [ESCANEO], [hallazgo(1, sev_zap="Medium", severidad="media")])
    h = datos["hallazgos"][0]
    assert h["prioridad"] == "p2"
    assert h["prioridad_origen"] == "regla"


def test_la_prioridad_humana_manda_sobre_la_regla_y_la_ia():
    f = hallazgo(1, enriquecimientos=[ia(priority="p1")],
                 validaciones=[validacion(1, priority_override="p3")])
    h = armar_datos(OBJETIVO, [], [f])["hallazgos"][0]
    assert h["prioridad"] == "p3"
    assert h["prioridad_origen"] == "persona"
    assert h["ia"]["prioridad"] == "p1"  # la sugerencia se conserva


def test_usa_la_decision_mas_reciente():
    f = hallazgo(1, validaciones=[validacion(1, minutos=5, decision="confirmado"),
                                  validacion(1, minutos=1, decision="requiere_segunda_opinion")])
    assert armar_datos(OBJETIVO, [], [f])["hallazgos"][0]["decision"]["decision"] == "confirmado"


def test_ignora_enriquecimientos_historicos_o_fallidos():
    f = hallazgo(1, enriquecimientos=[ia(is_current=False), ia(state="failed")])
    assert armar_datos(OBJETIVO, [], [f])["hallazgos"][0]["ia"] is None


def test_descartados_van_aparte_y_no_cuentan_como_vigentes():
    datos = armar_datos(OBJETIVO, [], [hallazgo(1), hallazgo(2, estado="falso_positivo"),
                                       hallazgo(3, estado="duplicado")])
    assert [h["id"] for h in datos["hallazgos"]] == ["1"]
    assert {h["id"] for h in datos["descartados"]} == {"2", "3"}
    assert datos["resumen"]["vigentes"] == 1
    assert datos["resumen"]["descartados"] == 2


def test_orden_por_prioridad_y_luego_severidad():
    datos = armar_datos(OBJETIVO, [], [
        hallazgo(1, titulo="Baja", severidad="baja", sev_zap="Low"),
        hallazgo(2, titulo="Alta", severidad="alta", sev_zap="High"),
        hallazgo(3, titulo="Media", severidad="media", sev_zap="Medium"),
    ])
    assert [h["titulo"] for h in datos["hallazgos"]] == ["Alta", "Media", "Baja"]


def test_metricas_cuentan_la_ultima_respuesta_por_revisor_y_hallazgo():
    vs = [
        validacion(1, "Felipe", 0, ai_alucinacion=True),
        validacion(1, "  felipe ", 5, ai_alucinacion=False),   # mismo revisor, más reciente
        validacion(1, "Joaquín", 0, ai_alucinacion=True),
        validacion(2, "Felipe", 0, ai_alucinacion=None),       # sin responder: no cuenta
    ]
    m = metricas_golden_set(vs)
    assert m["alucinacion"] == {"si": 1, "n": 2}
    assert m["revisores"] == ["felipe", "joaquín"]


def test_el_html_escapa_la_evidencia():
    datos = armar_datos(OBJETIVO, [ESCANEO], [hallazgo(1, evidencia="<script>alert(1)</script>")])
    pagina = renderizar_html(datos)
    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in pagina


def test_el_html_trae_las_secciones_y_el_hash_del_reporte():
    f = hallazgo(1, enriquecimientos=[ia()],
                 validaciones=[validacion(1, ai_owasp_correcto=True, ai_alucinacion=False)])
    pagina = renderizar_html(armar_datos(OBJETIVO, [ESCANEO], [f]))
    for texto in ("1. Resumen", "2. Escaneos de origen", "3. Hallazgos", "4. Descartados",
                  "5. Calidad de la IA", "Sugerencia de la IA", "Decisión humana", "ab" * 32):
        assert texto in pagina


def test_el_html_sin_validaciones_explica_que_faltan():
    pagina = renderizar_html(armar_datos(OBJETIVO, [], [hallazgo(1)]))
    assert "Todavía no hay validaciones" in pagina
    assert "Pendiente de revisión" in pagina
    assert "Sin enriquecer" in pagina


def test_marca_revisar_cuando_el_modelo_no_coincide_con_la_tabla():
    # CWE 89 (inyección SQL) es A05:2025 en la tabla; el modelo dice otra cosa.
    f = hallazgo(1, cwe=89, enriquecimientos=[ia(owasp_category="A03:2025")])
    datos = armar_datos(OBJETIVO, [], [f])
    h = datos["hallazgos"][0]
    assert h["revisar"] is True
    assert h["motivo_revision"] == "categoria_distinta"
    assert datos["resumen"]["por_revisar"] == 1
    pagina = renderizar_html(datos)
    assert "Revisar · categoría distinta" in pagina
    assert 'class="hallazgo revisar"' in pagina


def test_sin_marca_cuando_el_modelo_coincide_o_no_hay_ia():
    coincide = hallazgo(1, cwe=89, enriquecimientos=[ia(owasp_category="A05:2025")])
    sin_ia = hallazgo(2, cwe=89)
    datos = armar_datos(OBJETIVO, [], [coincide, sin_ia])
    assert [h["revisar"] for h in datos["hallazgos"]] == [False, False]
    assert "Revisar ·" not in renderizar_html(datos)


def test_resumen_no_depende_del_plural():
    # Antes decía "1 tienen decisión humana"; la frase no debe cambiar con el número.
    f = hallazgo(1, validaciones=[validacion(1, revisor="Prueba")])
    pagina = renderizar_html(armar_datos(OBJETIVO, [], [f]))
    assert "Con sugerencia de la IA: 0. Con decisión humana: 1." in pagina
    assert "1 tienen" not in pagina
