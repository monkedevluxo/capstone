// Tema del dashboard: Bronce claro, Bronce nocturno o el que diga el sistema.
// Vive fuera de los módulos "use client" porque lo usan el layout (servidor)
// y el selector (cliente).

export type Tema = "claro" | "oscuro" | "sistema";

export const COOKIE_TEMA = "tema";

/** Sin cookie, o con un valor desconocido, el dashboard abre en claro. */
export function leerTema(valor: string | undefined): Tema {
  return valor === "oscuro" || valor === "sistema" ? valor : "claro";
}

/**
 * Con "sistema" el servidor no sabe si el computador está en oscuro: este
 * script corre en <head> antes del primer pintado y pone la clase. Así no hay
 * un destello claro al cargar. Los cambios posteriores del sistema los
 * escucha el selector.
 */
export const SCRIPT_TEMA_SISTEMA =
  "(function(){try{if(matchMedia('(prefers-color-scheme: dark)').matches)document.documentElement.classList.add('dark')}catch(e){}})()";
