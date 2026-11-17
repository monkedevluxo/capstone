import { Upload } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ListaEscaneos, type FilaEscaneo } from "@/components/lista-escaneos";
import { Aviso, AvisoApiCaida, Marco } from "@/components/marco";
import { buttonVariants } from "@/components/ui/button";
import { ErrorApi, listarEscaneos, obtenerResumen, type Escaneo } from "@/lib/api";
import { claseBotonPrincipal, claseEnlace } from "@/lib/estilos";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Escaneos · SentinelAI" };

export default async function PaginaEscaneos() {
  let escaneos: Escaneo[];
  try {
    escaneos = await listarEscaneos();
  } catch (error) {
    if (!(error instanceof ErrorApi)) throw error;
    return (
      <Marco>
        <Encabezado />
        <AvisoApiCaida titulo="No se pudo cargar la lista de escaneos" mensaje={error.message} />
      </Marco>
    );
  }

  // Un resumen por escaneo, en paralelo. Si uno falla, esa fila muestra "—"
  // en vez de botar la página: el escaneo existe aunque no sepamos sus conteos.
  const resumenes = await Promise.allSettled(
    escaneos.map((e) => obtenerResumen(new URLSearchParams({ scan_id: e.id }))),
  );
  const filas: FilaEscaneo[] = escaneos.map((escaneo, i) => {
    const r = resumenes[i];
    return {
      escaneo,
      sinEnriquecer: r.status === "fulfilled" ? r.value.sin_enriquecer : null,
      revisar: r.status === "fulfilled" ? r.value.revisar : null,
    };
  });

  return (
    <Marco>
      <Encabezado conAccion={escaneos.length > 0} />
      {escaneos.length === 0 ? (
        <Aviso
          titulo="Todavía no hay escaneos"
          accion={
            <Link href="/" className={claseEnlace}>
              Importar un reporte de ZAP
            </Link>
          }
        >
          Cada reporte que importes aparece acá, del más reciente al más antiguo, con sus
          hallazgos y cuántos faltan por enriquecer.
        </Aviso>
      ) : (
        <ListaEscaneos filas={filas} />
      )}
    </Marco>
  );
}

function Encabezado({ conAccion = false }: { conAccion?: boolean }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
      <h1 className="text-2xl font-semibold tracking-tight text-navy">Escaneos</h1>
      {conAccion && (
        <Link href="/" className={cn(buttonVariants(), "px-3", claseBotonPrincipal)}>
          <Upload aria-hidden />
          Importar reporte
        </Link>
      )}
    </div>
  );
}
