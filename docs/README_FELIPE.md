# SentinelAI · Rol de Felipe

**Laboratorio y Validación**

---

## Contexto en 60 segundos

SentinelAI toma los resultados de un escáner de seguridad (OWASP ZAP), los ordena en un formato común, se los pasa a un modelo de lenguaje local para que los explique y priorice, y los muestra en un dashboard donde una persona valida.

El flujo completo: **escaneo → normalización → IA → validación humana → informe**.

Tu rol cubre las dos puntas: **generar los datos** que alimentan el sistema, y **verificar que el sistema no se está equivocando**.

**Para instalar todo:** `docs/guias/GUIA_INSTALACION.md`. Está escrita para Windows 11 y tiene una sección específica para ti.

---

## Lo segundo es más importante de lo que parece

Cualquiera puede mostrar una pantalla con hallazgos y decir "la IA los clasificó". La pregunta que el profesor va a hacer, y que hunde proyectos, es:

> *¿Cómo saben que la IA acierta?*

Sin una respuesta con números, tienen una demo. Con números, tienen resultados.

**Esos números son tuyos.** Salen de comparar lo que dice el modelo contra lo que dice una persona que revisó el mismo hallazgo. Eso se llama *golden set* y es la parte del proyecto que lo convierte en proyecto de título.

No necesitas saber FastAPI ni React para esto. Necesitas criterio, y eso se construye leyendo hallazgos.

---

## Lo que tienes que entregar en las próximas 2 semanas

Hay presentación con MVP funcional.

| Prioridad | Qué | Cuándo |
|---|---|---|
| **1** | Escaneo con Ajax Spider y su fixture en el repo | Días 1-4 |
| **2** | 10-15 hallazgos anotados a mano | Días 5-10 |
| **3** | Una lámina con las métricas | Día 11 |

Solo 10-15 hallazgos por ahora. El golden set completo de 30-50 va en la semana 11.

---

# Parte 1 · El laboratorio

## Qué es

Contenedores Docker en una red aislada. Dentro vive **OWASP Juice Shop**, una tienda en línea construida a propósito con más de cien vulnerabilidades, que es material didáctico oficial de OWASP. **ZAP** la ataca desde adentro de esa red y produce un JSON con lo que encuentra.

La red del laboratorio no tiene salida a internet. Eso no es una convención del equipo: es una restricción de Docker (`internal: true`) y se puede demostrar con un comando.

Si Docker te es nuevo, lee `docs/guias/DOCKER_BASICO.md` antes. Son 20 minutos.

## Tu equipo es el mejor del grupo para esto

Tienes 32 GB de RAM. Eso importa más de lo que parece.

El primer escaneo full se corrió en el notebook de Luciano y encontró solo **3 tipos de hallazgo**. Juice Shop tiene más de cien vulnerabilidades plantadas. ¿Por qué tan pocas?

Porque el spider tradicional de ZAP lee HTML y sigue los enlaces que encuentra. Juice Shop es una aplicación Angular: el servidor entrega un HTML casi vacío y todo el contenido lo construye el navegador ejecutando JavaScript. El spider no ve nada de eso. Encontró 88 URLs y ahí se quedó.

**La solución es el Ajax Spider**, que levanta un navegador headless dentro del contenedor, deja que el JavaScript se ejecute, y hace clic en todo lo que puede. Es pesado: en el notebook falló por falta de recursos, y una regla relacionada (`DomXssScanRule`) se comió 337 segundos intentando arrancar un navegador sin conseguirlo.

Con 32 GB, tu equipo debería poder. **Ese es tu aporte más importante de estas dos semanas.**

## Escanear

```bash
cd ~/capstone

# Rápido, solo pasivo (1-2 minutos) — para confirmar que todo funciona
docker compose run --rm zap zap-baseline.py -t http://juiceshop:3000 -J baseline.json -I

# Completo, sin Ajax (unos 9 minutos) — línea base de comparación
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -J full.json -I

# Completo + Ajax Spider — el que importa
docker compose run --rm zap zap-full-scan.py -t http://juiceshop:3000 -J full_ajax.json -I -j
```

Corre los tres. Los dos últimos te sirven para **medir cuánto ganaste**, que es un dato para el informe:

```bash
python3 -c "import json;d=json.load(open('lab/salidas/full.json'));print(sum(len(s['alerts']) for s in d['site']),'alertas sin ajax')"
python3 -c "import json;d=json.load(open('lab/salidas/full_ajax.json'));print(sum(len(s['alerts']) for s in d['site']),'alertas con ajax')"
```

Si sale `Permission denied` al escribir el JSON:

```bash
sudo chown -R $USER:$USER lab/salidas
```

## Congelar el resultado como fixture

Esto es lo que desbloquea a Luciano y Joaquín: con un escaneo guardado, ellos desarrollan en segundos en vez de esperar 9 minutos cada vez.

```bash
cp lab/salidas/full_ajax.json lab/fixtures/zap_juiceshop_ajax_v2.json
git add lab/fixtures/
git commit -m "lab: fixture de escaneo con ajax spider"
git push
```

**Avísales en el grupo cuando lo subas.** Joaquín lo necesita para probar el parser contra datos reales.

## Si el Ajax Spider falla

Puede pasar, y el error típico es "failed to start browser". Antes de darlo por perdido:

- Cierra el navegador y todo lo pesado antes de lanzarlo
- Prueba primero el baseline con `-j`, que es más liviano: `zap-baseline.py -t http://juiceshop:3000 -J baseline_ajax.json -I -j`
- Pega el error completo en el grupo

## Si alcanzas: escaneo autenticado

