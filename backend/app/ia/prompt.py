"""
SentinelAI · Prompt de enriquecimiento (tarea T-029).

Es el prompt "v2" medido en lab/prueba_prompt.py (13/18 de acierto OWASP en
dos corridas, contra 7/18 de la v1). Si se cambia una sola palabra, se cambia
PROMPT_VERSION: cada fila de ai_enrichments guarda la versión y el hash del
prompt, y sin eso no se puede demostrar qué versión produjo qué resultado.
"""

from __future__ import annotations

import json
import re

PROMPT_VERSION = "v2"

PLANTILLA = """Eres un analista de seguridad web. Analiza el hallazgo y responde
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

# Se agrega al final del prompt cuando la respuesta anterior no pasó la validación.
REPARACION = """

Tu respuesta anterior NO es valida por estos motivos:
{errores}
Responde de nuevo con el objeto JSON completo y corregido, con los seis campos."""


def _sin_html(texto: str | None, maximo: int = 400) -> str | None:
    if not texto:
        return None
    limpio = re.sub(r"<[^>]+>", " ", texto)
    limpio = re.sub(r"\s+", " ", limpio).strip()
    return limpio[:maximo] or None


def datos_para_el_modelo(hallazgo: dict) -> dict:
    """
    Arma lo que ve el modelo a partir de un hallazgo normalizado por el parser.

    Solo pasa evidencia. Nada de IDs internos, claves de deduplicación ni
    campos que el modelo no necesita: menos ruido, menos alucinación.
    """
    return {
        "titulo": hallazgo.get("titulo"),
        "url": hallazgo.get("url"),
        "param": hallazgo.get("param"),
        "evidencia": hallazgo.get("evidence_snippet"),
        "severidad_zap": hallazgo.get("severity_tool_raw"),
        "cwe": hallazgo.get("cwe_id"),
        "descripcion": _sin_html(hallazgo.get("descripcion")),
    }


def construir_prompt(hallazgo: dict) -> str:
    datos = json.dumps(datos_para_el_modelo(hallazgo), ensure_ascii=False)
    return PLANTILLA.format(hallazgo=datos)


def construir_reparacion(prompt_base: str, errores: list[str]) -> str:
    lista = "\n".join(f"- {e}" for e in errores)
    return prompt_base + REPARACION.format(errores=lista)
