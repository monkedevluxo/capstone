import { Lock, UserCheck } from "lucide-react";

import { Apartado, Capa } from "@/components/detalle/capa";
import type { HallazgoDetalle, Prioridad } from "@/lib/api";
import { DECISION } from "@/lib/etiquetas";
import { fechaHora } from "@/lib/formato";

const OPCIONES = [
  { valor: "confirmado", etiqueta: "Confirmar", ayuda: "Es real y hay que corregirlo." },
  { valor: "falso_positivo", etiqueta: "Falso positivo", ayuda: "La evidencia no lo sostiene." },
  { valor: "riesgo_aceptado", etiqueta: "Riesgo aceptado", ayuda: "Es real, pero se asume." },
] as const;

const PRIORIDADES: Prioridad[] = ["p1", "p2", "p3", "p4"];

/**
 * Capa de la persona: la decisión final es suya. Por ahora muestra el
 * historial; el formulario queda visible pero deshabilitado hasta que exista
 * el registro de decisiones (T-056/T-057).
 */
export function CapaPersona({ hallazgo: h }: { hallazgo: HallazgoDetalle }) {
  const sugerida = h.referencia.prioridad_regla ?? "p4";

  return (
    <Capa
      tono="persona"
      icono={UserCheck}
      id="capa-persona"
      titulo="Tu decisión"
      bajada="Lo que decide una persona después de mirar la evidencia y la sugerencia"
      className="mt-6"
    >
      <div className="@container">
        <div className="grid gap-6 @3xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] @3xl:gap-8">
          <Apartado titulo={`Historial (${h.validaciones.length})`}>
            {h.validaciones.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Todavía nadie ha validado este hallazgo.
              </p>
            ) : (
              <ol className="flex flex-col divide-y rounded-md border">
                {h.validaciones.map((v, i) => (
                  <li key={`${v.fecha}-${i}`} className="flex flex-col gap-1 px-3.5 py-3 text-sm">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <span className="inline-flex h-6 items-center rounded-md border border-persona/40 bg-persona-suave px-2 text-xs font-semibold text-persona-fuerte">
                        {DECISION[v.decision] ?? v.decision}
                      </span>
                      {v.prioridad_corregida && (
                        <span className="text-xs text-muted-foreground">
                          prioridad final{" "}
                          <span className="font-mono font-semibold text-persona-fuerte">
                            {v.prioridad_corregida}
                          </span>
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium text-foreground">{v.revisor}</span> ·{" "}
                      <time dateTime={v.fecha}>{fechaHora(v.fecha)}</time>
                    </p>
                    {v.comentario && (
                      <p className="max-w-prose leading-relaxed whitespace-pre-line text-foreground">
                        {v.comentario}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Apartado>

          <form aria-describedby="nota-registro" className="flex flex-col gap-4">
            <p
              id="nota-registro"
              className="flex items-start gap-2 rounded-md border border-dashed border-persona/50 px-3 py-2.5 text-sm text-persona-fuerte"
            >
              <Lock aria-hidden className="mt-0.5 size-4 shrink-0" />
              Disponible con el registro de decisiones (T-056/T-057).
            </p>
            {/* Visible para mostrar qué se va a poder decidir, pero sin enviar nada. */}
            <fieldset disabled className="flex min-w-0 flex-col gap-4 opacity-70">
              <legend className="sr-only">Registrar una decisión</legend>
              <fieldset className="min-w-0">
                <legend className="mb-2 text-xs font-semibold text-muted-foreground">Decisión</legend>
                <div className="grid gap-2 sm:grid-cols-3">
                  {OPCIONES.map((o) => (
                    <label
                      key={o.valor}
                      className="flex cursor-not-allowed flex-col gap-0.5 rounded-md border px-3 py-2.5"
                    >
                      <span className="flex items-center gap-2 text-sm font-medium text-navy">
                        <input type="radio" name="decision" value={o.valor} className="accent-persona-fuerte" />
                        {o.etiqueta}
                      </span>
                      <span className="text-xs text-muted-foreground">{o.ayuda}</span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="grid gap-4 sm:grid-cols-[10rem_1fr]">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-muted-foreground">Prioridad final</span>
                  <select
                    name="prioridad"
                    defaultValue={sugerida}
                    className="h-9 cursor-not-allowed rounded-md border bg-card px-2.5 font-mono text-sm text-navy"
                  >
                    {PRIORIDADES.map((p) => (
                      <option key={p} value={p}>
                        {p}
                        {p === h.referencia.prioridad_regla ? " (por regla)" : ""}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-semibold text-muted-foreground">Comentario</span>
                  <textarea
                    name="comentario"
                    rows={2}
                    placeholder="Qué miraste y por qué decides esto"
                    className="cursor-not-allowed resize-none rounded-md border bg-card px-2.5 py-2 text-sm"
                  />
                </label>
              </div>

              <div>
                <button
                  type="submit"
                  className="inline-flex h-9 cursor-not-allowed items-center rounded-lg bg-persona-fuerte px-4 text-sm font-medium text-white"
                >
                  Guardar decisión
                </button>
              </div>
            </fieldset>
          </form>
        </div>
      </div>
    </Capa>
  );
}
