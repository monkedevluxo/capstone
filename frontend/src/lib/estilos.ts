// Clases compartidas entre componentes de servidor y de cliente. Viven fuera
// de los módulos "use client" porque un Server Component no puede importar
// valores (solo componentes) desde ellos.

/** Botón principal en navy: el azul queda reservado para lo que dice la IA. */
export const claseBotonPrincipal = "bg-navy text-white hover:bg-navy/90";

/** Enlace de acción dentro de una tarjeta. */
export const claseEnlace =
  "rounded-sm text-sm font-medium text-navy underline underline-offset-4 decoration-navy/30 hover:decoration-navy focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";
