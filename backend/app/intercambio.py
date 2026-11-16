"""
SentinelAI · Intercambio de enriquecimientos y validaciones entre equipos.

Cada integrante tiene su propia base y los ids no coinciden entre bases. Lo
que sí coincide es:

    el objetivo        targets.base_url (http://juiceshop:3000)
    el hallazgo        su dedupe_key dentro de ese objetivo
    la fila exportada  su uuid, que se conserva al importar

Flujo del golden set entre varios revisores:

    1. Joaquín enriquece con Ollama real y exporta los enriquecimientos.
    2. Cada uno los importa: todos juzgan las mismas sugerencias.
    3. Cada uno anota en su dashboard y exporta sus validaciones.
    4. Luciano importa todas y calcula las métricas.

Reglas al importar (todo en una transacción; el llamador hace commit):

- Un uuid que ya existe se omite. Si existe con contenido distinto es un
  conflicto: se reporta y no se pisa. `is_current` no cuenta como diferencia,
  porque cambia con la vida de cada base.
- Un hallazgo que no está en esta base se omite y se reporta. Nunca se crean
  hallazgos.
- La vigencia de un enriquecimiento la decide `registrar_enriquecimiento`, la
  misma regla del enriquecimiento con Ollama: un fallo no desplaza a un ok.
- Una validación cuyo enriquecimiento no está en la base se omite: unas
  banderas ai_* sin la sugerencia que juzgaron no sirven para las métricas.
  Al reimportar después de traer los enriquecimientos, entra normal.
- El estado de cada hallazgo tocado se recalcula con `recalcular_estado`, la
  misma regla de POST /findings/{id}/validaciones.
- Si el archivo no es válido (formato, versión, enums, fechas, uuids
  repetidos), no se importa nada.
"""

from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from typing import Annotated, Any, Literal

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, ValidationError,
    model_validator,
)
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.enriquecimiento import registrar_enriquecimiento
from app.models import (
    AiEnrichment, CategoriaOwasp, DecisionValidacion, EstadoIA, Finding, Prioridad,
    Target, Validation,
)
from app.validacion import recalcular_estado

FORMATO = "sentinelai-intercambio"
VERSION = 1
TIPOS = ("enriquecimientos", "validaciones")

# Campos que viajan tal cual, con el mismo nombre que la columna.
CAMPOS_ENRIQUECIMIENTO = (
    "state", "owasp_version", "owasp_category", "priority", "confidence",
    "explanation", "impact", "remediation_summary", "remediation_steps",
    "failure_reason", "model", "prompt_version", "prompt_sha256", "attempts",
    "latency_ms", "generated_at", "is_current",
)
CAMPOS_VALIDACION = (
    "decision", "reviewer", "reviewed_at", "priority_override", "comment",
    "ai_owasp_correcto", "ai_prioridad_correcta", "ai_remediacion_util",
    "ai_alucinacion", "ai_nota",
)
BANDERAS = ("ai_owasp_correcto", "ai_prioridad_correcta", "ai_remediacion_util", "ai_alucinacion")
# Lo que puede diferir entre bases sin que sea un conflicto.
NO_COMPARAR = {"is_current"}


# ── Formato del archivo ───────────────────────────────────────────────────

class _Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class RefHallazgo(_Estricto):
    base_url: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    dedupe_key: Annotated[str, StringConstraints(min_length=1, max_length=16)]
    # Solo ayuda legible: no se usan para buscar el hallazgo.
    titulo: str | None = None
    ruta: str | None = None


class ItemEnriquecimiento(_Estricto):
    uuid: uuid.UUID
    hallazgo: RefHallazgo
    state: EstadoIA
    owasp_version: str | None
    owasp_category: CategoriaOwasp | None
    priority: Prioridad | None
    confidence: Annotated[float, Field(ge=0, le=1)] | None
    explanation: str | None
    impact: str | None
    remediation_summary: str | None
    remediation_steps: list | None
    failure_reason: Annotated[str, StringConstraints(max_length=40)] | None
    model: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    prompt_version: Annotated[str, StringConstraints(min_length=1, max_length=30)]
    prompt_sha256: Annotated[str, StringConstraints(max_length=64)] | None
    attempts: Annotated[int, Field(ge=1)]
    latency_ms: int | None
    generated_at: AwareDatetime
    is_current: bool

    @model_validator(mode="after")
    def _como_la_base(self):
        # Las mismas restricciones que ck_enrichment_*: mejor rechazarlo acá,
        # con un mensaje claro, que con un error de PostgreSQL a mitad de camino.
        if self.state == EstadoIA.failed.value and any(
            v is not None for v in (self.owasp_category, self.priority,
                                    self.explanation, self.remediation_summary)
        ):
            raise ValueError("un enriquecimiento fallido no puede traer owasp, prioridad ni textos")
        if self.state == EstadoIA.ok.value and self.failure_reason is not None:
            raise ValueError("failure_reason solo aplica a un enriquecimiento fallido")
        return self


