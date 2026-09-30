"""
SentinelAI · Prueba del prompt de enriquecimiento (tarea de IA, S4)
 
Qué mide
========
1. Latencia real con los 6 campos del prompt definitivo.
2. Si el JSON trae todos los campos y con el formato esperado.
3. Si la categoría OWASP es la correcta para hallazgos DISTINTOS.
4. Cuántas veces el modelo usa la numeración del Top 10 de 2021.
5. Si la "confianza" del modelo distingue sus aciertos de sus errores.
 
Uso (desde Windows, en la raíz del repo):
    python lab\\prueba_prompt.py              # prompt v2 (por defecto)
    python lab\\prueba_prompt.py --prompt v1  # prompt original, para comparar
 
Mismos hallazgos, mismo criterio y mismas repeticiones para ambas versiones:
lo único que cambia es el prompt. Así la comparación es justa.
 
Solo biblioteca estándar. Guarda el detalle en lab/salidas/ (no se versiona).
"""
 
from __future__ import annotations
 
import argparse
import json
import os
import re
import statistics
import time
import urllib.request
from datetime import datetime
from pathlib import Path
 
MODELO = "llama3.1:8b-instruct-q4_K_M"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
REPETICIONES = 3          # por hallazgo: permite ver si el modelo es consistente
RAIZ = Path(__file__).resolve().parent
FIXTURE = RAIZ / "fixtures" / "zap_juiceshop_baseline_v1.json"
 
CAMPOS = {"explicacion", "impacto", "owasp", "prioridad", "confianza", "remediacion"}
PRIORIDADES = {"p1", "p2", "p3", "p4"}
FORMATO_OWASP = re.compile(r"^A(0[1-9]|10):2025$")
 
# ── Criterio humano ───────────────────────────────────────────────────────
# "aceptadas": categorías 2025 que se consideran correctas (vacío = sin puntuar).
# "trampa_2021": el código que tendría ese concepto en el Top 10 de 2021.
#
# CORS acepta A01 y A02: la guía de OWASP lista "CORS misconfiguration" dentro
# de Broken Access Control, y su CWE (264) es de control de acceso; pero también
# es una configuración del servidor. Ambas son defendibles; A06 no lo es.
CRITERIO = {
    "10038": {"aceptadas": {"A02:2025"},             "trampa_2021": "A05"},  # CSP ausente
    "10098": {"aceptadas": {"A01:2025", "A02:2025"}, "trampa_2021": "A05"},  # CORS permisivo
    "10096": {"aceptadas": set(),                    "trampa_2021": None},   # Timestamp: discutible
    "10109": {"aceptadas": set(),                    "trampa_2021": None},   # Informativo
    "40012": {"aceptadas": {"A05:2025"},             "trampa_2021": "A03"},  # XSS -> Injection
}
 
# ── Prompts ───────────────────────────────────────────────────────────────
 
PROMPT_V1 = """Eres un analista de seguridad web. Analiza el hallazgo y responde
UNICAMENTE con un objeto JSON, sin texto adicional ni markdown. Escribe en español.
 
Reglas:
- Basate SOLO en la evidencia entregada. No afirmes impactos que la evidencia no respalda.
- "owasp" debe ser una categoria del OWASP Top 10 EDICION 2025, con formato "AXX:2025".
- "prioridad": p1 (urgente) | p2 (alta) | p3 (media) | p4 (baja o informativa).
- "confianza": numero entre 0.0 y 1.0 sobre tu propia clasificacion.
- "remediacion": una accion concreta que un desarrollador pueda aplicar.
 
OWASP Top 10:2025
A01 Broken Access Control
A02 Security Misconfiguration
A03 Software Supply Chain Failures
A04 Cryptographic Failures
A05 Injection
A06 Insecure Design
A07 Authentication Failures
A08 Software or Data Integrity Failures
A09 Security Logging and Alerting Failures
A10 Mishandling of Exceptional Conditions
 
Hallazgo:
{hallazgo}
 
Formato exacto:
{{"explicacion": "...", "impacto": "...", "owasp": "AXX:2025", "prioridad": "p1", "confianza": 0.0, "remediacion": "..."}}"""
 
