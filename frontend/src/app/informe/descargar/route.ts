// Descarga del informe en PDF, CSV o XLSX (GET /informe.pdf, /informe.csv y
// /informe.xlsx de la API).
//
// Igual que /informe/ver: el servidor de Next pide el archivo y lo entrega al
// navegador con el nombre que puso la API, así el navegador nunca ve API_URL.

import { API_URL, SIN_CONEXION } from "@/lib/api";

export const dynamic = "force-dynamic";

const FORMATOS = new Set(["pdf", "csv", "xlsx"]);

export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const formato = params.get("formato") ?? "";
  if (!FORMATOS.has(formato)) {
    return texto(400, "Formato no válido: usa pdf, csv o xlsx.");
  }
  const objetivo = params.get("objetivo");
  const ruta = `/informe.${formato}${objetivo ? `?${new URLSearchParams({ objetivo })}` : ""}`;

  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
  } catch (causa) {
    console.error(`[api] GET ${API_URL}${ruta} falló:`, causa);
    return texto(502, `${SIN_CONEXION}. Revisa que el laboratorio esté arriba.`);
  }

  if (!respuesta.ok) {
    const { detail } = (await respuesta.json().catch(() => ({}))) as { detail?: string };
    return texto(respuesta.status === 404 ? 404 : 502, detail ?? `La API respondió ${respuesta.status}.`);
  }

  const cabeceras = new Headers({
    "Content-Type": respuesta.headers.get("content-type") ?? "application/octet-stream",
    "Cache-Control": "no-store",
  });
  const disposicion = respuesta.headers.get("content-disposition");
  if (disposicion) cabeceras.set("Content-Disposition", disposicion);
  return new Response(respuesta.body, { headers: cabeceras });
}

function texto(estado: number, mensaje: string) {
  return new Response(mensaje, {
    status: estado,
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
