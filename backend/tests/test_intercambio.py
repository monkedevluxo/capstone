"""
SentinelAI · Tests del intercambio entre equipos (scripts/intercambio.py).

Exportar enriquecimientos y validaciones de una base e importarlos en otra,
donde los ids de los hallazgos son distintos. La "otra base" se simula
borrando las tablas y reimportando dentro del mismo test.

    cd backend
    python -m pytest tests/test_intercambio.py -v

OJO: vacían las tablas. No los corras contra una base con datos que te importen.
"""

import copy
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db import engine

try:
    with engine.connect() as _c:
        _c.execute(text("SELECT 1 FROM findings LIMIT 1"))
except Exception:  # noqa: BLE001
    pytest.skip("sin PostgreSQL migrado disponible", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.ia.cliente import Respuesta  # noqa: E402
from app.intercambio import (  # noqa: E402
    ArchivoInvalido,
    exportar,
    importar,
    kappa,
    metricas,
    validar_archivo,
)
from app.main import app  # noqa: E402
from app.models import Finding, Validation  # noqa: E402
from app.rutas import get_cliente  # noqa: E402
from app.validacion import recalcular_estado  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
FIXTURES = BACKEND.parent / "lab" / "fixtures"
api = TestClient(app)

VALIDA = {
    "explicacion": "La entrada del usuario llega sin filtrar a la consulta SQL.",
    "impacto": "Un atacante podría leer o modificar datos de la base.",
    "owasp": "A05:2025",
    "prioridad": "p1",
    "confianza": 0.9,
    "remediacion": "Usar consultas parametrizadas.",
}


class ClienteFalso:
    def __init__(self, respuesta: str):
        self.respuesta = respuesta
        self.modelo = "modelo-falso"
        self.url = "http://falso"

    def generar(self, prompt):
        return Respuesta(texto=self.respuesta, latencia_ms=100)


def _vaciar(*tablas):
    with engine.begin() as c:
        c.execute(text(f"TRUNCATE {', '.join(tablas)} CASCADE"))


def _otra_base():
    """Borra todo y reimporta el escaneo: mismos dedupe_key, ids nuevos."""
    _vaciar("validations", "ai_enrichments", "finding_observations",
            "finding_instances", "findings", "scans", "targets")
    crudo = json.loads((FIXTURES / "zap_juiceshop_ajax_v2.json").read_text(encoding="utf-8"))
    assert api.post("/scans/import", json=crudo).status_code == 201


@pytest.fixture(autouse=True)
def base_vacia():
    _otra_base()
    yield
    app.dependency_overrides.clear()


def _id(titulo: str) -> str:
    items = api.get("/findings", params={"q": titulo}).json()["items"]
    return next(i["id"] for i in items if i["titulo"] == titulo)


def _enriquecer(finding_id: str, respuesta: str | None = None) -> dict:
    app.dependency_overrides[get_cliente] = lambda: ClienteFalso(respuesta or json.dumps(VALIDA))
    r = api.post(f"/findings/{finding_id}/enrich")
    assert r.status_code == 200, r.text
    return r.json()


def _sugerencia(finding_id: str) -> str:
    with engine.connect() as c:
        return str(c.scalar(text(
            "SELECT id FROM ai_enrichments WHERE finding_id = :f AND is_current"
        ), {"f": finding_id}))


def _validar(finding_id: str, **cuerpo) -> dict:
    r = api.post(
        f"/findings/{finding_id}/validaciones",
        json={"decision": "confirmado", "revisor": "Felipe", **cuerpo},
    )
    assert r.status_code == 201, r.text
    return r.json()["validacion"]


def _estado(finding_id: str) -> str:
    with engine.connect() as c:
        return c.scalar(text("SELECT status FROM findings WHERE id = :f"), {"f": finding_id})


def _conteo(tabla: str) -> int:
    with engine.connect() as c:
        return c.scalar(text(f"SELECT count(*) FROM {tabla}"))


def _exportar(que: str, revisor: str | None = None) -> dict:
    with SessionLocal() as db:
        return json.loads(json.dumps(exportar(db, que, revisor=revisor), default=str))


def _importar(archivo: dict):
    with SessionLocal() as db:
        reporte = importar(db, archivo)
        db.commit()
        return reporte


def _sin_fecha_de_exportacion(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "exportado_en"}


def _con_banderas(f: str, revisor: str = "Felipe", decision: str = "confirmado", **banderas):
    return _validar(
        f, decision=decision, revisor=revisor, enrichment_id=_sugerencia(f),
        **{"ai_owasp_correcto": True, "ai_prioridad_correcta": True,
           "ai_remediacion_util": True, "ai_alucinacion": False, **banderas},
    )


# ── Ida y vuelta ──────────────────────────────────────────────────────────

def test_ida_y_vuelta_conserva_uuids_campos_y_estado():
    sqli, csp = _id("SQL Injection"), _id("Content Security Policy (CSP) Header Not Set")
    _enriquecer(sqli)
    _enriquecer(sqli)  # el primero queda histórico
    _enriquecer(csp)
    _con_banderas(sqli, decision="falso_positivo", ai_nota="Ojo con la evidencia.")
    _validar(csp, decision="riesgo_aceptado", comentario="Sin IA.")

    enr, val = _exportar("enriquecimientos"), _exportar("validaciones")
    assert enr["formato"] == "sentinelai-intercambio" and enr["version"] == 1
    assert enr["tipo"] == "enriquecimientos" and len(enr["items"]) == 3
    assert val["tipo"] == "validaciones" and len(val["items"]) == 2
    assert "sentinel_local" not in json.dumps(enr)  # nunca credenciales
    item = next(i for i in enr["items"] if i["is_current"] and i["hallazgo"]["titulo"] == "SQL Injection")
    assert set(item["hallazgo"]) == {"base_url", "dedupe_key", "titulo", "ruta"}

    _otra_base()
    r1 = _importar(enr)
    r2 = _importar(val)
    assert (r1.importados, r2.importados) == (3, 2)

    assert _sin_fecha_de_exportacion(_exportar("enriquecimientos"))["items"] == enr["items"]
    assert _sin_fecha_de_exportacion(_exportar("validaciones"))["items"] == val["items"]
    assert _estado(_id("SQL Injection")) == "falso_positivo"
    assert _estado(_id("Content Security Policy (CSP) Header Not Set")) == "riesgo_aceptado"


def test_exportar_validaciones_filtra_por_revisor():
    f = _id("SQL Injection")
    _validar(f, revisor="Felipe")
    _validar(f, revisor="Joaquín")
    items = _exportar("validaciones", revisor="Joaquín")["items"]
    assert [i["reviewer"] for i in items] == ["Joaquín"]


# ── Idempotencia y conflictos ─────────────────────────────────────────────

def test_importar_dos_veces_no_duplica():
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    enr, val = _exportar("enriquecimientos"), _exportar("validaciones")
    _otra_base()
    _importar(enr), _importar(val)

    r1, r2 = _importar(enr), _importar(val)
    assert (r1.importados, r1.ya_estaban, r2.importados, r2.ya_estaban) == (0, 1, 0, 1)
    assert (_conteo("ai_enrichments"), _conteo("validations")) == (1, 1)


def test_uuid_existente_con_contenido_distinto_es_conflicto_y_no_se_pisa():
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    enr, val = _exportar("enriquecimientos"), _exportar("validaciones")
    enr["items"][0]["explanation"] = "Otra explicación."
    val["items"][0]["ai_owasp_correcto"] = False

    r1, r2 = _importar(enr), _importar(val)
    assert (len(r1.conflictos), len(r2.conflictos)) == (1, 1)
    assert "explanation" in r1.conflictos[0]
    assert "ai_owasp_correcto" in r2.conflictos[0]
    with engine.connect() as c:
        assert c.scalar(text("SELECT explanation FROM ai_enrichments")) == VALIDA["explicacion"]
        assert c.scalar(text("SELECT ai_owasp_correcto FROM validations")) is True


def test_is_current_distinto_no_es_conflicto():
    f = _id("SQL Injection")
    _enriquecer(f)
    enr = _exportar("enriquecimientos")
    _enriquecer(f)  # el exportado pasa a histórico en esta base
    r = _importar(enr)
    assert (r.ya_estaban, r.conflictos) == (1, [])


def test_hallazgo_ausente_se_omite_y_se_reporta():
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    enr, val = _exportar("enriquecimientos"), _exportar("validaciones")
    enr["items"][0]["hallazgo"]["dedupe_key"] = "ffffffffffffffff"
    val["items"][0]["hallazgo"]["base_url"] = "http://otro-objetivo:3000"
    _otra_base()

    r1, r2 = _importar(enr), _importar(val)
    assert (r1.importados, len(r1.no_encontrados)) == (0, 1)
    assert (r2.importados, len(r2.no_encontrados)) == (0, 1)
    assert "ffffffffffffffff" in r1.no_encontrados[0]
    assert _conteo("findings") == 13  # nunca crea hallazgos


def test_validacion_sin_su_enriquecimiento_se_omite_y_entra_al_reimportar():
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    enr, val = _exportar("enriquecimientos"), _exportar("validaciones")
    _otra_base()

    r = _importar(val)
    assert (r.importados, len(r.sin_enriquecimiento)) == (0, 1)
    assert "importa primero los enriquecimientos de" in r.sin_enriquecimiento[0]
    assert val["base_origen"] in r.sin_enriquecimiento[0]
    assert _conteo("validations") == 0

    _importar(enr)
    r = _importar(val)
    assert (r.importados, r.sin_enriquecimiento) == (1, [])
    with engine.connect() as c:
        assert c.scalar(text("SELECT enrichment_id IS NOT NULL FROM validations"))


def test_validacion_sin_ia_entra_aunque_no_haya_enriquecimientos():
    _validar(_id("SQL Injection"), decision="duplicado")
    val = _exportar("validaciones")
    _otra_base()
    assert _importar(val).importados == 1
    assert _estado(_id("SQL Injection")) == "duplicado"


# ── is_current ────────────────────────────────────────────────────────────

def test_ok_vigente_importado_deja_el_local_como_historico():
    f = _id("SQL Injection")
    _enriquecer(f)
    enr = _exportar("enriquecimientos")
    _otra_base()
    f = _id("SQL Injection")
    _enriquecer(f)
    local = _sugerencia(f)

    r = _importar(enr)
    assert r.importados == 1 and r.avisos == []
    assert _sugerencia(f) == enr["items"][0]["uuid"]
    with engine.connect() as c:
        assert c.scalar(text("SELECT is_current FROM ai_enrichments WHERE id = :i"), {"i": local}) is False
    assert _conteo("ai_enrichments") == 2


def test_fallido_vigente_importado_no_desplaza_un_ok_local():
    f = _id("SQL Injection")
    _enriquecer(f, respuesta="esto no es json")
    enr = _exportar("enriquecimientos")
    assert enr["items"][0]["state"] == "failed" and enr["items"][0]["is_current"]
    _otra_base()
    f = _id("SQL Injection")
    _enriquecer(f)
    local = _sugerencia(f)

    r = _importar(enr)
    assert r.importados == 1
    assert len(r.avisos) == 1 and "histórico" in r.avisos[0]
    assert _sugerencia(f) == local


def test_historico_importado_no_toca_el_vigente():
    f = _id("SQL Injection")
    _enriquecer(f)
    _enriquecer(f)
    enr = _exportar("enriquecimientos")
    enr["items"] = [i for i in enr["items"] if not i["is_current"]]
    _otra_base()
    f = _id("SQL Injection")
    _enriquecer(f)
    local = _sugerencia(f)
    assert _importar(enr).importados == 1
    assert _sugerencia(f) == local


# ── Estado del hallazgo ───────────────────────────────────────────────────

def test_el_estado_lo_fija_la_validacion_mas_reciente_aunque_llegue_importada():
    f = _id("SQL Injection")
    _validar(f, decision="confirmado")
    val = _exportar("validaciones")
    antigua, nueva = copy.deepcopy(val), copy.deepcopy(val)
    antigua["items"][0].update(uuid=str(uuid.uuid4()), decision="falso_positivo",
                               reviewed_at="2020-01-01T00:00:00+00:00")
    # Más nueva que la local, pero dentro de la tolerancia de reloj (10 min).
    nueva["items"][0].update(uuid=str(uuid.uuid4()), decision="riesgo_aceptado",
                             reviewed_at=_en(minutos=5))

    _importar(antigua)
    assert _estado(f) == "confirmado"
    _importar(nueva)
    assert _estado(f) == "riesgo_aceptado"


def test_recalcular_estado_desempata_por_id():
    f = _id("SQL Injection")
    mismo_momento = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    menor, mayor = uuid.UUID(int=1), uuid.UUID(int=2)
    with SessionLocal() as db:
        # Se insertan al revés del orden esperado, a propósito.
        for i, d in ((mayor, "duplicado"), (menor, "falso_positivo")):
            db.add(Validation(id=i, finding_id=f, decision=d, reviewer="X", reviewed_at=mismo_momento))
        hallazgo = db.get(Finding, f)
        assert recalcular_estado(db, hallazgo).value == "duplicado"


# ── --simular y archivo inválido ──────────────────────────────────────────

def _cli(*args, entrada: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "scripts/intercambio.py", *args],
        input=entrada, capture_output=True, text=True, cwd=BACKEND, env=os.environ.copy(),
    )


