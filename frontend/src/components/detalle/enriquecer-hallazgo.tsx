"use client";

import { CircleAlert, CircleCheck, LoaderCircle, RotateCcw, Sparkles } from "lucide-react";
import { useState, useTransition } from "react";

import { enriquecerHallazgo, type ResultadoEnriquecerHallazgo } from "@/app/acciones";
import { Button } from "@/components/ui/button";
import { MOTIVO_FALLO, textoMotivo } from "@/lib/etiquetas";
import { cn } from "@/lib/utils";

/**
 * Botón de la capa IA. Llama a POST /findings/{id}/enrich por una Server
 * Action; si el modelo respondió, la acción revalida la página y la capa se
 * redibuja con lo nuevo.
 */
export function EnriquecerHallazgo({
  id,
  situacion,
}: {
  id: string;
  /** Qué hay hoy: cambia el texto del botón. */
  situacion: "sin_enriquecer" | "fallido" | "ok";
}) {
  const [resultado, setResultado] = useState<ResultadoEnriquecerHallazgo | null>(null);
  const [enCurso, iniciar] = useTransition();

  function enriquecer() {
    setResultado(null);
    iniciar(async () => {
      try {
        setResultado(await enriquecerHallazgo(id));
      } catch {
        setResultado({ tipo: "error", mensaje: "No se pudo contactar al servidor." });
      }
    });
  }

  const principal = situacion === "sin_enriquecer";
  const texto =
    situacion === "sin_enriquecer"
      ? "Enriquecer con IA local"
      : situacion === "fallido"
        ? "Reintentar"
        : "Volver a enriquecer";
  const Icono = situacion === "sin_enriquecer" ? Sparkles : RotateCcw;

  return (
    <div className={cn("flex flex-col gap-3", !principal && "border-t pt-4")}>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Button
          type="button"
          size="lg"
          variant={principal ? "default" : "outline"}
          disabled={enCurso}
          onClick={enriquecer}
          className={cn(
            "px-4",
            principal
              ? "bg-ia text-white hover:bg-ia/90"
              : "border-ia/40 bg-card text-ia hover:bg-ia-suave hover:text-ia",
          )}
        >
          {enCurso ? <LoaderCircle aria-hidden className="animate-spin" /> : <Icono aria-hidden />}
          {enCurso ? "Enriqueciendo…" : texto}
        </Button>
        {enCurso && (
          <p className="text-xs text-muted-foreground" role="status">
            El modelo corre local: suele tardar unos segundos, más si recién se está cargando.
          </p>
        )}
      </div>
      <div aria-live="polite">{resultado && !enCurso && <Mensaje resultado={resultado} />}</div>
    </div>
  );
}

function Mensaje({ resultado: r }: { resultado: ResultadoEnriquecerHallazgo }) {
  switch (r.tipo) {
    case "ok":
      if (!r.vigente) {
        return (
          <Aviso>
            El nuevo intento falló ({textoMotivo(MOTIVO_FALLO, r.motivoFallo) ?? "sin motivo"}); se
            conserva el enriquecimiento anterior.
          </Aviso>
        );
      }
      if (r.estado === "failed") return null; // La capa ya muestra el fallo y su motivo.
      return (
        <p className="flex items-center gap-1.5 text-sm text-ia">
          <CircleCheck aria-hidden className="size-4 shrink-0" />
          Listo: el modelo dejó una nueva sugerencia.
        </p>
      );
    case "ollama_apagado":
      return (
        <Aviso>
          Ollama no está disponible. El hallazgo queda como estaba y puedes reintentar después.
        </Aviso>
      );
    case "tiempo":
      return <Aviso>El modelo tardó demasiado y se cortó. Puedes reintentar.</Aviso>;
    case "no_existe":
      return <Aviso>Este hallazgo ya no existe.</Aviso>;
    case "api_caida":
      return (
        <Aviso>
          {r.mensaje}. Revisa que el servicio <code className="font-mono">api</code> esté arriba.
        </Aviso>
      );
    case "error":
      return <Aviso>{r.mensaje}</Aviso>;
  }
}

function Aviso({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="flex gap-2 text-sm leading-relaxed text-foreground">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-escaner" />
      <span>{children}</span>
    </p>
  );
}