Es el que de verdad abre Juice Shop, porque la mayoría de las vulnerabilidades están detrás del login. Requiere configurar un contexto de ZAP con credenciales y son varias horas de trabajo.

No es para estas dos semanas. Anótalo para el sprint 7.

## Una advertencia que va en serio

Juice Shop es **genuinamente vulnerable**: inyección SQL real, XSS real, autenticación rota real.

- Nunca la expongas fuera de `127.0.0.1`
- Nunca la pongas en la red del campus
- Los escaneos corren solo contra ella, nunca contra un sitio que no sea nuestro

Esto no es formalidad académica: es lo que la diapositiva de marco ético promete y lo que la Ley 21.459 delimita.

---

# Parte 2 · La validación

## Cómo funciona

Cada hallazgo pasa por el modelo, que produce cuatro cosas: una explicación, una categoría del OWASP Top 10, una prioridad sugerida y un nivel de confianza.

Tu trabajo es tomar el hallazgo, mirar la evidencia original, decidir tú qué corresponde, y después comparar con lo que dijo el modelo.

## La rúbrica

Para cada hallazgo revisado, cuatro respuestas:

**¿La categoría OWASP es correcta?** ¿El modelo la clasificó donde corresponde según el Top 10:2025? Un XSS reflejado va en A05 Injection. Una cabecera de seguridad faltante va en A02 Security Misconfiguration.

**¿La prioridad es correcta?** No es lo mismo que la severidad. Severidad es cuán grave es el tipo de falla; prioridad es qué tan urgente es arreglarla **en este caso**. Un XSS en el buscador público es más urgente que el mismo XSS en un panel interno.

**¿La remediación sirve?** ¿Un desarrollador podría tomar esa recomendación y arreglar el problema? "Validar la entrada del usuario" no sirve. "Codificar el parámetro q en HTML antes de renderizarlo" sí.

**¿Hay alucinación?** ¿El modelo afirmó algo que la evidencia no respalda? Por ejemplo, decir que el hallazgo permite ejecución remota de código cuando la evidencia solo muestra una cabecera faltante. **Esta es la métrica más importante de las cuatro.**

## Cómo registrarlo

Por ahora, una planilla con estas columnas:

```
id_hallazgo | titulo | severidad | owasp_modelo | owasp_tuyo |
owasp_correcto | prioridad_modelo | prioridad_tuya | prioridad_correcta |
remediacion_util | alucinacion | nota
```

Guárdala en `docs/evidencias/validacion_manual.csv`. **Es una de las seis evidencias comprometidas del proyecto.**

Más adelante esto se hace desde el dashboard, pero para la presentación la planilla basta.

## Las tres métricas

```
Acierto OWASP     = owasp_correcto verdadero / total revisados
Acierto prioridad = prioridad_correcta verdadero / total revisados
Tasa alucinación  = alucinacion verdadero / total revisados
```

Con 10 hallazgos ya puedes decir algo como *"el modelo acertó la categoría en 8 de 10 y alucinó en 1"*. Eso, en la presentación, vale más que una funcionalidad extra.

**Di siempre el denominador.** "80% de acierto" sin decir sobre cuántos casos es un número que no significa nada, y un profesor lo va a notar.

## Dos reglas de método

**Decide tú primero, mira el modelo después.** Si lees su respuesta antes de formarte tu opinión, vas a estar de acuerdo con él. Se llama sesgo de anclaje y arruina la medición.

**Anota por qué.** Cuando marques algo como incorrecto, escribe una línea explicando la razón. En la semana 15 no vas a recordar, y esas notas son lo que hace defendible la métrica.

---

## Lo que viene después de la presentación

- **Semanas 11-12:** el golden set completo, 30-50 hallazgos con dos revisores por caso
- **Semanas 15-16:** el informe técnico exportable (te toca a ti)
- **Desde la semana 13:** apoyo al frontend, porque ahí Luciano queda sobrecargado

---

## Convenciones

```bash
git checkout -b felipe/lab-escaneos
git commit -m "lab: fixture de escaneo con ajax spider"
```

Tipos: `feat`, `fix`, `docs`, `lab`, `chore`. Nada entra a `main` directo, todo por pull request.

---

## Para aprender lo justo de seguridad

No estudies seguridad en general. Cuatro cosas, en este orden:

1. **Abre el JSON de un escaneo y lee diez alertas.** En dos horas reconoces los patrones.
2. **El OWASP Top 10:2025**, una página por categoría: `owasp.org/Top10/2025/`
3. **El score-board de Juice Shop.** Levántala con el puerto publicado en local y entra a `/#/score-board`. Es la lista de desafíos plantados, ordenados por dificultad.
4. **Qué es un CWE.** Solo el concepto: un catálogo numerado de tipos de debilidad.

Con eso puedes anotar con criterio y defender tu parte.

---

## Checklist

**Laboratorio**
- [ ] Entorno instalado según `docs/guias/GUIA_INSTALACION.md`
- [ ] `docker compose up -d` funciona
- [ ] Escaneo baseline ejecutado
- [ ] Escaneo full ejecutado
- [ ] **Escaneo full con Ajax Spider ejecutado**
- [ ] Comparación de cantidad de alertas anotada
- [ ] Fixture commiteado y avisado en el grupo

**Validación**
- [ ] Planilla creada en `docs/evidencias/`
- [ ] 10-15 hallazgos anotados
- [ ] Las tres métricas calculadas
- [ ] Una lámina con los números y el denominador

---

Si algo de la rúbrica no te calza al revisar hallazgos reales, dilo en el grupo. Es mejor ajustar los criterios ahora que descubrir en la semana 12 que anotaste cincuenta casos con un criterio que no servía.