class ItemValidacion(_Estricto):
    uuid: uuid.UUID
    hallazgo: RefHallazgo
    enrichment_uuid: uuid.UUID | None
    decision: DecisionValidacion
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    reviewed_at: AwareDatetime
    priority_override: Prioridad | None
    comment: str | None
    ai_owasp_correcto: bool | None
    ai_prioridad_correcta: bool | None
    ai_remediacion_util: bool | None
    ai_alucinacion: bool | None
    ai_nota: str | None

    @model_validator(mode="after")
    def _banderas_con_sugerencia(self):
        # Igual que la API (T-057): opinar de la IA exige decir qué sugerencia.
        opina = any(getattr(self, b) is not None for b in BANDERAS) or self.ai_nota is not None
        if opina and self.enrichment_uuid is None:
            raise ValueError("banderas ai_* sin enrichment_uuid: no se sabe qué sugerencia juzgaron")
        return self


class Archivo(_Estricto):
    formato: Literal["sentinelai-intercambio"]
    version: Literal[1]
    tipo: Literal["enriquecimientos", "validaciones"]
    exportado_en: AwareDatetime
    base_origen: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    items: list[dict[str, Any]]


class ArchivoInvalido(Exception):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores))
        self.errores = errores


def _errores(e: ValidationError, prefijo: str = "") -> list[str]:
    return [
        f"{prefijo}{'.'.join(str(p) for p in err['loc']) or '(raíz)'}: {err['msg']}"
        for err in e.errors()
    ]


def validar_archivo(d: Any) -> tuple[Archivo, list[ItemEnriquecimiento] | list[ItemValidacion]]:
    """Valida el archivo completo. Lanza ArchivoInvalido con TODOS los errores."""
    if not isinstance(d, dict):
        raise ArchivoInvalido(["el archivo no es un objeto JSON"])
    try:
        archivo = Archivo.model_validate(d)
    except ValidationError as e:
        raise ArchivoInvalido(_errores(e)) from None

    modelo = ItemEnriquecimiento if archivo.tipo == "enriquecimientos" else ItemValidacion
    items, errores, vistos = [], [], set()
    for n, crudo in enumerate(archivo.items):
        try:
            item = modelo.model_validate(crudo)
        except ValidationError as e:
            errores += _errores(e, prefijo=f"items[{n}].")
            continue
        if item.uuid in vistos:
            errores.append(f"items[{n}].uuid: {item.uuid} aparece más de una vez")
        vistos.add(item.uuid)
        items.append(item)
    if errores:
        raise ArchivoInvalido(errores)
    return archivo, items


# ── Exportar ──────────────────────────────────────────────────────────────

