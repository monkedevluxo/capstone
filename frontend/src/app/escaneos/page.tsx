import type { Metadata } from "next";

import { Aviso, Marco } from "@/components/marco";

export const metadata: Metadata = { title: "Escaneos · SentinelAI" };

export default function PaginaEscaneos() {
  return (
    <Marco>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight text-navy">Escaneos</h1>
      <Aviso titulo="En construcción">
        Acá se van a importar reportes de ZAP y enriquecer los hallazgos pendientes.
      </Aviso>
    </Marco>
  );
}
