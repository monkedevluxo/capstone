import type { Metadata } from "next";
import Link from "next/link";

import { VistaInforme } from "@/components/informe/vista-informe";
import { Aviso, AvisoApiCaida, Marco } from "@/components/marco";
import { ErrorApi, obtenerResumen } from "@/lib/api";
import { claseEnlace } from "@/lib/estilos";

export const metadata: Metadata = { title: "Informe · SentinelAI" };

export default async function PaginaInforme({
  searchParams,
}: {
  searchParams: Promise<{ objetivo?: string | string[] }>;
}) {
  // Leer searchParams hace que la página se renderice en cada request.
  const { objetivo } = await searchParams;
  const elegido = typeof objetivo === "string" && objetivo ? objetivo : undefined;

  let total: number;
  try {
    total = (await obtenerResumen(new URLSearchParams())).total;
  } catch (error) {
    if (!(error instanceof ErrorApi)) throw error;
    return (
      <Marco>
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-navy">Informe</h1>
        <AvisoApiCaida titulo="No se pudo preparar el informe" mensaje={error.message} />
      </Marco>
    );
  }

  if (total === 0) {
    return (
      <Marco>
        <h1 className="mb-6 text-2xl font-semibold tracking-tight text-navy">Informe</h1>
        <Aviso
          titulo="Todavía no hay informe"
          accion={
            <Link href="/" className={claseEnlace}>
              Importar un reporte de ZAP
            </Link>
          }
        >
          El informe se arma con los hallazgos importados. Cuando haya al menos un escaneo, podrás
          verlo acá y exportarlo a PDF, Excel o CSV.
        </Aviso>
      </Marco>
    );
  }

  return (
    <Marco>
      <VistaInforme objetivo={elegido} />
    </Marco>
  );
}
