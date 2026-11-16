"use client";

import { Check, Search, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { Severidad } from "@/lib/api";
import {
  CATEGORIAS_OWASP,
  SEVERIDADES,
  hayFiltros,
  hrefHallazgos,
  type Filtros,
} from "@/lib/filtros";
import { cn } from "@/lib/utils";

const TODAS = "todas";

const ITEMS_OWASP: Record<string, string> = {
  [TODAS]: "Todas las categorías",
  ...Object.fromEntries(CATEGORIAS_OWASP.map((c) => [c.valor, `${c.valor.slice(0, 3)} · ${c.nombre}`])),
};

/**
 * Filtros de la lista. No guardan estado propio: cada cambio navega a una URL
 * nueva (router.push), así el botón Atrás deshace el último filtro y la vista
 * se puede compartir copiando la dirección.
 */
export function FiltrosHallazgos({
  filtros,
  hayCriticas,
}: {
  filtros: Filtros;
  /** Si hay hallazgos críticos en total (sin filtros). */
  hayCriticas: boolean;
}) {
  // "Crítica" solo se ofrece si existe alguno, igual que su tarjeta. Si llegó
  // marcada en la URL se muestra igual, para poder desmarcarla.
  const severidades = SEVERIDADES.filter(
    (s) => s.valor !== "critica" || hayCriticas || filtros.severidad.includes("critica"),
  );

  const router = useRouter();
  const [pendiente, iniciar] = useTransition();

  function ir(cambios: Partial<Filtros>) {
    iniciar(() => router.push(hrefHallazgos(filtros, cambios), { scroll: false }));
  }

  return (
    <section
      aria-label="Filtros"
      aria-busy={pendiente}
      className={cn(
        "flex flex-col gap-4 rounded-lg border bg-card p-4 transition-opacity",
        pendiente && "opacity-70",
      )}
    >
      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium text-muted-foreground">
          <span id="etiqueta-severidad">Severidad</span>
          {filtros.severidad.length === 0 && (
            <span className="font-normal"> · Todas</span>
          )}
        </span>
        <ToggleGroup
          multiple
          aria-labelledby="etiqueta-severidad"
          value={filtros.severidad}
          onValueChange={(valor) => ir({ severidad: valor as Severidad[] })}
          variant="outline"
          size="sm"
          className="flex-wrap"
        >
          {severidades.map((s) => {
            const activa = filtros.severidad.includes(s.valor);
            return (
              <ToggleGroupItem
                key={s.valor}
                value={s.valor}
                className="rounded-full aria-pressed:border-navy aria-pressed:bg-navy aria-pressed:text-white hover:aria-pressed:bg-navy/90"
              >
                {activa && <Check aria-hidden className="size-3.5" />}
                {s.etiqueta}
              </ToggleGroupItem>
            );
          })}
        </ToggleGroup>
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end">
        <label className="flex items-center gap-2 text-sm font-medium text-persona-fuerte md:h-8">
          <Switch
            checked={filtros.revisar}
            onCheckedChange={(valor) => ir({ revisar: valor })}
            className="data-checked:bg-persona-texto"
          />
          Solo revisar primero
        </label>

        <div className="flex flex-col gap-1.5">
          <span id="etiqueta-owasp" className="text-xs font-medium text-muted-foreground">
            Categoría OWASP (tabla CWE)
          </span>
          <Select
            items={ITEMS_OWASP}
            value={filtros.owaspRef ?? TODAS}
            onValueChange={(valor) => ir({ owaspRef: !valor || valor === TODAS ? null : valor })}
          >
            <SelectTrigger aria-labelledby="etiqueta-owasp" className="w-full md:w-72">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(ITEMS_OWASP).map(([valor, etiqueta]) => (
                <SelectItem key={valor} value={valor}>
                  {etiqueta}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <form
          role="search"
          className="flex flex-1 flex-col gap-1.5 md:min-w-64"
          onSubmit={(e) => {
            e.preventDefault();
            const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
            ir({ q });
          }}
        >
          <label htmlFor="busqueda" className="text-xs font-medium text-muted-foreground">
            Buscar en título y ruta
          </label>
          <div className="flex gap-2">
            {/* key: si la URL cambia (Atrás, Limpiar), el campo toma el valor nuevo */}
            <Input
              key={filtros.q}
              id="busqueda"
              name="q"
              type="search"
              defaultValue={filtros.q}
              minLength={2}
              placeholder="Ej: redirect, /rest/basket"
            />
            <Button type="submit" variant="outline" aria-label="Buscar">
              <Search aria-hidden />
            </Button>
          </div>
        </form>
      </div>

      {hayFiltros(filtros) && (
        <div className="flex flex-wrap items-center gap-2 border-t pt-3 text-sm">
          {filtros.scanId && (
            <button
              type="button"
              onClick={() => ir({ scanId: null })}
              title={`Escaneo ${filtros.scanId}`}
              className="inline-flex h-7 items-center gap-1 rounded-full border border-escaner/40 bg-escaner-suave px-2.5 text-escaner hover:border-escaner hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              Escaneo <span className="font-mono">{filtros.scanId.slice(0, 8)}</span>
              <span aria-hidden className="text-escaner/60">·</span>
              Quitar
            </button>
          )}
          {filtros.sinEnriquecer && (
            <button
              type="button"
              onClick={() => ir({ sinEnriquecer: false })}
              className="inline-flex h-7 items-center gap-1 rounded-full border border-dashed border-muted-foreground/60 px-2.5 text-muted-foreground hover:border-muted-foreground hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              Solo sin enriquecer
              <X aria-hidden className="size-3.5" />
              <span className="sr-only">: quitar filtro</span>
            </button>
          )}
          <Link
            href="/hallazgos"
            className="ml-auto text-sm font-medium text-ia underline-offset-4 hover:underline"
          >
            Limpiar filtros
          </Link>
        </div>
      )}
    </section>
  );
}
