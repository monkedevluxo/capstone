"use client";

import { usePathname } from "next/navigation";

import { moduloActivo } from "@/components/barra-lateral";
import { SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Franja mínima sobre el contenido: dice dónde estás. En el teléfono también
 * abre la navegación; en pantallas grandes eso se hace desde la propia barra.
 */
export function FranjaSuperior() {
  const ruta = usePathname();
  const modulo = moduloActivo(ruta);
  const enDetalle = modulo?.href !== undefined && modulo.href !== "/" && ruta !== modulo.href;

  return (
    <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/95 px-2 backdrop-blur-sm sm:px-4">
      <SidebarTrigger
        aria-label="Abrir la navegación"
        className="text-tinta hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 md:hidden"
      />
      <span aria-hidden className="h-4 w-px bg-border md:hidden" />
      <p className="truncate text-sm font-medium text-tinta">
        {modulo?.etiqueta ?? "SentinelAI"}
        {enDetalle && <span className="font-normal text-muted-foreground"> / Detalle</span>}
      </p>
    </header>
  );
}
