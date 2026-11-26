# Capturas del dashboard

**Tarea:** T-060 · **Responsable:** Luciano Zambrano · **Tomadas:** 25-11-2026

Capturas del dashboard funcional para la evidencia 6. El criterio de la tarea pide resumen, lista filtrada, detalle y validación, con datos reales.

## De dónde salen los datos

- **Hallazgos y sugerencias:** una copia de la base de la demo (`sentinelai`) en la base de pruebas (`sentinelai_test`), hecha con `pg_dump` y `pg_restore`. Son los 3 escaneos de los fixtures acordados (`full_v1`, `ajax_v2` y `ajax_auth_v1`), los 17 hallazgos únicos y las 17 sugerencias de Llama 3.1 8B con el prompt v2.
- **Decisión humana:** una decisión real registrada por Luciano Zambrano desde el dashboard sobre Off-site Redirect, siguiendo la regla común de anotación (`../rubrica_anotacion.md`): duplicado de External Redirect, categoría del modelo incorrecta (A05 en vez de A01), prioridad correcta, remediación útil y sin invención. Coincide con la decisión de los dos revisores del golden set para ese hallazgo.
- La decisión se guardó en la base de pruebas; la base de la demo no se modificó.

Tema claro, 1440 px de ancho.

## Capturas

| Archivo | Qué muestra |
|---|---|
| `01-resumen.png` | Hallazgos: totales por severidad, "Revisar primero" y "Sin enriquecer", y la lista ordenada por severidad |
| `02-lista-filtrada.png` | Lista filtrada por severidad alta y media, solo los marcados para revisar: 6 de 17 |
| `03-detalle.png` | Detalle de Off-site Redirect antes de decidir: OWASP de referencia por la tabla CWE, prioridad por regla, "Revisar" porque el modelo propone otra categoría, y las capas del escáner y del modelo por separado |
| `04a-validacion-formulario.png` | El formulario de la decisión humana: tipo de decisión, comentario, prioridad final y las cuatro preguntas sobre la sugerencia del modelo |
| `04b-validacion-registrada.png` | La decisión ya registrada en el historial del hallazgo |
| `04c-detalle-tras-decidir.png` | El mismo hallazgo después de decidir: su estado pasó a Duplicado |
| `05-escaneos.png` | Escaneos importados, con hallazgos nuevos, sin enriquecer y para revisar por escaneo |
| `06-informe.png` | Pantalla Informe: vista previa del informe técnico y botón para exportarlo a PDF, Excel o CSV |
