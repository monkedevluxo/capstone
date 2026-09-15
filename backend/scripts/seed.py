"""
SentinelAI · Datos de prueba sintéticos (tarea T-016).

    python scripts/seed.py           # carga
    python scripts/seed.py --reset   # borra lo anterior y recarga

IMPORTANTE: este script NO parsea salidas de ZAP. Eso es el parser (T-019) y
es trabajo del rol de Arquitectura e IA. Acá se generan hallazgos sintéticos
que cumplen el esquema, con un único propósito: poder construir la API y el
dashboard sin depender de que el parser exista todavía.

El objetivo se llama "(datos de prueba)" a propósito, para que nadie confunda
estos números con resultados reales de un escaneo en el informe final.
"""

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AiEnrichment,
    CategoriaOwasp,
    DecisionValidacion,
    EstadoEscaneo,
    EstadoHallazgo,
    EstadoIA,
    Finding,
    FindingInstance,
    FindingObservation,
    Herramienta,
    Prioridad,
    Scan,
    Severidad,
    Target,
    Validation,
)
from app.normalizacion import correlation_key, dedupe_key, path_template  # noqa: E402

BASE_URL = "http://juiceshop:3000"

# (rule_id, título, severidad, cwe, categoría OWASP 2025, prioridad sugerida)
CATALOGO = [
    ("40012", "Cross Site Scripting (Reflected)", Severidad.alta, 79, CategoriaOwasp.a05, Prioridad.p1),
    ("40018", "SQL Injection", Severidad.alta, 89, CategoriaOwasp.a05, Prioridad.p1),
    ("90020", "Remote OS Command Injection", Severidad.alta, 78, CategoriaOwasp.a05, Prioridad.p1),
    ("6", "Path Traversal", Severidad.alta, 22, CategoriaOwasp.a01, Prioridad.p1),
    ("10038", "Content Security Policy (CSP) Header Not Set", Severidad.media, 693, CategoriaOwasp.a02, Prioridad.p2),
    ("10098", "Cross-Domain Misconfiguration", Severidad.media, 264, CategoriaOwasp.a02, Prioridad.p2),
    ("10202", "Absence of Anti-CSRF Tokens", Severidad.media, 352, CategoriaOwasp.a01, Prioridad.p2),
    ("10020", "Missing Anti-clickjacking Header", Severidad.media, 1021, CategoriaOwasp.a02, Prioridad.p3),
    ("10003", "Vulnerable JS Library", Severidad.media, 1395, CategoriaOwasp.a03, Prioridad.p2),
    ("10010", "Cookie No HttpOnly Flag", Severidad.baja, 1004, CategoriaOwasp.a02, Prioridad.p3),
    ("10037", "Server Leaks Information via X-Powered-By Header", Severidad.baja, 200, CategoriaOwasp.a02, Prioridad.p4),
    ("10096", "Timestamp Disclosure - Unix", Severidad.baja, 200, CategoriaOwasp.a02, Prioridad.p4),
    ("10109", "Modern Web Application", Severidad.informativa, None, None, Prioridad.p4),
]

RUTAS = [
    ("/rest/products/search", "q", "GET"),
    ("/rest/products/47/reviews", None, "GET"),
    ("/rest/user/login", "email", "POST"),
    ("/api/Users/", None, "GET"),
    ("/api/Feedbacks/", "comment", "POST"),
    ("/ftp", None, "GET"),
    ("/robots.txt", None, "GET"),
    ("/styles.css", None, "GET"),
    ("/main.js", None, "GET"),
    ("/rest/basket/3", None, "GET"),
]

SEV_TOOL = {
    Severidad.alta: "High",
    Severidad.media: "Medium",
    Severidad.baja: "Low",
    Severidad.informativa: "Informational",
}


def limpiar(db):
    for modelo in (Validation, AiEnrichment, FindingInstance,
                   FindingObservation, Finding, Scan, Target):
        db.execute(delete(modelo))
    db.commit()
    print("Datos anteriores eliminados.")


