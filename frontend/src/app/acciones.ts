"use server";

// Server Actions de la pantalla Inicio. El navegador nunca habla con la API:
// le manda el archivo al servidor de Next y este lo reenvía a API_URL. Así la
// API no necesita CORS y su dirección no llega al navegador.

import { revalidatePath } from "next/cache";

import { ErrorApi, enviar, type ResumenImportacion } from "@/lib/api";
import { MAX_REPORTE_BYTES } from "@/lib/limites";

export type ResultadoImportacion =
  | { tipo: "ok"; resumen: ResumenImportacion }
  /** 403: el objetivo no es del laboratorio. */
  | { tipo: "fuera_del_lab"; host: string }
  /** 409: el mismo reporte ya se importó; scanId es el escaneo previo. */
  | { tipo: "repetido"; scanId: string | null }
  /** 422 o JSON inválido. */
  | { tipo: "no_es_zap"; detalle: string | null }
  | { tipo: "muy_grande" }
  /** La API no respondió. */
  | { tipo: "api_caida"; mensaje: string }
  /** Cualquier otro código: no debería pasar. */
  | { tipo: "error"; mensaje: string };

export async function importarReporte(datos: FormData): Promise<ResultadoImportacion> {
  const archivo = datos.get("reporte");
  if (!(archivo instanceof File)) return { tipo: "no_es_zap", detalle: null };
  if (archivo.size > MAX_REPORTE_BYTES) return { tipo: "muy_grande" };

  // Se valida acá que sea JSON antes de mandarlo: un archivo cualquiera
  // terminaría en un 422 genérico de FastAPI.
  const texto = await archivo.text();
  let reporte: unknown;
  try {
    reporte = JSON.parse(texto);
  } catch {
    return { tipo: "no_es_zap", detalle: "No es un JSON válido." };
  }
  if (typeof reporte !== "object" || reporte === null || Array.isArray(reporte)) {
    return { tipo: "no_es_zap", detalle: null };
  }

  let respuesta;
  try {
    respuesta = await enviar("/scans/import", texto, 30_000);
  } catch (error) {
    if (error instanceof ErrorApi) return { tipo: "api_caida", mensaje: error.message };
    throw error;
  }

  const detalle = detalleDe(respuesta.datos);
  switch (respuesta.status) {
    case 201:
      // El "Último escaneo" de la página cambia.
      revalidatePath("/");
      return { tipo: "ok", resumen: respuesta.datos as ResumenImportacion };
    case 403:
      return { tipo: "fuera_del_lab", host: hostDelReporte(reporte) ?? hostDelError(detalle) };
    case 409:
      return { tipo: "repetido", scanId: typeof detalle?.scan_id === "string" ? detalle.scan_id : null };
    case 422:
      return {
        tipo: "no_es_zap",
        detalle: typeof detalle?.error === "string" ? detalle.error : null,
      };
    default:
      return { tipo: "error", mensaje: `La API respondió ${respuesta.status} al importar.` };
  }
}

/** `detail` de un HTTPException de FastAPI, si es un objeto. */
function detalleDe(datos: unknown): Record<string, unknown> | null {
  if (typeof datos !== "object" || datos === null) return null;
  const detail = (datos as { detail?: unknown }).detail;
  return typeof detail === "object" && detail !== null && !Array.isArray(detail)
    ? (detail as Record<string, unknown>)
    : null;
}

/** Host del objetivo según el propio reporte (site[0]["@name"]). */
function hostDelReporte(reporte: object): string | null {
  const sitios = (reporte as { site?: unknown }).site;
  const sitio = Array.isArray(sitios) ? sitios[0] : null;
  const nombre = (sitio as { "@name"?: unknown } | null)?.["@name"];
  if (typeof nombre !== "string") return null;
  try {
    return new URL(nombre).host;
  } catch {
    return null;
  }
}

/** Respaldo: la API escribe "'<host>' no es un objetivo del laboratorio…". */
function hostDelError(detalle: Record<string, unknown> | null): string {
  const texto = typeof detalle?.error === "string" ? detalle.error : "";
  return /^'([^']+)'/.exec(texto)?.[1] ?? "un host desconocido";
}
