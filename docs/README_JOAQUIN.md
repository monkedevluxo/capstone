# SentinelAI · Rol de Joaquín

**Arquitectura, IA y Parser**

---

## Contexto en 60 segundos

SentinelAI toma los resultados de un escáner de seguridad (OWASP ZAP), los ordena en un formato común, se los pasa a un modelo de lenguaje que corre localmente para que los explique y priorice, y los muestra en un dashboard donde una persona valida.

El flujo completo: **escaneo → normalización → IA → validación humana → informe**.

Tu rol cubre dos piezas: **el parser** (convierte la salida de ZAP al formato común) y **la IA** (el nodo de inferencia y el prompt). Son las dos piezas que están entre lo que produce Felipe y lo que consume Luciano.

**Para instalar todo:** `docs/guias/GUIA_INSTALACION.md`. Está escrita para Windows 11 y tiene una sección específica para ti, incluida la parte de Ollama.

**Lee también:** `docs/diseno/ESQUEMA_HALLAZGO.md`. Es el contrato de datos de todo el proyecto y sin él nada de lo que sigue tiene sentido. Son 15 minutos.

---

## Lo que tienes que entregar en las próximas 2 semanas

Hay presentación con MVP funcional. Dos cosas, en este orden:

| Prioridad | Qué | Por qué importa |
|---|---|---|
| **1** | Parser de ZAP funcionando | Sin esto no hay datos reales en el sistema. Bloquea a Luciano. |
| **2** | Ollama devolviendo JSON válido | Es la parte que hace que el proyecto se llame SentinelAI y no "un dashboard de ZAP". |

Lo demás (iteración del prompt, métricas, reintentos) viene después de la presentación.

---

# Parte 1 · El parser

## Qué hace

Recibe el JSON que escupe ZAP y devuelve una lista de hallazgos con campos uniformes. Luciano toma esa lista y la guarda en la base. Tú no tocas la base de datos: solo transformas datos.

## Empezar

```bash
cd ~/capstone
git checkout -b joaquin/parser-zap
cd backend
pip install pytest
python -m pytest tests/test_zap_parser.py -v
```

Vas a ver **25 tests fallando**. Eso es correcto: los tests son la especificación, y pasan cuando el parser esté listo.

## Los archivos

| Archivo | Qué es |
|---|---|
| `app/parsers/zap.py` | Lo que tienes que escribir. Tiene 4 funciones con `NotImplementedError`. |
| `tests/test_zap_parser.py` | La especificación. No lo modifiques. |
| `app/normalizacion.py` | Funciones ya hechas y probadas. Úsalas, no las reescribas. |
| `lab/fixtures/` | Escaneos reales de Juice Shop, para probar al final. |

## Cómo trabajar

Ve de a una función, en este orden: `_a_entero` → `_extraer_instancias` → `parsear_alerta` → `parsear_reporte`.

```bash
python -m pytest tests/test_zap_parser.py::test_a_entero_convierte -v
```

Cuando pasen los 25:

```bash
python -m app.parsers.zap ../lab/fixtures/zap_juiceshop_full_v1.json
```

Debe imprimir el conteo de hallazgos por severidad y confirmar que no hay claves repetidas.

Felipe va a subir un fixture nuevo con Ajax Spider, que trae más variedad. Prueba con los dos.

## Las cinco reglas que no se negocian

**1. `source_raw` va tal cual viene de ZAP.** No recortes, no corrijas, no traduzcas. Es la evidencia original que respalda todo el proyecto, y en la defensa es la respuesta a *"¿cómo saben que la IA no alteró el hallazgo?"*.

**2. `cwe_id` es entero o `None`.** ZAP lo entrega como string y a veces vacío. Si guardas `"79"` en vez de `79`, la correlación entre herramientas deja de funcionar y nadie se da cuenta hasta el S7.

**3. Una alerta con N instancias es UN hallazgo con `occurrences=N`.** No N hallazgos. Ese es exactamente el ruido que el proyecto existe para eliminar.

**4. Nunca inventes un campo.** Si ZAP no lo trae, va `None`. Un campo rellenado "para que se vea completo" es un dato falso en el informe final.

**5. Usa `app/normalizacion.py` para las claves.** Ya está probado. Si reimplementas el hash y te queda distinto, la deduplicación de Luciano deja de funcionar.

## El detalle que más cuesta

ZAP reporta `/rest/products/1`, `/rest/products/2`, `/rest/products/47`… como URLs distintas. Sin normalizar, un solo problema aparece cuarenta veces.

`path_template()` lo resuelve: convierte todas esas en `/rest/products/{id}`. Por eso la clave de deduplicación se calcula sobre la plantilla, no sobre la URL.

---

# Parte 2 · El nodo de inferencia

## Por qué en tu PC

