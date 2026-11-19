// T-058 / T-059: el módulo "Informe" abre el informe técnico.
//
// La página la arma la API (GET /informe) y es HTML autocontenido, pensado
// para guardarlo o imprimirlo a PDF. Este handler la pide desde el servidor de
// Next y la devuelve tal cual: el navegador no habla con la API directo, igual
// que en el resto del dashboard.

import { API_URL, SIN_CONEXION } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const objetivo = new URL(request.url).searchParams.get("objetivo");
  const ruta = objetivo ? `/informe?${new URLSearchParams({ objetivo })}` : "/informe";

  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
  } catch (causa) {
    console.error(`[api] GET ${API_URL}${ruta} falló:`, causa);
    return pagina(502, "Informe no disponible", `${SIN_CONEXION}. Revisa que el laboratorio esté arriba.`);
  }

  if (respuesta.status === 404) {
    const { detail } = (await respuesta.json().catch(() => ({}))) as { detail?: string };
    return pagina(404, "Todavía no hay informe", `La API respondió: ${detail ?? "no hay datos"}.`);
  }
  if (!respuesta.ok) {
    return pagina(502, "Informe no disponible", `La API respondió ${respuesta.status}.`);
  }

  return new Response(await respuesta.text(), {
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

/** Página mínima para los errores: el informe se abre en otra pestaña, fuera del dashboard. */
function pagina(estado: number, titulo: string, mensaje: string) {
  const entidades: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const escapar = (s: string) => s.replace(/[&<>"']/g, (c) => entidades[c] ?? c);
  const html = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>${escapar(titulo)} · SentinelAI</title>
<style>body{font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem;color:#1f2937}</style>
</head><body><h1>${escapar(titulo)}</h1><p>${escapar(mensaje)}</p>
<p><a href="/">Volver al dashboard</a></p></body></html>`;
  return new Response(html, { status: estado, headers: { "Content-Type": "text/html; charset=utf-8" } });
}
