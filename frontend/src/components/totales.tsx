import { TriangleAlert } from "lucide-react";
import Link from "next/link";

import type { ResumenHallazgos } from "@/lib/api";
import { hrefHallazgos, type Filtros } from "@/lib/filtros";
import { cn } from "@/lib/utils";

/**
 * Fila de totales. Los conteos vienen de GET /findings/resumen con los mismos
 * filtros que la tabla, así que siempre cuadran con lo que se ve abajo.
 */
export function Totales({ resumen, filtros }: { resumen: ResumenHallazgos; filtros: Filtros }) {
  const s = resumen.por_severidad;

  return (
    <section aria-label="Totales" className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Tarjeta etiqueta="Hallazgos únicos" valor={resumen.total} />
      {s.critica > 0 && (
        <Tarjeta etiqueta="Crítica" valor={s.critica} marca="bg-sev-critica-fondo" />
      )}
      <Tarjeta etiqueta="Alta" valor={s.alta} marca="bg-sev-alta" />
      <Tarjeta etiqueta="Media" valor={s.media} marca="bg-sev-media" />
      <Tarjeta etiqueta="Baja e informativa" valor={s.baja + s.informativa} marca="bg-sev-baja" />

      <Link
        href={hrefHallazgos(filtros, { revisar: !filtros.revisar })}
        className={cn(
          "group rounded-lg border border-persona/40 bg-persona-suave p-4 transition-colors hover:border-persona focus-visible:ring-3 focus-visible:ring-persona/40 focus-visible:outline-none",
          filtros.revisar && "border-persona ring-2 ring-persona/30",
        )}
      >
        <span className="flex items-center gap-1.5 text-sm font-medium text-persona-fuerte">
          <TriangleAlert aria-hidden className="size-4" />
          Revisar primero
        </span>
        <span className="mt-1 block text-3xl font-semibold text-persona-fuerte tabular-nums">
          {resumen.revisar}
        </span>
        <span className="mt-1 block text-xs text-persona-texto group-hover:underline">
          {filtros.revisar ? "Quitar filtro" : "Ver solo estos"}
        </span>
      </Link>

      <Link
        href={hrefHallazgos(filtros, { sinEnriquecer: !filtros.sinEnriquecer })}
        className={cn(
          "group rounded-lg border border-dashed border-muted-foreground/50 bg-card p-4 transition-colors hover:border-muted-foreground focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none",
          filtros.sinEnriquecer && "border-solid border-navy ring-2 ring-navy/20",
        )}
      >
        <span className="text-sm font-medium text-muted-foreground">Sin enriquecer</span>
        <span className="mt-1 block text-3xl font-semibold text-navy tabular-nums">
          {resumen.sin_enriquecer}
        </span>
        <span className="mt-1 block text-xs text-muted-foreground group-hover:underline">
          {filtros.sinEnriquecer ? "Quitar filtro" : "Ver solo estos"}
        </span>
      </Link>
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
