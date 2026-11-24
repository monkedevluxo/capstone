"use client";

import { ChevronDown, Download, ExternalLink, FileSpreadsheet, FileText, Sheet } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuLinkItem,
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
 * genera la API y se descargan por /informe/descargar.
 */
export function VistaInforme({ objetivo }: { objetivo?: string }) {
  const marco = useRef<HTMLIFrameElement>(null);
  const [cargado, setCargado] = useState(false);

  // El iframe puede terminar de cargar antes de que React se hidrate, y
  // entonces onLoad nunca llega: se revisa una vez al montar.
  useEffect(() => {
    if (marco.current?.contentDocument?.readyState === "complete") setCargado(true);
  }, []);

  const consulta = objetivo ? `?${new URLSearchParams({ objetivo })}` : "";
  const urlVer = `/informe/ver${consulta}`;
  const descarga = (formato: "csv" | "xlsx") =>
    `/informe/descargar?${new URLSearchParams({ formato, ...(objetivo ? { objetivo } : {}) })}`;

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
          <h1 className="text-2xl font-semibold tracking-tight text-navy">Informe</h1>
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
            <DropdownMenuTrigger className={cn(buttonVariants(), "px-3", claseBotonPrincipal)}>
              <Download aria-hidden />
              Exportar informe
              <ChevronDown aria-hidden className="transition-transform group-aria-expanded/button:rotate-180" />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-64">
              <DropdownMenuLabel>Formato</DropdownMenuLabel>
              <DropdownMenuItem onClick={imprimirPdf}>
                <FileText aria-hidden className="text-muted-foreground" />
                <Opcion titulo="PDF" detalle="El informe completo, desde el diálogo de impresión" />
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuLinkItem href={descarga("xlsx")} download closeOnClick>
                <FileSpreadsheet aria-hidden className="text-muted-foreground" />
                <Opcion titulo="Excel (XLSX)" detalle="Resumen, hallazgos con filtros y escaneos" />
              </DropdownMenuLinkItem>
              <DropdownMenuLinkItem href={descarga("csv")} download closeOnClick>
                <Sheet aria-hidden className="text-muted-foreground" />
                <Opcion titulo="CSV" detalle="Un hallazgo por fila, para otras herramientas" />
              </DropdownMenuLinkItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

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

function Opcion({ titulo, detalle }: { titulo: string; detalle: string }) {
  return (
    <span className="flex flex-col">
      <span className="font-medium">{titulo}</span>
      <span className="text-xs text-muted-foreground">{detalle}</span>
    </span>
  );
}