Tienes 8 GB de VRAM. En el notebook de Luciano, sin GPU dedicada, la inferencia por CPU son 40-60 segundos por hallazgo. En el tuyo debería ser 5-10. Tu PC queda como nodo de inferencia y el suyo solo desarrolla.

Con 8 GB entra cómodo un modelo de 8B cuantizado, que ocupa unos 5 GB:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama run llama3.1:8b-instruct-q4_K_M "responde solo: ok"
```

Mientras responde, abre otra ventana y corre `nvidia-smi`. Debe aparecer `ollama` usando memoria de GPU. Si no aparece, está calculando por CPU y hay que revisar los drivers.

**El paso a paso completo de instalación y configuración está en `docs/guias/GUIA_INSTALACION.md`, sección "Joaquín · Ollama".**

## Dos cosas que te van a morder

**`OLLAMA_HOST` debe ser `0.0.0.0:11434`**, como variable de entorno de Windows, y hay que cerrar sesión para que aplique. Sin eso, Ollama escucha solo en localhost y el backend no lo alcanza. El error que da no explica nada.

**`host.docker.internal` no funciona con Docker Engine.** Esto es distinto a lo que dice `ADDENDUM_OLLAMA_REMOTO.md`, que asume Docker Desktop. Con Docker Engine en WSL2 hay que encontrar la IP del host:

```bash
ip route show | grep default | awk '{print $3}'
```

Esa IP cambia cuando reinicias WSL. La guía de instalación tiene el detalle y una alternativa más estable.

## Medir la latencia

Este número define la arquitectura del proyecto. Guárdalo como `lab/prueba_humo.py` y córrelo **desde Windows**:

```python
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
```

| Mediana | Qué significa |
|---|---|
| Menos de 15 s | Cómodo, seguimos con el plan |
| 15 a 40 s | Viable con enriquecimiento por lotes |
| Más de 40 s | Modelo más chico, o enriquecer solo severidad alta |

Con 8 GB de VRAM deberías estar en el primer tramo. Si no, algo pasa con los drivers.

## El prompt

Requisitos mínimos para la presentación:

- Salida **solo JSON**. Usa `"format": "json"` en la llamada, ayuda bastante.
- Campos: `explicacion`, `impacto`, `owasp`, `prioridad`, `confianza`, `remediacion`
- `temperature: 0.1` — no queremos creatividad acá

## El problema que vas a tener

**El modelo va a clasificar con el OWASP Top 10 de 2021**, no con el de 2025. Su entrenamiento es mayormente anterior.

La edición vigente es **Top 10:2025**. Cambios: dos categorías nuevas (Software Supply Chain Failures en A03, Mishandling of Exceptional Conditions en A10), Security Misconfiguration subió a A02, y SSRF dejó de ser categoría propia — ahora está dentro de Broken Access Control.

Dos cosas:

1. **Pon la lista de 2025 explícita en el prompt.** Las diez categorías con su ID.
2. **Cuenta cuántas veces responde con categorías de 2021 igual.** Ese número es material directo para la sección de resultados del informe: es evidencia medida de por qué hace falta validar la salida del modelo.

---

## Coordinación con el equipo

**Con Luciano:** él consume tu lista de diccionarios. El contrato está escrito en el docstring de `app/parsers/zap.py` y verificado por los tests. Mientras respetes esas claves, pueden trabajar en paralelo sin bloquearse. Si necesitas cambiar el contrato, avísale **antes**, no después.

**Con Felipe:** él ejecuta los escaneos y sube los fixtures. Va a probar el Ajax Spider en su equipo, que tiene más RAM, y eso debería traer más variedad de hallazgos. Si el JSON que te llega tiene una forma que el parser no maneja, díselo.

---

## Convenciones

```bash
git checkout -b joaquin/parser-zap
git commit -m "feat: parser de ZAP a esquema normalizado"
```

Tipos de commit: `feat`, `fix`, `docs`, `test`, `chore`. Nada entra a `main` directo, todo por pull request con al menos un revisor.

Corre los tests antes de cada push.

---

## Checklist

**Parser**
- [ ] Entorno instalado según `docs/guias/GUIA_INSTALACION.md`
- [ ] Los 25 tests pasan
- [ ] Corre contra el fixture real sin errores
- [ ] No hay claves de deduplicación repetidas
- [ ] Los conteos por severidad tienen sentido

**IA**
- [ ] `OLLAMA_HOST` configurado y sesión reiniciada
- [ ] `nvidia-smi` confirma que usa la GPU
- [ ] Un contenedor alcanza Ollama por la IP del host
- [ ] Latencia mediana medida y anotada
- [ ] Prompt devolviendo JSON válido con categorías 2025
- [ ] Contadas las respuestas que vinieron con categorías 2021

---

Si algo del esquema no calza con lo que ves en el JSON real de ZAP, dilo en el grupo antes de improvisar una solución. El esquema se puede cambiar; lo que no se puede es que cada uno asuma algo distinto.
