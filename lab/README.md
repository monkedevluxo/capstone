# Laboratorio · scripts de escaneo

Scripts para ejecutar escaneos de OWASP ZAP contra Juice Shop dentro de la red aislada `lab_interna` y versionar sus resultados. Tarea T-018.

Todos se corren **desde la raíz del repositorio**, con el laboratorio arriba (`docker compose up -d`).

## `escanear.sh`

```bash
./lab/escanear.sh [baseline|full|ajax]
```

| Modo | Qué hace | Duración aprox. |
|---|---|---|
| `baseline` (por defecto) | Solo análisis pasivo | 1-2 min |
| `full` | Escaneo activo con el spider tradicional | 6-9 min |
| `ajax` | Escaneo activo con Ajax Spider y límites de tiempo | ~15 min |

- El resultado queda en `lab/salidas/<modo>_<fecha>.json`, así un escaneo nunca pisa al anterior.
- Antes de empezar verifica que Docker esté corriendo, que Juice Shop esté arriba y que haya permiso de escritura en `lab/salidas/`. Si algo falla, dice qué comando lo arregla.
- Al terminar muestra un resumen con los tipos de alerta por nivel de riesgo.

### Por qué el modo `ajax` tiene límites

Sin límites, el escaneo full con Ajax Spider quedó colgado más de 3 horas: ZAP acumuló cientos de procesos de navegador headless sin cerrarlos (regla de DOM XSS) mientras Juice Shop no recibía carga. El script aplica:

| Parámetro | Valor | Efecto |
|---|---|---|
| `-m` | 5 | El Ajax Spider explora durante 5 minutos |
| `scanner.maxRuleDurationInMins` | 5 | Ninguna regla de ataque dura más de 5 minutos |
| `scanner.maxScanDurationInMins` | 60 | El escaneo activo se corta a la hora |

Con esos límites el escaneo terminó en unos 15 minutos y encontró 13 tipos de alerta, contra 5 del spider tradicional, incluida una inyección SQL.

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
