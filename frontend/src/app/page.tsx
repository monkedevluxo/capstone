import { History } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ImportarReporte } from "@/components/importar-reporte";
import { Aviso, AvisoApiCaida, Marco } from "@/components/marco";
import { claseEnlace } from "@/lib/estilos";
import { ErrorApi, listarEscaneos, type Escaneo } from "@/lib/api";
import { hrefHallazgosDeEscaneo } from "@/lib/filtros";

export const metadata: Metadata = { title: "Inicio · SentinelAI" };

const HERRAMIENTAS: Record<string, string> = { zap: "OWASP ZAP" };

const formatoFecha = new Intl.DateTimeFormat("es-CL", {
  dateStyle: "long",
  timeStyle: "short",
  timeZone: "America/Santiago",
});

export default function Inicio() {
  return (
    <Marco>
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <h1 className="text-2xl font-semibold tracking-tight text-navy">Inicio</h1>
        <ImportarReporte />
        <UltimoEscaneo />
      </div>
    </Marco>
  );
}

async function UltimoEscaneo() {
  let escaneo: Escaneo | undefined;
  try {
    [escaneo] = await listarEscaneos();
  } catch (error) {
    if (error instanceof ErrorApi) {
      return (
        <section aria-labelledby="titulo-ultimo">
          <TituloUltimo />
          <AvisoApiCaida titulo="No se pudo cargar el último escaneo" mensaje={error.message} />
        </section>
      );
    }
    throw error;
  }

  return (
    <section aria-labelledby="titulo-ultimo">
      <TituloUltimo />
      {!escaneo ? (
        <Aviso titulo="Todavía no hay escaneos">
          Cuando importes el primer reporte de ZAP, acá vas a ver cuándo fue y cuántos hallazgos
          trajo.
        </Aviso>
      ) : (
        <div className="rounded-lg border bg-card p-5">
          <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-muted-foreground">Fecha</dt>
            <dd className="text-foreground">
              <time dateTime={escaneo.fecha}>{formatoFecha.format(new Date(escaneo.fecha))}</time>
            </dd>
            <dt className="text-muted-foreground">Herramienta</dt>
            <dd className="text-foreground">
              {HERRAMIENTAS[escaneo.herramienta] ?? escaneo.herramienta}
              {escaneo.version && <span className="text-muted-foreground"> {escaneo.version}</span>}
            </dd>
            <dt className="text-muted-foreground">Objetivo</dt>
            <dd className="font-mono break-all text-escaner">{escaneo.objetivo}</dd>
            {escaneo.stats?.hallazgos !== undefined && (
              <>
                <dt className="text-muted-foreground">Hallazgos</dt>
                <dd className="text-foreground tabular-nums">
                  {escaneo.stats.hallazgos}
                  {escaneo.stats.nuevos !== undefined && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {escaneo.stats.nuevos} {escaneo.stats.nuevos === 1 ? "nuevo" : "nuevos"}
                    </span>
                  )}
                </dd>
              </>
            )}
          </dl>
          <div className="mt-4 border-t pt-4">
            <Link href={hrefHallazgosDeEscaneo(escaneo.id)} className={claseEnlace}>
              Ver sus hallazgos
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function TituloUltimo() {
  return (
    <h2 id="titulo-ultimo" className="mb-3 flex items-center gap-2 font-semibold text-navy">
      <History aria-hidden className="size-4 text-escaner" />
      Último escaneo
    </h2>
  );
}