def _json(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if hasattr(v, "value"):  # enums
        return v.value
    return v


def _ref(f: Finding, t: Target) -> dict:
    return {"base_url": t.base_url, "dedupe_key": f.dedupe_key, "titulo": f.titulo, "ruta": f.path_template}


def _item_enriquecimiento(e: AiEnrichment, f: Finding, t: Target) -> dict:
    return {"uuid": str(e.id), "hallazgo": _ref(f, t),
            **{c: _json(getattr(e, c)) for c in CAMPOS_ENRIQUECIMIENTO}}


def _item_validacion(v: Validation, f: Finding, t: Target) -> dict:
    return {"uuid": str(v.id), "hallazgo": _ref(f, t),
            "enrichment_uuid": _json(v.enrichment_id),
            **{c: _json(getattr(v, c)) for c in CAMPOS_VALIDACION}}


def base_origen(db: Session) -> str:
    """Nombre de la base y un id corto del cluster. Nunca credenciales."""
    nombre = db.scalar(text("SELECT current_database()"))
    try:
        with db.begin_nested():
            ident = db.scalar(text("SELECT system_identifier::text FROM pg_control_system()"))
    except Exception:  # noqa: BLE001 — sin permiso para leerlo, basta el nombre
        return nombre
    return f"{nombre}@{hashlib.sha256(ident.encode()).hexdigest()[:8]}"


def exportar(db: Session, que: str, revisor: str | None = None) -> dict:
    """El archivo de intercambio, listo para json.dumps. No escribe nada."""
    if que not in TIPOS:
        raise ValueError(f"tipo desconocido: {que}")
    if que == "enriquecimientos":
        filas = db.execute(
            select(AiEnrichment, Finding, Target)
            .join(Finding, AiEnrichment.finding_id == Finding.id)
            .join(Target, Finding.target_id == Target.id)
            .order_by(Target.base_url, Finding.dedupe_key, AiEnrichment.generated_at, AiEnrichment.id)
        ).all()
        items = [_item_enriquecimiento(*fila) for fila in filas]
    else:
        consulta = (
            select(Validation, Finding, Target)
            .join(Finding, Validation.finding_id == Finding.id)
            .join(Target, Finding.target_id == Target.id)
            .order_by(Validation.reviewed_at, Validation.id)
        )
        if revisor is not None:
            consulta = consulta.where(Validation.reviewer == revisor.strip())
        items = [_item_validacion(*fila) for fila in db.execute(consulta).all()]
    return {
        "formato": FORMATO,
        "version": VERSION,
        "tipo": que,
        "exportado_en": datetime.now(timezone.utc).isoformat(),
        "base_origen": base_origen(db),
        "items": items,
    }


# ── Importar ──────────────────────────────────────────────────────────────

@dataclass
class Reporte:
    tipo: str
    base_origen: str
    total: int = 0
    importados: int = 0
    ya_estaban: int = 0
    conflictos: list[str] = field(default_factory=list)
    no_encontrados: list[str] = field(default_factory=list)
    sin_enriquecimiento: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)

    def texto(self, simulado: bool = False) -> str:
        lineas = []
        if simulado:
            lineas.append("SIMULACIÓN: no se guardó nada (rollback).")
        lineas += [
            f"Importación de {self.tipo} desde {self.base_origen} ({self.total} en el archivo)",
            f"  importados ................ {self.importados}",
            f"  ya estaban ................ {self.ya_estaban}",
            f"  conflictos (no se pisan) .. {len(self.conflictos)}",
            f"  hallazgos no encontrados .. {len(self.no_encontrados)}",
        ]
        if self.tipo == "validaciones":
            lineas.append(f"  sin su enriquecimiento .... {len(self.sin_enriquecimiento)}")
        for titulo, lista in (
            ("Conflictos", self.conflictos),
            ("Hallazgos no encontrados", self.no_encontrados),
            ("Validaciones sin su enriquecimiento", self.sin_enriquecimiento),
            ("Avisos", self.avisos),
            ("Estados recalculados", self.estados),
        ):
            if lista:
                lineas.append(f"\n{titulo}:")
                lineas += [f"  - {x}" for x in lista]
        return "\n".join(lineas)


def _legible(ref: RefHallazgo) -> str:
    return f"{ref.titulo or '(sin título)'} [{ref.base_url} · {ref.dedupe_key}]"


class _Hallazgos:
    """Busca hallazgos por (base_url, dedupe_key), con caché."""

    def __init__(self, db: Session):
        self.db, self.cache = db, {}

    def __call__(self, ref: RefHallazgo) -> Finding | None:
        clave = (ref.base_url, ref.dedupe_key)
        if clave not in self.cache:
            self.cache[clave] = self.db.scalar(
                select(Finding).join(Target, Finding.target_id == Target.id)
                .where(Target.base_url == ref.base_url, Finding.dedupe_key == ref.dedupe_key)
            )
        return self.cache[clave]


def _diferencias(existente: dict, item: BaseModel) -> list[str]:
    """Campos en que difieren la fila de esta base y el ítem del archivo."""
    nuevo = item.model_dump(mode="json", exclude={"uuid", "hallazgo"})
    actual = {k: v for k, v in existente.items() if k in nuevo}
    distintos = []
    for k, v in nuevo.items():
        if k in NO_COMPARAR:
            continue
        a = actual.get(k)
        if k.endswith("_at"):  # misma instante aunque cambie la zona horaria
            a, v = datetime.fromisoformat(a), datetime.fromisoformat(v.replace("Z", "+00:00"))
        if a != v:
            distintos.append(k)
    return distintos


