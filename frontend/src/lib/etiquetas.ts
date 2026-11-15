// Textos para los códigos que devuelve la API. Un solo lugar para que la
// lista y el detalle digan lo mismo.

import type { DecisionValidacion, EstadoHallazgo } from "@/lib/api";
import { CATEGORIAS_OWASP } from "@/lib/filtros";

export const ESTADO_HALLAZGO: Record<EstadoHallazgo, string> = {
  nuevo: "Nuevo",
  en_triage: "En triage",
  confirmado: "Confirmado",
  falso_positivo: "Falso positivo",
  riesgo_aceptado: "Riesgo aceptado",
  remediado: "Remediado",
};

/** motivo_revision de la referencia (app/ia/owasp_por_cwe.py). */
export const MOTIVO_REVISION: Record<string, string> = {
  categoria_distinta: "categoría distinta",
  cwe_fuera_de_tabla: "CWE fuera de la tabla",
};

/** motivo_fallo de un enriquecimiento fallido (app/ia/). */
export const MOTIVO_FALLO: Record<string, string> = {
  json_invalido: "el modelo no devolvió JSON válido en ninguno de sus intentos",
  esquema_invalido: "la respuesta del modelo no cumplió el esquema en ninguno de sus intentos",
  timeout: "el modelo no respondió a tiempo",
  respuesta_http_invalida: "Ollama respondió con un error",
  ollama_no_disponible: "Ollama no estaba disponible",
  error_ollama: "error al hablar con Ollama",
  sin_intentos: "no se alcanzó a hacer ningún intento",
};

export const DECISION: Record<DecisionValidacion, string> = {
  confirmado: "Confirmado",
  falso_positivo: "Falso positivo",
  riesgo_aceptado: "Riesgo aceptado",
  duplicado: "Duplicado",
  requiere_segunda_opinion: "Requiere segunda opinión",
};

/** "A05:2025" -> "Injection" */
export function nombreOwasp(categoria: string | null | undefined): string | null {
  return CATEGORIAS_OWASP.find((c) => c.valor === categoria)?.nombre ?? null;
}

export function textoMotivo(mapa: Record<string, string>, codigo: string | null | undefined) {
  return codigo ? (mapa[codigo] ?? codigo) : null;
}
