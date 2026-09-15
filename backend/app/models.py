"""
SentinelAI · Modelos de datos (SQLAlchemy 2.0, PostgreSQL)

Deriva de finding.schema.json v1.0.0. Si cambia el esquema, cambia esto.

Alembic genera la migración desde aquí:
    alembic revision --autogenerate -m "esquema inicial"
    alembic upgrade head
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SCHEMA_VERSION = "1.0.0"


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def _ahora() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Enumeraciones ─────────────────────────────────────────────────────────
# Enums nativos de PostgreSQL: la base rechaza un valor inválido aunque el
# código tenga un bug. Agregar un valor exige migración, y eso es deseable:
# obliga a decidirlo en vez de que aparezca solo.

class Herramienta(str, enum.Enum):
    zap = "zap"
    nikto = "nikto"
    openvas = "openvas"


class Severidad(str, enum.Enum):
    critica = "critica"
    alta = "alta"
    media = "media"
    baja = "baja"
    informativa = "informativa"


class Prioridad(str, enum.Enum):
    p1 = "p1"
    p2 = "p2"
    p3 = "p3"
    p4 = "p4"


class EstadoHallazgo(str, enum.Enum):
    nuevo = "nuevo"
    en_triage = "en_triage"
    confirmado = "confirmado"
    falso_positivo = "falso_positivo"
    riesgo_aceptado = "riesgo_aceptado"
    remediado = "remediado"


class EstadoEscaneo(str, enum.Enum):
    pendiente = "pendiente"
    ejecutando = "ejecutando"
    importado = "importado"
    fallido = "fallido"


class EstadoIA(str, enum.Enum):
    ok = "ok"
    failed = "failed"


class CategoriaOwasp(str, enum.Enum):
    """OWASP Top 10:2025. Guardar la edición junto a la categoría (columna
    owasp_version) es lo que mantiene interpretable el dato cuando cambie."""
    a01 = "A01:2025"   # Broken Access Control (absorbe SSRF)
    a02 = "A02:2025"   # Security Misconfiguration
    a03 = "A03:2025"   # Software Supply Chain Failures
    a04 = "A04:2025"   # Cryptographic Failures
    a05 = "A05:2025"   # Injection (incluye XSS)
    a06 = "A06:2025"   # Insecure Design
    a07 = "A07:2025"   # Authentication Failures
    a08 = "A08:2025"   # Software or Data Integrity Failures
    a09 = "A09:2025"   # Security Logging & Alerting Failures
    a10 = "A10:2025"   # Mishandling of Exceptional Conditions


class DecisionValidacion(str, enum.Enum):
    confirmado = "confirmado"
    falso_positivo = "falso_positivo"
    riesgo_aceptado = "riesgo_aceptado"
    duplicado = "duplicado"
    requiere_segunda_opinion = "requiere_segunda_opinion"


# ── Tablas ────────────────────────────────────────────────────────────────

class Target(Base):
    """Aplicación objetivo del laboratorio."""
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = _pk()
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, server_default="lab")
    created_at: Mapped[datetime] = _ahora()

    scans: Mapped[list["Scan"]] = relationship(back_populates="target", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="target", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("base_url", name="uq_targets_base_url"),
        # Ancla en la base la restricción ética del proyecto: si alguien intenta
        # registrar un objetivo fuera del laboratorio, la inserción falla.
        CheckConstraint("environment = 'lab'", name="ck_targets_solo_lab"),
    )


class Scan(Base):
    """Una ejecución de una herramienta sobre un objetivo."""
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = _pk()
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    tool: Mapped[Herramienta] = mapped_column(
        Enum(Herramienta, name="herramienta", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    tool_version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[EstadoEscaneo] = mapped_column(
        Enum(EstadoEscaneo, name="estado_escaneo", values_callable=lambda e: [i.value for i in e]),
        nullable=False, server_default="pendiente",
    )
    started_at: Mapped[datetime] = _ahora()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_sha256: Mapped[str | None] = mapped_column(
        String(64),
        comment="Hash del JSON crudo importado. Permite demostrar que el informe no se editó después.",
    )
    stats: Mapped[dict | None] = mapped_column(
        JSONB, comment="Totales del escaneo: hallazgos, nuevos, enriquecidos, fallidos."
    )

    target: Mapped[Target] = relationship(back_populates="scans")
    observations: Mapped[list["FindingObservation"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_scans_target_started", "target_id", "started_at"),)


class Finding(Base):
    """
    Un problema del objetivo, no de un escaneo.

    Decisión central del modelo: la unicidad es (target_id, dedupe_key), NO
    (scan_id, dedupe_key). Reescanear no crea filas nuevas: agrega una
    FindingObservation y actualiza last_seen. Eso da gratis 'este XSS lleva
    tres escaneos abierto', que es imposible si el hallazgo pertenece al escaneo.

    Alternativa más simple, si el equipo prefiere: mover scan_id acá y borrar
    FindingObservation. Se pierde el histórico entre escaneos.
    """
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = _pk()
    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, server_default=SCHEMA_VERSION)

    # Origen — nunca se modifica después de la ingesta
    tool: Mapped[Herramienta] = mapped_column(
        Enum(Herramienta, name="herramienta", create_type=False,
             values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_name: Mapped[str | None] = mapped_column(String(300))
    source_raw: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        comment="Bloque crudo de la herramienta, sin alterar. Es la evidencia que respalda todo lo demás.",
    )

    # Normalizado
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    path_template: Mapped[str] = mapped_column(String(1000), nullable=False)
    method: Mapped[str | None] = mapped_column(String(10))
    param: Mapped[str | None] = mapped_column(String(200))
    evidence_snippet: Mapped[str | None] = mapped_column(Text)

    severity: Mapped[Severidad] = mapped_column(
        Enum(Severidad, name="severidad", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    severity_tool_raw: Mapped[str | None] = mapped_column(String(50))
    tool_confidence: Mapped[str | None] = mapped_column(String(20))
    cvss_score: Mapped[float | None] = mapped_column(Float)
    cwe_id: Mapped[int | None] = mapped_column(Integer)
    wasc_id: Mapped[int | None] = mapped_column(Integer)

    # Agrupación
    dedupe_key: Mapped[str] = mapped_column(String(16), nullable=False)
    correlation_key: Mapped[str | None] = mapped_column(String(16))
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    first_seen_at: Mapped[datetime] = _ahora()
    last_seen_at: Mapped[datetime] = _ahora()

    status: Mapped[EstadoHallazgo] = mapped_column(
        Enum(EstadoHallazgo, name="estado_hallazgo", values_callable=lambda e: [i.value for i in e]),
        nullable=False, server_default="nuevo",
    )
    created_at: Mapped[datetime] = _ahora()
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    target: Mapped[Target] = relationship(back_populates="findings")
    observations: Mapped[list["FindingObservation"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    instances: Mapped[list["FindingInstance"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    enrichments: Mapped[list["AiEnrichment"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    validations: Mapped[list["Validation"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan",
        order_by="Validation.reviewed_at.desc()",
    )

    __table_args__ = (
        # El corazón de la deduplicación. Reimportar el mismo escaneo choca acá
        # y se resuelve con ON CONFLICT DO UPDATE, no con lógica de aplicación.
        UniqueConstraint("target_id", "dedupe_key", name="uq_findings_target_dedupe"),
        # Índice del listado del dashboard: filtra por objetivo, estado y severidad.
        Index("ix_findings_dashboard", "target_id", "status", "severity"),
        Index("ix_findings_correlation", "correlation_key"),
        Index("ix_findings_cwe", "cwe_id"),
        CheckConstraint("occurrences >= 1", name="ck_findings_occurrences"),
        CheckConstraint(
            "cvss_score IS NULL OR (cvss_score >= 0 AND cvss_score <= 10)",
            name="ck_findings_cvss_rango",
        ),
    )


class FindingObservation(Base):
    """Cada vez que un escaneo vuelve a ver el mismo hallazgo."""
    __tablename__ = "finding_observations"

    id: Mapped[uuid.UUID] = _pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    instance_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    observed_at: Mapped[datetime] = _ahora()

    finding: Mapped[Finding] = relationship(back_populates="observations")
    scan: Mapped[Scan] = relationship(back_populates="observations")

    __table_args__ = (
        UniqueConstraint("finding_id", "scan_id", name="uq_observacion_unica"),
        Index("ix_observations_scan", "scan_id"),
    )


class FindingInstance(Base):
    """URLs concretas agrupadas bajo un mismo hallazgo. Se limita a 50 por
    hallazgo en la ingesta; el total real vive en Finding.occurrences."""
    __tablename__ = "finding_instances"

    id: Mapped[uuid.UUID] = _pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    method: Mapped[str | None] = mapped_column(String(10))
    param: Mapped[str | None] = mapped_column(String(200))

    finding: Mapped[Finding] = relationship(back_populates="instances")

    __table_args__ = (Index("ix_instances_finding", "finding_id"),)


class AiEnrichment(Base):
    """
    Salida del modelo local. Es histórico a propósito: reenriquecer con otro
    prompt agrega una fila y marca la anterior como no vigente. Sin eso no se
    puede demostrar que ajustar el prompt mejoró algo (tarea T-047).
    """
    __tablename__ = "ai_enrichments"

    id: Mapped[uuid.UUID] = _pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[EstadoIA] = mapped_column(
        Enum(EstadoIA, name="estado_ia", values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    generated_at: Mapped[datetime] = _ahora()
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    explanation: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    owasp_version: Mapped[str | None] = mapped_column(String(10), server_default="2025")
    owasp_category: Mapped[CategoriaOwasp | None] = mapped_column(
        Enum(CategoriaOwasp, name="categoria_owasp", values_callable=lambda e: [i.value for i in e])
    )
    priority: Mapped[Prioridad | None] = mapped_column(
        Enum(Prioridad, name="prioridad", values_callable=lambda e: [i.value for i in e])
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    remediation_summary: Mapped[str | None] = mapped_column(Text)
    remediation_steps: Mapped[list | None] = mapped_column(JSONB)
    failure_reason: Mapped[str | None] = mapped_column(String(40))

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    prompt_sha256: Mapped[str | None] = mapped_column(
        String(64), comment="Hash del prompt exacto enviado. Permite reproducir la corrida."
    )

    finding: Mapped[Finding] = relationship(back_populates="enrichments")

    __table_args__ = (
        # Índice parcial: garantiza a nivel de base que haya como máximo un
        # enriquecimiento vigente por hallazgo, sin impedir el histórico.
        Index(
            "uq_enrichment_vigente", "finding_id",
            unique=True, postgresql_where=text("is_current"),
        ),
        Index("ix_enrichments_finding", "finding_id"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_enrichment_confianza_rango",
        ),
        # Un fallo no deja campos rellenados a medias: o la salida es válida
        # y completa, o el hallazgo queda visiblemente sin enriquecer.
        CheckConstraint(
            "state = 'ok' OR (owasp_category IS NULL AND priority IS NULL "
            "AND explanation IS NULL AND remediation_summary IS NULL)",
            name="ck_enrichment_fallo_sin_datos",
        ),
        CheckConstraint(
            "state = 'failed' OR failure_reason IS NULL",
            name="ck_enrichment_motivo_solo_si_falla",
        ),
    )


class Validation(Base):
    """
    Decisión humana sobre un hallazgo. Histórico: cada revisión es una fila.
    El estado vigente de Finding.status se actualiza desde la más reciente.

    Las cuatro banderas ai_* son el golden set: si los revisores las completan
    durante el triage normal, las métricas del S6 se calculan solas.
    """
    __tablename__ = "validations"

    id: Mapped[uuid.UUID] = _pk()
    finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    enrichment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_enrichments.id", ondelete="SET NULL"),
        comment="Qué salida de IA se estaba juzgando. Sin esto, comparar prompts es ambiguo.",
    )
    decision: Mapped[DecisionValidacion] = mapped_column(
        Enum(DecisionValidacion, name="decision_validacion",
             values_callable=lambda e: [i.value for i in e]),
        nullable=False,
    )
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    reviewed_at: Mapped[datetime] = _ahora()
    priority_override: Mapped[Prioridad | None] = mapped_column(
        Enum(Prioridad, name="prioridad", create_type=False,
             values_callable=lambda e: [i.value for i in e])
    )
    comment: Mapped[str | None] = mapped_column(Text)

    ai_owasp_correcto: Mapped[bool | None] = mapped_column(Boolean)
    ai_prioridad_correcta: Mapped[bool | None] = mapped_column(Boolean)
    ai_remediacion_util: Mapped[bool | None] = mapped_column(Boolean)
    ai_alucinacion: Mapped[bool | None] = mapped_column(Boolean)
    ai_nota: Mapped[str | None] = mapped_column(Text)

    finding: Mapped[Finding] = relationship(back_populates="validations")

    __table_args__ = (
        Index("ix_validations_finding_fecha", "finding_id", "reviewed_at"),
        Index("ix_validations_reviewer", "reviewer"),
    )
