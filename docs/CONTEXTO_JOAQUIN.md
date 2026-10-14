# Contexto y aprendizajes · Joaquín

Resumen de lo trabajado en mi parte de SentinelAI (Arquitectura, IA y Parser), para retomar rápido o ponerle contexto a otra persona (o a otra IA). **Actualizado:** 04-10-2026.

---

## 1. Dónde estoy parado

**Mi parte en una línea:** convertir la salida de ZAP a un formato común (el **parser**) y lograr que un modelo local explique y clasifique cada hallazgo de forma **validada** (la **IA**).

**Mi entorno:** Windows + VS Code + Python 3.12 en `backend\.venv`. WSL2 (Ubuntu 26.04, 8 GB) con Docker Engine 29.9 desde el 14-10-2026. Repo en `C:\Proyectotitulo\capstone`, rama `joaquin/parser-zap`. Ollama instalado en Windows, con una RTX 3060 Ti de 8 GB.

| Hecho | Archivo |
|---|---|
| Parser de ZAP, 25/25 tests | `backend/app/parsers/zap.py` |
| Ollama en GPU, latencia medida | `docs/evidencias/latencia_ollama.md` |
| Prompt v1 y v2 medidos (7/18 → 13/18) | `lab/prueba_prompt.py`, `docs/evidencias/respuestas_modelo/` |
| Cliente Ollama, validación y reintentos | `backend/app/ia/` + `tests/test_enriquecer.py` |
| Decisión de modelo y prompt documentada | `docs/diseno/IA_MODELO_Y_PROMPT.md` |
| Comandos de referencia | `docs/guias/COMANDOS_JOAQUIN.md` |

**Avance estimado de mi parte:** sobre el 70% de los días de la planilla, con el S4 casi cerrado. Voy alrededor de un sprint adelantado respecto del calendario.

---

## 2. Decisiones tomadas (y por qué)

- **`""` de ZAP se guarda como `None`** (regla 4: nunca inventar). No cambia la `dedupe_key`, porque el hash trata `None` como `""`.
- **`severity_tool_raw` sale de `riskcode`**, porque `riskdesc` no siempre viene.
- **Modelo `llama3.1:8b-instruct-q4_K_M`**: cabe 100% en la GPU y responde en unos 2 s por hallazgo, así que se enriquece todo.
- **Prompt v2 como vigente.** No lo seguimos afinando para llegar a 9/9: con 3 casos sería sobreajuste, no mejora.
- **Sin RAG ni embeddings.** El hallazgo cabe completo en el prompt, y para clasificar existe una clave exacta (el CWE), que es más confiable que una búsqueda semántica.
- **Pendiente con el grupo:** quién asigna la categoría OWASP. A: el modelo. B: una tabla por CWE. O una mezcla.

---

## 3. Lo que aprendí

**Ingeniería**

- **Los tests son la especificación.** Se avanza de a una función, corriendo un test a la vez (`::nombre_test` o `-k palabra`).
- **Normalizar antes de deduplicar.** `/rest/products/1` y `/rest/products/47` son el mismo problema. `path_template()` los convierte en `/rest/products/{id}`.
- **La evidencia original no se toca** (`source_raw`). Es la respuesta a "¿cómo saben que la IA no alteró el hallazgo?".
- **Un fallo se marca, no se rellena.** Si el modelo no entrega algo válido, el hallazgo queda "sin enriquecer".

**Ollama y modelos locales**

- Ollama es un **servidor HTTP** en el puerto 11434. Con `OLLAMA_HOST=0.0.0.0` acepta conexiones desde WSL y Docker, no solo desde Windows. Eso también lo expone en la red local, por eso el firewall va con `-Profile Private`.
- `8b` = 8 mil millones de parámetros, `q4` = comprimido a 4 bits, lo que permite que quepa en 8 GB de VRAM. `ollama ps` debe decir `100% GPU`.
- **Arranque en frío:** la primera llamada tarda unos 15 s porque carga el modelo. Se evita con `keep_alive`.
- `format: json` garantiza que sea JSON, **no** que el contenido sea correcto. Por eso se valida con Pydantic.
- `temperature 0.1` reduce la variación, pero no la elimina: los resultados cambiaron ±1 de 9 entre corridas. `seed` la elimina, y eso sirve para demos pero no para medir.

**Medir una IA**

- **Siempre con el denominador.** Decir "13 de 18" es honesto; decir "72%" a secas no lo es.
- **Una corrida no prueba nada.** Hay que repetir y mirar el rango.
- **El modelo arrastra lo que aprendió:** clasifica con la numeración de OWASP 2021 aunque le digas explícitamente que no lo haga.
- **La "confianza" que reporta el modelo no está calibrada.** Da lo mismo cuando acierta que cuando falla.
- **Las alucinaciones son sutiles:** exagerar un impacto o ubicar mal un dato. Por eso existe la validación humana, que es la tesis del proyecto.

---

## 4. Próximos pasos (checklist de `README_JOAQUIN.md`)

1. ~~Que un contenedor alcance a Ollama~~ ✅ (14-10-2026): WSL2 + Docker Engine instalados; un contenedor llega a Ollama en `http://172.31.32.1:11434` y uno en red `--internal` no llega. Evidencia: `docs/evidencias/contenedor_ollama.md`.
2. ~~Probar el enriquecimiento real~~ ✅: 8/8 en `ajax_v1` y 26/26 en `ajax_v2`. Evidencia: `docs/evidencias/enriquecimiento_ajax_v2.md`.
3. **PR del módulo `app/ia`** (rama `joaquin/ia-enriquecimiento`), con Luciano de revisor. Él lo conecta en `POST /findings/{id}/enrich` (T-032).
4. **Cerrar con el grupo la decisión A/B/mixta.**
5. ~~Probar con `ajax_v2`~~ ✅: el parser normaliza 13 hallazgos sin claves repetidas.
6. **S5:** medir el tiempo de enriquecer un escaneo completo (T-039). **S6:** script que compare contra el golden set (T-045).
