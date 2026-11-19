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

export default async function Inicio() {
  let escaneo: Escaneo | undefined;
  let fallo: ErrorApi | null = null;
  try {
    [escaneo] = await listarEscaneos();
  } catch (error) {
    if (!(error instanceof ErrorApi)) throw error;
    fallo = error;
  }

  return (
    <Marco>
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <h1 className="text-2xl font-semibold tracking-tight text-navy">Inicio</h1>
        {/* ImportarReporte recibe el id del último escaneo: si es el que se
            acaba de importar, oculta el enlace repetido de "Último escaneo". */}
        <ImportarReporte ultimoEscaneoId={escaneo?.id ?? null}>
          {fallo ? (
            <section aria-labelledby="titulo-ultimo">
              <TituloUltimo />
              <AvisoApiCaida titulo="No se pudo cargar el último escaneo" mensaje={fallo.message} />
            </section>
          ) : (
            <UltimoEscaneo escaneo={escaneo} />
          )}
        </ImportarReporte>
      </div>
    </Marco>
  );
}

function UltimoEscaneo({ escaneo }: { escaneo: Escaneo | undefined }) {
  return (
    <section aria-labelledby="titulo-ultimo">
      <TituloUltimo conEnlace={escaneo !== undefined} />
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
          {/* Oculto si es el escaneo recién importado (o el que un 409 dice que
              ya estaba): el resultado de arriba ya enlaza a sus hallazgos. */}
          <div className="mt-4 border-t pt-4 group-data-[recien-importado=true]/ultimo:hidden">
            <Link href={hrefHallazgosDeEscaneo(escaneo.id)} className={claseEnlace}>
              Ver sus hallazgos
            </Link>
          </div>
        </div>
      )}
    </section>
  );
}

function TituloUltimo({ conEnlace = false }: { conEnlace?: boolean }) {
  return (
    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
      <h2 id="titulo-ultimo" className="flex items-center gap-2 font-semibold text-navy">
        <History aria-hidden className="size-4 text-escaner" />
        Último escaneo
      </h2>
      {conEnlace && (
        <Link href="/escaneos" className={claseEnlace}>
          Ver todos los escaneos
        </Link>
      )}
    </div>
  );
}
