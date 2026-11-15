import type { Metadata } from "next";

import { Aviso, Marco } from "@/components/marco";

export const metadata: Metadata = { title: "Inicio · SentinelAI" };

export default function Inicio() {
  return (
    <Marco>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight text-navy">Inicio</h1>
      <Aviso titulo="En construcción">
        Acá vas a subir el reporte JSON de ZAP y ver el resumen del último escaneo.
      </Aviso>
    </Marco>
  );
}