# v2 cambia cuatro cosas respecto de v1 (y nada más):
#   1. Cada categoría trae una descripción con ejemplos, tomados de la
#      descripción oficial de OWASP (no de nuestros hallazgos).
#   2. Aviso explícito de que la numeración cambió respecto de 2021.
#   3. Reglas contra la exageración del impacto (defensa ausente != ataque).
#   4. Guía para prioridad (partir de la severidad de ZAP) y para confianza.
PROMPT_V2 = """Eres un analista de seguridad web. Analiza el hallazgo y responde
UNICAMENTE con un objeto JSON, sin texto adicional ni markdown. Escribe en español.
 
CLASIFICACION OWASP
Usa SOLO el OWASP Top 10 EDICION 2025. La numeracion CAMBIO respecto de 2021:
no uses los codigos de 2021 (por ejemplo, en 2025 A05 ya NO es Security
Misconfiguration: ahora es Injection). Elige la categoria segun la descripcion,
no segun el numero que recuerdes.
 
A01 Broken Access Control: el usuario accede a datos o acciones que no le corresponden;
    rutas sin autorizacion, IDs manipulables, CORS que permite origenes no confiables, SSRF.
A02 Security Misconfiguration: configuracion insegura del servidor o del framework;
    cabeceras de seguridad ausentes, opciones por defecto, mensajes de error detallados,
    servicios o archivos innecesarios expuestos.
A03 Software Supply Chain Failures: dependencias o componentes de terceros vulnerables,
    desactualizados o comprometidos.
A04 Cryptographic Failures: datos sensibles sin cifrar o con cifrado debil; HTTP sin TLS,
    algoritmos obsoletos, claves expuestas.
A05 Injection: datos del usuario interpretados como codigo o consulta; SQL injection,
    XSS, inyeccion de comandos.
A06 Insecure Design: fallas de la logica o del diseño de la aplicacion, no de su
    configuracion ni de su codigo puntual.
A07 Authentication Failures: login, sesiones o contraseñas debiles o mal gestionadas.
A08 Software or Data Integrity Failures: codigo o datos que se aceptan sin verificar
    su integridad; deserializacion insegura, actualizaciones sin firma.
A09 Security Logging and Alerting Failures: ausencia de registros o alertas de eventos
    de seguridad.
A10 Mishandling of Exceptional Conditions: errores y excepciones mal manejados que dejan
    la aplicacion en un estado inseguro.
 
REGLAS
- Basate SOLO en la evidencia entregada. No agregues datos que no esten en el hallazgo.
- "impacto": describe lo que la evidencia permite afirmar. Si el hallazgo es la AUSENCIA
  de una defensa (por ejemplo, una cabecera faltante), dilo asi: no afirmes que hay robo
  de datos, acceso no autorizado o ejecucion de codigo si la evidencia no lo muestra.
- "prioridad": p1 (urgente) | p2 (alta) | p3 (media) | p4 (baja o informativa).
  Parte de la severidad de ZAP: High -> p1 o p2, Medium -> p2 o p3, Low -> p3 o p4,
  Informational -> p4. Cambia de tramo solo si la evidencia lo justifica.
- "confianza": numero entre 0.0 y 1.0 sobre tu clasificacion OWASP. Usa menos de 0.5 si
  el hallazgo es informativo o si podria pertenecer a mas de una categoria.
- "remediacion": una accion concreta y especifica (que cabecera, que parametro, que
  configuracion). Evita frases genericas como "validar la entrada".
 
Hallazgo:
{hallazgo}
 
Formato exacto:
{{"explicacion": "...", "impacto": "...", "owasp": "AXX:2025", "prioridad": "p1", "confianza": 0.0, "remediacion": "..."}}"""
 
PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}
 
 
def _sin_html(texto: str | None, maximo: int = 400) -> str | None:
    if not texto:
        return None
    limpio = re.sub(r"<[^>]+>", " ", texto)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio[:maximo]
 
 
def cargar_hallazgos() -> list[dict]:
    """Toma las alertas reales del fixture y agrega el XSS de la prueba de humo."""
    with open(FIXTURE, encoding="utf-8") as f:
        crudo = json.load(f)
 
    hallazgos = []
    for sitio in crudo.get("site", []):
        for a in sitio.get("alerts", []):
            inst = (a.get("instances") or [{}])[0]
            hallazgos.append({
                "rule_id": a.get("pluginid"),
                "titulo": a.get("alert"),
                "url": inst.get("uri"),
                "param": inst.get("param") or None,
                "evidencia": inst.get("evidence") or None,
                "severidad_zap": (a.get("riskdesc") or "").split(" (")[0] or None,
                "cwe": int(a["cweid"]) if str(a.get("cweid", "")).lstrip("-").isdigit()
                       and int(a["cweid"]) > 0 else None,
                "descripcion": _sin_html(a.get("desc")),
            })
 
    hallazgos.append({
        "rule_id": "40012",
        "titulo": "Cross Site Scripting (Reflected)",
        "url": "http://juiceshop:3000/rest/products/search?q=<script>alert(1)</script>",
        "param": "q",
        "evidencia": "<script>alert(1)</script>",
        "severidad_zap": "High",
        "cwe": 79,
        "descripcion": None,
    })
    return hallazgos
 
 
