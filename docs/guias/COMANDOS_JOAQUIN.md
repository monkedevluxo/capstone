# Comandos · Rol de Joaquín (Arquitectura, IA y Parser)

Referencia rápida de los comandos de mi parte del proyecto, agrupados por dónde se corren.

- La **terminal de VS Code** (`Ctrl+ñ`) es PowerShell integrado al editor.
- **CMD no se usa** en esta parte.
- **Ubuntu (WSL)** solo se necesita para conectar Ollama con Docker (sección 6).

---

## 1 · Terminal de VS Code (PowerShell) · carpeta `backend`

**Para qué:** el parser de ZAP y sus tests.

```powershell
cd C:\Proyectotitulo\capstone\backend

# Permite activar el entorno virtual (solo afecta a esta ventana)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activa el entorno virtual: debe aparecer (.venv) al inicio de la línea
.\.venv\Scripts\Activate.ps1

# Los 25 tests del parser
python -m pytest tests/test_zap_parser.py -v

# Un solo test, o varios filtrados por palabra
python -m pytest tests/test_zap_parser.py::test_a_entero_convierte -v
python -m pytest tests/test_zap_parser.py -k extraer_instancias -v

# Correr el parser contra los escaneos reales
python -m app.parsers.zap ..\lab\fixtures\zap_juiceshop_baseline_v1.json
python -m app.parsers.zap ..\lab\fixtures\zap_juiceshop_ajax_v1.json
```

**Resultado esperado:** `25 passed`, y en los fixtures `claves únicas: N de N hallazgos`.

---

## 2 · Terminal de VS Code (PowerShell) · raíz del repo

**Para qué:** experimentos con el modelo. Requiere Ollama corriendo.

```powershell
cd C:\Proyectotitulo\capstone

python lab\prueba_humo.py               # latencia rápida (5 llamadas, 4 campos)
python lab\prueba_prompt.py --prompt v1 # prompt original, 6 campos
python lab\prueba_prompt.py --prompt v2 # prompt mejorado, 6 campos
```

El detalle con todas las respuestas del modelo queda en `lab\salidas\` (no se versiona).

---

## 3 · Git · terminal de VS Code (PowerShell)

```powershell
cd C:\Proyectotitulo\capstone

git status                        # qué cambió y en qué rama estoy
git checkout joaquin/parser-zap   # cambiarme a mi rama
git pull origin main              # traer lo nuevo del equipo

git add backend/app/parsers/zap.py lab/prueba_prompt.py docs/evidencias/
git commit -m "feat: parser de ZAP y pruebas del prompt"
git push -u origin joaquin/parser-zap   # el -u solo la primera vez
```

- Formato de commit: `tipo: descripción` con `feat`, `fix`, `docs`, `test`, `lab` o `chore`.
- Nada entra a `main` directo: el Pull Request se abre en GitHub, con al menos un revisor.
- Correr los tests antes de cada push.

---

## 4 · PowerShell normal (fuera de VS Code) · Ollama y GPU

**Para qué:** revisar y administrar el nodo de inferencia. Se corre desde cualquier carpeta.

```powershell
# Estado
ollama ps                                   # modelos cargados: debe decir 100% GPU
ollama list                                 # modelos descargados
curl.exe http://localhost:11434/api/tags    # ¿responde el servidor?
nvidia-smi                                  # uso de la GPU

# Modelo
ollama pull llama3.1:8b-instruct-q4_K_M     # descargar
ollama run llama3.1:8b-instruct-q4_K_M "responde solo: ok"   # prueba manual

# Red
$env:OLLAMA_HOST                            # debe mostrar 0.0.0.0:11434
netstat -ano | findstr 11434                # debe mostrar 0.0.0.0:11434 LISTENING

# Variable de entorno (solo una vez; después hay que cerrar sesión de Windows)
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
```

**Notas:**
- Usar `curl.exe` y no `curl`: en PowerShell, `curl` es otro comando.
- Ollama descarga el modelo de la GPU tras 5 minutos sin uso. La primera llamada después de eso tarda unos 15 s (arranque en frío).
- Si `ollama ps` no muestra `100% GPU`, cerrar programas que usen la tarjeta (navegador, Discord, juegos).

---

## 5 · PowerShell **como administrador**

**Para qué:** abrir el puerto de Ollama en el firewall, solo si WSL o Docker no lo alcanzan. Se hace una vez.

```powershell
New-NetFirewallRule -DisplayName "Ollama SentinelAI" -Direction Inbound `
  -LocalPort 11434 -Protocol TCP -Action Allow -Profile Private
```

`-Profile Private` es importante: bloquea el puerto en redes públicas (wifi de Duoc, cafés). Con `OLLAMA_HOST=0.0.0.0`, sin esa protección cualquiera en la misma red podría usar el modelo.

---

## 6 · Ubuntu (WSL) · pendiente

**Para qué:** que el backend en Docker llegue a Ollama.

```bash
cd ~/capstone
docker compose up -d db api                    # levantar base de datos y API
docker compose ps                              # ver qué está corriendo

ip route show | grep default | awk '{print $3}'   # IP de Windows vista desde WSL
curl http://<ESA_IP>:11434/api/tags               # ¿WSL llega a Ollama?
```

**Pendientes:**
- `host.docker.internal` no apunta a Windows con Docker Engine en WSL2. Hay que poner `OLLAMA_URL=http://<ESA_IP>:11434` en el `.env` de la raíz del repo.
- Esa IP cambia al reiniciar WSL. Alternativa estable: `networkingMode=mirrored` en `.wslconfig` (ver `GUIA_INSTALACION.md`).
- Mi repo está en `C:\Proyectotitulo`, pero la guía del equipo lo pone en `~/capstone` dentro de Ubuntu. Para el parser y Ollama da igual; para Docker, revisarlo antes.
