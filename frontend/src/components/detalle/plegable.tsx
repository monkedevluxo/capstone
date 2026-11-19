"use client";

import { ChevronDown } from "lucide-react";
import { useCallback, useId, useRef, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Texto largo de ZAP recortado a ~4 líneas con "Ver más", que lo expande en
 * el mismo lugar. Así la capa ZAP no queda mucho más alta que la de IA y
 * "Tu decisión" no se va al fondo de la página.
 *
 * El botón aparece solo si hay algo escondido: texto que no cabe o `extra`
 * (por ejemplo las referencias), que se muestra únicamente al expandir.
 */
export function Plegable({
  children,
  extra,
  etiqueta,
}: {
  children: React.ReactNode;
  extra?: React.ReactNode;
  /** Para el lector de pantalla: "Ver más de la solución". */
  etiqueta: string;
}) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [desborda, setDesborda] = useState(false);
  const observador = useRef<ResizeObserver | null>(null);

  // Mide si el texto recortado esconde algo. El ResizeObserver avisa al
  // conectarse y cada vez que cambia el ancho (columna o ventana).
  const medir = useCallback((nodo: HTMLDivElement | null) => {
    observador.current?.disconnect();
    if (!nodo) return;
    observador.current = new ResizeObserver(() => {
      setDesborda(nodo.scrollHeight > nodo.clientHeight + 1);
    });
    observador.current.observe(nodo);
  }, []);

  const hayMas = desborda || Boolean(extra);

  return (
    <div>
      <div
        id={id}
        ref={abierto ? undefined : medir}
        className={cn(
          "relative",
          !abierto &&
            "max-h-[5.75rem] overflow-hidden [mask-image:linear-gradient(to_bottom,black_60%,transparent)]",
          !abierto && !desborda && "[mask-image:none]",
        )}
      >
        {children}
        {extra && <div hidden={!abierto}>{extra}</div>}
      </div>
      {(hayMas || abierto) && (
        <button
          type="button"
          aria-expanded={abierto}
          aria-controls={id}
          onClick={() => setAbierto((v) => !v)}
          className="mt-1.5 inline-flex items-center gap-1 rounded-sm text-sm font-medium text-navy underline-offset-4 hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <ChevronDown
            aria-hidden
            className={cn("size-4 transition-transform", abierto && "rotate-180")}
          />
          {abierto ? "Ver menos" : "Ver más"}
          <span className="sr-only"> {etiqueta}</span>
        </button>
      )}
    </div>
  );
}
