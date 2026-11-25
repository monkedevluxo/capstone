"use client";

import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { COOKIE_TEMA, type Tema } from "@/lib/tema";

const OPCIONES: { valor: Tema; etiqueta: string; icono: LucideIcon }[] = [
  { valor: "claro", etiqueta: "Tema claro", icono: Sun },
  { valor: "oscuro", etiqueta: "Tema oscuro", icono: Moon },
  { valor: "sistema", etiqueta: "Tema del sistema", icono: Monitor },
];

const UN_ANO = 60 * 60 * 24 * 365;

function aplicar(tema: Tema) {
  const oscuro =
    tema === "oscuro" || (tema === "sistema" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", oscuro);
}

/**
 * Claro, oscuro o el del sistema. El cambio se ve al instante y queda en la
 * cookie "tema", que el layout lee para pintar la página ya en el tema elegido.
 */
export function SelectorTema({ inicial }: { inicial: Tema }) {
  const [tema, setTema] = useState<Tema>(inicial);

  // En "sistema", seguir al computador si cambia de claro a oscuro.
  useEffect(() => {
    if (tema !== "sistema") return;
    const consulta = matchMedia("(prefers-color-scheme: dark)");
    const alCambiar = () => aplicar("sistema");
    consulta.addEventListener("change", alCambiar);
    return () => consulta.removeEventListener("change", alCambiar);
  }, [tema]);

  function elegir(valores: string[]) {
    // Un grupo de una sola opción permite des-seleccionar; acá siempre hay una.
    const nuevo = valores[0] as Tema | undefined;
    if (!nuevo || nuevo === tema) return;
    setTema(nuevo);
    aplicar(nuevo);
    document.cookie = `${COOKIE_TEMA}=${nuevo}; path=/; max-age=${UN_ANO}; samesite=lax`;
  }

  return (
    <ToggleGroup
      aria-label="Tema de la pantalla"
      value={[tema]}
      onValueChange={elegir}
      variant="outline"
      size="sm"
      spacing={0}
    >
      {OPCIONES.map(({ valor, etiqueta, icono: Icono }) => (
        <Tooltip key={valor}>
          <TooltipTrigger
            render={
              <ToggleGroupItem
                value={valor}
                aria-label={etiqueta}
                className="text-muted-foreground aria-pressed:bg-muted aria-pressed:text-tinta"
              />
            }
          >
            <Icono aria-hidden />
          </TooltipTrigger>
          <TooltipContent side="bottom">{etiqueta}</TooltipContent>
        </Tooltip>
      ))}
    </ToggleGroup>
  );
}
