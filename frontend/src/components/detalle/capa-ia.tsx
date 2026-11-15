import { CircleDashed, CircleX, Sparkles, TriangleAlert } from "lucide-react";

import { Apartado, Capa, Texto } from "@/components/detalle/capa";
import type { DetalleIA, HallazgoDetalle } from "@/lib/api";
import { MOTIVO_FALLO, nombreOwasp, textoMotivo } from "@/lib/etiquetas";
import { confianza as formatearConfianza, fecha, segundos } from "@/lib/formato";

/** Umbral del aviso: el modelo declara confianza alta sobre algo que ZAP dudó. */
const CONFIANZA_ALTA = 0.9;

/**
 * Capa del modelo: lo que interpretó Llama sobre la alerta. Es una sugerencia;
 * la decisión la toma una persona en la capa de abajo.
 */
export function CapaIA({
  hallazgo: h,
  acciones,
}: {
  hallazgo: HallazgoDetalle;
  /** Botón para (volver a) enriquecer. */
  acciones?: React.ReactNode;
}) {
  const ia = h.ia;

  return (
    <Capa
      tono="ia"
      icono={Sparkles}
      id="capa-ia"
      titulo="Lo que interpretó el modelo"
      bajada="Llama 3.1 local · sugerencia, no decisión"
    >
      {ia === null ? (
        <Estado icono={CircleDashed} titulo="Todavía sin enriquecer">
          El modelo local aún no revisa este hallazgo. Por ahora solo está lo que reportó el
          escáner.
        </Estado>
      ) : ia.estado === "failed" ? (
        <>
          <Estado icono={CircleX} titulo="El último intento falló">
            {primeraMayuscula(textoMotivo(MOTIVO_FALLO, ia.motivo_fallo) ?? "motivo desconocido")}.
            No se guardó ninguna interpretación a medias.
          </Estado>
          <Traza ia={ia} />
        </>
      ) : (
        <Interpretacion hallazgo={h} ia={ia} />
      )}
      {acciones}
    </Capa>
  );
}

function Interpretacion({ hallazgo: h, ia }: { hallazgo: HallazgoDetalle; ia: DetalleIA }) {
  const avisoConfianza =
    h.confianza_herramienta?.toLowerCase() === "low" &&
    ia.confianza !== null &&
    ia.confianza >= CONFIANZA_ALTA;

  return (
    <>
      {ia.explicacion && (
        <Apartado titulo="Explicación">
          <Texto parrafos={[ia.explicacion]} />
        </Apartado>
      )}
      {ia.impacto && (
        <Apartado titulo="Impacto">
          <Texto parrafos={[ia.impacto]} />
        </Apartado>
      )}
      {(ia.remediacion || (ia.pasos && ia.pasos.length > 0)) && (
        <Apartado titulo="Remediación">
          {ia.remediacion && <Texto parrafos={[ia.remediacion]} />}
          {ia.pasos && ia.pasos.length > 0 && (
            <ol className="mt-2 flex max-w-prose list-decimal flex-col gap-1 pl-5 text-sm leading-relaxed">
              {ia.pasos.map((paso, i) => (
                <li key={i}>{paso}</li>
              ))}
            </ol>
          )}
        </Apartado>
      )}

      <dl className="grid grid-cols-1 gap-3 rounded-md border border-ia/15 bg-ia-suave/50 p-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">OWASP del modelo</dt>
          <dd className="font-mono font-semibold text-ia">{ia.owasp ?? "—"}</dd>
          {ia.owasp && <dd className="text-xs text-muted-foreground">{nombreOwasp(ia.owasp)}</dd>}
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Prioridad del modelo</dt>
          <dd className="font-mono font-semibold text-ia">{ia.prioridad ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">Confianza declarada</dt>
          <dd>
            {ia.confianza === null ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <BarraConfianza valor={ia.confianza} />
            )}
          </dd>
        </div>
      </dl>

      {avisoConfianza && (
        <div
          role="note"
          className="flex gap-2.5 rounded-md border border-sev-media/25 bg-sev-media-fondo px-3.5 py-3 text-sm leading-relaxed text-sev-media"
        >
          <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <p>
            ZAP marcó este hallazgo con confianza baja y el modelo declara{" "}
            {formatearConfianza(ia.confianza!)}. En el golden set la confianza fue igual de alta en
            errores que en aciertos: confirma con la evidencia.
          </p>
        </div>
      )}

      <Traza ia={ia} />
    </>
  );
}

function BarraConfianza({ valor }: { valor: number }) {
  const porcentaje = Math.min(Math.max(valor, 0), 1) * 100;
  return (
    <span className="mt-1 flex items-center gap-2">
      <span aria-hidden className="h-1.5 w-full max-w-24 overflow-hidden rounded-full bg-ia-suave ring-1 ring-ia/10">
        <span className="block h-full rounded-full bg-ia" style={{ width: `${porcentaje}%` }} />
      </span>
      <span className="font-mono text-sm text-ia tabular-nums">{formatearConfianza(valor)}</span>
    </span>
  );
}

/** Pie con todo lo necesario para reproducir la corrida. */
function Traza({ ia }: { ia: DetalleIA }) {
  const partes = [
    ia.modelo,
    `prompt ${ia.prompt_version} · ${ia.prompt_sha256.slice(0, 8)}`,
    `${ia.intentos} ${ia.intentos === 1 ? "intento" : "intentos"}${ia.latencia_ms !== null ? ` · ${segundos(ia.latencia_ms)}` : ""}`,
    fecha(ia.generado),
  ];
  return (
    <p
      className="border-t pt-3 font-mono text-[11px] leading-relaxed break-words text-muted-foreground"
      title={`prompt_sha256 ${ia.prompt_sha256}`}
    >
      {partes.join(" · ")}
    </p>
  );
}

function Estado({
  icono: Icono,
  titulo,
  children,
}: {
  icono: typeof CircleDashed;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <Icono aria-hidden className="mt-0.5 size-5 shrink-0 text-ia" />
      <div>
        <h3 className="font-semibold text-navy">{titulo}</h3>
        <p className="mt-1 max-w-prose text-sm leading-relaxed text-foreground">{children}</p>
      </div>
    </div>
  );
}

const primeraMayuscula = (s: string) => s[0].toUpperCase() + s.slice(1);
