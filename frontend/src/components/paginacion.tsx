import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

import { hrefHallazgos, POR_PAGINA, type Filtros } from "@/lib/filtros";
import { cn } from "@/lib/utils";

/** "X–Y de Z" con enlaces Anterior / Siguiente que conservan los filtros. */
export function Paginacion({
  filtros,
  mostrados,
  total,
}: {
  filtros: Filtros;
  mostrados: number;
  total: number;
}) {
  const desde = (filtros.pagina - 1) * POR_PAGINA + 1;
  const hasta = desde + mostrados - 1;
  const hayAnterior = filtros.pagina > 1;
  const haySiguiente = hasta < total;

  return (
    <nav
      aria-label="Paginación"
      className="flex flex-wrap items-center justify-between gap-3 text-sm"
    >
      <p className="text-muted-foreground tabular-nums">
        <span className="font-medium text-foreground">
          {desde}–{hasta}
        </span>{" "}
        de {total}
      </p>
      <div className="flex gap-2">
        <EnlacePagina
          href={hayAnterior ? hrefHallazgos(filtros, { pagina: filtros.pagina - 1 }) : null}
        >
          <ChevronLeft aria-hidden className="size-4" />
          Anterior
        </EnlacePagina>
        <EnlacePagina
          href={haySiguiente ? hrefHallazgos(filtros, { pagina: filtros.pagina + 1 }) : null}
        >
          Siguiente
          <ChevronRight aria-hidden className="size-4" />
        </EnlacePagina>
      </div>
    </nav>
  );
}

function EnlacePagina({ href, children }: { href: string | null; children: React.ReactNode }) {
  const clases =
    "inline-flex h-8 items-center gap-1 rounded-lg border px-3 text-sm font-medium transition-colors";
  if (href === null) {
    return (
      <span aria-disabled className={cn(clases, "cursor-not-allowed text-muted-foreground/60")}>
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className={cn(
        clases,
        "bg-card text-foreground hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none",
      )}
    >
      {children}
    </Link>
  );
}
