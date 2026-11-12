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
                <TableHead>Prioridad (regla)</TableHead>
                <TableHead>IA</TableHead>
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
  return (
    <TableRow>
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
      <TableCell className="font-mono text-xs">
        <span className="text-escaner">{h.referencia.owasp_referencia ?? "—"}</span>
        <span className="text-muted-foreground"> · </span>
        <span className="text-ia">{h.ia?.estado === "ok" ? (h.ia.owasp ?? "—") : "—"}</span>
      </TableCell>
      <TableCell className="font-mono text-xs uppercase">
        {h.referencia.prioridad_regla ?? "—"}
      </TableCell>
      <TableCell className="text-xs">
        <EstadoIA hallazgo={h} />
      </TableCell>
    </TableRow>
  );
}

function EstadoIA({ hallazgo: h }: { hallazgo: HallazgoResumen }) {
  if (h.ia === null) {
    return <span className="text-muted-foreground">Sin enriquecer</span>;
  }
  if (h.ia.estado === "failed") {
    return (
      <span className="font-medium text-destructive" title={h.ia.motivo_fallo ?? undefined}>
        Falló
      </span>
    );
  }
  const confianza = h.ia.confianza === null ? null : Math.round(h.ia.confianza * 100);
  return (
    <span className="text-ia">
      {h.ia.prioridad?.toUpperCase() ?? "—"}
      {confianza !== null && <span className="text-muted-foreground"> · {confianza}%</span>}
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