def test_simular_muestra_el_reporte_y_no_cambia_nada():
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    salida = _cli("exportar", "--que", "enriquecimientos")
    assert salida.returncode == 0, salida.stderr
    enr = salida.stdout
    val = _cli("exportar", "--que", "validaciones").stdout
    _otra_base()

    for archivo in (enr, val):
        r = _cli("importar", "--simular", entrada=archivo)
        assert r.returncode == 0, r.stderr
        assert "SIMULACIÓN" in r.stdout and "importados" in r.stdout
    assert (_conteo("ai_enrichments"), _conteo("validations")) == (0, 0)
    assert _estado(_id("SQL Injection")) == "nuevo"

    r = _cli("importar", entrada=enr)
    assert r.returncode == 0, r.stderr
    assert _conteo("ai_enrichments") == 1


def _archivo_valido() -> dict:
    f = _id("SQL Injection")
    _enriquecer(f)
    _con_banderas(f)
    _validar(_id("Content Security Policy (CSP) Header Not Set"))
    return _exportar("validaciones")


@pytest.mark.parametrize("dañar", [
    lambda d: d.update(formato="otro"),
    lambda d: d.update(version=2),
    lambda d: d.update(tipo="hallazgos"),
    lambda d: d["items"][1].update(decision="quizas"),
    lambda d: d["items"][1].update(priority_override="p9"),
    lambda d: d["items"][1].update(reviewed_at="2026-11-15T12:00:00"),  # sin zona
    lambda d: d["items"][1].update(uuid=d["items"][0]["uuid"]),
    lambda d: d["items"][0].update(enrichment_uuid=None),  # banderas ai_* sin sugerencia
    lambda d: d["items"][1].pop("reviewer"),
    lambda d: d["items"][1].update(campo_extra=1),
], ids=["formato", "version", "tipo", "enum", "prioridad", "fecha_sin_zona",
        "uuid_repetido", "banderas_sin_enriquecimiento", "falta_campo", "campo_extra"])
