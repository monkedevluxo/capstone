import { ChevronRight, ExternalLink, ScanSearch } from "lucide-react";

import { Apartado, Capa, Texto } from "@/components/detalle/capa";
import type { HallazgoDetalle, OrigenZap } from "@/lib/api";
import {
  instanciasConEvidencia,
  parrafos,
  referencias,
  riesgoYConfianza,
  type InstanciaConEvidencia,
} from "@/lib/zap";

/** Instancias que se ven sin desplegar. */
const VISIBLES = 5;

/**
 * Capa del escáner: lo que reportó ZAP, sin interpretar. Todo sale de la
 * alerta original (`origen`) y de las instancias normalizadas.
 */
export function CapaZap({ hallazgo: h }: { hallazgo: HallazgoDetalle }) {
  const o: OrigenZap = h.origen ?? {};
  const { riesgo, confianza } = riesgoYConfianza(h);
  const instancias = instanciasConEvidencia(h);
  const descripcion = parrafos(o.desc ?? h.descripcion);
  const solucion = parrafos(o.solution);
  const enlaces = referencias(o.reference);
  // Guion que no se parte (U+2011): "WASC-15" no queda en dos líneas.
  const regla = [o.pluginid, o.wascid && o.wascid !== "-1" && `WASC\u2011${o.wascid}`]
    .filter(Boolean)
    .join(" · ");

  return (
    <Capa
      tono="escaner"
      icono={ScanSearch}
      id="capa-zap"
      titulo="Lo que reportó el escáner"
      bajada="OWASP ZAP · evidencia original, sin modificar"
    >
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <Dato etiqueta="Riesgo ZAP" valor={riesgo} />
        <Dato etiqueta="Confianza ZAP" valor={confianza} />
        <Dato etiqueta="Regla ZAP" valor={regla || null} mono />
      </dl>

      {descripcion.length > 0 && (
        <Apartado titulo="Descripción">
          <Texto parrafos={descripcion} />
        </Apartado>
      )}

      <Apartado titulo={`Instancias (${instancias.length})`}>
        {instancias.length === 0 ? (
          <p className="text-sm text-muted-foreground">ZAP no informó instancias.</p>
        ) : (
          <div className="overflow-hidden rounded-md bg-navy font-mono text-xs text-[#e3e9f0]">
            <ListaInstancias instancias={instancias.slice(0, VISIBLES)} />
            {instancias.length > VISIBLES && (
              <details className="group border-t border-white/10">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 font-sans text-xs font-medium text-white/80 hover:text-white focus-visible:ring-2 focus-visible:ring-white/60 focus-visible:outline-none focus-visible:ring-inset [&::-webkit-details-marker]:hidden">
                  <ChevronRight aria-hidden className="size-3.5 transition-transform group-open:rotate-90" />
                  <span className="group-open:hidden">Ver todas ({instancias.length})</span>
                  <span className="hidden group-open:inline">Ocultar las demás</span>
                </summary>
                <ListaInstancias instancias={instancias.slice(VISIBLES)} desde={VISIBLES} />
              </details>
            )}
          </div>
        )}
      </Apartado>

      {solucion.length > 0 && (
        <Apartado titulo="Solución que propone ZAP">
          <Texto parrafos={solucion} />
        </Apartado>
      )}

      {enlaces.length > 0 && (
        <Apartado titulo="Referencias">
          <ul className="flex flex-col gap-1 text-sm">
            {enlaces.map((url) => (
              <li key={url} className="min-w-0">
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex max-w-full items-center gap-1 rounded-sm text-navy underline decoration-navy/30 underline-offset-4 hover:decoration-navy focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <span className="truncate">{url.replace(/^https?:\/\//, "")}</span>
                  <ExternalLink aria-hidden className="size-3.5 shrink-0" />
                </a>
              </li>
            ))}
          </ul>
        </Apartado>
      )}

      {h.origen && (
        <details className="group rounded-md border">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 text-sm font-medium text-navy hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none [&::-webkit-details-marker]:hidden">
            <ChevronRight aria-hidden className="size-4 transition-transform group-open:rotate-90" />
            Ver JSON original completo
          </summary>
          <pre className="max-h-96 overflow-auto border-t bg-escaner-suave p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap break-all text-foreground">
            {JSON.stringify(h.origen, null, 2)}
          </pre>
        </details>
      )}
    </Capa>
  );
}

function Dato({ etiqueta, valor, mono = false }: { etiqueta: string; valor: string | null; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{etiqueta}</dt>
      <dd className={mono ? "font-mono text-xs leading-6 text-navy" : "font-medium text-navy"}>
        {valor ?? "—"}
      </dd>
    </div>
  );
}

function ListaInstancias({ instancias, desde = 0 }: { instancias: InstanciaConEvidencia[]; desde?: number }) {
  return (
    <ol start={desde + 1} className="divide-y divide-white/10">
      {instancias.map((i, n) => (
        <li key={`${desde + n}-${i.url}`} className="px-3 py-2.5">
          <div className="break-all">
            <span className="font-medium text-white">{i.metodo ?? "—"}</span> {i.url}
          </div>
          <dl className="mt-1 grid grid-cols-[5.5rem_1fr] gap-x-2 gap-y-0.5">
            {i.parametro && <Campo nombre="param" valor={i.parametro} />}
            {i.attack && <Campo nombre="attack" valor={i.attack} />}
            {i.evidence && <Campo nombre="evidence" valor={i.evidence} />}
          </dl>
        </li>
      ))}
    </ol>
  );
}

function Campo({ nombre, valor }: { nombre: string; valor: string }) {
  return (
    <>
      <dt className="text-[#9fb0c3]">{nombre}</dt>
      {/* Texto que viene del sitio escaneado: siempre como texto, nunca HTML. */}
      <dd className="break-all whitespace-pre-wrap">{valor}</dd>
    </>
  );
}
