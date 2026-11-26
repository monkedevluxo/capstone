"use client";

import {
  CircleCheck,
  CircleSlash,
  FileJson,
  FileUp,
  FileWarning,
  Info,
  LoaderCircle,
  ShieldAlert,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { importarReporte, type ResultadoImportacion } from "@/app/acciones";
import { EnriquecerEscaneo, EnriquecerTanda } from "@/components/enriquecer-escaneo";
import { AvisoApiCaida } from "@/components/marco";
import { InsigniaSeveridad } from "@/components/severidad";
import { Button, buttonVariants } from "@/components/ui/button";
import type { ResumenImportacion } from "@/lib/api";
import { SEVERIDADES, hrefHallazgosDeEscaneo } from "@/lib/filtros";
import { claseBotonPrincipal, claseEnlace } from "@/lib/estilos";
import { MAX_REPORTE_BYTES, MAX_REPORTE_TEXTO } from "@/lib/limites";
import { cn } from "@/lib/utils";

/** Cuántos reportes se pueden poner en una misma tanda. */
const MAX_ARCHIVOS = 20;

type EstadoArchivo =
  /** Elegido, espera a que la persona apriete "Procesar". */
  | { tipo: "pendiente" }
  /** No pasó la validación del navegador: no se envía. */
  | { tipo: "invalido"; motivo: string }
  | { tipo: "procesando" }
  | { tipo: "listo"; resultado: ResultadoImportacion }
  /** La tanda se cortó (API caída) antes de llegar a este archivo. */
  | { tipo: "no_procesado" };

interface Archivo {
  clave: string;
  archivo: File;
  estado: EstadoArchivo;
}

/** Mismo nombre, tamaño y fecha: es el mismo archivo elegido dos veces. */
const claveDe = (a: File) => `${a.name}·${a.size}·${a.lastModified}`;

function validar(a: File): EstadoArchivo {
  // Primera validación en el navegador, para no subir algo que se va a
  // rechazar. La Server Action vuelve a validar.
  if (!/\.json$/i.test(a.name) && a.type !== "application/json") {
    return { tipo: "invalido", motivo: "No es un archivo .json." };
  }
  if (a.size > MAX_REPORTE_BYTES) return { tipo: "invalido", motivo: `Pesa más de ${MAX_REPORTE_TEXTO}.` };
  return { tipo: "pendiente" };
}

/**
 * Se puede (re)enviar: los pendientes, los que una caída dejó sin procesar y
 * los que fallaron por la API o el servidor. Los rechazados por contenido
 * (fuera del lab, no es ZAP, repetido) darían lo mismo otra vez.
 */
const porEnviar = (a: Archivo) =>
  a.estado.tipo === "pendiente" ||
  a.estado.tipo === "no_procesado" ||
  (a.estado.tipo === "listo" && (a.estado.resultado.tipo === "api_caida" || a.estado.resultado.tipo === "error"));

/**
 * Subida de reportes de ZAP: se eligen o arrastran uno o varios .json, quedan
 * en una lista y se importan recién al apretar "Procesar". Cada archivo va a
 * la Server Action (app/acciones.ts) por separado y en orden, nunca directo a
 * la API: así cada envío queda bajo el límite de tamaño y la deduplicación de
 * la API ve los reportes uno tras otro.
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
  const [archivos, setArchivos] = useState<Archivo[]>([]);
  /** Avance de la tanda en curso: "Procesando 2 de 5". Null si no hay tanda. */
  const [progreso, setProgreso] = useState<{ actual: number; total: number } | null>(null);
  const procesando = progreso !== null;
  const [aviso, setAviso] = useState<string | null>(null);

  const enviables = archivos.filter(porEnviar).length;
  const terminados = archivos.filter((a) => a.estado.tipo === "listo");

  function agregar(lista: FileList | null | undefined) {
    if (!lista || procesando) return;
    const claves = new Set(archivos.map((a) => a.clave));
    const nuevos: Archivo[] = [];
    let repetidos = 0;
    let sobran = 0;
    for (const archivo of Array.from(lista)) {
      const clave = claveDe(archivo);
      if (claves.has(clave)) {
        repetidos++;
        continue;
      }
      if (archivos.length + nuevos.length >= MAX_ARCHIVOS) {
        sobran++;
        continue;
      }
      claves.add(clave);
      nuevos.push({ clave, archivo, estado: validar(archivo) });
    }
    const partes = [];
    if (repetidos) partes.push(`${repetidos} ya estaba${repetidos > 1 ? "n" : ""} en la lista`);
    if (sobran) partes.push(`${sobran} no se agregó${sobran > 1 ? "aron" : ""}: el máximo es ${MAX_ARCHIVOS} por tanda`);
    setAviso(partes.length ? `${partes.join(" y ")}.` : null);
    setArchivos([...archivos, ...nuevos]);
  }

  function quitar(clave: string) {
    setArchivos((actuales) => actuales.filter((a) => a.clave !== clave));
    setAviso(null);
  }

  function marcar(clave: string, estado: EstadoArchivo) {
    setArchivos((actuales) => actuales.map((a) => (a.clave === clave ? { ...a, estado } : a)));
  }

  async function procesar() {
    if (procesando) return;
    const cola = archivos.filter(porEnviar);
    if (cola.length === 0) return;
    setAviso(null);
    for (let i = 0; i < cola.length; i++) {
      const { clave, archivo } = cola[i];
      setProgreso({ actual: i + 1, total: cola.length });
      marcar(clave, { tipo: "procesando" });
      const datos = new FormData();
      datos.set("reporte", archivo);
      let resultado: ResultadoImportacion;
      try {
        resultado = await importarReporte(datos);
      } catch {
        // La acción misma no respondió (servidor de Next caído o cuerpo
        // rechazado por bodySizeLimit).
        resultado = { tipo: "error", mensaje: "No se pudo enviar el archivo al servidor." };
      }
      marcar(clave, { tipo: "listo", resultado });
      if (resultado.tipo === "api_caida") {
        // Sin API, los que siguen fallarían igual: quedan para reintentar.
        for (const resto of cola.slice(i + 1)) marcar(resto.clave, { tipo: "no_procesado" });
        break;
      }
    }
    setProgreso(null);
  }

  // Con un solo archivo procesado se muestra el detalle completo, como antes.
  const unico = archivos.length === 1 && terminados.length === 1 ? terminados[0] : null;
  // Escaneos importados en la tanda: con varios archivos, un solo botón los
  // enriquece todos (la tarjeta del archivo único ya trae el suyo).
  const importados = [
    ...new Set(
      terminados.flatMap(({ estado }) =>
        estado.tipo === "listo" && estado.resultado.tipo === "ok" ? [estado.resultado.resumen.scan_id] : [],
      ),
    ),
  ];
  const recienImportado =
    ultimoEscaneoId !== null &&
    terminados.some(({ estado }) => {
      const r = estado.tipo === "listo" ? estado.resultado : null;
      return (r?.tipo === "ok" && r.resumen.scan_id === ultimoEscaneoId) ||
        (r?.tipo === "repetido" && r.scanId === ultimoEscaneoId);
    });

  return (
    <div className="flex flex-col gap-4">
      <section aria-labelledby="titulo-importar" className="rounded-lg border bg-card p-5">
        <h2 id="titulo-importar" className="font-semibold text-tinta">
          Importar reportes de ZAP
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Son los archivos JSON que genera ZAP con la opción{" "}
          <code className="font-mono whitespace-nowrap">-J</code>. Puedes elegir uno o varios; se
          importan al apretar <span className="font-medium text-foreground">Procesar</span>. Solo se
          aceptan objetivos del laboratorio.
        </p>

        <div
          aria-disabled={procesando}
          onDragEnter={(e) => {
            e.preventDefault();
            if (!procesando) setArrastrando(true);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = procesando ? "none" : "copy";
          }}
          onDragLeave={(e) => {
            // Solo al salir de la zona, no al pasar sobre un hijo.
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastrando(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setArrastrando(false);
            agregar(e.dataTransfer.files);
          }}
          className={cn(
            "mt-4 flex flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border bg-background px-4 py-8 text-center transition-colors",
            arrastrando && "border-tinta/60 bg-escaner-suave",
          )}
        >
          <FileUp aria-hidden className="size-6 text-escaner" />
          {/* En el teléfono no se arrastra: queda solo el botón. */}
          <p className="hidden text-sm text-foreground sm:block">Arrastra uno o varios archivos acá, o</p>
          <Button
            type="button"
            size="lg"
            variant="outline"
            disabled={procesando}
            onClick={() => entrada.current?.click()}
            className="px-4"
          >
            Elegir archivos
          </Button>
          <p className="text-xs text-muted-foreground">
            Solo .json, hasta {MAX_REPORTE_TEXTO} cada uno y {MAX_ARCHIVOS} por tanda.
          </p>
          <input
            ref={entrada}
            type="file"
            multiple
            accept=".json,application/json"
            tabIndex={-1}
            aria-hidden
            className="sr-only"
            onChange={(e) => {
              agregar(e.target.files);
              // Permite volver a elegir el mismo archivo.
              e.target.value = "";
            }}
          />
        </div>

        {aviso && (
          <p role="status" className="mt-3 flex items-start gap-2 text-sm text-muted-foreground">
            <Info aria-hidden className="mt-0.5 size-4 shrink-0" />
            {aviso}
          </p>
        )}

        {archivos.length > 0 && (
          <div className="mt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 id="titulo-lista" className="text-sm font-medium text-tinta">
                {archivos.length === 1 ? "1 archivo" : `${archivos.length} archivos`}
              </h3>
              {!procesando && (
                <button
                  type="button"
                  onClick={() => {
                    setArchivos([]);
                    setAviso(null);
                  }}
                  className="rounded-sm text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  Quitar todos
                </button>
              )}
            </div>
            <ul aria-labelledby="titulo-lista" className="mt-2 divide-y rounded-md border">
              {archivos.map((a) => (
                <FilaArchivo
                  key={a.clave}
                  archivo={a}
                  bloqueada={procesando}
                  onQuitar={() => quitar(a.clave)}
                />
              ))}
            </ul>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p role="status" aria-live="polite" className="text-sm text-muted-foreground">
                {progreso ? `Procesando ${progreso.actual} de ${progreso.total}…` : resumenTanda(archivos)}
              </p>
              <Button
                type="button"
                size="lg"
                disabled={procesando || enviables === 0}
                onClick={procesar}
                className={cn("px-4", claseBotonPrincipal)}
              >
                {procesando ? (
                  <>
                    <LoaderCircle aria-hidden className="animate-spin" />
                    Procesando…
                  </>
                ) : enviables === 0 ? (
                  "Procesar"
                ) : enviables === 1 ? (
                  "Procesar 1 reporte"
                ) : (
                  `Procesar ${enviables} reportes`
                )}
              </Button>
            </div>

            {!unico && !procesando && importados.length > 0 && (
              <div className="mt-4 flex flex-col gap-2 border-t pt-4">
                <p className="text-sm text-muted-foreground">
                  {importados.length === 1
                    ? "Se importó 1 escaneo."
                    : `Se importaron ${importados.length} escaneos.`}{" "}
                  El modelo local puede sugerir la categoría, la prioridad y la remediación de sus
                  hallazgos.
                </p>
                <EnriquecerTanda key={importados.join(",")} scanIds={importados} />
              </div>
            )}
          </div>
        )}
      </section>

      {unico?.estado.tipo === "listo" && (
        <div aria-live="polite">
          <Resultado resultado={unico.estado.resultado} />
        </div>
      )}

      <div className="group/ultimo mt-4" data-recien-importado={recienImportado}>
        {children}
      </div>
    </div>
  );
}

/** Resumen de lo que hay en la lista, antes o después de procesar. */
function resumenTanda(archivos: Archivo[]) {
  const cuenta = (f: (a: Archivo) => boolean) => archivos.filter(f).length;
  const tipo = (a: Archivo) => (a.estado.tipo === "listo" ? a.estado.resultado.tipo : null);
  const partes = [
    [cuenta((a) => tipo(a) === "ok"), "importado", "importados"],
    [cuenta((a) => tipo(a) === "repetido"), "ya estaba", "ya estaban"],
    [cuenta((a) => tipo(a) !== null && tipo(a) !== "ok" && tipo(a) !== "repetido"), "con error", "con error"],
    [cuenta((a) => a.estado.tipo === "no_procesado"), "sin procesar", "sin procesar"],
    [cuenta((a) => a.estado.tipo === "pendiente"), "listo para procesar", "listos para procesar"],
    [cuenta((a) => a.estado.tipo === "invalido"), "no se puede enviar", "no se pueden enviar"],
  ] as const;
  return partes
    .filter(([n]) => n > 0)
    .map(([n, uno, varios]) => `${n} ${n === 1 ? uno : varios}`)
    .join(" · ");
}

function FilaArchivo({
  archivo: { archivo, estado },
  bloqueada,
  onQuitar,
}: {
  archivo: Archivo;
  bloqueada: boolean;
  onQuitar: () => void;
}) {
  const { icono: Icono, tono, texto, accion } = describir(estado);
  const kb = Math.max(1, Math.round(archivo.size / 1024));

  return (
    <li className="flex items-start gap-3 px-3 py-2.5">
      <Icono
        aria-hidden
        className={cn("mt-0.5 size-4 shrink-0", tono, estado.tipo === "procesando" && "animate-spin")}
      />
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span className="font-mono break-all text-foreground">{archivo.name}</span>
          <span className="text-xs text-muted-foreground tabular-nums">{kb.toLocaleString("es-CL")} KB</span>
        </p>
        <p className="text-sm text-muted-foreground">{texto}</p>
        {accion && <div className="mt-1">{accion}</div>}
      </div>
      {!bloqueada && estado.tipo !== "procesando" && (
        <button
          type="button"
          onClick={onQuitar}
          aria-label={`Quitar ${archivo.name} de la lista`}
          className="-m-1 shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        >
          <X aria-hidden className="size-4" />
        </button>
      )}
    </li>
  );
}

/** Ícono, color, texto y enlace de cada fila según su estado. */
function describir(estado: EstadoArchivo): {
  icono: LucideIcon;
  tono: string;
  texto: React.ReactNode;
  accion?: React.ReactNode;
} {
  switch (estado.tipo) {
    case "pendiente":
      return { icono: FileJson, tono: "text-escaner", texto: "Listo para procesar." };
    case "invalido":
      return { icono: FileWarning, tono: "text-sev-alta", texto: `${estado.motivo} No se enviará.` };
    case "procesando":
      return { icono: LoaderCircle, tono: "text-escaner", texto: "Importando…" };
    case "no_procesado":
      return {
        icono: CircleSlash,
        tono: "text-escaner",
        texto: "No se procesó porque la API dejó de responder. Puedes volver a intentarlo.",
      };
    case "listo": {
      const r = estado.resultado;
      switch (r.tipo) {
        case "ok":
          return {
            icono: CircleCheck,
            tono: "text-exito",
            texto: (
              <>
                Importado: <span className="font-medium text-foreground">{r.resumen.nuevos}</span>{" "}
                {r.resumen.nuevos === 1 ? "hallazgo nuevo" : "hallazgos nuevos"}
                {r.resumen.repetidos > 0 && `, ${r.resumen.repetidos} ya conocidos`}.
              </>
            ),
            accion: (
              <Link href={hrefHallazgosDeEscaneo(r.resumen.scan_id)} className={claseEnlace}>
                Ver hallazgos
              </Link>
            ),
          };
        case "repetido":
          return {
            icono: Info,
            tono: "text-escaner",
            texto: "Ya estaba importado; no se agregó nada.",
            accion: r.scanId ? (
              <Link href={hrefHallazgosDeEscaneo(r.scanId)} className={claseEnlace}>
                Ver hallazgos de ese escaneo
              </Link>
            ) : undefined,
          };
        case "fuera_del_lab":
          return {
            icono: ShieldAlert,
            tono: "text-sev-alta",
            texto: (
              <>
                Apunta a <code className="font-mono">{r.host}</code>, que no es un objetivo del
                laboratorio.
              </>
            ),
          };
        case "no_es_zap":
          return {
            icono: FileWarning,
            tono: "text-sev-alta",
            texto: `No parece un reporte JSON de ZAP.${r.detalle ? ` ${r.detalle}` : ""}`,
          };
        case "muy_grande":
          return { icono: FileWarning, tono: "text-sev-alta", texto: `Pesa más de ${MAX_REPORTE_TEXTO}.` };
        case "api_caida":
          return {
            icono: FileWarning,
            tono: "text-sev-alta",
            texto: `${r.mensaje}. Revisa que el servicio api esté arriba.`,
          };
        case "error":
          return { icono: FileWarning, tono: "text-sev-alta", texto: r.mensaje };
      }
    }
  }
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
        <h3 className="font-semibold text-tinta">{titulo}</h3>
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
        <CircleCheck aria-hidden className="mt-0.5 size-5 shrink-0 text-exito" />
        <div className="min-w-0">
          <h3 id="titulo-importado" className="font-semibold text-tinta">
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
                <span className="text-sm font-medium text-tinta tabular-nums">
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
          destacada ? "text-tinta" : "text-foreground/80",
        )}
      >
        {valor}
      </dd>
    </div>
  );
}
