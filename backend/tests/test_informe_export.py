"""Tests de la exportación del informe a CSV y XLSX (app/informe_export.py).
No necesitan base de datos: arman los datos con los mismos objetos simples
que test_informe.py."""

import csv
import io
from datetime import datetime, timezone

from openpyxl import load_workbook

from app.informe import armar_datos
from app.informe_export import COLUMNAS, a_csv, a_xlsx, nombre_archivo
from tests.test_informe import ESCANEO, OBJETIVO, hallazgo, ia, validacion

GENERADO = datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc)
ENCABEZADOS = [c[0] for c in COLUMNAS]


def _datos(*hallazgos):
    return armar_datos(OBJETIVO, [ESCANEO], list(hallazgos), generado_en=GENERADO)


def _leer_csv(contenido: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(contenido.decode("utf-8-sig"))))


def _columna(nombre: str) -> int:
    return ENCABEZADOS.index(nombre) + 1


def test_csv_un_hallazgo_por_fila_vigentes_antes_que_descartados():
    datos = _datos(
        hallazgo(1, titulo="Descartado", estado="falso_positivo"),
        hallazgo(2, titulo="SQL Injection", enriquecimientos=[ia()],
                 validaciones=[validacion(2, priority_override="p2", comment="Revisado")]),
    )
    contenido = a_csv(datos)
    assert contenido.startswith(b"\xef\xbb\xbf")  # BOM: Excel lee bien los tildes

    filas = _leer_csv(contenido)
    assert list(filas[0]) == ENCABEZADOS
    assert [f["Título"] for f in filas] == ["SQL Injection", "Descartado"]
    assert [f["Sección"] for f in filas] == ["Vigente", "Descartado"]

    sql = filas[0]
    assert sql["Prioridad"] == "p2"
    assert sql["Prioridad fijada por"] == "persona"
    assert sql["OWASP (tabla CWE)"] == "A05:2025"
    assert sql["OWASP (IA)"] == "A05:2025"
    assert sql["Remediación (IA)"] == "Usar consultas parametrizadas"
    assert sql["Decisión"] == "Confirmado"
    assert sql["Comentario"] == "Revisado"
    # Sin IA ni decisión, las celdas quedan vacías, no con "None".
    assert filas[1]["OWASP (IA)"] == ""
    assert filas[1]["Revisor"] == ""


def test_csv_neutraliza_textos_que_una_planilla_ejecutaria_como_formula():
    peligroso = '=HYPERLINK("http://evil.test","clic")'
    filas = _leer_csv(a_csv(_datos(hallazgo(1, titulo=peligroso, evidencia="-1+1", cwe=None))))
    assert filas[0]["Título"] == "'" + peligroso
    assert filas[0]["Evidencia"] == "'-1+1"


def test_xlsx_tiene_resumen_hallazgos_y_escaneos():
    datos = _datos(hallazgo(1), hallazgo(2, titulo="Duplicado", estado="duplicado"))
    libro = load_workbook(io.BytesIO(a_xlsx(datos)))
    assert libro.sheetnames == ["Resumen", "Hallazgos", "Escaneos"]

    hoja = libro["Hallazgos"]
    assert [c.value for c in hoja[1]] == ENCABEZADOS
    assert hoja.max_row == 3  # encabezado + 2 hallazgos
    assert hoja.auto_filter.ref == f"A1:{hoja.cell(1, len(ENCABEZADOS)).column_letter}3"
    assert hoja.freeze_panes == "D2"

    escaneos = libro["Escaneos"]
    assert escaneos.cell(2, 4).value == "ab" * 32

    resumen = {f[0].value: f[1].value for f in libro["Resumen"].iter_rows() if f[0].value}
    assert resumen["Total"] == 2
    assert resumen["Vigentes"] == 1
    assert resumen["Descartados"] == 1


def test_xlsx_guarda_como_texto_lo_que_parece_formula_y_quita_caracteres_de_control():
    datos = _datos(hallazgo(1, titulo="=1+1", evidencia="token\x00\x07ok"))
    hoja = load_workbook(io.BytesIO(a_xlsx(datos)))["Hallazgos"]
    titulo = hoja.cell(2, _columna("Título"))
    assert titulo.value == "=1+1"
    assert titulo.data_type == "s"
    assert hoja.cell(2, _columna("Evidencia")).value == "tokenok"


def test_nombre_de_archivo_con_el_host_y_la_fecha():
    datos = _datos(hallazgo(1))
    assert nombre_archivo(datos, "csv") == "informe_juiceshop-3000_20261124.csv"
    assert nombre_archivo(datos, "xlsx").endswith(".xlsx")


def test_la_fecha_del_nombre_de_archivo_es_la_de_chile_no_la_de_utc():
    # 25-11 a las 00:03 UTC es todavía el 24-11 a las 21:03 en Santiago (UTC-3).
    noche = armar_datos(OBJETIVO, [ESCANEO], [hallazgo(1)],
                        generado_en=datetime(2026, 11, 25, 0, 3, tzinfo=timezone.utc))
    assert nombre_archivo(noche, "csv") == "informe_juiceshop-3000_20261124.csv"
    # En invierno Chile está en UTC-4: 1-07 a las 03:30 UTC es el 30-06 a las 23:30.
    invierno = armar_datos(OBJETIVO, [ESCANEO], [hallazgo(1)],
                           generado_en=datetime(2026, 7, 1, 3, 30, tzinfo=timezone.utc))
    assert nombre_archivo(invierno, "csv") == "informe_juiceshop-3000_20260630.csv"
