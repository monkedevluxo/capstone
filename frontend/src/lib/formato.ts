// Fechas y números como se leen en Chile.

const fechaLarga = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "America/Santiago",
});

const fechaCorta = new Intl.DateTimeFormat("es-CL", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "America/Santiago",
});

/** "11 de noviembre de 2026 a las 11:25 p. m." */
export const fechaHora = (iso: string) => fechaLarga.format(new Date(iso));

/** "11 nov 2026" */
export const fecha = (iso: string) => fechaCorta.format(new Date(iso));

/** 0.9 -> "0,90" */
export const confianza = (valor: number) => valor.toFixed(2).replace(".", ",");

/** 21295 -> "21,3 s" */
export const segundos = (ms: number) => `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