def test_archivo_invalido_no_importa_nada(dañar):
    archivo = _archivo_valido()
    _vaciar("validations")
    dañar(archivo)

    with pytest.raises(ArchivoInvalido) as e:
        validar_archivo(archivo)
    assert e.value.errores

    r = _cli("importar", entrada=json.dumps(archivo))
    assert r.returncode == 2
    assert "no se importó nada" in r.stderr
    assert _conteo("validations") == 0


def test_enriquecimiento_fallido_con_datos_es_invalido():
    f = _id("SQL Injection")
    _enriquecer(f, respuesta="esto no es json")
    enr = _exportar("enriquecimientos")
    enr["items"][0]["owasp_category"] = "A05:2025"
    with pytest.raises(ArchivoInvalido):
        validar_archivo(enr)


def test_json_roto_no_importa_nada():
    r = _cli("importar", entrada="{no es json")
    assert r.returncode == 2 and "no se importó nada" in r.stderr


# ── Métricas ──────────────────────────────────────────────────────────────

def test_kappa_calculado_a_mano():
    # A y B coinciden en 8 de 10. Cada uno dice "sí" 6 veces.
    # po = 0,8 ; pe = 0,6·0,6 + 0,4·0,4 = 0,52 ; κ = (0,8 − 0,52) / 0,48 = 0,5833…
    a = [True, True, True, False, False, True, False, True, True, False]
    b = [True, True, False, False, False, True, True, True, True, False]
    assert kappa(list(zip(a, b))) == pytest.approx(0.583333, abs=1e-6)


