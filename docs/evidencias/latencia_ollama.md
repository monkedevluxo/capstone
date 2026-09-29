# Evidencia · Latencia del nodo de inferencia

**Responsable:** Joaquín Herrera · **Fecha:** 28-09-2026 · **Script:** `lab/prueba_humo.py`

## Entorno

| Elemento | Valor |
|---|---|
| GPU | NVIDIA GeForce RTX 3060 Ti · 8 GB VRAM · driver 32.0.16.1692 |
| Ollama | Instalado en Windows, `OLLAMA_HOST=0.0.0.0:11434` |
| Modelo | `llama3.1:8b-instruct-q4_K_M` (4.9 GB en disco, 5.3 GB cargado) |
| Ejecución | `100% GPU` según `ollama ps` · contexto 4096 tokens |
| Parámetros | `format: json` · `temperature: 0.1` · `stream: false` |

## Resultado

| Intento | Tiempo | OWASP | Prioridad |
|---|---|---|---|
| 1 | 14.0 s | A05:2025 | p1 |
| 2 | 1.0 s | A05:2025 | p1 |
| 3 | 1.1 s | A05:2025 | p1 |
| 4 | 1.0 s | A05:2025 | p1 |
| 5 | 1.1 s | A05:2025 | p1 |

- **Mediana:** 1.1 s por hallazgo
- **Arranque en frío:** 14.0 s (intento 1, carga del modelo en la GPU)
- **JSON válido con edición 2025:** 5/5
- **Proyección para 300 hallazgos:** ~5 minutos

**Decisión:** mediana bajo 15 s → tramo "cómodo". Se mantiene el plan de enriquecer todos los hallazgos, sin lotes ni filtro por severidad.

## Limitaciones de esta medición

1. **Prompt reducido:** pide 4 campos cortos. El prompt definitivo pide 6 (`impacto` y `remediacion` son textos más largos), por lo que se espera una latencia mayor. Se mide en `lab/prueba_prompt.py`.
2. **Un solo hallazgo repetido 5 veces** con temperatura 0.1: mide velocidad, no calidad de clasificación.
3. **La validación solo revisa el sufijo `:2025`**, no que la categoría sea correcta. Un código de 2021 con sufijo 2025 (p. ej. `A05:2025` para una cabecera faltante, que en 2021 era A05 Security Misconfiguration) pasaría como válido.
4. **Arranque en frío:** Ollama descarga el modelo tras 5 minutos sin uso. El backend deberá usar `keep_alive` para evitar los 14 s en la primera llamada de cada lote.

## Observación cualitativa

En la prueba manual `ollama run ... "responde solo: ok"`, el modelo respondió "¿En qué puedo ayudarte?" en dos intentos: **no siguió una instrucción directa**. Es evidencia de por qué la salida del modelo se fuerza con `format: json` y se valida siempre.
