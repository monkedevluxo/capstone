import json, time, urllib.request

MODELO = "llama3.1:8b-instruct-q4_K_M"
HALLAZGO = {
    "titulo": "Cross Site Scripting (Reflected)",
    "url": "http://juiceshop:3000/rest/products/search?q=<script>alert(1)</script>",
    "param": "q",
    "evidencia": "<script>alert(1)</script>",
    "severidad_zap": "High",
    "cwe": 79,
}

PROMPT = f"""Eres un analista de seguridad. Analiza este hallazgo y responde
UNICAMENTE con un objeto JSON, sin texto adicional ni markdown.

Hallazgo: {json.dumps(HALLAZGO, ensure_ascii=False)}

Formato exacto:
{{"explicacion": "...", "owasp": "A05:2025", "prioridad": "p1", "confianza": 0.0}}

La categoria debe ser del OWASP Top 10 EDICION 2025: A01 Broken Access Control,
A02 Security Misconfiguration, A03 Software Supply Chain Failures,
A04 Cryptographic Failures, A05 Injection, A06 Insecure Design,
A07 Authentication Failures, A08 Software or Data Integrity Failures,
A09 Security Logging and Alerting Failures,
A10 Mishandling of Exceptional Conditions."""

cuerpo = json.dumps({
    "model": MODELO,
    "prompt": PROMPT,
    "stream": False,
    "format": "json",
    "options": {"temperature": 0.1},
}).encode()

tiempos, validos = [], 0
for i in range(5):
    t0 = time.perf_counter()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate", data=cuerpo,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        salida = json.loads(r.read())["response"]
    dt = time.perf_counter() - t0
    tiempos.append(dt)
    try:
        d = json.loads(salida)
        ok = d.get("owasp", "").endswith(":2025")
        validos += ok
        print(f"  {i+1}. {dt:6.1f}s  owasp={d.get('owasp')}  prioridad={d.get('prioridad')}")
    except json.JSONDecodeError:
        print(f"  {i+1}. {dt:6.1f}s  JSON INVALIDO")

print(f"\nMediana: {sorted(tiempos)[2]:.1f}s por hallazgo")
print(f"JSON valido con edicion 2025: {validos}/5")
print(f"Proyeccion para 300 hallazgos: {sorted(tiempos)[2]*300/60:.0f} minutos")