def test_kappa_indefinido_si_todos_responden_lo_mismo():
    assert kappa([(True, True), (True, True)]) is None
    assert kappa([]) is None


def test_metricas_por_revisor_total_y_acuerdo():
    sqli, csp = _id("SQL Injection"), _id("Content Security Policy (CSP) Header Not Set")
    redirect = _id("External Redirect")
    for f in (sqli, csp, redirect):
        _enriquecer(f)
    # Felipe cambia de opinión en sqli: cuenta solo su última respuesta.
    _con_banderas(sqli, revisor="Felipe", ai_owasp_correcto=False)
    _con_banderas(sqli, revisor="Felipe", ai_owasp_correcto=True)
    _con_banderas(csp, revisor="Felipe", ai_owasp_correcto=True, ai_alucinacion=True)
    _con_banderas(redirect, revisor="Felipe", ai_owasp_correcto=None)
    _con_banderas(sqli, revisor="Joaquín", ai_owasp_correcto=True)
    _con_banderas(csp, revisor="Joaquín", ai_owasp_correcto=False)
    _con_banderas(redirect, revisor="Joaquín", ai_owasp_correcto=True)
    _validar(sqli, revisor="Luciano", decision="confirmado")  # sin banderas: no cuenta

    with SessionLocal() as db:
        m = metricas(db)

    felipe = m["revisores"]["Felipe"]
    assert felipe["validaciones"] == 3
    assert felipe["ai_owasp_correcto"] == {"si": 2, "no": 0, "n": 2, "pct": 100.0}
    assert felipe["ai_alucinacion"] == {"si": 1, "no": 2, "n": 3, "pct": pytest.approx(33.3, abs=0.1)}
    assert m["total"]["ai_owasp_correcto"] == {"si": 4, "no": 1, "n": 5, "pct": 80.0}
    assert "Luciano" not in m["revisores"]
    assert m["hallazgos_con_2_o_mas_revisores"] == 3

    [par] = m["acuerdo_ai_owasp_correcto"]
    assert par["revisores"] == ["Felipe", "Joaquín"]
    assert par["n"] == 2  # redirect se excluye: Felipe dijo "no sé"
    assert par["acuerdo_pct"] == 50.0
    # po = 0,5 ; Felipe sí 2/2, Joaquín sí 1/2 ; pe = 1·0,5 + 0·0,5 = 0,5 ; κ = 0
    assert par["kappa"] == pytest.approx(0.0)

    salida = _cli("metricas")
    assert salida.returncode == 0, salida.stderr
    assert "Felipe" in salida.stdout and "κ" in salida.stdout and "n = 2" in salida.stdout
    assert json.loads(_cli("metricas", "--json").stdout)["total"]["ai_owasp_correcto"]["n"] == 5


