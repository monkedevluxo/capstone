// Filtros de la lista de hallazgos. Todo el estado vive en la URL, así una
// vista se puede compartir y el botón Atrás funciona. Este módulo traduce en
// los dos sentidos: URL -> filtros validados -> parámetros de la API.
//
// La URL usa los mismos nombres que la API, salvo la página, que va como
// número (1, 2, …) en vez de offset.

import type { Severidad } from "@/lib/api";

export const POR_PAGINA = 25;

export const SEVERIDADES: { valor: Severidad; etiqueta: string }[] = [
  { valor: "critica", etiqueta: "Crítica" },
  { valor: "alta", etiqueta: "Alta" },
  { valor: "media", etiqueta: "Media" },
  { valor: "baja", etiqueta: "Baja" },
  { valor: "informativa", etiqueta: "Informativa" },
];

export const CATEGORIAS_OWASP: { valor: string; nombre: string }[] = [
  { valor: "A01:2025", nombre: "Broken Access Control" },
  { valor: "A02:2025", nombre: "Security Misconfiguration" },
  { valor: "A03:2025", nombre: "Software Supply Chain Failures" },
  { valor: "A04:2025", nombre: "Cryptographic Failures" },
  { valor: "A05:2025", nombre: "Injection" },
  { valor: "A06:2025", nombre: "Insecure Design" },
  { valor: "A07:2025", nombre: "Authentication Failures" },
  { valor: "A08:2025", nombre: "Software or Data Integrity Failures" },
  { valor: "A09:2025", nombre: "Security Logging & Alerting Failures" },
  { valor: "A10:2025", nombre: "Mishandling of Exceptional Conditions" },
];

export interface Filtros {
  severidad: Severidad[];
  /** Solo los marcados para revisar primero (requiere_revision). */
  revisar: boolean;
  /** Solo los sin enriquecer (con_ia=false en la API). */
  sinEnriquecer: boolean;
  /** Categoría de la tabla CWE -> OWASP (owasp_ref en la API). */
  owaspRef: string | null;
  q: string;
  /** Empieza en 1. */
  pagina: number;
}

export type SearchParams = Record<string, string | string[] | undefined>;

function lista(valor: string | string[] | undefined): string[] {
  if (valor === undefined) return [];
  return Array.isArray(valor) ? valor : [valor];
}

function primero(valor: string | string[] | undefined): string | undefined {
  return lista(valor)[0];
}

/**
 * Lee los filtros desde la URL. Lo que no se reconoce se descarta en vez de
 * mandarlo a la API: una URL editada a mano no termina en un error 422.
 */
export function leerFiltros(sp: SearchParams): Filtros {
  // En el orden de SEVERIDADES y sin repetidos, venga como venga en la URL.
  const pedidas = lista(sp.severidad);
  const severidad = SEVERIDADES.map((s) => s.valor).filter((v) => pedidas.includes(v));

  const owasp = primero(sp.owasp_ref)?.toUpperCase();
  const owaspRef = CATEGORIAS_OWASP.some((c) => c.valor === owasp) ? owasp! : null;

  // La API exige al menos 2 caracteres en la búsqueda.
  const q = (primero(sp.q) ?? "").trim().slice(0, 100);

  const pagina = Number.parseInt(primero(sp.pagina) ?? "1", 10);

  return {
    severidad,
    revisar: primero(sp.revisar) === "true",
    sinEnriquecer: primero(sp.con_ia) === "false",
    owaspRef,
    q: q.length >= 2 ? q : "",
    pagina: Number.isFinite(pagina) && pagina >= 1 ? pagina : 1,
  };
}

export function hayFiltros(f: Filtros): boolean {
  return f.severidad.length > 0 || f.revisar || f.sinEnriquecer || f.owaspRef !== null || f.q !== "";
}

/** Parámetros de filtro comunes a la URL del dashboard y a la API. */
function parametrosFiltro(f: Filtros): URLSearchParams {
  const p = new URLSearchParams();
  for (const s of f.severidad) p.append("severidad", s);
  if (f.revisar) p.set("revisar", "true");
  if (f.sinEnriquecer) p.set("con_ia", "false");
  if (f.owaspRef) p.set("owasp_ref", f.owaspRef);
  if (f.q) p.set("q", f.q);
  return p;
}

/** Los mismos filtros para /findings y /findings/resumen, así siempre coinciden. */
export function parametrosApi(f: Filtros): URLSearchParams {
  return parametrosFiltro(f);
}

/**
 * URL de /hallazgos con los filtros cambiados. Cambiar un filtro vuelve a la
 * página 1; solo se conserva la página si se la pide explícitamente.
 */
export function hrefHallazgos(f: Filtros, cambios: Partial<Filtros> = {}): string {
  const nuevo = { ...f, pagina: 1, ...cambios };
  const p = parametrosFiltro(nuevo);
  if (nuevo.pagina > 1) p.set("pagina", String(nuevo.pagina));
  const qs = p.toString();
  return qs ? `/hallazgos?${qs}` : "/hallazgos";
}
