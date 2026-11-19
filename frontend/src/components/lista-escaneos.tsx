"use client";

import Link from "next/link";

import {
  BotonEnriquecer,
  EstadoEnriquecimiento,
  useEnriquecerEscaneo,
} from "@/components/enriquecer-escaneo";
import type { Escaneo } from "@/lib/api";
import { claseEnlace } from "@/lib/estilos";
import { hrefHallazgosDeEscaneo } from "@/lib/filtros";
import { fecha, hora } from "@/lib/formato";
import { cn } from "@/lib/utils";

export interface FilaEscaneo {
  escaneo: Escaneo;
  /** null si GET /findings/resumen?scan_id= falló para este escaneo. */
  sinEnriquecer: number | null;
  revisar: number | null;
}

const HERRAMIENTAS: Record<string, string> = { zap: "OWASP ZAP" };

/**
 * Historial de escaneos: filas de una grilla cuando el contenedor es ancho y
 * tarjetas apiladas cuando no, con la misma regla que la lista de hallazgos
 * (ancho del contenedor, no de la ventana).
 *
 * A diferencia de esa tabla, cada escaneo es UN solo elemento que cambia de
 * forma (subgrid en ancho, tarjeta en angosto): así el enriquecimiento en
 * curso o su resultado no se pierde al cambiar de tamaño, y hay un solo
 * botón por escaneo en el árbol de accesibilidad. Las etiquetas de cada dato
 * son visibles en la tarjeta y quedan solo para lectores de pantalla en la
 * grilla, donde las dice el encabezado.
 */
export function ListaEscaneos({ filas }: { filas: FilaEscaneo[] }) {
  return (
    <div className="@container">
      <ul
        aria-label="Escaneos importados, del más reciente al más antiguo"
        className={cn(
          "flex flex-col gap-3",
          "@4xl:grid @4xl:grid-cols-[7rem_minmax(0,1fr)_5.5rem_7.5rem_5rem_max-content] @4xl:gap-0",
          "@4xl:rounded-lg @4xl:border @4xl:bg-card",
        )}
      >
        <li
          aria-hidden
          className="hidden text-sm font-medium whitespace-nowrap text-foreground @4xl:col-span-full @4xl:grid @4xl:grid-cols-subgrid @4xl:border-b"
        >
          <span className="px-3 py-2.5">Fecha</span>
          <span className="px-2 py-2.5">Escaneo</span>
          <span className="px-2 py-2.5 text-right">Hallazgos</span>
          <span className="px-2 py-2.5 text-right">Sin enriquecer</span>
          <span className="px-2 py-2.5 text-right">Revisar</span>
          <span className="py-2.5 pr-3 pl-4">Acciones</span>
        </li>
        {filas.map((f) => (
          <ElementoEscaneo key={f.escaneo.id} fila={f} />
        ))}
      </ul>
    </div>
  );
}