# ── Revisión final ────────────────────────────────────────────────────────

@pytest.mark.parametrize("dañar", [
    lambda i: i.update(owasp_version="OWASP-2025-x"),   # String(10) en la base
    lambda i: i.update(latency_ms=2**31),                 # int4 en la base
    lambda i: i.update(attempts=2**31),
], ids=["owasp_version_largo", "latencia_int4", "intentos_int4"])
def test_valores_que_la_base_rechazaria_hacen_invalido_el_archivo(dañar):
    _enriquecer(_id("SQL Injection"))
    enr = _exportar("enriquecimientos")
    dañar(enr["items"][0])
    _otra_base()
    r = _cli("importar", entrada=json.dumps(enr))
    assert r.returncode == 2 and "no se importó nada" in r.stderr
    assert "Traceback" not in r.stderr


def test_ai_nota_sobre_un_enriquecimiento_fallido_es_conflicto():
    f = _id("SQL Injection")
    _enriquecer(f, respuesta="esto no es json")
    fallido = _sugerencia(f)
    _validar(f)
    val = _exportar("validaciones")
    val["items"][0].update(uuid=str(uuid.uuid4()), enrichment_uuid=fallido, ai_nota="Raro.")
    r = _importar(val)
    assert (r.importados, len(r.conflictos)) == (0, 1)


