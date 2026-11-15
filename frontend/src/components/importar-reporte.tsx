"use client";

import {
  CircleCheck,
  FileUp,
  FileWarning,
  Info,
  LoaderCircle,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState, useTransition } from "react";

import { importarReporte, type ResultadoImportacion } from "@/app/acciones";
import { EnriquecerEscaneo } from "@/components/enriquecer-escaneo";
import { AvisoApiCaida } from "@/components/marco";
import { InsigniaSeveridad } from "@/components/severidad";
import { Button, buttonVariants } from "@/components/ui/button";
import type { ResumenImportacion } from "@/lib/api";
import { SEVERIDADES, hrefHallazgosDeEscaneo } from "@/lib/filtros";
import { claseBotonPrincipal, claseEnlace } from "@/lib/estilos";
import { MAX_REPORTE_BYTES, MAX_REPORTE_TEXTO } from "@/lib/limites";
import { cn } from "@/lib/utils";

/**
 * Subida del reporte de ZAP: arrastrar y soltar o "Elegir archivo". El archivo
 * va a una Server Action (app/acciones.ts), nunca directo a la API.
 */
export function ImportarReporte({
  ultimoEscaneoId,
  children,
}: {
  /** Id del escaneo más reciente según el servidor. */
  ultimoEscaneoId: string | null;
  /** La sección "Último escaneo", que va debajo del resultado. */
  children: React.ReactNode;
}) {
  const entrada = useRef<HTMLInputElement>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const [nombre, setNombre] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null);
  const [importando, iniciar] = useTransition();

  function subir(archivo: File | undefined) {
    if (!archivo || importando) return;
    setNombre(archivo.name);

    // Primera validación en el navegador, para no subir algo que se va a
    // rechazar. La Server Action vuelve a validar.
    if (!/\.json$/i.test(archivo.name) && archivo.type !== "application/json") {
      setResultado({ tipo: "no_es_zap", detalle: "Solo se aceptan archivos .json." });
      return;
    }
    if (archivo.size > MAX_REPORTE_BYTES) {
      setResultado({ tipo: "muy_grande" });
      return;
    }

    const datos = new FormData();
    datos.set("reporte", archivo);
    setResultado(null);
    iniciar(async () => {
      try {
        setResultado(await importarReporte(datos));
      } catch {
        // La acción misma no respondió (servidor de Next caído o cuerpo
        // rechazado por bodySizeLimit).
        setResultado({ tipo: "error", mensaje: "No se pudo enviar el archivo al servidor." });
      }
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="titulo-importar" className="rounded-lg border bg-card p-5">
        <h2 id="titulo-importar" className="font-semibold text-navy">
          Importar reporte de ZAP
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Es el archivo JSON que genera ZAP con la opción{" "}
          <code className="font-mono whitespace-nowrap">-J</code>.
          Solo se aceptan objetivos del laboratorio.
        </p>

        <div
          aria-busy={importando}
          onDragEnter={(e) => {
            e.preventDefault();
            setArrastrando(true);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = importando ? "none" : "copy";
          }}
          onDragLeave={(e) => {
            // Solo al salir de la zona, no al pasar sobre un hijo.
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastrando(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setArrastrando(false);
            subir(e.dataTransfer.files[0]);
          }}
          className={cn(
            "mt-4 flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border bg-background px-4 py-8 text-center transition-colors",
            arrastrando && "border-navy/60 bg-escaner-suave",
          )}
        >
          <FileUp aria-hidden className="size-6 text-escaner" />
          {importando ? (
            <p className="text-sm text-foreground" role="status">
              Importando <span className="font-mono break-all">{nombre}</span>…
            </p>
          ) : (
            // En el teléfono no se arrastra: queda solo el botón.
            <p className="hidden text-sm text-foreground sm:block">Arrastra el archivo acá, o</p>
          )}
          <Button
            type="button"
            size="lg"
            disabled={importando}
            onClick={() => entrada.current?.click()}
            className={cn("px-4", claseBotonPrincipal)}
          >
            {importando ? (
              <>
                <LoaderCircle aria-hidden className="animate-spin" />
                Importando…
              </>
            ) : (
              "Elegir archivo"
            )}
          </Button>
          <p className="text-xs text-muted-foreground">Solo .json, hasta {MAX_REPORTE_TEXTO}.</p>
          <input
            ref={entrada}
            type="file"
            accept=".json,application/json"
            tabIndex={-1}
            aria-hidden
            className="sr-only"
            onChange={(e) => {
              subir(e.target.files?.[0]);
              // Permite volver a elegir el mismo archivo.
              e.target.value = "";
            }}
          />
        </div>
      </section>

      <div aria-live="polite">
        {resultado && !importando && <Resultado resultado={resultado} />}
      </div>

      <div
        className="group/ultimo mt-4"
        data-recien-importado={
          ultimoEscaneoId !== null &&
          ((resultado?.tipo === "ok" && resultado.resumen.scan_id === ultimoEscaneoId) ||
            (resultado?.tipo === "repetido" && resultado.scanId === ultimoEscaneoId))
        }
      >
        {children}
      </div>
    </div>
  );
}

function Resultado({ resultado: r }: { resultado: ResultadoImportacion }) {
  switch (r.tipo) {
    case "ok":
      return <ReporteImportado resumen={r.resumen} />;
    case "fuera_del_lab":
      return (
        <Mensaje icono={ShieldAlert} tono="bloqueo" titulo="Objetivo fuera del laboratorio">
          Ese reporte apunta a <code className="font-mono font-medium">{r.host}</code>, que no es un
          objetivo del laboratorio. SentinelAI solo importa resultados de entornos aislados.
        </Mensaje>
      );
    case "repetido":
      return (
        <Mensaje
          icono={Info}
          titulo="Ese reporte ya estaba importado"
          accion={
            r.scanId && (
              <Link href={hrefHallazgosDeEscaneo(r.scanId)} className={claseEnlace}>
                Ver los hallazgos de ese escaneo
              </Link>
            )
          }
        >
          Cada reporte se importa una sola vez, así que no se agregó nada nuevo.
        </Mensaje>
      );
    case "no_es_zap":
      return (
        <Mensaje icono={FileWarning} titulo="El archivo no parece un reporte JSON de ZAP.">
          Genera el reporte con la opción <code className="font-mono whitespace-nowrap">-J</code>{" "}
          de ZAP y vuelve a subirlo.
          {r.detalle && (
            <span className="mt-1 block text-muted-foreground">Motivo: {r.detalle}</span>
          )}
        </Mensaje>
      );
    case "muy_grande":
      return (
        <Mensaje icono={FileWarning} titulo={`El archivo pesa más de ${MAX_REPORTE_TEXTO}.`}>
          Un reporte de ZAP sobre el laboratorio pesa bastante menos. Revisa que sea el archivo
          correcto.
        </Mensaje>
      );
    case "api_caida":
      return <AvisoApiCaida titulo="No se pudo importar el reporte" mensaje={r.mensaje} />;
    case "error":
      return (
        <Mensaje icono={FileWarning} titulo="No se pudo importar el reporte">
          {r.mensaje}
        </Mensaje>
      );
  }
}

export function Mensaje({
  icono: Icono,
  titulo,
  children,
  accion,
  tono = "neutro",
}: {
  icono: LucideIcon;
  titulo: string;
  children: React.ReactNode;
  accion?: React.ReactNode;
  tono?: "neutro" | "bloqueo";
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex gap-3 rounded-lg border bg-card p-5",
        tono === "bloqueo" && "border-sev-alta/25",
      )}
    >
      <Icono
        aria-hidden
        className={cn("mt-0.5 size-5 shrink-0", tono === "bloqueo" ? "text-sev-alta" : "text-escaner")}
      />
      <div className="min-w-0">
        <h3 className="font-semibold text-navy">{titulo}</h3>
        <p className="mt-1 text-sm leading-relaxed text-foreground">{children}</p>
        {accion && <div className="mt-3">{accion}</div>}
      </div>
    </div>
  );
}

