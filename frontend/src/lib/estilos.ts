// Clases compartidas entre componentes de servidor y de cliente. Viven fuera
// de los módulos "use client" porque un Server Component no puede importar
// valores (solo componentes) desde ellos.

/** Botón principal neutro (grafito en claro, acero en oscuro): el color queda para las capas. */
export const claseBotonPrincipal = "bg-boton text-boton-texto hover:bg-boton/90";

/** Enlace de acción dentro de una tarjeta. */
export const claseEnlace =
  "rounded-sm text-sm font-medium text-tinta underline underline-offset-4 decoration-tinta/30 hover:decoration-tinta focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";
