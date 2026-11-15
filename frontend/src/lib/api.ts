// Cliente de la API de SentinelAI. Solo se usa desde el servidor de Next:
// API_URL no lleva el prefijo NEXT_PUBLIC_, así que nunca llega al navegador
// y la API no necesita CORS.
//
// Los tipos reflejan a mano lo que devuelve backend/app/rutas.py. Si cambia
// la respuesta de la API, hay que cambiarlos acá.

import { unstable_rethrow } from "next/navigation";

export type Severidad = "critica" | "alta" | "media" | "baja" | "informativa";

export type EstadoHallazgo =
  | "nuevo"
  | "en_triage"
  | "confirmado"
  | "falso_positivo"
  | "riesgo_aceptado"
  | "remediado";

export type Prioridad = "p1" | "p2" | "p3" | "p4";

/** Ej: "A05:2025" */
export type CategoriaOwasp = `A${string}:2025`;

export interface ResumenIA {
  estado: "ok" | "failed";
  owasp: CategoriaOwasp | null;
  prioridad: Prioridad | null;
  confianza: number | null;
  motivo_fallo: string | null;
}

/** Campos de la opción mixta: los calcula la API al consultar. */
export interface Referencia {
  owasp_referencia: CategoriaOwasp | null;
  prioridad_regla: Prioridad | null;
  requiere_revision: boolean;
  motivo_revision: string | null;
}

export interface HallazgoResumen {
  id: string;
  titulo: string;
  severidad: Severidad;
  estado: EstadoHallazgo;
  ruta: string | null;
  metodo: string | null;
  parametro: string | null;
  cwe: number | null;
  ocurrencias: number;
  visto_por_ultima_vez: string;
  /** null si el hallazgo nunca se enriqueció. */
  ia: ResumenIA | null;
  referencia: Referencia;
}

export interface Pagina<T> {
  total: number;
  limit: number;
  offset: number;
  items: T[];
}

/** La API no respondió o respondió con un error. */
export class ErrorApi extends Error {
  constructor(
    message: string,
    readonly status?: number,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ErrorApi";
  }
}

const API_URL = process.env.API_URL ?? "http://localhost:8000";

/**
 * Lo que ve el navegador cuando la API no responde. La dirección interna
 * (http://api:8000) no se muestra: queda solo en el log del servidor.
 */
export const SIN_CONEXION = "No se pudo conectar con la API de SentinelAI";

function registrarFallo(metodo: string, ruta: string, causa: unknown) {
  console.error(`[api] ${metodo} ${API_URL}${ruta} falló:`, causa);
}

async function obtener<T>(ruta: string): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch (causa) {
    // Errores internos de Next (ej. el que marca la ruta como dinámica al
    // prerenderizar) no son fallas de la API: deben seguir su camino.
    unstable_rethrow(causa);
    registrarFallo("GET", ruta, causa);
    throw new ErrorApi(SIN_CONEXION, undefined, { cause: causa });
  }
  if (!respuesta.ok) {
    throw new ErrorApi(`La API respondió ${respuesta.status} en ${ruta}`, respuesta.status);
  }
  return (await respuesta.json()) as T;
}

export interface ResumenHallazgos {
  total: number;
  por_severidad: Record<Severidad, number>;
  por_estado: Record<EstadoHallazgo, number>;
  /** Marcados para revisar primero (requiere_revision). */
  revisar: number;
  /** Sin enriquecimiento vigente, o con uno fallido. */
  sin_enriquecer: number;
}

/** `filtros` son los mismos que recibe obtenerResumen, para que cuadren. */
export function listarHallazgos(filtros: URLSearchParams, limit: number, offset: number) {
  const q = new URLSearchParams(filtros);
  q.set("limit", String(limit));
  q.set("offset", String(offset));
  return obtener<Pagina<HallazgoResumen>>(`/findings?${q}`);
}

export function obtenerResumen(filtros: URLSearchParams) {
  const qs = filtros.toString();
  return obtener<ResumenHallazgos>(`/findings/resumen${qs ? `?${qs}` : ""}`);
}

// ── Escaneos e importación ───────────────────────────────────────────────

export interface Escaneo {
  id: string;
  target_id: string;
  /** base_url del target, ej. "http://juiceshop:3000". */
  objetivo: string;
  herramienta: string;
  version: string | null;
  estado: string;
  /** ISO 8601 */
  fecha: string;
  stats: {
    hallazgos?: number;
    nuevos?: number;
    repetidos?: number;
    descartados?: number;
    por_severidad?: Partial<Record<Severidad, number>>;
  } | null;
}

/** GET /scans: el primero es el más reciente. */
export function listarEscaneos() {
  return obtener<Escaneo[]>("/scans");
}

/** Respuesta 201 de POST /scans/import. */
export interface ResumenImportacion {
  scan_id: string;
  target_id: string;
  objetivo: string;
  /** Tipos de alerta en el reporte de ZAP. */
  hallazgos_en_reporte: number;
  nuevos: number;
  repetidos: number;
  descartados: number;
  por_severidad: Partial<Record<Severidad, number>>;
}

/** Respuesta sin interpretar: el que llama decide qué hacer con cada código. */
export interface RespuestaApi {
  status: number;
  datos: unknown;
}

/**
 * POST a la API. A diferencia de obtener(), no lanza error si la API responde
 * con un código de error: devuelve el código y el cuerpo. Solo lanza ErrorApi
 * si no hubo respuesta (API caída o se acabó el tiempo).
 */
export async function enviar(
  ruta: string,
  cuerpo: string | undefined,
  timeoutMs: number,
): Promise<RespuestaApi> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      method: "POST",
      cache: "no-store",
      headers: cuerpo === undefined ? undefined : { "Content-Type": "application/json" },
      body: cuerpo,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (causa) {
    unstable_rethrow(causa);
    registrarFallo("POST", ruta, causa);
    const tiempo = causa instanceof DOMException && causa.name === "TimeoutError";
    throw new ErrorApi(
      tiempo ? `La API no respondió en ${Math.round(timeoutMs / 1000)} s` : SIN_CONEXION,
      undefined,
      { cause: causa },
    );
  }
  let datos: unknown = null;
  try {
    datos = await respuesta.json();
  } catch {
    // Cuerpo vacío o que no es JSON: el código basta.
  }
  return { status: respuesta.status, datos };
}

/** Respuesta 200 de POST /scans/{id}/enrich. */
export interface ResumenLote {
  scan_id: string;
  procesados: number;
  enriquecidos: number;
  fallidos: number;
  /** Ya tenían un enriquecimiento válido (solo_pendientes=true). */
  omitidos: number;
  /** Ej. "ollama_no_disponible" si Ollama se cayó a la mitad. */
  detenido_por: string | null;
  hallazgos: { id: string; titulo: string; estado: "ok" | "failed"; motivo_fallo: string | null }[];
}
