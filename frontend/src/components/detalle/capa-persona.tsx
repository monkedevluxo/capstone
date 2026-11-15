import { UserCheck } from "lucide-react";

import { Apartado, Capa } from "@/components/detalle/capa";
import { FormularioDecision } from "@/components/detalle/formulario-decision";
import type { HallazgoDetalle } from "@/lib/api";
import { DECISION } from "@/lib/etiquetas";
import { fechaHora } from "@/lib/formato";

/**
 * Capa de la persona: la decisión final es suya (T-056). El historial muestra
 * qué decidió cada uno, pero no sus respuestas sobre la sugerencia del
 * modelo: así cada revisor anota el golden set sin influencia de los demás.
 */
export function CapaPersona({
  hallazgo: h,
  revisorInicial,
}: {
  hallazgo: HallazgoDetalle;
  /** El nombre que dejó la última decisión en este navegador (cookie). */
  revisorInicial: string;
}) {
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
        {/* En el DOM el historial va primero (se lee antes de decidir); en
            pantalla ancha el formulario se lleva el espacio y el historial
            queda a la derecha. */}
        <div className="grid gap-6 @3xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] @3xl:gap-8">
          <Apartado titulo={`Historial (${h.validaciones.length})`} className="@3xl:order-last">
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

          <div>
            <h3 className="mb-2 text-xs font-semibold text-muted-foreground">Registrar una decisión</h3>
            <FormularioDecision
              hallazgoId={h.id}
              enrichmentId={h.ia?.id ?? null}
              sugerencia={{
                ok: h.ia?.estado === "ok",
                owaspModelo: h.ia?.owasp ?? null,
                owaspTabla: h.referencia.owasp_referencia,
                prioridadModelo: h.ia?.prioridad ?? null,
              }}
              prioridadRegla={h.referencia.prioridad_regla}
              revisorInicial={revisorInicial}
            />
          </div>
        </div>
      </div>
    </Capa>
  );
}
