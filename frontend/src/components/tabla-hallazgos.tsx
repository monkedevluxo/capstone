import { TriangleAlert } from "lucide-react";
import Link from "next/link";

import { InsigniaSeveridad } from "@/components/severidad";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { HallazgoResumen } from "@/lib/api";
import { MOTIVO_REVISION } from "@/lib/etiquetas";
import { hrefDetalle, type Filtros } from "@/lib/filtros";
import { confianza as formatearConfianza } from "@/lib/formato";
import { cn } from "@/lib/utils";

/**
 * Lista de hallazgos: tabla cuando el espacio alcanza, tarjetas apiladas si
 * no. Lo decide el ancho del contenedor (@container), no el de la ventana:
 * con la barra lateral abierta a 1024 px quedan ~720 px y la tabla no cabe.
 * Los dos muestran los mismos datos.
 *
 * La tabla usa anchos fijos (table-fixed) para todo menos "Hallazgo", que se
 * lleva lo que sobra: el título se parte en líneas y la ruta se trunca con
 * la ruta completa en el title. Así nunca necesita scroll horizontal.
 */
export function TablaHallazgos({
  hallazgos,
  filtros,
}: {
  hallazgos: HallazgoResumen[];
  /** Para que el detalle sepa a qué vista de la lista volver. */
  filtros: Filtros;
}) {
  return (
    <div className="@container">
      <div className="hidden rounded-lg border bg-card @3xl:block">
        <Table className="table-fixed">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[6.5rem] pl-3">Severidad</TableHead>
              <TableHead>Hallazgo</TableHead>
              <TableHead className="w-[6.5rem] text-right">Ocurrencias</TableHead>
              <TableHead className="w-52 whitespace-normal">OWASP tabla · modelo</TableHead>
              <TableHead className="w-20">Prioridad</TableHead>
              <TableHead className="w-32 pr-3">Confianza IA</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {hallazgos.map((h) => (
              <FilaHallazgo key={h.id} hallazgo={h} href={hrefDetalle(h.id, filtros)} />
            ))}
          </TableBody>
        </Table>
      </div>

      <ul className="flex flex-col gap-3 @3xl:hidden">
        {hallazgos.map((h) => (
          <TarjetaHallazgo key={h.id} hallazgo={h} href={hrefDetalle(h.id, filtros)} />
        ))}
      </ul>
    </div>
  );
}

function FilaHallazgo({ hallazgo: h, href }: { hallazgo: HallazgoResumen; href: string }) {
  const revisar = h.referencia.requiere_revision;
  return (
    <TableRow className={cn(revisar && "bg-revisar-fondo hover:bg-revisar-fondo")}>
      <TableCell className="pl-3">
        <InsigniaSeveridad severidad={h.severidad} />
      </TableCell>
      <TableCell className="whitespace-normal">
        <TituloHallazgo hallazgo={h} href={href} />
        <RutaHallazgo hallazgo={h} />
      </TableCell>
      <TableCell className="text-right tabular-nums">{h.ocurrencias}</TableCell>
      <TableCell className="whitespace-normal">
        <CategoriasOwasp hallazgo={h} />
      </TableCell>
      <TableCell>
        <PrioridadRegla hallazgo={h} />
      </TableCell>
      <TableCell className="pr-3 text-xs">
        <ConfianzaIA hallazgo={h} />
      </TableCell>
    </TableRow>
  );
}

function TarjetaHallazgo({ hallazgo: h, href }: { hallazgo: HallazgoResumen; href: string }) {
  const revisar = h.referencia.requiere_revision;
  return (
    <li
      className={cn(
        "rounded-lg border bg-card p-4",
        revisar && "border-persona/40 bg-revisar-fondo",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <InsigniaSeveridad severidad={h.severidad} />
        <span className="text-xs text-muted-foreground tabular-nums">
          {h.ocurrencias} {h.ocurrencias === 1 ? "ocurrencia" : "ocurrencias"}
        </span>
      </div>
      <div className="mt-2">
        <TituloHallazgo hallazgo={h} href={href} />
        <RutaHallazgo hallazgo={h} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
        <div className="col-span-2">
          <dt className="mb-0.5 text-muted-foreground">OWASP tabla · modelo</dt>
          <dd>
            <CategoriasOwasp hallazgo={h} />
          </dd>
        </div>
        <div>
          <dt className="mb-0.5 text-muted-foreground">Prioridad</dt>
          <dd>
            <PrioridadRegla hallazgo={h} />
          </dd>
        </div>
        <div>
          <dt className="mb-0.5 text-muted-foreground">Confianza IA</dt>
          <dd>
            <ConfianzaIA hallazgo={h} />
          </dd>
        </div>
      </dl>
    </li>
  );
}

function TituloHallazgo({ hallazgo: h, href }: { hallazgo: HallazgoResumen; href: string }) {
  return (
    <Link
      href={href}
      className="rounded-sm font-medium text-foreground underline-offset-4 hover:text-ia hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
    >
      {h.titulo}
    </Link>
  );
}

function RutaHallazgo({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  if (!h.ruta) return null;
  return (
    <div className="truncate font-mono text-xs text-escaner" title={h.ruta}>
      {h.metodo ? `${h.metodo} ` : ""}
      {h.ruta}
      {h.parametro ? ` · ${h.parametro}` : ""}
    </div>
  );
}

function CategoriasOwasp({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  return (
    <>
      <div className="font-mono text-xs">
        <span className="text-escaner">{h.referencia.owasp_referencia ?? "—"}</span>
        <span className="text-muted-foreground"> · </span>
        <span className="text-ia">{h.ia?.estado === "ok" ? (h.ia.owasp ?? "—") : "—"}</span>
      </div>
      {h.referencia.requiere_revision && (
        <div className="mt-1 flex items-start gap-1 text-xs font-medium text-persona-texto">
          <TriangleAlert aria-hidden className="mt-px size-3.5 shrink-0" />
          Revisar
          {h.referencia.motivo_revision &&
            ` · ${MOTIVO_REVISION[h.referencia.motivo_revision] ?? h.referencia.motivo_revision}`}
        </div>
      )}
    </>
  );
}

function PrioridadRegla({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  return (
    <>
      <div className="font-mono text-sm">{h.referencia.prioridad_regla ?? "—"}</div>
      <div className="text-xs text-muted-foreground">por regla</div>
    </>
  );
}

function ConfianzaIA({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  if (h.ia === null) {
    return (
      <span className="inline-flex h-6 items-center rounded-full border border-dashed border-muted-foreground/50 px-2 text-muted-foreground">
        Sin enriquecer
      </span>
    );
  }
  if (h.ia.estado === "failed") {
    return (
      <span
        className="inline-flex h-6 items-center rounded-full border border-destructive/40 px-2 font-medium text-destructive"
        title={h.ia.motivo_fallo ?? undefined}
      >
        Falló
      </span>
    );
  }
  if (h.ia.confianza === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const porcentaje = Math.min(Math.max(h.ia.confianza, 0), 1) * 100;
  return (
    <span className="inline-flex items-center gap-2">
      <span aria-hidden className="h-1.5 w-14 overflow-hidden rounded-full bg-ia-suave">
        <span className="block h-full rounded-full bg-ia" style={{ width: `${porcentaje}%` }} />
      </span>
      <span className="font-mono text-ia tabular-nums">{formatearConfianza(h.ia.confianza)}</span>
    </span>
  );
}
