import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import type { ResumenHallazgos } from "@/lib/api";
import { hayFiltros, hrefHallazgos, type Filtros } from "@/lib/filtros";
import { cn } from "@/lib/utils";

/**
 * Fila de totales. Los conteos vienen de GET /findings/resumen con los mismos
 * filtros que la tabla, así que siempre cuadran con lo que se ve abajo.
 */
export function Totales({ resumen, filtros }: { resumen: ResumenHallazgos; filtros: Filtros }) {
  const s = resumen.por_severidad;

  return (
    <section aria-label="Totales" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Tarjeta
        etiqueta={hayFiltros(filtros) ? "Con estos filtros" : "Hallazgos únicos"}
        valor={resumen.total}
      />
      {s.critica > 0 && (
        <Tarjeta etiqueta="Crítica" valor={s.critica} marca="bg-sev-critica-fondo" />
      )}
      <Tarjeta etiqueta="Alta" valor={s.alta} marca="bg-sev-alta" />
      <Tarjeta etiqueta="Media" valor={s.media} marca="bg-sev-media" />
      <Tarjeta etiqueta="Baja e informativa" valor={s.baja + s.informativa} marca="bg-sev-baja" />

      <TarjetaFiltro
        etiqueta={
          <>
            <TriangleAlert aria-hidden className="size-4" />
            Revisar primero
          </>
        }
        valor={resumen.revisar}
        activo={filtros.revisar}
        href={hrefHallazgos(filtros, { revisar: !filtros.revisar })}
        clases={{
          base: "border-persona/40 bg-persona-suave",
          enlace: "hover:border-persona focus-visible:ring-persona/40",
          activo: "border-persona ring-2 ring-persona/30",
          etiqueta: "text-persona-fuerte",
          valor: "text-persona-fuerte",
          pista: "text-persona-texto",
        }}
      />

      <TarjetaFiltro
        etiqueta="Sin enriquecer"
        valor={resumen.sin_enriquecer}
        activo={filtros.sinEnriquecer}
        href={hrefHallazgos(filtros, { sinEnriquecer: !filtros.sinEnriquecer })}
        clases={{
          base: "border-dashed border-muted-foreground/50 bg-card",
          enlace: "hover:border-muted-foreground focus-visible:ring-ring/40",
          activo: "border-solid border-navy ring-2 ring-navy/20",
          etiqueta: "text-muted-foreground",
          valor: "text-navy",
          pista: "text-muted-foreground",
        }}
      />
    </section>
  );
}

function Tarjeta({ etiqueta, valor, marca }: { etiqueta: string; valor: number; marca?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <span className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        {marca && <span aria-hidden className={cn("size-2 rounded-full", marca)} />}
        {etiqueta}
      </span>
      <span className="mt-1 block text-3xl font-semibold text-navy tabular-nums">{valor}</span>
    </div>
  );
}

/**
 * Tarjeta que además activa o quita un filtro. Con conteo 0 y el filtro
 * apagado no es enlace: llevaría a una lista vacía. Si el filtro está activo
 * sigue siendo enlace aunque cuente 0, para poder quitarlo.
 */
function TarjetaFiltro({
  etiqueta,
  valor,
  activo,
  href,
  clases,
}: {
  etiqueta: ReactNode;
  valor: number;
  activo: boolean;
  href: string;
  clases: Record<"base" | "enlace" | "activo" | "etiqueta" | "valor" | "pista", string>;
}) {
  const contenido = (
    <>
      <span className={cn("flex items-center gap-1.5 text-sm font-medium", clases.etiqueta)}>
        {etiqueta}
      </span>
      <span className={cn("mt-1 block text-3xl font-semibold tabular-nums", clases.valor)}>
        {valor}
      </span>
      <span className={cn("mt-1 block text-xs", clases.pista, (activo || valor > 0) && "group-hover:underline")}>
        {activo ? "Quitar filtro" : valor > 0 ? "Ver solo estos" : "Ninguno"}
      </span>
    </>
  );

  if (!activo && valor === 0) {
    return <div className={cn("rounded-lg border p-4 opacity-70", clases.base)}>{contenido}</div>;
  }

  return (
    <Link
      href={href}
      className={cn(
        "group rounded-lg border p-4 transition-colors focus-visible:ring-3 focus-visible:outline-none",
        clases.base,
        clases.enlace,
        activo && clases.activo,
      )}
    >
      {contenido}
    </Link>
  );
}
