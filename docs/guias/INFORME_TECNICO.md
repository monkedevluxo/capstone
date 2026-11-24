# Informe técnico exportable

**Tareas:** T-058 y T-059 · **Responsable:** Felipe Cayún

El informe técnico reúne, para un objetivo, todo lo que el sistema sabe de sus hallazgos: la evidencia original del escáner, la sugerencia de la IA y la decisión humana. Se genera como una página HTML autocontenida (sin dependencias externas), lista para abrir en el navegador o guardar como PDF, y se exporta también a Excel (XLSX) y CSV.

## Cómo generarlo

### Desde el dashboard

En `http://127.0.0.1:3000`, el módulo **Informe** de la barra lateral muestra una vista previa del informe del objetivo con más hallazgos (o del que indique `?objetivo=<base_url>`). Si todavía no hay escaneos importados, la pantalla lo dice.

El botón **Exportar informe** despliega tres formatos:

| Formato | Cómo se genera | Contenido |
|---|---|---|
| PDF | Abre el diálogo de impresión del navegador sobre la vista previa → Guardar como PDF | El informe completo, con la hoja de estilos de impresión |
| Excel (XLSX) | Lo genera la API (`GET /informe.xlsx`) y se descarga | Tres hojas: Resumen (indicadores y calidad de la IA), Hallazgos (una fila por hallazgo, con filtros) y Escaneos (con el SHA-256 de cada reporte) |
| CSV | Lo genera la API (`GET /informe.csv`) y se descarga | Un hallazgo por fila, con las mismas columnas de la hoja Hallazgos. UTF-8 con BOM, separado por comas |

El PDF no se genera en el servidor a propósito: el HTML ya está diseñado para imprimirse y así no se agregan librerías de sistema a la imagen de la API. **Abrir en otra pestaña** muestra el HTML solo, como antes.

Por debajo, el dashboard pide la página y los archivos a la API (`GET /informe`, `/informe.xlsx` y `/informe.csv`, con `?objetivo=<base_url>` opcional) desde su servidor, igual que el resto de los datos: el navegador no habla con la API directo.

### Desde la terminal

Desde la raíz del repositorio, con el laboratorio arriba (`docker compose up -d`):

```bash
# Ver qué objetivos hay en la base
docker compose exec -T api python scripts/informe.py --listar

# Generar el informe del objetivo con más hallazgos
docker compose exec -T api python scripts/informe.py > informe.html

# O de un objetivo en particular
docker compose exec -T api python scripts/informe.py --objetivo http://juiceshop:3000 > informe.html
```

Para PDF: abrir `informe.html` en el navegador → Imprimir (Ctrl + P) → Guardar como PDF.

El HTML sale por la salida estándar y los avisos por la salida de errores, así que la redirección `>` deja solo el informe en el archivo. **El informe no se versiona**: se genera cuando se necesita, a partir de la base.

## Qué contiene

| Sección | Contenido |
|---|---|
| 1. Resumen | Hallazgos vigentes y descartados, conteos por severidad, prioridad y estado |
| 2. Escaneos de origen | Herramienta, versión, fecha y SHA-256 de cada reporte importado |
| 3. Hallazgos | Una ficha por hallazgo vigente, ordenada por prioridad y severidad |
| 4. Descartados | Falsos positivos y duplicados, con quién los descartó |
| 5. Calidad de la IA | Las métricas del golden set, con su denominador |

Cada ficha de hallazgo tiene tres capas separadas:

1. **Evidencia original (ZAP):** ubicación, fragmento, descripción, solución propuesta e instancias, tal como los entregó la herramienta (T-059).
2. **Sugerencia de la IA:** explicación, impacto, categoría, prioridad y remediación, con el modelo, la versión del prompt y la confianza declarada.
3. **Decisión humana:** la última validación, con revisor, fecha y comentario.

## Reglas

- **La evidencia no se edita.** Se muestra lo que trae `source_raw`.
- **La IA es una sugerencia.** Su categoría y su prioridad aparecen como "sugeridas".
- **La prioridad final la fija una persona.** Si nadie la ha cambiado, se usa la regla por severidad de la decisión mixta (`docs/diseno/IA_MODELO_Y_PROMPT.md`, sección 5). La ficha indica cuál de las dos se usó.
- **Nada se borra.** Los falsos positivos y duplicados van en su propia sección.
- **Las métricas dicen su denominador.** Se cuenta la última respuesta de cada revisor por hallazgo, y las banderas sin responder no entran en el cálculo.

## Seguridad

La evidencia de ZAP contiene ataques reales (por ejemplo `<script>alert(1)</script>` o comillas para inyección SQL). Todo texto que entra al informe pasa por `html.escape`, así que al abrirlo se muestra como texto y no se ejecuta. Hay un test que lo verifica (`test_el_html_escapa_la_evidencia`).

En las exportaciones el riesgo es otro: una celda que empieza con `=`, `+`, `-` o `@` se ejecuta como fórmula al abrir el archivo en una planilla (inyección de fórmulas, CWE-1236). El CSV antepone un apóstrofo a esos textos y el XLSX guarda toda celda de texto como texto, nunca como fórmula. El XLSX además quita los caracteres de control que el formato no admite. Lo verifican `test_csv_neutraliza_textos_que_una_planilla_ejecutaria_como_formula` y `test_xlsx_guarda_como_texto_lo_que_parece_formula_y_quita_caracteres_de_control`.

## Código

| Archivo | Qué hace |
|---|---|
| `backend/app/informe.py` | Arma los datos y la página. No consulta la base, así que se prueba sin PostgreSQL |
| `backend/app/informe_consulta.py` | Elige el objetivo y carga sus escaneos y hallazgos. Lo usan la terminal y la API, así las dos entregan el mismo informe |
| `backend/scripts/informe.py` | Línea de comandos: escribe el HTML en la salida estándar |
| `backend/app/informe_export.py` | Arma el CSV y el XLSX a partir de los mismos datos que el HTML |
| `backend/app/rutas.py` | `GET /informe`, `/informe.csv` y `/informe.xlsx` (404 si no hay escaneos o el objetivo no existe) |
| `frontend/src/app/informe/page.tsx` | Pantalla Informe: vista previa y botón **Exportar informe** (`components/informe/vista-informe.tsx`) |
| `frontend/src/app/informe/ver/route.ts` | Pide el HTML a la API para la vista previa y para abrirlo en otra pestaña |
| `frontend/src/app/informe/descargar/route.ts` | Pide el CSV o el XLSX a la API y lo entrega como descarga |
| `backend/tests/test_informe.py` | Tests sin base: prioridad, decisión vigente, descartados, orden, métricas, marca "Revisar" y escape HTML |
| `backend/tests/test_informe_export.py` | Tests sin base del CSV y el XLSX: columnas, orden, hojas, nombre del archivo e inyección de fórmulas |
| `backend/tests/test_informe_api.py` | 8 tests contra PostgreSQL: respuesta HTML, objetivo, 404, que la API y la terminal generen lo mismo, y las descargas CSV y XLSX |

## Pendiente

- Elegir el objetivo desde el dashboard. Hoy la pantalla muestra el del objetivo con más hallazgos, que en el laboratorio es el único (Juice Shop); la API y la pantalla ya aceptan `?objetivo=`.
