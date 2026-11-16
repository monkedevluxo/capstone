import { ArrowLeft } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Aviso, Marco } from "@/components/marco";

export const metadata: Metadata = { title: "Hallazgo · SentinelAI" };

// El detalle con las tres capas (escáner, IA y persona) llega con T-052.
export default async function PaginaHallazgo({ params }: PageProps<"/hallazgos/[id]">) {
  const { id } = await params;

  return (
    <Marco>
      <Link
        href="/hallazgos"
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-ia underline-offset-4 hover:underline"
      >
        <ArrowLeft aria-hidden className="size-4" />
        Volver a hallazgos
      </Link>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight text-navy">Detalle del hallazgo</h1>
      <Aviso titulo="En construcción">
        Acá se va a ver la evidencia de ZAP, la sugerencia del modelo y la decisión de la persona
        para el hallazgo <code className="font-mono break-all">{id}</code>.
      </Aviso>
    </Marco>
  );
}
