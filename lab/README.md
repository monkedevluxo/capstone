# Laboratorio · scripts de escaneo

Scripts para ejecutar escaneos de OWASP ZAP contra Juice Shop dentro de la red aislada `lab_interna` y versionar sus resultados. Tarea T-018.

Todos se corren **desde la raíz del repositorio**, con el laboratorio arriba (`docker compose up -d`).

## `escanear.sh`

```bash
./lab/escanear.sh [baseline|full|ajax|ajax-auth]
```

| Modo | Qué hace | Duración aprox. |
|---|---|---|
| `baseline` (por defecto) | Solo análisis pasivo | 1-2 min |
| `full` | Escaneo activo con el spider tradicional | 6-9 min |
| `ajax` | Escaneo activo con Ajax Spider y límites de tiempo | ~15 min |
| `ajax-auth` | Igual que `ajax`, con sesión iniciada como usuario de prueba | ~15-20 min |

- El resultado queda en `lab/salidas/<modo>_<fecha>.json`, así un escaneo nunca pisa al anterior.
- Antes de empezar verifica que Docker esté corriendo, que Juice Shop esté arriba y que haya permiso de escritura en `lab/salidas/`. Si algo falla, dice qué comando lo arregla.
- Al terminar muestra un resumen con los tipos de alerta por nivel de riesgo.

### Por qué los modos `ajax` tienen límites

Sin límites, el escaneo full con Ajax Spider quedó colgado más de 3 horas: ZAP acumuló cientos de procesos de navegador headless sin cerrarlos (regla de DOM XSS) mientras Juice Shop no recibía carga. El script aplica:

| Parámetro | Valor | Efecto |
|---|---|---|
| `-m` | 5 | El Ajax Spider explora durante 5 minutos |
| `scanner.maxRuleDurationInMins` | 5 | Ninguna regla de ataque dura más de 5 minutos |
| `scanner.maxScanDurationInMins` | 60 | El escaneo activo se corta a la hora |

Con esos límites el escaneo terminó en unos 15 minutos y encontró 13 tipos de alerta, contra 5 del spider tradicional, incluida una inyección SQL.

### Modo `ajax-auth`

Obtiene un token con `token_juiceshop.sh` y se lo entrega a ZAP con la opción oficial `ZAP_AUTH_HEADER_VALUE`, que agrega `Authorization: Bearer <token>` a cada petición. El token no se guarda en ningún archivo. Resultados y comparación en `docs/evidencias/escaneo_autenticado.md`.

## `token_juiceshop.sh`

```bash
./lab/token_juiceshop.sh
```

Crea el usuario de prueba `zap@sentinel.lab` en Juice Shop (si no existe) e imprime su token de sesión. Las peticiones se hacen desde un contenedor conectado a `lab_interna`, porque Juice Shop no publica puertos. Juice Shop borra sus usuarios al reiniciarse, por eso el script intenta crearlo cada vez.

La cuenta solo existe en el laboratorio local. **El token es una credencial: no lo pegues en archivos versionados.**

## `congelar_fixture.sh`

```bash
./lab/congelar_fixture.sh <archivo_en_salidas> <nombre_fixture>
```

Copia un resultado de `lab/salidas/` a `lab/fixtures/` para versionarlo. Verifica que el JSON sea válido y **nunca sobrescribe un fixture existente**, porque los tests del parser y las métricas del golden set dependen de ellos. Para una versión nueva, sube el sufijo (`_v3`).

## Carpetas

| Carpeta | Contenido | ¿Se versiona? |
|---|---|---|
| `salidas/` | Resultados de cada ejecución | No |
| `fixtures/` | Escaneos congelados que usan los tests y las métricas | Sí |

## `e2e.sh` · prueba de extremo a extremo (T-061)

```bash
./lab/e2e.sh                # con el fixture zap_juiceshop_ajax_v2
./lab/e2e.sh --escanear     # escanea Juice Shop primero y usa ese resultado
```

Recorre el flujo completo y verifica cada paso:

| Paso | Qué comprueba |
|---|---|
| 1 | Crea (si falta), migra y vacía la base de pruebas `sentinelai_test` |
| 2 | Levanta una API de pruebas en `127.0.0.1:8001` y espera a que responda `/health` |
| 3 | Importa el reporte: 201 y al menos un hallazgo nuevo |
| 4 | Importa el mismo reporte otra vez: 409 |
| 5 | El resumen de la API cuenta los mismos hallazgos que se importaron |
| 6 | Enriquece el escaneo con la IA. Si Ollama no responde, avisa y sigue: el sistema está diseñado para funcionar con hallazgos "sin enriquecer" |
| 7 | Genera el informe técnico en `lab/salidas/e2e_informe.html` y verifica sus 5 secciones y una ficha por hallazgo |

Termina con `E2E OK` o con la lista de pasos que fallaron, y sale con código 1 si hubo fallas.

**Nunca toca la base de la demo** (`sentinelai`): todo ocurre en `sentinelai_test`, como exige `CONTRIBUTING.md`. La API de pruebas se detiene al terminar, aunque el script falle a la mitad.