function ReporteImportado({ resumen: r }: { resumen: ResumenImportacion }) {
  const severidades = SEVERIDADES.filter((s) => (r.por_severidad[s.valor] ?? 0) > 0);

  return (
    <section aria-labelledby="titulo-importado" className="rounded-lg border bg-card p-5">
      <div className="flex gap-3">
        <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-emerald-700" />
        <div className="min-w-0">
          <h3 id="titulo-importado" className="font-semibold text-navy">
            Reporte importado
          </h3>
          <p className="mt-0.5 font-mono text-sm break-all text-escaner">{r.objetivo}</p>
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-md border bg-border sm:grid-cols-4">
        <Cifra etiqueta="Alertas en el reporte" valor={r.hallazgos_en_reporte} />
        <Cifra etiqueta="Hallazgos nuevos" valor={r.nuevos} destacada />
        <Cifra etiqueta="Ya conocidos" valor={r.repetidos} />
        <Cifra etiqueta="Descartados" valor={r.descartados} />
      </dl>

      {severidades.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-medium text-muted-foreground">Por severidad</h4>
          <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-2">
            {severidades.map((s) => (
              <li key={s.valor} className="flex items-center gap-1.5">
                <InsigniaSeveridad severidad={s.valor} />
                <span className="text-sm font-medium text-navy tabular-nums">
                  {r.por_severidad[s.valor]}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5 flex flex-col gap-4 border-t pt-4">
        <EnriquecerEscaneo scanId={r.scan_id} />
        <div>
          <Link
            href={hrefHallazgosDeEscaneo(r.scan_id)}
            className={cn(buttonVariants({ size: "lg" }), "px-4", claseBotonPrincipal)}
          >
            Ver hallazgos de este escaneo
          </Link>
        </div>
      </div>
    </section>
  );
}

function Cifra({
  etiqueta,
  valor,
  destacada = false,
}: {
  etiqueta: string;
  valor: number;
  destacada?: boolean;
}) {
  return (
    <div className="bg-card px-3 py-2.5">
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd
        className={cn(
          "mt-0.5 text-xl font-semibold tabular-nums",
          destacada ? "text-navy" : "text-foreground/80",
        )}
      >
        {valor}
      </dd>
    </div>
  );
}
