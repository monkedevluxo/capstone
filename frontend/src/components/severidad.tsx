import { cn } from "@/lib/utils";
import type { Severidad } from "@/lib/api";

const ETIQUETA: Record<Severidad, string> = {
  critica: "Crítica",
  alta: "Alta",
  media: "Media",
  baja: "Baja",
  informativa: "Informativa",
};

const ESTILO: Record<Severidad, string> = {
  critica: "bg-sev-critica-fondo text-sev-critica border-sev-critica-fondo",
  alta: "bg-sev-alta-fondo text-sev-alta border-sev-alta/20",
  media: "bg-sev-media-fondo text-sev-media border-sev-media/20",
  baja: "bg-sev-baja-fondo text-sev-baja border-sev-baja/15",
  informativa: "bg-sev-informativa-fondo text-sev-informativa border-border",
};

/** La severidad siempre se lee como texto; el color solo la refuerza. */
export function InsigniaSeveridad({ severidad }: { severidad: Severidad }) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center rounded-md border px-2 text-xs font-semibold",
        ESTILO[severidad],
      )}
    >
      {ETIQUETA[severidad]}
    </span>
  );
}
