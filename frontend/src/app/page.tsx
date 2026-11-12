import { TriangleAlert } from "lucide-react";
import { connection } from "next/server";

import { InsigniaSeveridad } from "@/components/severidad";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ErrorApi, listarHallazgos, type HallazgoResumen } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Texto para cada motivo_revision que devuelve la API. */
const MOTIVO_REVISION: Record<string, string> = {
  categoria_distinta: "categoría distinta",
  cwe_fuera_de_tabla: "CWE fuera de la tabla",
};

export default async function PaginaHallazgos() {
  // Renderiza en cada request: los hallazgos cambian con cada importación y
  // `next build` no debe intentar llamar a la API para prerenderizar.
  await connection();

  let pagina;
  try {
    pagina = await listarHallazgos({ limit: 50 });
  } catch (error) {
    if (error instanceof ErrorApi) {
      return (
        <Marco>
          <Aviso titulo="No se pudo cargar la lista de hallazgos">
            {error.message}. Revisa que el servicio <code className="font-mono">api</code>{" "}
            esté levantado (<code className="font-mono">docker compose ps</code>).
          </Aviso>
        </Marco>
      );
    }
    throw error;
  }

  return (
    <Marco>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight text-navy">Hallazgos</h1>
        <p className="text-sm text-muted-foreground">
          {pagina.items.length < pagina.total
            ? `Mostrando ${pagina.items.length} de ${pagina.total}`
            : `${pagina.total} ${pagina.total === 1 ? "hallazgo" : "hallazgos"}`}
        </p>
      </div>

      {pagina.items.length === 0 ? (
        <Aviso titulo="Todavía no hay hallazgos">
          Importa un reporte de ZAP con <code className="font-mono">POST /scans/import</code>{" "}
          para verlos acá.
        </Aviso>
      ) : (
        <div className="rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-28">Severidad</TableHead>
                <TableHead>Hallazgo</TableHead>
                <TableHead className="text-right">Ocurrencias</TableHead>
                <TableHead>OWASP tabla · modelo</TableHead>
                <TableHead>Prioridad</TableHead>
                <TableHead>Confianza IA</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {pagina.items.map((h) => (
                <FilaHallazgo key={h.id} hallazgo={h} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Marco>
  );
}

function FilaHallazgo({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  const revisar = h.referencia.requiere_revision;
  return (
    <TableRow className={cn(revisar && "bg-revisar-fondo hover:bg-revisar-fondo")}>
      <TableCell>
        <InsigniaSeveridad severidad={h.severidad} />
      </TableCell>
      <TableCell className="max-w-md whitespace-normal">
        <div className="font-medium">{h.titulo}</div>
        {h.ruta && (
          <div className="truncate font-mono text-xs text-escaner" title={h.ruta}>
            {h.metodo ? `${h.metodo} ` : ""}
            {h.ruta}
            {h.parametro ? ` · ${h.parametro}` : ""}
          </div>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">{h.ocurrencias}</TableCell>
      <TableCell>
        <div className="font-mono text-xs">
          <span className="text-escaner">{h.referencia.owasp_referencia ?? "—"}</span>
          <span className="text-muted-foreground"> · </span>
          <span className="text-ia">{h.ia?.estado === "ok" ? (h.ia.owasp ?? "—") : "—"}</span>
        </div>
        {revisar && (
          <div className="mt-1 flex items-center gap-1 text-xs font-medium text-persona-texto">
            <TriangleAlert aria-hidden className="size-3.5 shrink-0" />
            Revisar
            {h.referencia.motivo_revision &&
              ` · ${MOTIVO_REVISION[h.referencia.motivo_revision] ?? h.referencia.motivo_revision}`}
          </div>
        )}
      </TableCell>
      <TableCell>
        <div className="font-mono text-sm">{h.referencia.prioridad_regla ?? "—"}</div>
        <div className="text-xs text-muted-foreground">por regla</div>
      </TableCell>
      <TableCell className="text-xs">
        <ConfianzaIA hallazgo={h} />
      </TableCell>
    </TableRow>
  );
}

/** 0.94 -> "0,94" */
function formatearConfianza(valor: number) {
  return valor.toFixed(2).replace(".", ",");
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
      <span aria-hidden className="h-1.5 w-[72px] overflow-hidden rounded-full bg-ia-suave">
        <span className="block h-full rounded-full bg-ia" style={{ width: `${porcentaje}%` }} />
      </span>
      <span className="font-mono text-ia tabular-nums">{formatearConfianza(h.ia.confianza)}</span>
    </span>
  );
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
      <p className="mb-1 text-xs font-semibold tracking-wide text-ia uppercase">SentinelAI</p>
      {children}
    </main>
  );
}

function Aviso({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <h2 className="font-semibold text-navy">{titulo}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{children}</p>
    </div>
  );
}
