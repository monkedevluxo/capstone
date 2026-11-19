// Lectura de lo que trae ZAP en `origen` (la alerta sin modificar).
//
// ZAP escribe la descripción, la solución y las referencias con un HTML mínimo
// (<p>…</p>). Acá se pasa a texto: nunca se inserta como HTML, porque parte de
// lo que trae una alerta (evidencia, attack, otherinfo) viene del sitio
// escaneado y no es de confianza.

import type { HallazgoDetalle, InstanciaZap } from "@/lib/api";

const ENTIDADES: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};

function decodificar(texto: string): string {
  return texto.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (entera, cuerpo: string) => {
    if (cuerpo[0] === "#") {
      const n = cuerpo[1].toLowerCase() === "x" ? parseInt(cuerpo.slice(2), 16) : parseInt(cuerpo.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : entera;
    }
    return ENTIDADES[cuerpo.toLowerCase()] ?? entera;
  });
}

/** "<p>Uno.</p><p>Dos.</p>" -> ["Uno.", "Dos."]. Sin etiquetas, como texto. */
export function parrafos(html: string | null | undefined): string[] {
  if (!html) return [];
  return html
    .split(/<\/p>|<br\s*\/?>|\n{2,}/i)
    .map((trozo) => decodificar(trozo.replace(/<[^>]*>/g, "")).trim())
    .filter(Boolean);
}

/** Enlaces http(s) que trae `reference`. Cualquier otro esquema se descarta. */
export function referencias(html: string | null | undefined): string[] {
  const vistos = new Set<string>();
  for (const p of parrafos(html)) {
    for (const candidato of p.split(/\s+/)) {
      try {
        const url = new URL(candidato);
        if (url.protocol === "http:" || url.protocol === "https:") vistos.add(url.href);
      } catch {
        // No es una URL.
      }
    }
  }
  return [...vistos];
}

export interface InstanciaConEvidencia {
  url: string;
  metodo: string | null;
  parametro: string | null;
  attack: string | null;
  evidence: string | null;
}

const vacio = (v: string | null | undefined) => (v ? v : null);

/**
 * Las instancias normalizadas (todas las que se han visto, de todos los
 * escaneos) con el attack y la evidence de la alerta original de ZAP cuando
 * coinciden URL, método y parámetro.
 */
export function instanciasConEvidencia(h: HallazgoDetalle): InstanciaConEvidencia[] {
  const crudas: InstanciaZap[] = Array.isArray(h.origen?.instances) ? h.origen.instances : [];
  const clave = (url?: string | null, metodo?: string | null, param?: string | null) =>
    `${url ?? ""}|${(metodo ?? "").toUpperCase()}|${param ?? ""}`;
  const porClave = new Map(crudas.map((i) => [clave(i.uri, i.method, i.param), i]));

  return h.instancias.map((i) => {
    const zap = porClave.get(clave(i.url, i.metodo, i.parametro));
    return {
      url: i.url,
      metodo: i.metodo,
      parametro: i.parametro,
      attack: vacio(zap?.attack),
      evidence: vacio(zap?.evidence),
    };
  });
}

/** "High (Low)" -> { riesgo: "High", confianza: "Low" } */
export function riesgoYConfianza(h: HallazgoDetalle): { riesgo: string | null; confianza: string | null } {
  const m = /^\s*([^()]+?)\s*\(([^)]+)\)\s*$/.exec(h.origen?.riskdesc ?? "");
  const capital = (s: string | null) => (s ? s[0].toUpperCase() + s.slice(1) : null);
  return {
    riesgo: m?.[1] ?? h.severidad_herramienta,
    confianza: m?.[2] ?? capital(h.confianza_herramienta),
  };
}
