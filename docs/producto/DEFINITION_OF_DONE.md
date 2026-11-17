# Definición de terminado (Definition of Done)

**SentinelAI** · Actualizado: 16-11-2026

Una tarea está **terminada** cuando cumple su criterio de aceptación y, además, todo lo que esta página exige para su tipo. El criterio de aceptación dice *qué* debe lograr cada tarea y está en la planilla de sprints (`docs/SentinelAI_Plan_Sprints.xlsx`, hoja Backlog). Esta página dice *con qué calidad*.

## La regla general

Una tarea pasa a **Hecho** en la planilla solo cuando su cambio está integrado en la rama `main`. Hasta entonces está **En curso**, aunque el código ya funcione en el equipo de quien lo escribió.

Para llegar a `main`, todo cambio debe:

- [ ] Entrar por un pull request desde una rama `persona/tema`.
- [ ] Indicar en la descripción qué tareas cubre (T-0xx) y cómo se probó.
- [ ] Pasar los checks obligatorios de la integración continua: **Tests** y **Migraciones y restricciones**.
- [ ] Tener la aprobación de otro integrante. Nadie aprueba su propio pull request.
- [ ] No incluir contraseñas, tokens ni otros secretos.

## Según el tipo de cambio

### Código del backend

- [ ] Tiene pruebas automáticas que fallan sin el cambio y pasan con él.
- [ ] Los casos de error devuelven un código HTTP y un mensaje definidos, no un error 500.
- [ ] Si agrega o cambia un endpoint, el README lo documenta.
- [ ] La evidencia original del escáner no se modifica en ningún paso.

### Cambios en la base de datos

- [ ] El cambio va en una migración de Alembic, nunca a mano.
- [ ] `alembic check` no detecta diferencias entre los modelos y las migraciones.
- [ ] La migración se puede revertir y volver a aplicar sobre una base limpia.
- [ ] Las restricciones del proyecto siguen activas: la base rechaza objetivos fuera del laboratorio.
- [ ] Antes de migrar la base de la demostración se hace un respaldo.

### Dashboard

- [ ] Pasa el lint, el chequeo de tipos y la compilación.
- [ ] Se revisó en ancho de escritorio y de teléfono, sin desplazamiento horizontal.
- [ ] Maneja los estados vacío, cargando y error, incluida la API caída.
- [ ] Se puede usar con el teclado y los controles tienen nombre para lectores de pantalla.
- [ ] El texto que viene del escáner se muestra como texto, nunca como HTML.
- [ ] Distingue a la vista lo que dijo el escáner, lo que sugirió la IA y lo que decidió la persona.

### Módulo de IA

- [ ] La salida del modelo se valida contra el esquema antes de guardarse.
- [ ] Cada respuesta guardada registra el modelo, la versión del prompt y la fecha.
- [ ] Si el modelo no responde, el sistema sigue funcionando y el hallazgo queda "sin enriquecer".
- [ ] Un cambio de prompt se mide otra vez contra el golden set antes de adoptarse.

### Laboratorio y escaneos

- [ ] El escaneo se ejecuta solo contra el objetivo del laboratorio, en la red sin salida a internet.
- [ ] El resultado que se quiere conservar se guarda como fixture versionado, con un nombre nuevo.
- [ ] Los scripts verifican sus condiciones antes de empezar y fallan con un mensaje claro.

### Documentos y evidencias

- [ ] Está en la carpeta que corresponde dentro de `docs/` y enlazado desde el README o desde el índice de evidencias.
- [ ] Indica responsable y fecha de actualización.
- [ ] Toda cifra indica de dónde sale y cómo reproducirla.
- [ ] Lo revisó otro integrante.

## Terminado para un sprint

Un sprint se cierra cuando:

- [ ] Se cumple su hito verificable, descrito en la hoja Sprints de la planilla.
- [ ] La planilla refleja el estado real de cada tarea.
- [ ] Las tareas que no se cerraron pasan al sprint siguiente, con el motivo anotado.
- [ ] La rama `main` tiene todos los checks en verde.

## Terminado para una entrega

Antes de cada entrega al docente:

- [ ] La prueba de extremo a extremo termina sin fallas.
- [ ] Una persona que no escribió el código puede levantar el proyecto siguiendo solo el README.
- [ ] El README, la planilla y el índice de evidencias están al día.
- [ ] La demostración se ensayó completa en el equipo donde se va a presentar.
