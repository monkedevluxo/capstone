import { CircleCheck, CircleDashed, TriangleAlert } from "lucide-react";

import { InsigniaSeveridad } from "@/components/severidad";
import type { HallazgoDetalle } from "@/lib/api";
import { ESTADO_HALLAZGO, MOTIVO_REVISION, nombreOwasp, textoMotivo } from "@/lib/etiquetas";
import { fecha } from "@/lib/formato";
import { cn } from "@/lib/utils";

const SEVERIDAD_TEXTO: Record<HallazgoDetalle["severidad"], string> = {
  critica: "crítica",
  alta: "alta",
  media: "media",
  baja: "baja",
  informativa: "informativa",
};

/** Cabecera del detalle: qué es, dónde está y los tres indicadores de la opción mixta. */
export function CabeceraHallazgo({ hallazgo: h }: { hallazgo: HallazgoDetalle }) {
  const ubicacion = [
    h.ruta ? `${h.metodo ? `${h.metodo} ` : ""}${h.ruta}` : null,
    h.parametro ? `parámetro ${h.parametro}` : null,
    h.cwe ? `CWE-${h.cwe}` : null,
    `${h.instancias.length} ${h.instancias.length === 1 ? "instancia" : "instancias"}`,
  ].filter(Boolean);
  const nEscaneos = h.escaneos.length;

  return (
    <header className="@container">
      <div className="flex flex-col gap-5 @4xl:flex-row @4xl:items-start @4xl:justify-between @4xl:gap-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
            <InsigniaSeveridad severidad={h.severidad} />
            <span className="inline-flex h-6 items-center rounded-md border border-border bg-card px-2 text-xs font-medium text-tinta">
              {ESTADO_HALLAZGO[h.estado]}
            </span>
            <span className="text-muted-foreground">
              Visto en {nEscaneos} {nEscaneos === 1 ? "escaneo" : "escaneos"} · primera vez{" "}
              <time dateTime={h.primera_vez}>{fecha(h.primera_vez)}</time>
            </span>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-balance text-tinta">
            {h.titulo}
          </h1>
          <p className="mt-1.5 font-mono text-xs leading-relaxed text-escaner">
            {ubicacion.map((parte, i) => (
              <span key={i}>
                {i > 0 && " · "}
                {/* Solo la ruta (la primera parte) puede partirse; el resto va entero. */}
                <span className={i === 0 ? "break-all" : "whitespace-nowrap"}>{parte}</span>
              </span>
            ))}
          </p>
        </div>

        <dl className="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-3 @4xl:w-[34rem]">
          <IndicadorOwasp hallazgo={h} />
          <Indicador etiqueta="Prioridad">
            <dd className="font-mono text-lg font-semibold text-tinta">
              {h.referencia.prioridad_regla ?? "—"}
            </dd>
            <dd className="text-xs text-muted-foreground">
              Regla: severidad {SEVERIDAD_TEXTO[h.severidad]}
            </dd>
          </Indicador>
          <IndicadorCoincidencia hallazgo={h} />
        </dl>
      </div>
    </header>
  );
}

function Indicador({
  etiqueta,
  children,
  className,
}: {
  etiqueta: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-0.5 rounded-lg border bg-card px-3.5 py-3", className)}>
      <dt className="text-xs font-medium text-muted-foreground">{etiqueta}</dt>
      {children}
    </div>
  );
}

function IndicadorOwasp({ hallazgo: h }: { hallazgo: HallazgoDetalle }) {
  const ref = h.referencia.owasp_referencia;
  return (
    <Indicador etiqueta="OWASP de referencia">
      <dd className="font-mono text-lg font-semibold text-tinta">{ref ?? "—"}</dd>
      <dd className="text-xs text-muted-foreground">
        {ref ? nombreOwasp(ref) : h.cwe ? "CWE fuera de la tabla" : "Sin CWE"}
      </dd>
    </Indicador>
  );
}

/** ¿Coinciden la categoría del modelo y la de la tabla CWE -> OWASP? */
function IndicadorCoincidencia({ hallazgo: h }: { hallazgo: HallazgoDetalle }) {
  const r = h.referencia;
  const sinIA = h.ia === null || h.ia.estado === "failed";

  let tono: "neutro" | "bien" | "revisar";
  let titulo: string;
  let detalle: string;
  if (sinIA) {
    tono = "neutro";
    titulo = "Sin enriquecer";
    detalle = h.ia ? "El último intento falló" : "El modelo aún no lo revisa";
  } else if (r.requiere_revision) {
    tono = "revisar";
    titulo = "Revisar";
    detalle = textoMotivo(MOTIVO_REVISION, r.motivo_revision) ?? "categorías distintas";
  } else if (!r.owasp_referencia) {
    // Sin CWE: no hay tabla con qué comparar. Decir "coinciden" sería falso.
    tono = "neutro";
    titulo = "Sin referencia";
    detalle = "Sin CWE, no hay con qué comparar";
  } else {
    tono = "bien";
    titulo = "Coinciden";
    detalle = "No requiere revisión previa";
  }

  const Icono = tono === "bien" ? CircleCheck : tono === "revisar" ? TriangleAlert : CircleDashed;
  return (
    <Indicador
      etiqueta="Modelo y tabla"
      className={cn(
        tono === "bien" && "border-exito/25 bg-exito-fondo",
        tono === "revisar" && "border-persona/40 bg-persona-suave",
      )}
    >
      <dd
        className={cn(
          "flex items-center gap-1.5 text-base font-semibold",
          tono === "bien" && "text-exito",
          tono === "revisar" && "text-persona-fuerte",
          tono === "neutro" && "text-tinta",
        )}
      >
        <Icono aria-hidden className="size-4 shrink-0" />
        {titulo}
      </dd>
      <dd
        className={cn(
          "text-xs",
          tono === "bien" && "text-exito/90",
          tono === "revisar" && "text-persona-texto",
          tono === "neutro" && "text-muted-foreground",
        )}
      >
        {detalle}
      </dd>
    </Indicador>
  );
}
