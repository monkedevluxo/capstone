// Compartido entre el navegador (validación antes de subir) y la Server
// Action (validación de verdad). Debe quedar bajo serverActions.bodySizeLimit
// de next.config.ts (5 MB), que además cuenta el overhead del multipart.

/** Tamaño máximo del reporte de ZAP que se acepta subir. */
export const MAX_REPORTE_BYTES = 4 * 1024 * 1024;
export const MAX_REPORTE_TEXTO = "4 MB";
