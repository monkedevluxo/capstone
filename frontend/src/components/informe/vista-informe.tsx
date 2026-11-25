"use client";

import {
  ChevronDown,
  CircleAlert,
  Download,
  ExternalLink,
  FileSpreadsheet,
  FileText,
  LoaderCircle,
  Sheet,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { claseBotonPrincipal } from "@/lib/estilos";
import { cn } from "@/lib/utils";

/**
 * Pantalla Informe: la vista previa del informe técnico y el botón Exportar.
 *
 * El HTML viene de /informe/ver (mismo origen que el dashboard), así que el PDF
 * se saca imprimiendo el iframe: el informe ya trae su hoja de estilos para
 * imprimir y abre las descripciones de ZAP antes de hacerlo. CSV y XLSX los
 * genera la API y se descargan por /informe/descargar: se piden con fetch para
 * poder avisar acá si fallan (con un enlace de descarga, el error no se ve).
 */
export function VistaInforme({ objetivo }: { objetivo?: string }) {
  const marco = useRef<HTMLIFrameElement>(null);
  const [cargado, setCargado] = useState(false);
  const [descargando, setDescargando] = useState<Formato | null>(null);
  const [error, setError] = useState<string | null>(null);

  // El iframe puede terminar de cargar antes de que React se hidrate, y
  // entonces onLoad nunca llega: se revisa una vez al montar. Mientras carga
  // el src, el iframe tiene un about:blank inicial que ya está "complete", así
  // que eso no cuenta como cargado: en ese caso se espera a onLoad.
  useEffect(() => {
    const doc = marco.current?.contentDocument;
    if (doc?.readyState === "complete" && doc.location.href !== "about:blank") setCargado(true);
  }, []);

  const consulta = objetivo ? `?${new URLSearchParams({ objetivo })}` : "";
  const urlVer = `/informe/ver${consulta}`;
  const descarga = (formato: Formato) =>
    `/informe/descargar?${new URLSearchParams({ formato, ...(objetivo ? { objetivo } : {}) })}`;

  async function descargar(formato: Formato) {
    setError(null);
    setDescargando(formato);
    try {
      const respuesta = await fetch(descarga(formato), { cache: "no-store" });
      if (!respuesta.ok) {
        // /informe/descargar responde los errores en texto plano, ya redactados.
        // El detail de la API viene en minúscula ("no existe el objetivo …").
        const texto = (await respuesta.text().catch(() => "")).trim();
        const motivo = texto.charAt(0).toUpperCase() + texto.slice(1);
        setError(`No se pudo descargar el ${NOMBRE[formato]}. ${motivo || `El servidor respondió ${respuesta.status}.`}`);
        return;
      }
      guardar(await respuesta.blob(), nombreArchivo(respuesta, formato));
    } catch {
      setError(`No se pudo descargar el ${NOMBRE[formato]}: el dashboard no respondió. Recarga la página e intenta de nuevo.`);
    } finally {
      setDescargando(null);
    }
  }

  function imprimirPdf() {
    const ventana = marco.current?.contentWindow;
    if (cargado && ventana) {
      ventana.focus();
      ventana.print();
    } else {
      // Si la vista previa todavía no carga, se imprime desde otra pestaña.
      window.open(urlVer, "_blank", "noopener");
    }
  }

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-tinta">Informe</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Informe técnico del objetivo: resumen, escaneos de origen y una ficha por hallazgo con la
            evidencia de ZAP, la sugerencia de la IA y la decisión humana.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a href={urlVer} target="_blank" rel="noopener" className={cn(buttonVariants({ variant: "ghost" }), "px-3")}>
            <ExternalLink aria-hidden />
            Abrir en otra pestaña
          </a>
          <DropdownMenu>
            <DropdownMenuTrigger
              disabled={descargando !== null}
              aria-busy={descargando !== null}
              className={cn(buttonVariants(), "px-3", claseBotonPrincipal)}
            >
              {descargando ? <LoaderCircle aria-hidden className="animate-spin" /> : <Download aria-hidden />}
              {descargando ? `Preparando ${NOMBRE[descargando]}…` : "Exportar informe"}
              <ChevronDown aria-hidden className="transition-transform group-aria-expanded/button:rotate-180" />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-64">
              <DropdownMenuLabel>Formato</DropdownMenuLabel>
              <DropdownMenuItem onClick={imprimirPdf}>
                <FileText aria-hidden className="text-muted-foreground" />
                <Opcion titulo="PDF" detalle="El informe completo, desde el diálogo de impresión" />
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => descargar("xlsx")}>
                <FileSpreadsheet aria-hidden className="text-muted-foreground" />
                <Opcion titulo="Excel (XLSX)" detalle="Resumen, hallazgos con filtros y escaneos" />
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => descargar("csv")}>
                <Sheet aria-hidden className="text-muted-foreground" />
                <Opcion titulo="CSV" detalle="Un hallazgo por fila, para otras herramientas" />
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-3 rounded-md border border-sev-media/25 bg-sev-media-fondo px-3.5 py-3 text-sm text-sev-media"
        >
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <p className="min-w-0 flex-1 leading-relaxed">{error}</p>
        </div>
      )}

      <div className="relative overflow-hidden rounded-lg border bg-card">
        {!cargado && (
          <div className="absolute inset-0 space-y-4 p-6" aria-hidden>
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-16 w-2/3" />
            <Skeleton className="h-40 w-full" />
          </div>
        )}
        <iframe
          ref={marco}
          src={urlVer}
          title="Vista previa del informe técnico"
          onLoad={() => setCargado(true)}
          className="block h-[calc(100dvh-14rem)] min-h-[32rem] w-full bg-white"
        />
      </div>
    </>
  );
}

type Formato = "csv" | "xlsx";

const NOMBRE: Record<Formato, string> = { csv: "CSV", xlsx: "Excel" };

/** El nombre que puso la API en Content-Disposition (ej. informe_juiceshop-3000_20261124.xlsx). */
function nombreArchivo(respuesta: Response, formato: Formato) {
  const disposicion = respuesta.headers.get("content-disposition") ?? "";
  return /filename="([^"]+)"/.exec(disposicion)?.[1] ?? `informe.${formato}`;
}

/** Entrega el archivo al navegador como descarga. */
function guardar(archivo: Blob, nombre: string) {
  const url = URL.createObjectURL(archivo);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  document.body.append(enlace);
  enlace.click();
  enlace.remove();
  // Revocar en el mismo tick puede cortar la descarga en algunos navegadores.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function Opcion({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <span className="flex flex-col">
      <span className="font-medium">{titulo}</span>
      <span className="text-xs text-muted-foreground">{detalle}</span>
    </span>
  );
}