def consultar(hallazgo: dict, plantilla: str) -> tuple[float, str]:
    datos = {k: v for k, v in hallazgo.items() if k != "rule_id"}
    cuerpo = json.dumps({
        "model": MODELO,
        "prompt": plantilla.format(hallazgo=json.dumps(datos, ensure_ascii=False)),
        "stream": False,
        "format": "json",
        "keep_alive": "10m",           # evita el arranque en frio entre llamadas
        "options": {"temperature": 0.1},
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=cuerpo,
        headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as r:
        salida = json.loads(r.read())["response"]
    return time.perf_counter() - t0, salida
 
 
def evaluar(salida: str, criterio: dict) -> dict:
    """Valida una respuesta. No corrige nada: solo describe lo que llegó."""
    r = {"json_valido": False, "campos_ok": False, "formato_owasp_ok": False,
         "prioridad_ok": False, "confianza_ok": False, "confianza": None,
         "owasp": None, "acierto": None, "numeracion_2021": False}
    try:
        d = json.loads(salida)
    except json.JSONDecodeError:
        return r
    if not isinstance(d, dict):
        return r
 
    r["json_valido"] = True
    r["campos_ok"] = CAMPOS <= set(d)
    owasp = str(d.get("owasp", "")).strip()
    r["owasp"] = owasp
    r["formato_owasp_ok"] = bool(FORMATO_OWASP.match(owasp))
    r["prioridad_ok"] = str(d.get("prioridad", "")).lower() in PRIORIDADES
    try:
        conf = float(d.get("confianza"))
        r["confianza"] = conf
        r["confianza_ok"] = 0.0 <= conf <= 1.0
    except (TypeError, ValueError):
        pass
 
    codigo = owasp.split(":")[0]
    if owasp.endswith(":2021"):
        r["numeracion_2021"] = True
    elif criterio.get("trampa_2021") and codigo == criterio["trampa_2021"] \
            and owasp not in criterio["aceptadas"]:
        r["numeracion_2021"] = True
    if criterio["aceptadas"]:
        r["acierto"] = owasp in criterio["aceptadas"]
    return r
 
 
def _promedio(valores: list[float]) -> str:
    return f"{statistics.mean(valores):.2f}" if valores else "  - "
 
 
def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba del prompt de SentinelAI")
    parser.add_argument("--prompt", choices=PROMPTS, default="v2")
    version = parser.parse_args().prompt
    plantilla = PROMPTS[version]
 
    hallazgos = cargar_hallazgos()
    print(f"Modelo: {MODELO}  ·  prompt {version}  ·  "
          f"{len(hallazgos)} hallazgos x {REPETICIONES} repeticiones\n")
 
    # Calentamiento: carga el modelo en la GPU para no contaminar la mediana.
    print("Calentando el modelo...", end=" ", flush=True)
    t_frio, _ = consultar(hallazgos[0], plantilla)
    print(f"{t_frio:.1f}s\n")
 
    registros, tiempos = [], []
    for h in hallazgos:
        criterio = CRITERIO.get(h["rule_id"], {"aceptadas": set(), "trampa_2021": None})
        esperado = " o ".join(sorted(criterio["aceptadas"])) or "sin puntuar"
        print(f"── {h['titulo']}  (esperado: {esperado})")
        for i in range(REPETICIONES):
            dt, salida = consultar(h, plantilla)
            tiempos.append(dt)
            ev = evaluar(salida, criterio)
            marca = {True: "OK ", False: "MAL", None: " · "}[ev["acierto"]]
            aviso = "  <- posible numeracion 2021" if ev["numeracion_2021"] else ""
            faltan = "" if ev["campos_ok"] else "  <- faltan campos"
            print(f"   {i+1}. {dt:5.1f}s  {marca} owasp={ev['owasp']}  "
                  f"conf={ev['confianza']}{aviso}{faltan}")
            registros.append({"rule_id": h["rule_id"], "titulo": h["titulo"],
                              "intento": i + 1, "segundos": round(dt, 2),
                              "aceptadas": sorted(criterio["aceptadas"]), **ev,
                              "respuesta": salida})
        print()
 
    # ── Resumen ──
    total = len(registros)
    puntuables = [r for r in registros if r["acierto"] is not None]
    def contar(clave): return sum(1 for r in registros if r[clave])
    conf_ok = [r["confianza"] for r in puntuables if r["acierto"] and r["confianza_ok"]]
    conf_mal = [r["confianza"] for r in puntuables if not r["acierto"] and r["confianza_ok"]]
 
    mediana = statistics.median(tiempos)
    print("=" * 60)
    print(f"Prompt:                      {version}")
    print(f"Arranque en frio:            {t_frio:.1f}s")
    print(f"Mediana por hallazgo:        {mediana:.1f}s   (min {min(tiempos):.1f}, max {max(tiempos):.1f})")
    print(f"Proyeccion 300 hallazgos:    {mediana * 300 / 60:.0f} minutos")
    print(f"JSON valido:                 {contar('json_valido')}/{total}")
    print(f"Con los 6 campos:            {contar('campos_ok')}/{total}")
    print(f"Formato AXX:2025:            {contar('formato_owasp_ok')}/{total}")
    print(f"Prioridad valida (p1-p4):    {contar('prioridad_ok')}/{total}")
    print(f"Confianza en [0,1]:          {contar('confianza_ok')}/{total}")
    print(f"Acierto OWASP:               {sum(r['acierto'] for r in puntuables)}/{len(puntuables)}"
          "   (solo hallazgos con criterio definido)")
    print(f"Posible numeracion 2021:     {contar('numeracion_2021')}/{total}")
    print(f"Confianza media si acierta:  {_promedio(conf_ok)}   (n={len(conf_ok)})")
    print(f"Confianza media si falla:    {_promedio(conf_mal)}   (n={len(conf_mal)})")
 
    salidas = RAIZ / "salidas"
    salidas.mkdir(exist_ok=True)
    archivo = salidas / f"prueba_prompt_{version}_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(archivo, "w", encoding="utf-8") as f:
        json.dump({"modelo": MODELO, "prompt_version": version,
                   "fecha": datetime.now().isoformat(),
                   "arranque_frio_s": round(t_frio, 2), "mediana_s": round(mediana, 2),
                   "registros": registros}, f, ensure_ascii=False, indent=2)
    print(f"\nDetalle completo (con las respuestas del modelo): {archivo}")
 
 
if __name__ == "__main__":
    main()