def sembrar(db, cantidad: int = 40):
    rnd = random.Random(42)   # semilla fija: el seed es reproducible
    ahora = datetime.now(timezone.utc)

    target = Target(
        nombre="OWASP Juice Shop (datos de prueba)",
        base_url=BASE_URL,
        environment="lab",
    )
    db.add(target)
    db.flush()

    escaneos = []
    for i in range(2):
        s = Scan(
            target_id=target.id,
            tool=Herramienta.zap,
            tool_version="2.17.0",
            status=EstadoEscaneo.importado,
            started_at=ahora - timedelta(days=7 - i * 6),
            finished_at=ahora - timedelta(days=7 - i * 6) + timedelta(minutes=9),
            stats={"origen": "seed sintetico"},
        )
        db.add(s)
        escaneos.append(s)
    db.flush()

    # Cada hallazgo es una combinación única de (regla, ruta, parámetro).
    # Pedir más que eso haría girar el bucle para siempre.
    maximo = len(CATALOGO) * len(RUTAS)
    if cantidad > maximo:
        print(f"Aviso: se pidieron {cantidad} pero solo hay {maximo} combinaciones "
              f"únicas posibles. Se cargarán {maximo}.")
        cantidad = maximo

    vistos = set()
    creados = 0
    intentos = 0

    while creados < cantidad:
        intentos += 1
        if intentos > maximo * 50:
            print(f"Corte por seguridad: {creados} hallazgos creados.")
            break

        rule_id, titulo, sev, cwe, owasp, prio = rnd.choice(CATALOGO)
        ruta, param, metodo = rnd.choice(RUTAS)

        url = f"{BASE_URL}{ruta}" + (f"?{param}=test" if param else "")
        plantilla = path_template(url)
        clave = dedupe_key("zap", rule_id, plantilla, param, metodo)

        if clave in vistos:
            continue        # la unicidad (target_id, dedupe_key) lo rechazaría
        vistos.add(clave)

        ocurrencias = rnd.randint(1, 12)

        f = Finding(
            target_id=target.id,
            tool=Herramienta.zap,
            rule_id=rule_id,
            rule_name=titulo,
            source_raw={
                "pluginid": rule_id,
                "alert": titulo,
                "riskcode": {"alta": "3", "media": "2", "baja": "1", "informativa": "0"}[sev.value],
                "confidence": str(rnd.randint(1, 3)),
                "cweid": str(cwe) if cwe else "",
                "_nota": "REGISTRO SINTETICO generado por scripts/seed.py",
            },
            titulo=titulo,
            descripcion=f"Hallazgo sintético de prueba sobre {ruta}.",
            url=url,
            path_template=plantilla,
            method=metodo,
            param=param,
            evidence_snippet=f"<evidencia de prueba para {rule_id}>",
            severity=sev,
            severity_tool_raw=SEV_TOOL[sev],
            tool_confidence=rnd.choice(["low", "medium", "high"]),
            cwe_id=cwe,
            dedupe_key=clave,
            correlation_key=correlation_key(cwe, plantilla, param),
            occurrences=ocurrencias,
            status=EstadoHallazgo.nuevo,
        )
        db.add(f)
        db.flush()

        for k in range(min(ocurrencias, 3)):
            db.add(FindingInstance(
                finding_id=f.id,
                url=f"{url}&i={k}" if param else f"{url}?i={k}",
                method=metodo,
                param=param,
            ))

        for s in escaneos if rnd.random() < 0.6 else escaneos[:1]:
            db.add(FindingObservation(
                finding_id=f.id, scan_id=s.id, instance_count=ocurrencias
            ))

        # ~70% enriquecidos, y de esos ~10% fallidos: así el dashboard tiene
        # que resolver los tres estados desde el primer día.
        if rnd.random() < 0.7:
            fallo = rnd.random() < 0.1
            if fallo:
                e = AiEnrichment(
                    finding_id=f.id,
                    state=EstadoIA.failed,
                    model="llama3.1:8b-instruct-q4_K_M",
                    prompt_version="p-1.2.0",
                    failure_reason="esquema_invalido",
                    attempts=3,
                    is_current=True,
                )
            else:
                e = AiEnrichment(
                    finding_id=f.id,
                    state=EstadoIA.ok,
                    model="llama3.1:8b-instruct-q4_K_M",
                    prompt_version="p-1.2.0",
                    latency_ms=rnd.randint(4000, 15000),
                    explanation=f"Explicación sintética del hallazgo {titulo}.",
                    impact="Impacto sintético para pruebas de interfaz.",
                    owasp_version="2025",
                    owasp_category=owasp,
                    priority=prio,
                    confidence=round(rnd.uniform(0.55, 0.95), 2),
                    remediation_summary="Medida de remediación sintética.",
                    remediation_steps=["Paso uno de prueba.", "Paso dos de prueba."],
                    is_current=True,
                )
            db.add(e)
            db.flush()

            # ~40% de los enriquecidos ya revisados por una persona
            if not fallo and rnd.random() < 0.4:
                decision = rnd.choices(
                    [DecisionValidacion.confirmado, DecisionValidacion.falso_positivo],
                    weights=[0.75, 0.25],
                )[0]
                db.add(Validation(
                    finding_id=f.id,
                    enrichment_id=e.id,
                    decision=decision,
                    reviewer=rnd.choice(["luciano.zambrano", "felipe.cayun", "joaquin.herrera"]),
                    comment="Revisión sintética de prueba.",
                    ai_owasp_correcto=rnd.random() < 0.8,
                    ai_prioridad_correcta=rnd.random() < 0.7,
                    ai_remediacion_util=rnd.random() < 0.75,
                    ai_alucinacion=rnd.random() < 0.1,
                ))
                f.status = (
                    EstadoHallazgo.confirmado
                    if decision == DecisionValidacion.confirmado
                    else EstadoHallazgo.falso_positivo
                )

        creados += 1

    db.commit()
    return creados


def main():
    ap = argparse.ArgumentParser(description="Carga datos de prueba en SentinelAI")
    ap.add_argument("--reset", action="store_true", help="borra los datos existentes")
    ap.add_argument("-n", type=int, default=40, help="cantidad de hallazgos")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            limpiar(db)
        n = sembrar(db, args.n)
        print(f"{n} hallazgos sintéticos cargados.")
        print("Verificar con: curl http://localhost:8000/stats")
    finally:
        db.close()


if __name__ == "__main__":
    main()
