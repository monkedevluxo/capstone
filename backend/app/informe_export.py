"""
SentinelAI · Exportar el informe técnico a PDF, CSV y XLSX.

Parte de los mismos datos que el informe HTML (app/informe.armar_datos), así
que los tres formatos cuentan lo mismo: un hallazgo por fila, con la prioridad
final, la referencia de la tabla CWE → OWASP, la sugerencia vigente de la IA y
la última decisión humana. El PDF es el mismo HTML con su hoja de impresión,
convertido con WeasyPrint.

Los textos vienen de ZAP, de la IA o de una persona, y la evidencia de ZAP trae
payloads reales. Para que una celda que empieza con "=", "+", "-" o "@" no se
ejecute como fórmula al abrir el archivo en una planilla (inyección de
fórmulas, CWE-1236), en el CSV se antepone un apóstrofo y en el XLSX la celda
se guarda como texto.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.informe import (ETIQUETA_DECISION, ETIQUETA_ESTADO, ETIQUETA_SEVERIDAD, MOTIVO_REVISION,
                         renderizar_html)

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TIPO_CSV = "text/csv; charset=utf-8"
TIPO_PDF = "application/pdf"

# Zona del equipo y del laboratorio, para la fecha del nombre de archivo.
ZONA_LOCAL = ZoneInfo("America/Santiago")

# (encabezado, ancho en el XLSX, cómo sacar el valor de un hallazgo)
COLUMNAS: list[tuple[str, int, Any]] = [
    ("N°", 5, lambda h, n, seccion: n),
    ("Sección", 11, lambda h, n, seccion: seccion),
    ("Título", 42, lambda h, n, s: h["titulo"]),
    ("Estado", 15, lambda h, n, s: ETIQUETA_ESTADO.get(h["estado"], h["estado"])),
    ("Severidad", 11, lambda h, n, s: ETIQUETA_SEVERIDAD.get(h["severidad"], h["severidad"])),
    ("Severidad ZAP", 13, lambda h, n, s: h["severidad_zap"]),
    ("Confianza ZAP", 13, lambda h, n, s: h["confianza_zap"]),
    ("CWE", 7, lambda h, n, s: h["cwe"]),
    ("Prioridad", 9, lambda h, n, s: h["prioridad"]),
    ("Prioridad fijada por", 18, lambda h, n, s: h["prioridad_origen"]),
    ("OWASP (tabla CWE)", 17, lambda h, n, s: h["owasp_referencia"]),
    ("OWASP (IA)", 12, lambda h, n, s: (h["ia"] or {}).get("owasp")),
    ("Revisar", 8, lambda h, n, s: "Sí" if h["revisar"] else "No"),
    ("Motivo para revisar", 22, lambda h, n, s: MOTIVO_REVISION.get(h["motivo_revision"],
                                                                     h["motivo_revision"])),
    ("Prioridad (IA)", 13, lambda h, n, s: (h["ia"] or {}).get("prioridad")),
    ("Confianza declarada (IA)", 13, lambda h, n, s: (h["ia"] or {}).get("confianza")),
    ("Remediación (IA)", 50, lambda h, n, s: (h["ia"] or {}).get("remediacion")),
    ("Método", 8, lambda h, n, s: h["ubicacion"]["metodo"]),
    ("Ruta", 34, lambda h, n, s: h["ubicacion"]["ruta"]),
    ("Parámetro", 14, lambda h, n, s: h["ubicacion"]["parametro"]),
    ("Ocurrencias", 11, lambda h, n, s: h["ubicacion"]["ocurrencias"]),
    ("Evidencia", 40, lambda h, n, s: h["evidencia"]["fragmento"]),
    ("Decisión", 16, lambda h, n, s: ETIQUETA_DECISION.get((h["decision"] or {}).get("decision"),
                                                         (h["decision"] or {}).get("decision"))),
    ("Revisor", 18, lambda h, n, s: (h["decision"] or {}).get("revisor")),
    ("Fecha de la decisión", 18, lambda h, n, s: (h["decision"] or {}).get("fecha")),
    ("Comentario", 40, lambda h, n, s: (h["decision"] or {}).get("comentario")),
    ("Clave de deduplicación", 20, lambda h, n, s: h["dedupe_key"]),
    ("ID", 38, lambda h, n, s: h["id"]),
]

_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def filas(datos: dict) -> list[list[Any]]:
    """Un hallazgo por fila: primero los vigentes, después los descartados."""
    resultado = []
    n = 0
    for seccion, lista in (("Vigente", datos["hallazgos"]), ("Descartado", datos["descartados"])):
        for h in lista:
            n += 1
            resultado.append([valor(h, n, seccion) for _, _, valor in COLUMNAS])
    return resultado


def _celda_csv(v: Any) -> Any:
    if isinstance(v, str) and v.startswith(_PELIGROSOS):
        return "'" + v
    return "" if v is None else v


def a_csv(datos: dict) -> bytes:
    """CSV separado por comas, en UTF-8 con BOM para que Excel lea los tildes."""
    salida = io.StringIO(newline="")
    escritor = csv.writer(salida)
    escritor.writerow([c[0] for c in COLUMNAS])
    for fila in filas(datos):
        escritor.writerow([_celda_csv(v) for v in fila])
    return salida.getvalue().encode("utf-8-sig")


_ENCABEZADO = Font(bold=True, color="FFFFFF")
_FONDO_ENCABEZADO = PatternFill("solid", fgColor="14263D")
_TITULO = Font(bold=True, size=14, color="14263D")
_NEGRITA = Font(bold=True)
_ARRIBA = Alignment(vertical="top", wrap_text=True)


def _texto(celda, v: Any) -> None:
    """Escribe el valor; un texto siempre queda como texto, nunca como fórmula.

    Quita los caracteres de control que el formato XLSX no admite: la evidencia
    de ZAP puede traerlos y openpyxl se niega a guardarlos.
    """
    if isinstance(v, str):
        v = ILLEGAL_CHARACTERS_RE.sub("", v)
    celda.value = v
    if isinstance(v, str):
        celda.data_type = "s"


def _encabezados(hoja, nombres: list[str], fila: int = 1) -> None:
    for col, nombre in enumerate(nombres, start=1):
        c = hoja.cell(row=fila, column=col, value=nombre)
        c.font, c.fill = _ENCABEZADO, _FONDO_ENCABEZADO
        c.alignment = Alignment(vertical="center", wrap_text=True)


def _porcentaje(m: dict) -> str:
    return f"{m['si']}/{m['n']} ({round(100 * m['si'] / m['n'])} %)" if m["n"] else "sin respuestas"


def a_xlsx(datos: dict) -> bytes:
    """Libro con tres hojas: Resumen, Hallazgos y Escaneos."""
    libro = Workbook()

    resumen = libro.active
    resumen.title = "Resumen"
    r = datos["resumen"]
    m = datos["metricas"]
    obj = datos["objetivo"]
    resumen["A1"] = "Informe técnico · SentinelAI"
    resumen["A1"].font = _TITULO
    bloques: list[tuple[str, list[tuple[str, Any]]]] = [
        ("Objetivo", [("Nombre", obj["nombre"]), ("URL", obj["url"]), ("Entorno", obj["entorno"]),
                      ("Generado", datos["generado_en"])]),
        ("Hallazgos", [("Total", r["total"]), ("Vigentes", r["vigentes"]),
                       ("Descartados", r["descartados"]), ("Por revisar primero", r["por_revisar"]),
                       ("Con sugerencia de la IA", r["con_ia"]),
                       ("Con el enriquecimiento fallido", r["ia_fallida"]),
                       ("Con decisión humana", r["con_decision"])]),
        ("Vigentes por severidad", [(ETIQUETA_SEVERIDAD.get(k, k), v)
                                    for k, v in r["por_severidad"].items()]),
        ("Vigentes por prioridad", list(r["por_prioridad"].items())),
        ("Calidad de la IA (última respuesta de cada revisor)", [
            ("Revisores", ", ".join(m["revisores"]) or "ninguno"),
            ("Categoría OWASP correcta", _porcentaje(m["acierto_owasp"])),
            ("Prioridad correcta", _porcentaje(m["acierto_prioridad"])),
            ("Remediación útil", _porcentaje(m["remediacion_util"])),
            ("Inventó información", _porcentaje(m["alucinacion"])),
        ]),
    ]
    fila = 3
    for titulo, pares in bloques:
        resumen.cell(row=fila, column=1, value=titulo).font = _NEGRITA
        fila += 1
        for rotulo, v in pares:
            resumen.cell(row=fila, column=1, value=rotulo)
            _texto(resumen.cell(row=fila, column=2), v)
            fila += 1
        fila += 1
    resumen.column_dimensions["A"].width = 30
    resumen.column_dimensions["B"].width = 40

    hallazgos = libro.create_sheet("Hallazgos")
    _encabezados(hallazgos, [c[0] for c in COLUMNAS])
    for i, valores in enumerate(filas(datos), start=2):
        for col, v in enumerate(valores, start=1):
            c = hallazgos.cell(row=i, column=col)
            _texto(c, v)
            c.alignment = _ARRIBA
    for col, (_, ancho, _) in enumerate(COLUMNAS, start=1):
        hallazgos.column_dimensions[get_column_letter(col)].width = ancho
    hallazgos.freeze_panes = "D2"
    hallazgos.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNAS))}{max(hallazgos.max_row, 1)}"

    escaneos = libro.create_sheet("Escaneos")
    _encabezados(escaneos, ["Herramienta", "Versión", "Inicio", "SHA-256 del reporte"])
    for i, s in enumerate(datos["escaneos"], start=2):
        for col, v in enumerate([s["herramienta"], s["version"], s["inicio"], s["sha256"]], start=1):
            _texto(escaneos.cell(row=i, column=col), v)
    for letra, ancho in zip("ABCD", (12, 10, 20, 68)):
        escaneos.column_dimensions[letra].width = ancho

    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def a_pdf(datos: dict) -> bytes:
    """El informe en PDF (A4, con número de página), desde la versión pdf del HTML.

    WeasyPrint se importa acá y no arriba: necesita Pango del sistema, y así la
    API arranca igual en una máquina sin esas librerías (solo falla el PDF).
    """
    from weasyprint import HTML

    return HTML(string=renderizar_html(datos, pdf=True)).write_pdf()


def nombre_archivo(datos: dict, extension: str) -> str:
    """Ej: informe_juiceshop-3000_20261124.xlsx

    La fecha es la del día en Chile: generado_en viene en UTC, y desde las
    21:00 (20:00 en invierno) en UTC ya es el día siguiente.
    """
    host = re.sub(r"^[a-z]+://", "", datos["objetivo"]["url"] or "objetivo")
    host = re.sub(r"[^A-Za-z0-9]+", "-", host).strip("-").lower() or "objetivo"
    generado = datetime.fromisoformat(datos["generado_en"]) if datos["generado_en"] else datetime.now(ZONA_LOCAL)
    return f"informe_{host}_{generado.astimezone(ZONA_LOCAL):%Y%m%d}.{extension}"
