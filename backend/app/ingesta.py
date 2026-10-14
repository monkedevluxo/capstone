"""
SentinelAI · Ingesta de reportes de ZAP (tareas T-021, T-022, T-024).

Flujo de UN reporte:

    JSON crudo de ZAP
      -> ¿el objetivo es del laboratorio?  (si no, se rechaza: Ley 21.459)
      -> ¿este mismo reporte ya se importó? (hash del JSON; si sí, se rechaza)
      -> target (se crea la primera vez) y scan
      -> parser de Joaquín (app/parsers/zap.py)
      -> por cada hallazgo: INSERT ... ON CONFLICT (target_id, dedupe_key)
             nuevo     -> se crea con sus instancias
             repetido  -> se actualiza last_seen_at y occurrences
      -> una observación por hallazgo: qué escaneo lo vio y cuántas veces

La deduplicación la hace la base (uq_findings_target_dedupe), no el código:
dos importaciones simultáneas no pueden crear el mismo hallazgo dos veces.

Todo ocurre en UNA transacción: si algo falla a la mitad, no queda un
escaneo importado a medias.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    EstadoEscaneo,
    Finding,
    FindingInstance,
    FindingObservation,
    Herramienta,
    Scan,
    Target,
)
from app.parsers.zap import parsear_reporte

MAX_INSTANCIAS = 50


class ErrorIngesta(Exception):
    """Error esperado: el reporte no se puede importar. Lleva un código HTTP."""

    def __init__(self, mensaje: str, http: int = 422, **extra):
        super().__init__(mensaje)
        self.http = http
        self.extra = extra


@dataclass
class ResumenIngesta:
    scan_id: str
    target_id: str
    objetivo: str
    hallazgos_en_reporte: int = 0
    nuevos: int = 0
    repetidos: int = 0
    descartados: int = 0
    por_severidad: dict[str, int] = field(default_factory=dict)

    def como_dict(self) -> dict:
        return self.__dict__.copy()


def _hash_reporte(crudo: dict) -> str:
    # Serialización canónica: el mismo reporte da el mismo hash aunque el
    # orden de las claves o los espacios cambien entre lecturas.
    canon = json.dumps(crudo, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _objetivo(crudo: dict) -> str:
    """Saca la URL base del reporte y verifica que sea del laboratorio."""
    sitios = crudo.get("site") or []
    if not isinstance(sitios, list) or not sitios:
        raise ErrorIngesta("el reporte no trae 'site': no parece un JSON de ZAP")

    nombres = {s.get("@name") for s in sitios if s.get("@name")}
    if len(nombres) != 1:
        raise ErrorIngesta(f"el reporte debe traer un solo objetivo, trae {len(nombres)}")
    base_url = nombres.pop().rstrip("/")

    host = urlsplit(base_url).hostname or ""
    permitidos = {h.strip().lower() for h in settings.LAB_HOSTS.split(",") if h.strip()}
    if host.lower() not in permitidos:
        # Segunda barrera ética, antes de que la base la ataje con su CHECK:
        # no se importan resultados de sistemas fuera del laboratorio.
        raise ErrorIngesta(
            f"'{host}' no es un objetivo del laboratorio. Permitidos: {sorted(permitidos)}",
            http=403,
        )
    return base_url


def importar_reporte(db: Session, crudo: dict) -> ResumenIngesta:
    """
    Importa un reporte de ZAP ya cargado con json.load().

    Lanza ErrorIngesta si el reporte no es válido, no es del laboratorio o ya
    fue importado. No hace commit: lo hace quien llama (la ruta o el script).
    """
    base_url = _objetivo(crudo)
    sha = _hash_reporte(crudo)

    previo = db.scalar(select(Scan.id).where(Scan.report_sha256 == sha))
    if previo:
        raise ErrorIngesta("este reporte ya fue importado", http=409, scan_id=str(previo))

    # Objetivo: se crea la primera vez que aparece.
    target = db.scalar(select(Target).where(Target.base_url == base_url))
    if target is None:
        target = Target(nombre=urlsplit(base_url).hostname, base_url=base_url, environment="lab")
        db.add(target)
        db.flush()

    ahora = datetime.now(timezone.utc)
    scan = Scan(
        target_id=target.id,
        tool=Herramienta.zap,
        tool_version=crudo.get("@version"),
        status=EstadoEscaneo.importado,
        finished_at=ahora,
        report_sha256=sha,
    )
    db.add(scan)
    db.flush()

    hallazgos = parsear_reporte(crudo)
    r = ResumenIngesta(
        scan_id=str(scan.id),
        target_id=str(target.id),
        objetivo=base_url,
        hallazgos_en_reporte=len(hallazgos),
    )

    for h in hallazgos:
        # Defensa ante casos borde del parser: sin URL o sin regla no hay
        # hallazgo que se pueda guardar honestamente.
        if not h.get("url") or h.get("rule_id") in (None, "", "None"):
            r.descartados += 1
            continue

        valores = {
            "target_id": target.id,
            "tool": Herramienta.zap,
            "rule_id": h["rule_id"],
            "rule_name": h["rule_name"],
            "source_raw": h["source_raw"],
            "titulo": h["titulo"],
            "descripcion": h["descripcion"],
            "url": h["url"],
            "path_template": h["path_template"],
            "method": h["method"],
            "param": h["param"],
            "evidence_snippet": h["evidence_snippet"],
            "severity": h["severity"],
            "severity_tool_raw": h["severity_tool_raw"],
            "tool_confidence": h["tool_confidence"],
            "cwe_id": h["cwe_id"],
            "wasc_id": h["wasc_id"],
            "dedupe_key": h["dedupe_key"],
            "correlation_key": h["correlation_key"],
            "occurrences": h["occurrences"],
        }
        stmt = insert(Finding).values(**valores)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_findings_target_dedupe",
            set_={
                "last_seen_at": func.now(),
                # occurrences refleja el último escaneo que lo vio; el conteo
                # de cada escaneo queda en finding_observations.instance_count.
                "occurrences": stmt.excluded.occurrences,
            },
        ).returning(
            Finding.id,
            # xmax = 0 solo en filas recién insertadas: distingue nuevo de repetido.
            literal_column("(xmax = 0)").label("es_nuevo"),
        )
        fila = db.execute(stmt).one()

        if fila.es_nuevo:
            r.nuevos += 1
            for inst in h["instances"][:MAX_INSTANCIAS]:
                if inst.get("url"):
                    db.add(FindingInstance(
                        finding_id=fila.id,
                        url=inst["url"],
                        method=inst.get("method"),
                        param=inst.get("param"),
                    ))
        else:
            r.repetidos += 1

        db.add(FindingObservation(
            finding_id=fila.id, scan_id=scan.id, instance_count=h["occurrences"]
        ))
        r.por_severidad[h["severity"]] = r.por_severidad.get(h["severity"], 0) + 1

    scan.stats = {
        "hallazgos": r.hallazgos_en_reporte - r.descartados,
        "nuevos": r.nuevos,
        "repetidos": r.repetidos,
        "descartados": r.descartados,
        "por_severidad": r.por_severidad,
    }
    db.flush()
    return r
