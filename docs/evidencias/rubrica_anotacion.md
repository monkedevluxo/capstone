# Rúbrica de anotación · Golden set inicial

**Revisor:** Felipe · **Fecha:** 14-10-2026 · **Fuente:** `lab/fixtures/zap_juiceshop_ajax_v2.json` · **Tarea:** T-042 · **Planilla:** `docs/evidencias/validacion_manual.csv`

## Método

Se seleccionaron 10 de los 13 tipos de hallazgo del escaneo con Ajax Spider, cubriendo las tres severidades altas, la cabecera CSP y hallazgos de severidad baja e informativa. Se excluyeron Timestamp Disclosure (mismo CWE que Private IP Disclosure), Modern Web Application (aviso de la herramienta, no una vulnerabilidad) y User Agent Fuzzer (informativo, sin CWE).

Cada hallazgo se etiquetó **revisando solo la evidencia de ZAP, sin mirar las respuestas del modelo**, para evitar el sesgo de anclaje.

## Categoría OWASP 2025

Se eligió la categoría según **el mecanismo de la falla**, no según su gravedad:

- **A05 Injection:** la entrada del usuario llega sin filtrar a una consulta o intérprete (SQL Injection).
- **A02 Security Misconfiguration:** falta una defensa o hay una configuración demasiado permisiva (cabeceras ausentes, CORS abierto, información interna expuesta). Las redirecciones abiertas también se clasificaron aquí, como configuración insegura del enlace; la tabla oficial CWE→OWASP las ubica en A01, lo que se deja registrado como diferencia de criterio.
- **A07 Authentication Failures:** fallas en el manejo de la sesión (identificador de sesión en la URL).
- **A01 Broken Access Control:** datos accesibles más allá de lo necesario (información del carrito en el almacenamiento del navegador).

## Prioridad

La prioridad responde a **qué tan urgente es arreglarlo en este caso**, no a la severidad de ZAP:

- **p1:** explotable hoy y en funciones públicas (login, buscador, redirecciones).
- **p2:** defensa ausente, sin ataque confirmado (cabeceras de seguridad, CORS).
- **p3:** exposición de información de bajo impacto, o hallazgos solo en canales técnicos internos.
- **p4:** falsos positivos.

## Falso positivo

Se marcó como falso positivo cuando ZAP detecta algo real, pero **no es el problema que reporta**:

- **H03 (con duda):** la redirección al GitHub oficial está permitida por la propia aplicación.
- **H06 y H07:** la cabecera anti-clickjacking y el identificador en la URL corresponden al canal técnico de socket.io, no a páginas visibles ni a la sesión del usuario.

Resultado: 3 de 10 hallazgos marcados como falsos positivos.

## Limitaciones

Hay un solo revisor, por lo que no se mide el acuerdo entre revisores (queda para el golden set completo en S6). Los casos H02, H03, H05 y H10 admiten más de una categoría razonable.
