# Informe técnico exportable

**Tareas:** T-058 y T-059 · **Responsable:** Felipe Cayún

El informe técnico reúne, para un objetivo, todo lo que el sistema sabe de sus hallazgos: la evidencia original del escáner, la sugerencia de la IA y la decisión humana. Se genera como una página HTML autocontenida (sin dependencias externas), lista para abrir en el navegador o guardar como PDF.

## Cómo generarlo

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

## Código

| Archivo | Qué hace |
|---|---|
| `backend/app/informe.py` | Arma los datos y la página. No consulta la base, así que se prueba sin PostgreSQL |
| `backend/scripts/informe.py` | Consulta la base y escribe el HTML |
| `backend/tests/test_informe.py` | 10 tests: prioridad, decisión vigente, descartados, orden, métricas y escape HTML |

## Pendiente

- Conectar el botón "Informe" del dashboard, hoy deshabilitado ("Próximamente"), para descargarlo desde la interfaz.
