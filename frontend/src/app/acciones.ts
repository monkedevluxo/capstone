"use server";

// Server Actions de la pantalla Inicio. El navegador nunca habla con la API:
// le manda el archivo al servidor de Next y este lo reenvía a API_URL. Así la
// API no necesita CORS y su dirección no llega al navegador.

import { revalidatePath } from "next/cache";

import {
  ErrorApi,
  enviar,
  type DetalleIA,
  type ResumenImportacion,
  type ResumenLote,
} from "@/lib/api";
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

// ── Enriquecimiento ───────────────────────────────────────────────────────

/**
 * El lote es síncrono: 1-2 s por hallazgo y más la primera vez, mientras
 * Ollama carga el modelo. Los 10 s de obtener() no alcanzan. Queda bajo los
 * 300 s que espera por defecto el fetch de Node (undici) a que lleguen las
 * cabeceras, para que el corte sea nuestro y con mensaje claro.
 */
const TIMEOUT_ENRIQUECER_MS = 290_000;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ResultadoEnriquecimiento =
  | { tipo: "ok"; lote: ResumenLote }
  /** 503: Ollama no respondió y no se procesó nada. */
  | { tipo: "ollama_apagado" }
  /** 404 */
  | { tipo: "no_existe" }
  /** Se acabó el tiempo; lo ya procesado quedó guardado. */
  | { tipo: "tiempo" }
  | { tipo: "api_caida"; mensaje: string }
  | { tipo: "error"; mensaje: string };

export async function enriquecerEscaneo(scanId: string): Promise<ResultadoEnriquecimiento> {
  if (typeof scanId !== "string" || !UUID.test(scanId)) return { tipo: "no_existe" };

  let respuesta;
  try {
    respuesta = await enviar(
      `/scans/${scanId}/enrich?solo_pendientes=true`,
      undefined,
      TIMEOUT_ENRIQUECER_MS,
    );
  } catch (error) {
    if (error instanceof ErrorApi) {
      const causa = error.cause;
      if (causa instanceof DOMException && causa.name === "TimeoutError") return { tipo: "tiempo" };
      return { tipo: "api_caida", mensaje: error.message };
    }
    throw error;
  }

  switch (respuesta.status) {
    case 200:
      return { tipo: "ok", lote: respuesta.datos as ResumenLote };
    case 503:
      return { tipo: "ollama_apagado" };
    case 404:
      return { tipo: "no_existe" };
    default:
      return { tipo: "error", mensaje: `La API respondió ${respuesta.status} al enriquecer.` };
  }
}

// ── Enriquecer un hallazgo (detalle) ──────────────────────────────────────

export type ResultadoEnriquecerHallazgo =
  /** El modelo respondió. vigente:false = falló y se conservó el anterior. */
  | { tipo: "ok"; vigente: boolean; estado: "ok" | "failed"; motivoFallo: string | null }
  | { tipo: "ollama_apagado" }
  | { tipo: "no_existe" }
  | { tipo: "tiempo" }
  | { tipo: "api_caida"; mensaje: string }
  | { tipo: "error"; mensaje: string };

export async function enriquecerHallazgo(id: string): Promise<ResultadoEnriquecerHallazgo> {
  if (typeof id !== "string" || !UUID.test(id)) return { tipo: "no_existe" };

  let respuesta;
  try {
    // Hasta 3 intentos del modelo: el mismo margen que el lote.
    respuesta = await enviar(`/findings/${id}/enrich`, undefined, TIMEOUT_ENRIQUECER_MS);
  } catch (error) {
    if (error instanceof ErrorApi) {
      const causa = error.cause;
      if (causa instanceof DOMException && causa.name === "TimeoutError") return { tipo: "tiempo" };
      return { tipo: "api_caida", mensaje: error.message };
    }
    throw error;
  }

  switch (respuesta.status) {
    case 200: {
      const datos = respuesta.datos as { vigente: boolean; ia: DetalleIA };
      // La página vuelve a pedir el hallazgo y muestra lo nuevo.
      revalidatePath(`/hallazgos/${id}`);
      return {
        tipo: "ok",
        vigente: datos.vigente,
        estado: datos.ia.estado,
        motivoFallo: datos.ia.motivo_fallo,
      };
    }
    case 503:
      return { tipo: "ollama_apagado" };
    case 404:
      return { tipo: "no_existe" };
    default:
      return { tipo: "error", mensaje: `La API respondió ${respuesta.status} al enriquecer.` };
  }
}