def _importar_enriquecimientos(db: Session, items: list[ItemEnriquecimiento], r: Reporte) -> None:
    buscar = _Hallazgos(db)
    for it in sorted(items, key=lambda i: (i.generated_at, str(i.uuid))):
        f = buscar(it.hallazgo)
        if f is None:
            r.no_encontrados.append(f"enriquecimiento {it.uuid}: {_legible(it.hallazgo)}")
            continue
        existente = db.get(AiEnrichment, it.uuid)
        if existente is not None:
            if existente.finding_id != f.id:
                r.conflictos.append(f"enriquecimiento {it.uuid}: en esta base es de otro hallazgo")
            elif d := _diferencias(_item_enriquecimiento(existente, f, f.target), it):
                r.conflictos.append(f"enriquecimiento {it.uuid} ({_legible(it.hallazgo)}): difiere en {', '.join(d)}")
            else:
                r.ya_estaban += 1
            continue

        campos = it.model_dump(exclude={"uuid", "hallazgo"})
        fila = AiEnrichment(id=it.uuid, finding_id=f.id, **campos)
        quedo_vigente = registrar_enriquecimiento(db, f.id, fila)
        r.importados += 1
        if it.is_current and not quedo_vigente:
            r.avisos.append(
                f"enriquecimiento {it.uuid} ({_legible(it.hallazgo)}): era vigente en "
                f"{r.base_origen} pero falló, y aquí hay una sugerencia ok vigente; "
                "entró como histórico"
            )


def _importar_validaciones(db: Session, items: list[ItemValidacion], r: Reporte) -> None:
    buscar = _Hallazgos(db)
    tocados: dict[uuid.UUID, Finding] = {}
    for it in sorted(items, key=lambda i: (i.reviewed_at, str(i.uuid))):
        f = buscar(it.hallazgo)
        if f is None:
            r.no_encontrados.append(f"validación {it.uuid} de {it.reviewer}: {_legible(it.hallazgo)}")
            continue
        existente = db.get(Validation, it.uuid)
        if existente is not None:
            if existente.finding_id != f.id:
                r.conflictos.append(f"validación {it.uuid}: en esta base es de otro hallazgo")
            elif d := _diferencias(_item_validacion(existente, f, f.target), it):
                r.conflictos.append(f"validación {it.uuid} de {it.reviewer}: difiere en {', '.join(d)}")
            else:
                r.ya_estaban += 1
            continue

        if it.enrichment_uuid is not None:
            sugerencia = db.get(AiEnrichment, it.enrichment_uuid)
            if sugerencia is None:
                r.sin_enriquecimiento.append(
                    f"validación {it.uuid} de {it.reviewer} ({_legible(it.hallazgo)}): falta el "
                    f"enriquecimiento {it.enrichment_uuid}; importa primero los enriquecimientos "
                    f"de {r.base_origen}"
                )
                continue
            if sugerencia.finding_id != f.id:
                r.conflictos.append(
                    f"validación {it.uuid}: el enriquecimiento {it.enrichment_uuid} es de otro hallazgo en esta base"
                )
                continue
            if sugerencia.state != EstadoIA.ok and any(getattr(it, b) is not None for b in BANDERAS):
                r.conflictos.append(
                    f"validación {it.uuid}: trae banderas ai_* sobre un enriquecimiento fallido"
                )
                continue

        if f.id not in tocados:
            # Mismo bloqueo que la API: una decisión simultánea en el
            # dashboard se ordena con la importación.
            db.execute(select(Finding.id).where(Finding.id == f.id).with_for_update())
            tocados[f.id] = f
        db.add(Validation(
            id=it.uuid, finding_id=f.id, enrichment_id=it.enrichment_uuid,
            **it.model_dump(include=set(CAMPOS_VALIDACION)),
        ))
        r.importados += 1

    for f in tocados.values():
        antes = f.status
        despues = recalcular_estado(db, f)
        if despues is not None and despues != antes:
            r.estados.append(f"{f.titulo}: {antes.value} → {despues.value}")


def importar(db: Session, d: Any) -> Reporte:
    """Importa un archivo de intercambio. No hace commit: lo decide el llamador
    (commit normal, rollback con --simular). Lanza ArchivoInvalido antes de
    tocar la base si el archivo no es válido."""
    archivo, items = validar_archivo(d)
    r = Reporte(tipo=archivo.tipo, base_origen=archivo.base_origen, total=len(items))
    if archivo.tipo == "enriquecimientos":
        _importar_enriquecimientos(db, items, r)
    else:
        _importar_validaciones(db, items, r)
    db.flush()
    return r


# ── Métricas ──────────────────────────────────────────────────────────────

def kappa(pares: list[tuple[bool, bool]]) -> float | None:
    """κ de Cohen para dos revisores con respuestas sí/no.

    None si no hay pares o si el acuerdo esperado por azar es 1 (los dos
    respondieron siempre lo mismo): ahí κ no está definido.
    """
    n = len(pares)
    if n == 0:
        return None
    po = sum(a == b for a, b in pares) / n
    si_a = sum(a for a, _ in pares) / n
    si_b = sum(b for _, b in pares) / n
    pe = si_a * si_b + (1 - si_a) * (1 - si_b)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def _pct(valores: list[bool]) -> dict:
    si = sum(valores)
    n = len(valores)
    return {"si": si, "no": n - si, "n": n, "pct": round(100 * si / n, 1) if n else None}


