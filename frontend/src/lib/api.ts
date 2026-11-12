// Cliente de la API de SentinelAI. Solo se usa desde el servidor de Next:
// API_URL no lleva el prefijo NEXT_PUBLIC_, así que nunca llega al navegador
// y la API no necesita CORS.
//
// Los tipos reflejan a mano lo que devuelve backend/app/rutas.py. Si cambia
// la respuesta de la API, hay que cambiarlos acá.

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

async function obtener<T>(ruta: string): Promise<T> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch (causa) {
    throw new ErrorApi(`No se pudo conectar con la API en ${API_URL}`, undefined, {
      cause: causa,
    });
  }
  if (!respuesta.ok) {
    throw new ErrorApi(`La API respondió ${respuesta.status} en ${ruta}`, respuesta.status);
  }
  return (await respuesta.json()) as T;
}

export function listarHallazgos(params: { limit?: number; offset?: number } = {}) {
  const q = new URLSearchParams({
    limit: String(params.limit ?? 50),
    offset: String(params.offset ?? 0),
  });
  return obtener<Pagina<HallazgoResumen>>(`/findings?${q}`);
}