def _en(minutos: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutos)).isoformat()


def test_validacion_mas_de_10_minutos_en_el_futuro_se_omite_como_conflicto():
    f = _id("SQL Injection")
    _validar(f, decision="confirmado")
    val = _exportar("validaciones")
    futura = copy.deepcopy(val)
    futura["items"][0].update(uuid=str(uuid.uuid4()), decision="falso_positivo", reviewed_at=_en(minutos=11))

    r = _importar(futura)
    assert (r.importados, len(r.conflictos)) == (0, 1)
    assert f"fecha en el futuro: revisa el reloj de {val['base_origen']}" in r.conflictos[0]
    assert _conteo("validations") == 1
    assert _estado(f) == "confirmado"


def test_validacion_poco_en_el_futuro_entra_con_aviso():
    _validar(_id("SQL Injection"))
    val = _exportar("validaciones")
    val["items"][0].update(uuid=str(uuid.uuid4()), reviewed_at=_en(minutos=5))
    r = _importar(val)
    assert (r.importados, r.conflictos) == (1, [])
    assert any("futuro" in a for a in r.avisos)


def test_exportar_deja_json_valido_aunque_sql_echo_este_activo():
    _enriquecer(_id("SQL Injection"))
    r = subprocess.run(
        [sys.executable, "scripts/intercambio.py", "exportar", "--que", "enriquecimientos"],
        capture_output=True, text=True, cwd=BACKEND, env={**os.environ, "SQL_ECHO": "true"},
    )
    assert r.returncode == 0, r.stderr
    assert len(json.loads(r.stdout)["items"]) == 1


def test_metricas_agrupan_revisores_por_nombre_normalizado():
    sqli, csp = _id("SQL Injection"), _id("Content Security Policy (CSP) Header Not Set")
    for f in (sqli, csp):
        _enriquecer(f)
    _con_banderas(sqli, revisor="felipe  cayún")
    _con_banderas(csp, revisor=" Felipe Cayún ")
    # La más reciente: reemplaza su primera respuesta en sqli y su nombre es el que se muestra.
    _con_banderas(sqli, revisor="FELIPE CAYÚN", ai_owasp_correcto=False)
    _con_banderas(sqli, revisor="Joaquín")

    with SessionLocal() as db:
        m = metricas(db)

    assert sorted(m["revisores"]) == ["FELIPE CAYÚN", "Joaquín"]
    assert m["revisores"]["FELIPE CAYÚN"]["validaciones"] == 2
    assert m["revisores"]["FELIPE CAYÚN"]["ai_owasp_correcto"] == {"si": 1, "no": 1, "n": 2, "pct": 50.0}
    [par] = m["acuerdo_ai_owasp_correcto"]
    assert par["revisores"] == ["FELIPE CAYÚN", "Joaquín"] and par["n"] == 1
    assert m["hallazgos_con_2_o_mas_revisores"] == 1
