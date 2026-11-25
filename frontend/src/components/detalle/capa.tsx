import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Las tres capas del detalle, cada una con su color en todo el dashboard:
 *   escáner -> acero (lo que dijo la herramienta)
 *   ia      -> azul        (sugerencia del modelo, no decisión)
 *   persona -> naranjo     (lo que decide alguien)
 */
const TONO = {
  escaner: { cabecera: "bg-escaner-suave", titulo: "text-tinta", icono: "text-escaner" },
  ia: { cabecera: "bg-ia-suave", titulo: "text-ia", icono: "text-ia" },
  persona: { cabecera: "bg-persona-suave", titulo: "text-persona-fuerte", icono: "text-persona-texto" },
} as const;

export function Capa({
  tono,
  icono: Icono,
  titulo,
  bajada,
  id,
  className,
  children,
}: {
  tono: keyof typeof TONO;
  icono: LucideIcon;
  titulo: string;
  /** Lo que es y lo que no es esta capa, en pocas palabras. */
  bajada: string;
  id: string;
  className?: string;
  children: React.ReactNode;
}) {
  const t = TONO[tono];
  return (
    <section aria-labelledby={id} className={cn("overflow-hidden rounded-lg border bg-card", className)}>
      <header className={cn("flex items-start gap-2.5 border-b px-5 py-3", t.cabecera)}>
        <Icono aria-hidden className={cn("mt-0.5 size-4 shrink-0", t.icono)} />
        <div className="min-w-0">
          <h2 id={id} className={cn("font-semibold", t.titulo)}>
            {titulo}
          </h2>
          <p className="text-xs text-muted-foreground">{bajada}</p>
        </div>
      </header>
      <div className="flex flex-col gap-5 p-5">{children}</div>
    </section>
  );
}

/** Un bloque con título dentro de una capa. */
export function Apartado({
  titulo,
  children,
  className,
}: {
  titulo: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <h3 className="mb-1.5 text-xs font-semibold text-muted-foreground">
        {titulo}
      </h3>
      {children}
    </div>
  );
}

/** Párrafos de texto corrido, con un ancho cómodo de lectura. */
export function Texto({ parrafos }: { parrafos: string[] }) {
  return (
    <div className="flex max-w-prose flex-col gap-2 text-sm leading-relaxed text-foreground">
      {parrafos.map((p, i) => (
        <p key={i}>{p}</p>
      ))}
    </div>
  );
}