function ElementoEscaneo({ fila }: { fila: FilaEscaneo }) {
  const { escaneo: e, sinEnriquecer, revisar } = fila;
  const { enCurso, resultado, enriquecer } = useEnriquecerEscaneo(e.id);
  const quedanPendientes = sinEnriquecer !== null && sinEnriquecer > 0;
  const hallazgos = e.stats?.hallazgos;
  const nuevos = e.stats?.nuevos;

  return (
    <li
      className={cn(
        "rounded-lg border bg-card p-4",
        "@4xl:col-span-full @4xl:grid @4xl:grid-cols-subgrid @4xl:items-center",
        "@4xl:rounded-none @4xl:border-0 @4xl:border-b @4xl:bg-transparent @4xl:p-0 @4xl:last:border-b-0",
        "@4xl:transition-colors @4xl:hover:bg-muted/40",
      )}
    >
      <div className="contents">
        {/* Escaneo: herramienta, id corto y objetivo. Primero en la tarjeta,
            segunda columna en la grilla. */}
        <div className="min-w-0 @4xl:order-2 @4xl:px-2 @4xl:py-3">
          <dl className="flex flex-wrap items-baseline justify-between gap-x-3 @4xl:justify-start">
            <dt className="sr-only">Herramienta</dt>
            <dd className="font-medium text-foreground">
              {HERRAMIENTAS[e.herramienta] ?? e.herramienta}
              {e.version && <span className="font-normal text-muted-foreground"> {e.version}</span>}
            </dd>
            <dt className="sr-only">Id</dt>
            <dd className="font-mono text-xs text-muted-foreground" title={e.id}>
              {e.id.slice(0, 8)}
            </dd>
          </dl>
          <dl>
            <dt className="sr-only">Objetivo</dt>
            <dd className="truncate font-mono text-xs text-escaner" title={e.objetivo}>
              {e.objetivo}
            </dd>
          </dl>
        </div>

        <dl className="mt-1 text-sm text-muted-foreground @4xl:order-1 @4xl:mt-0 @4xl:px-3 @4xl:py-3">
          <dt className="sr-only">Fecha</dt>
          <dd>
            <time dateTime={e.fecha}>
              <span className="text-foreground @4xl:block">{fecha(e.fecha)}</span>
              <span className="@4xl:hidden">, </span>
              <span className="tabular-nums">{hora(e.fecha)}</span>
            </time>
          </dd>
        </dl>

        {/* Conteos: en la tarjeta, tres columnas con etiqueta; en la grilla,
            una celda cada uno (display: contents). */}
        <div className="mt-3 grid grid-cols-3 gap-3 border-t pt-3 text-sm @lg:grid-cols-[repeat(3,minmax(0,10rem))] @4xl:contents">
          <Conteo etiqueta="Hallazgos" orden="@4xl:order-3">
            {hallazgos === undefined ? (
              <SinDato />
            ) : (
              <>
                <span className="font-semibold text-navy">{hallazgos}</span>
                {nuevos !== undefined && (
                  <span className="block text-xs text-muted-foreground">
                    {nuevos} {nuevos === 1 ? "nuevo" : "nuevos"}
                  </span>
                )}
              </>
            )}
          </Conteo>
          <Conteo etiqueta="Sin enriquecer" orden="@4xl:order-4">
            {sinEnriquecer === null ? (
              <SinDato />
            ) : (
              <span className={sinEnriquecer > 0 ? "font-semibold text-ia" : "text-muted-foreground"}>
                {sinEnriquecer}
              </span>
            )}
          </Conteo>
          <Conteo etiqueta="Revisar" orden="@4xl:order-5">
            {revisar === null ? (
              <SinDato />
            ) : (
              <span
                className={revisar > 0 ? "font-semibold text-persona-texto" : "text-muted-foreground"}
              >
                {revisar}
              </span>
            )}
          </Conteo>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t pt-3 @4xl:order-6 @4xl:mt-0 @4xl:flex-nowrap @4xl:border-t-0 @4xl:py-2 @4xl:pr-3 @4xl:pl-4">
        <Link href={hrefHallazgosDeEscaneo(e.id)} className={cn(claseEnlace, "whitespace-nowrap")}>
          Ver hallazgos
        </Link>
        {quedanPendientes && !enCurso && !resultado && <BotonEnriquecer onClick={enriquecer} />}
      </div>

      {(enCurso || resultado) && (
        <div className="mt-3 border-t pt-3 @4xl:order-7 @4xl:col-span-full @4xl:mt-0 @4xl:border-dashed @4xl:px-3 @4xl:pb-4">
          <EstadoEnriquecimiento enCurso={enCurso} resultado={resultado} enriquecer={enriquecer} />
        </div>
      )}
    </li>
  );
}

function Conteo({
  etiqueta,
  orden,
  children,
}: {
  etiqueta: string;
  orden: string;
  children: React.ReactNode;
}) {
  return (
    <dl className={cn("tabular-nums @4xl:px-2 @4xl:py-3 @4xl:text-right", orden)}>
      <dt className="text-xs text-muted-foreground @4xl:sr-only">{etiqueta}</dt>
      <dd>{children}</dd>
    </dl>
  );
}

/** El dato no llegó (la consulta de ese escaneo falló). */
function SinDato() {
  return (
    <span className="text-muted-foreground" title="No se pudo consultar este dato">
      —<span className="sr-only"> (no se pudo consultar)</span>
    </span>
  );
}
