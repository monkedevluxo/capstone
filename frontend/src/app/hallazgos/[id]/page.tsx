import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { cookies } from "next/headers";
import { notFound } from "next/navigation";

import { CabeceraHallazgo } from "@/components/detalle/cabecera";
import { CapaIA } from "@/components/detalle/capa-ia";
import { CapaPersona } from "@/components/detalle/capa-persona";
import { CapaZap } from "@/components/detalle/capa-zap";
import { EnriquecerHallazgo } from "@/components/detalle/enriquecer-hallazgo";
import { AvisoApiCaida, Marco } from "@/components/marco";
import { ErrorApi, obtenerHallazgo, type HallazgoDetalle } from "@/lib/api";
import { UUID_VALIDO, hrefVolver } from "@/lib/filtros";
import { COOKIE_NOMBRE_REVISOR } from "@/lib/revisor";

/** "<título del hallazgo> · SentinelAI" en la pestaña. */
export async function generateMetadata({ params }: PageProps<"/hallazgos/[id]">): Promise<Metadata> {
  const id = (await params).id.toLowerCase();
  // Si no existe, la página llama a notFound() y queda el título del layout.
  if (!UUID_VALIDO.test(id)) return {};
  try {
    // La misma consulta que la página (cache): la API recibe una sola.
    const h = await obtenerHallazgo(id);
    return { title: `${h.titulo} · SentinelAI` };
  } catch {
    // 404 o API caída: la página muestra el aviso que corresponde.
    return { title: "Hallazgo · SentinelAI" };
  }
}

/**
 * Detalle de un hallazgo en tres capas: lo que dijo el escáner, lo que
 * interpretó el modelo y lo que decide una persona (T-052).
 */
export default async function PaginaHallazgo({ params, searchParams }: PageProps<"/hallazgos/[id]">) {
  const { id: crudo } = await params;
  const volver = hrefVolver((await searchParams).desde);

  // Un id que no es UUID no existe: no se le pregunta a la API.
  const id = crudo.toLowerCase();
  if (!UUID_VALIDO.test(id)) notFound();

  let hallazgo: HallazgoDetalle;
  try {
    hallazgo = await obtenerHallazgo(id);
  } catch (error) {
    if (error instanceof ErrorApi && error.status === 404) notFound();
    if (error instanceof ErrorApi) {
      return (
        <Marco>
          <EnlaceVolver href={volver} />
          <AvisoApiCaida titulo="No se pudo cargar el hallazgo" mensaje={error.message} />
        </Marco>
      );
    }
    throw error;
  }

  return (
    <Marco>
      <EnlaceVolver href={volver} />
      <CabeceraHallazgo hallazgo={hallazgo} />

      <div className="@container mt-8">
        <div className="grid items-start gap-6 @4xl:grid-cols-2">
          <CapaZap hallazgo={hallazgo} />
          <CapaIA
            hallazgo={hallazgo}
            acciones={
              <EnriquecerHallazgo
                id={hallazgo.id}
                situacion={
                  hallazgo.ia === null
                    ? "sin_enriquecer"
                    : hallazgo.ia.estado === "failed"
                      ? "fallido"
                      : "ok"
                }
              />
            }
          />
        </div>
      </div>

      <CapaPersona
        hallazgo={hallazgo}
        revisorInicial={(await cookies()).get(COOKIE_NOMBRE_REVISOR)?.value ?? ""}
      />
    </Marco>
  );
}

function EnlaceVolver({ href }: { href: string }) {
  return (
    <Link
      href={href}
      className="mb-5 inline-flex items-center gap-1 rounded-sm text-sm font-medium text-navy underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      <ArrowLeft aria-hidden className="size-4" />
      Volver a hallazgos
    </Link>
  );
}
