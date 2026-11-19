# Innovación

**SentinelAI** · Actualizado: 18-11-2026

Esta sección explica qué aporta SentinelAI frente a lo que ya existe, y qué parte de ese aporte está demostrada con evidencia.

## El punto de partida

Los escáneres de seguridad de aplicaciones web, como OWASP ZAP, detectan bien, pero entregan sus resultados como una lista larga, repetitiva y escrita para especialistas. Existen plataformas de gestión de vulnerabilidades que agregan y deduplican esos resultados, y en los últimos años han aparecido asistentes de IA que explican hallazgos. Estos asistentes suelen depender de modelos alojados en la nube, lo que obliga a enviar fuera de la organización la evidencia de sus vulnerabilidades.

SentinelAI no compite con el escáner. Trabaja después de él, en el paso que hoy es más manual: decidir qué significa cada hallazgo y qué hacer con él.

## Qué es nuevo

### 1. IA local aplicada al triage de resultados DAST

El modelo de lenguaje corre en un equipo propio, con Ollama, y nunca recibe más que la evidencia del hallazgo. La información sensible no sale del equipo y el sistema funciona sin internet. La latencia medida (mediana de 1,1 s por hallazgo en una tarjeta gráfica doméstica) muestra que no hace falta un servicio en la nube para que la herramienta sea usable.

### 2. La IA se mide, y el diseño cambió por esa medición

El equipo no asumió que el modelo acertaba. Comparó sus respuestas con el criterio de personas que anotaron sin verlas:

- La prioridad que proponía el modelo acertó **40 %**; una regla fija por severidad acertó **60 %**.
- La confianza que declaraba el modelo fue **igual de alta cuando se equivocaba** (0,93) que cuando acertaba (0,90).

Con esos datos se cambió el diseño (*decisión mixta*): la prioridad la propone una regla, la categoría se contrasta con la tabla oficial CWE → OWASP Top 10:2025, y la IA queda a cargo de explicar y recomendar. Cuando el modelo y la tabla no coinciden, el hallazgo se marca para revisar primero. El sistema usa la IA donde aporta y la acota donde se demostró débil.

Evidencia: `docs/evidencias/metricas_golden_set.md` y `docs/diseno/IA_MODELO_Y_PROMPT.md`, sección 5.

### 3. La evaluación de la IA ocurre dentro del trabajo diario

Normalmente, evaluar un modelo es un trabajo aparte, con planillas que se llenan una vez. En SentinelAI, la persona que registra su decisión sobre un hallazgo responde además cuatro preguntas sobre la sugerencia de la IA: si la categoría es correcta, si la prioridad es correcta, si la remediación es útil y si el modelo inventó algo.

- Cada respuesta queda asociada a la versión exacta de la sugerencia que se juzgó.
- Un revisor no ve las respuestas de los demás, para que las anotaciones sean independientes.
- Las métricas, incluido el acuerdo entre revisores (κ de Cohen), se calculan desde los datos guardados.

Así, la calidad del modelo se puede seguir midiendo mientras el sistema se usa, y un cambio de prompt se puede comparar con el anterior.

### 4. Tres capas que nunca se mezclan

Cada hallazgo separa lo que reportó el escáner, lo que interpretó la IA y lo que decidió una persona. Las tres se guardan por separado, ninguna sobrescribe a otra y la pantalla las muestra como capas distintas. La IA aparece siempre como "sugerencia, no decisión", y el estado de un hallazgo solo cambia con una decisión humana firmada.

### 5. La ética está en la infraestructura, no solo en un documento

El marco legal (Ley 21.459) no depende de que alguien recuerde respetarlo:

- La red del objetivo vulnerable no tiene salida a internet.
- La API rechaza reportes de equipos que no son del laboratorio.
- La base de datos rechaza registrar un objetivo fuera de él.

Cada una de estas barreras está verificada por una prueba automática o por un comando documentado.

## Lo que no es innovación

Para ser precisos con el alcance:

- **Detectar vulnerabilidades** lo hace OWASP ZAP; SentinelAI no descubre nada nuevo.
- **Deduplicar hallazgos** es una práctica conocida en plataformas de gestión de vulnerabilidades. Aquí se implementa de forma propia, con una limitación documentada: un mismo tipo de alerta en rutas distintas puede quedar como dos hallazgos, que una persona puede marcar como duplicados.
- **El modelo** es Llama 3.1, sin entrenamiento adicional. El aporte está en cómo se usa, se valida y se acota, no en el modelo.

## Limitaciones

- La evaluación se hizo sobre **17 hallazgos únicos** de un solo objetivo (Juice Shop): son todos los que producen los escaneos realizados. Los resultados son un censo de ese laboratorio, no una muestra representativa de aplicaciones reales.
- Se integró un solo escáner. El modelo de datos admite otros, pero no se probaron.
- El sistema está pensado para un equipo local, sin cuentas de usuario.

## Proyección

- **Más objetivos y escaneos autenticados** (DVWA, WebGoat), para ampliar la evaluación del modelo con hallazgos más variados.
- **Comparar versiones del prompt o del modelo** con las métricas que el propio sistema registra.
- **Verificación de remediación:** que un nuevo escaneo marque como remediados los hallazgos que dejaron de aparecer.
- **Uso docente:** el laboratorio aislado, con decisiones registradas y medidas, puede servir para enseñar triage de vulnerabilidades sin riesgo legal.
