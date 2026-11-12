# Escaneo autenticado y tamaño del golden set (T-041)

**Fecha:** 09-11-2026 · **Responsable:** Felipe Cayún · **Fixture:** `lab/fixtures/zap_juiceshop_ajax_auth_v1.json`

## Por qué

El golden set completo (S6) pide entre 30 y 50 hallazgos. Los cuatro fixtures anteriores suman solo **13 tipos de alerta distintos**, porque todos se obtuvieron sin sesión iniciada, y la mayor parte de Juice Shop (carrito, pedidos, perfil) está detrás del login.

## Cómo

1. `lab/token_juiceshop.sh` crea un usuario de prueba en Juice Shop (si no existe) e inicia sesión desde un contenedor conectado a `lab_interna`.
2. `lab/escanear.sh ajax-auth` entrega ese token a ZAP con la opción oficial `ZAP_AUTH_HEADER_VALUE`. ZAP agrega `Authorization: Bearer <token>` a cada petición, incluidas las del Ajax Spider.
3. Mismos límites que el modo `ajax`: Ajax Spider 5 minutos, 5 minutos por regla, 60 minutos de escaneo activo.

El token no se guarda en ningún archivo del repositorio: se genera al momento y se pasa directo al contenedor.

## Resultados

| Escaneo | Tipos de alerta | High | Medium | Low | Info |
|---|---|---|---|---|---|
| Full con Ajax Spider (`ajax_v2`) | 13 | 3 | 4 | 3 | 3 |
| Full con Ajax Spider y sesión (`ajax_auth_v1`) | **15** | 3 | 5 | 3 | 4 |

Alertas nuevas con sesión iniciada:

| Alerta | Riesgo | CWE |
|---|---|---|
| Information Disclosure - JWT in Browser localStorage | Medium | 922 |
| Information Disclosure - Information in Browser localStorage | Informational | 359 |

La primera confirma que el escaneo se hizo con la sesión activa: la aplicación guarda el token de sesión en `localStorage`, donde cualquier script de la página puede leerlo.

**La autenticación agregó solo 2 tipos.** El Ajax Spider explora 5 minutos y no completa flujos como comprar o agregar direcciones, que es donde Juice Shop concentra sus vulnerabilidades de control de acceso. Ampliar esa exploración requiere un contexto de ZAP con flujos guiados, lo que queda fuera de este sprint.

### Nota sobre la evidencia

La evidencia del hallazgo CWE-922 incluye el token del usuario de prueba. Se conserva sin modificar, porque los fixtures son la salida original del escáner. No expone nada adicional: la cuenta solo existe en el laboratorio local, se borra al reiniciar el contenedor de Juice Shop, el token expira en horas y su contraseña ya figura en `lab/token_juiceshop.sh`.

## Propuesta para la muestra del golden set (T-041)

Con ZAP sobre Juice Shop no es realista llegar a 30 **tipos** de alerta distintos. Pero el sistema no trabaja con tipos, sino con **hallazgos**: la clave de deduplicación agrupa por regla, plantilla de ruta y parámetro, y la IA enriquece cada hallazgo por separado. Por ejemplo, la falta de CSP en `/` y en `/ftp` son dos hallazgos distintos en la base de datos.

Contando así, los cuatro fixtures anteriores suman **alrededor de 34 hallazgos únicos**, a los que se agregan los del escaneo autenticado. Eso cae dentro del rango de 30 a 50.

**Propuesta:**

1. La unidad del golden set es el **hallazgo como lo guarda la base de datos**, no el tipo de alerta.
2. La muestra se toma importando todos los fixtures y consultando `/findings`, que entrega el conteo exacto y deduplicado.
3. Se incluyen todos los hallazgos de severidad alta y media, y se completa con baja e informativa hasta llegar a 30-50, cuidando que ningún tipo de alerta supere un tercio de la muestra, para que la CSP repetida en muchas rutas no domine las métricas.
4. Los 10 hallazgos ya anotados se reutilizan; no se anotan de nuevo.
5. Cada hallazgo lo anotan dos revisores por separado, con el mismo método usado en `acuerdo_alucinaciones.md`.

**Pendiente de acordar con el equipo** antes del inicio del S6 (16-11-2026).