def metricas(db: Session) -> dict:
    """Métricas del golden set sobre las validaciones con banderas ai_*.

    De cada revisor cuenta solo su ÚLTIMA validación por (hallazgo,
    enriquecimiento): si cambió de opinión, vale la última. Los null ("no sé")
    se excluyen de cada porcentaje y de cada par del acuerdo.
    """
    filas = db.scalars(select(Validation).order_by(Validation.reviewed_at, Validation.id)).all()
    ultima: dict[tuple, Validation] = {}
    for v in filas:
        if any(getattr(v, b) is not None for b in BANDERAS):
            ultima[(v.reviewer.strip(), v.finding_id, v.enrichment_id)] = v

    por_revisor: dict[str, list[Validation]] = defaultdict(list)
    for (revisor, _, _), v in ultima.items():
        por_revisor[revisor].append(v)

    def resumen(vs: list[Validation]) -> dict:
        return {"validaciones": len(vs),
                **{b: _pct([getattr(v, b) for v in vs if getattr(v, b) is not None]) for b in BANDERAS}}

    revisores_por_hallazgo: dict[uuid.UUID, set[str]] = defaultdict(set)
    for (revisor, finding_id, _) in ultima:
        revisores_por_hallazgo[finding_id].add(revisor)

    acuerdo = []
    for a, b in combinations(sorted(por_revisor), 2):
        pares = []
        for (revisor, finding_id, enrichment_id), va in ultima.items():
            if revisor != a or enrichment_id is None:
                continue
            vb = ultima.get((b, finding_id, enrichment_id))
            if vb is None or va.ai_owasp_correcto is None or vb.ai_owasp_correcto is None:
                continue
            pares.append((va.ai_owasp_correcto, vb.ai_owasp_correcto))
        if pares:
            acuerdo.append({
                "revisores": [a, b],
                "n": len(pares),
                "acuerdo_pct": round(100 * sum(x == y for x, y in pares) / len(pares), 1),
                "kappa": kappa(pares),
            })

    return {
        "validaciones_con_banderas": len(ultima),
        "revisores": {r: resumen(vs) for r, vs in sorted(por_revisor.items())},
        "total": resumen(list(ultima.values())),
        "hallazgos_con_2_o_mas_revisores": sum(len(s) >= 2 for s in revisores_por_hallazgo.values()),
        "acuerdo_ai_owasp_correcto": acuerdo,
    }


ETIQUETAS = {
    "ai_owasp_correcto": "OWASP correcto",
    "ai_prioridad_correcta": "prioridad correcta",
    "ai_remediacion_util": "remediación útil",
    "ai_alucinacion": "alucinación",
}
N_CHICO = 10


def metricas_texto(m: dict) -> str:
    def fila(nombre: str, r: dict) -> list[str]:
        out = [f"{nombre} ({r['validaciones']} validaciones)"]
        for b, etiqueta in ETIQUETAS.items():
            p = r[b]
            valor = "sin respuestas" if p["n"] == 0 else f"{p['pct']:5.1f} %  ({p['si']} de {p['n']})"
            out.append(f"  {etiqueta:<20} {valor}")
        return out

    lineas = [f"Validaciones con banderas ai_* (última de cada revisor): {m['validaciones_con_banderas']}", ""]
    for nombre, r in m["revisores"].items():
        lineas += fila(nombre, r) + [""]
    lineas += fila("TOTAL", m["total"]) + [""]
    lineas.append(f"Hallazgos con 2 o más revisores: {m['hallazgos_con_2_o_mas_revisores']}")
    lineas.append("")
    lineas.append("Acuerdo en «OWASP correcto» (sin contar «no sé»):")
    if not m["acuerdo_ai_owasp_correcto"]:
        lineas.append("  ningún par de revisores respondió el mismo hallazgo y enriquecimiento")
    for p in m["acuerdo_ai_owasp_correcto"]:
        k = "no definido (respondieron siempre lo mismo)" if p["kappa"] is None else f"{p['kappa']:.2f}"
        aviso = "  ← n chico: el κ engaña" if p["n"] < N_CHICO else ""
        lineas.append(
            f"  {p['revisores'][0]} / {p['revisores'][1]}: n = {p['n']}, "
            f"acuerdo {p['acuerdo_pct']:.1f} %, κ = {k}{aviso}"
        )
    return "\n".join(lineas)
