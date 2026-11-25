"use client";

import { CircleAlert, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useState, useTransition } from "react";

import { enriquecerEscaneo, type ResultadoEnriquecimiento } from "@/app/acciones";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Botón de la capa IA: azul, porque lo que produce es una sugerencia del modelo. */
const claseBotonIA = "border-ia/40 bg-card text-ia hover:bg-ia-suave hover:text-ia";

/**
 * Estado del "Enriquecer pendientes" de un escaneo. Lo usan Inicio (escaneo
 * recién importado) y la lista de /escaneos: cada uno decide dónde va el
 * botón y dónde el progreso o el resultado.
 */
export function useEnriquecerEscaneo(scanId: string) {
  const [resultado, setResultado] = useState<ResultadoEnriquecimiento | null>(null);
  const [enCurso, iniciar] = useTransition();

  function enriquecer() {
    setResultado(null);
    iniciar(async () => {
      try {
        setResultado(await enriquecerEscaneo(scanId));
      } catch {
        setResultado({ tipo: "error", mensaje: "No se pudo contactar al servidor." });
      }
    });
  }

  return { enCurso, resultado, enriquecer };
}

/**
 * "Enriquecer pendientes" de un escaneo recién importado. El lote es síncrono
 * y sin porcentaje: la API responde al final, así que el progreso es
 * indeterminado y el texto dice cuánto lleva, no cuánto falta.
 */
export function EnriquecerEscaneo({ scanId }: { scanId: string }) {
  const { enCurso, resultado, enriquecer } = useEnriquecerEscaneo(scanId);
  if (!enCurso && !resultado) {
    return <BotonEnriquecer onClick={enriquecer} className="self-start px-4" size="lg" />;
  }
  return <EstadoEnriquecimiento enCurso={enCurso} resultado={resultado} enriquecer={enriquecer} />;
}

export function BotonEnriquecer({
  onClick,
  className,
  size = "default",
}: {
  onClick: () => void;
  className?: string;
  size?: "default" | "lg";
}) {
  return (
    <Button
      type="button"
      size={size}
      variant="outline"
      onClick={onClick}
      className={cn(claseBotonIA, className)}
    >
      <Sparkles aria-hidden />
      Enriquecer pendientes
    </Button>
  );
}

/** Progreso mientras corre el lote, o su resultado con "Reintentar" si hace falta. */
export function EstadoEnriquecimiento({
  enCurso,
  resultado,
  enriquecer,
}: {
  enCurso: boolean;
  resultado: ResultadoEnriquecimiento | null;
  enriquecer: () => void;
}) {
  if (enCurso) return <EnCurso />;
  if (!resultado) return null;

  const reintentar = (
    <Button type="button" variant="outline" onClick={enriquecer} className={claseBotonIA}>
      <RotateCcw aria-hidden />
      Reintentar
    </Button>
  );

  switch (resultado.tipo) {
    case "ok": {
      const l = resultado.lote;
      return (
        <div className="w-full" role="status">
          <h4 className="text-sm font-semibold text-ia">
            {l.detenido_por ? "Enriquecimiento detenido" : "Enriquecimiento terminado"}
          </h4>
          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
            <Cifra etiqueta="Enriquecidos" valor={l.enriquecidos} />
            <Cifra etiqueta="Fallidos" valor={l.fallidos} />
            <Cifra etiqueta="Ya estaban" valor={l.omitidos} />
          </dl>
          {l.detenido_por ? (
            <Problema accion={reintentar}>
              Ollama dejó de responder a la mitad
              {l.detenido_por !== "ollama_no_disponible" && ` (${l.detenido_por})`}. Lo ya procesado
              quedó guardado; al reintentar sigue con los que faltan.
            </Problema>
          ) : l.fallidos > 0 ? (
            <Problema accion={reintentar}>
              {l.fallidos === 1 ? "Un hallazgo no se pudo" : `${l.fallidos} hallazgos no se pudieron`}{" "}
              enriquecer: el modelo no devolvió una respuesta válida. Quedan como fallidos y se
              pueden reintentar.
            </Problema>
          ) : null}
        </div>
      );
    }
    case "ollama_apagado":
      return (
        <Problema accion={reintentar}>
          Ollama no está disponible. Los hallazgos quedan sin enriquecer y puedes reintentar
          después.
        </Problema>
      );
    case "tiempo":
      return (
        <Problema accion={reintentar}>
          El enriquecimiento tardó más de lo esperado y se cortó. Lo ya procesado quedó guardado; al
          reintentar sigue con los que faltan.
        </Problema>
      );
    case "no_existe":
      return <Problema>Ese escaneo ya no existe.</Problema>;
    case "api_caida":
      return (
        <Problema accion={reintentar}>
          {resultado.mensaje}. Revisa que el servicio <code className="font-mono">api</code> esté
          arriba.
        </Problema>
      );
    case "error":
      return <Problema accion={reintentar}>{resultado.mensaje}</Problema>;
  }
}

function EnCurso() {
  // Segundos desde que empezó: ayuda a saber que sigue vivo.
  const [segundos, setSegundos] = useState(0);
  useEffect(() => {
    const inicio = Date.now();
    const id = setInterval(() => setSegundos(Math.floor((Date.now() - inicio) / 1000)), 1000);
    return () => clearInterval(id);
  }, []);
  const lleva = `${Math.floor(segundos / 60)}:${String(segundos % 60).padStart(2, "0")}`;

  return (
    <div className="w-full" role="status" aria-live="polite">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium text-ia">Enriqueciendo con el modelo local…</p>
        <span className="font-mono text-xs text-muted-foreground tabular-nums" aria-hidden>
          {lleva}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label="Enriqueciendo hallazgos"
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-ia-suave"
      >
        <div className="h-full w-1/4 rounded-full bg-ia animate-indeterminado motion-reduce:w-full motion-reduce:animate-none motion-reduce:opacity-40" />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Puede tardar un par de minutos; el modelo corre local. No cierres esta pestaña.
      </p>
    </div>
  );
}

function Cifra({ etiqueta, valor }: { etiqueta: string; valor: number }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-muted-foreground">{etiqueta}</dt>
      <dd className="font-semibold text-tinta tabular-nums">{valor}</dd>
    </div>
  );
}

function Problema({ children, accion }: { children: React.ReactNode; accion?: React.ReactNode }) {
  return (
    <div role="alert" className="mt-3 flex w-full flex-wrap items-start gap-x-3 gap-y-2 first:mt-0">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-escaner" />
      <p className="min-w-0 flex-1 text-sm leading-relaxed text-foreground">{children}</p>
      {accion}
    </div>
  );
}
