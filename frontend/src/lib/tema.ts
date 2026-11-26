// Tema del dashboard: Bronce claro u oscuro (nocturno).
// Vive fuera de los módulos "use client" porque lo usan el layout (servidor)
// y el botón de tema (cliente).

export type Tema = "claro" | "oscuro";

export const COOKIE_TEMA = "tema";

/** Sin cookie, o con un valor desconocido, el dashboard abre en claro. */
export function leerTema(valor: string | undefined): Tema {
  return valor === "oscuro" ? "oscuro" : "claro";
}
