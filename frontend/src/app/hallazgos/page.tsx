import Link from "next/link";
import type { Metadata } from "next";

import { FiltrosHallazgos } from "@/components/filtros-hallazgos";
import { Aviso, Marco } from "@/components/marco";
import { Paginacion } from "@/components/paginacion";
import { TablaHallazgos } from "@/components/tabla-hallazgos";
import { Totales } from "@/components/totales";
import { ErrorApi, listarHallazgos, obtenerResumen } from "@/lib/api";
import {
  POR_PAGINA,
  hayFiltros,
  hrefHallazgos,
  leerFiltros,
  parametrosApi,
  type SearchParams,
} from "@/lib/filtros";

export const metadata: Metadata = { title: "Hallazgos · SentinelAI" };

const claseEnlace = "font-medium text-ia underline-offset-4 hover:underline";

export default async function PaginaHallazgos({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  // Leer searchParams hace que la página se renderice en cada request, así
  // `next build` no intenta llamar a la API para prerenderizarla.
  const filtros = leerFiltros(await searchParams);
  const params = parametrosApi(filtros);

  let pagina, resumen;
  try {
    // Mismos filtros para la tabla y los totales: siempre cuadran.
    [pagina, resumen] = await Promise.all([
      listarHallazgos(params, POR_PAGINA, (filtros.pagina - 1) * POR_PAGINA),
      obtenerResumen(params),
    ]);
  } catch (error) {
    if (error instanceof ErrorApi) {
      return (
        <Marco>
          <Aviso titulo="No se pudo cargar la lista de hallazgos">
            {error.message}. Revisa que el servicio <code className="font-mono">api</code>{" "}
            esté levantado (<code className="font-mono">docker compose ps</code>).
          </Aviso>
        </Marco>
      );
    }
    throw error;
  }

  return (
    <Marco>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight text-navy">Hallazgos</h1>

      <div className="mb-6 flex flex-col gap-4">
        <Totales resumen={resumen} filtros={filtros} />
        <FiltrosHallazgos filtros={filtros} />
      </div>

      {pagina.total === 0 && !hayFiltros(filtros) ? (
        <Aviso titulo="Todavía no hay hallazgos">
          Importa un reporte de ZAP con <code className="font-mono">POST /scans/import</code>{" "}
          para verlos acá.
        </Aviso>
      ) : pagina.total === 0 ? (
        <Aviso
          titulo="Ningún hallazgo con estos filtros"
          accion={
            <Link href="/hallazgos" className={claseEnlace}>
              Limpiar filtros
            </Link>
          }
        >
          Prueba quitando alguno de los filtros de arriba.
        </Aviso>
      ) : pagina.items.length === 0 ? (
        <Aviso
          titulo="Esta página no tiene hallazgos"
          accion={
            <Link href={hrefHallazgos(filtros)} className={claseEnlace}>
              Ir a la primera página
            </Link>
          }
        >
          Hay {pagina.total} {pagina.total === 1 ? "hallazgo" : "hallazgos"} con estos filtros,
          pero no llegan hasta la página {filtros.pagina}.
        </Aviso>
      ) : (
        <div className="flex flex-col gap-4">
          <TablaHallazgos hallazgos={pagina.items} />
          <Paginacion filtros={filtros} mostrados={pagina.items.length} total={pagina.total} />
          <p className="max-w-3xl text-xs leading-relaxed text-muted-foreground">
            La confianza la declara el modelo. En el golden set fue igual de alta en aciertos
            (0,90) que en errores (0,93): úsala como contexto, no para decidir.
          </p>
        </div>
      )}
    </Marco>
  );
}
