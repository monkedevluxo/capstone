"use client";

import { CircleAlert, CircleCheck, LoaderCircle, RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";

import {
  registrarDecision,
  type CampoDecision,
  type DatosDecision,
  type ResultadoDecision,
} from "@/app/acciones";
import type { DecisionValidacion, Prioridad } from "@/lib/api";
import { ESTADO_HALLAZGO } from "@/lib/etiquetas";
import { cn } from "@/lib/utils";

const PRINCIPALES = [
  { valor: "confirmado", etiqueta: "Confirmar", ayuda: "Es real y hay que corregirlo." },
  { valor: "falso_positivo", etiqueta: "Falso positivo", ayuda: "La evidencia no lo sostiene." },
  { valor: "riesgo_aceptado", etiqueta: "Riesgo aceptado", ayuda: "Es real, pero se asume." },
] as const;

const SECUNDARIAS = [
  { valor: "duplicado", etiqueta: "Duplicado" },
  { valor: "requiere_segunda_opinion", etiqueta: "Requiere segunda opinión" },
] as const;

const PRIORIDADES: Prioridad[] = ["p1", "p2", "p3", "p4"];

/** Sí / No / No sé. "No sé" se guarda como null. */
type Respuesta = "si" | "no" | "nose";
const aBool = (r: Respuesta) => (r === "si" ? true : r === "no" ? false : null);

export interface ContextoSugerencia {
  /** Hay una sugerencia válida: se pregunta qué tal estuvo. */
  ok: boolean;
  owaspModelo: string | null;
  owaspTabla: string | null;
  prioridadModelo: Prioridad | null;
}

export function FormularioDecision({
  hallazgoId,
  enrichmentId,
  sugerencia,
  prioridadRegla,
  revisorInicial,
}: {
  hallazgoId: string;
  /** La sugerencia que se está mostrando (ok o fallida), o null. */
  enrichmentId: string | null;
  sugerencia: ContextoSugerencia;
  prioridadRegla: Prioridad | null;
  revisorInicial: string;
}) {
  const router = useRouter();
  const base = useId();
  const [decision, setDecision] = useState<DecisionValidacion | null>(null);
  const [revisor, setRevisor] = useState(revisorInicial);
  const [comentario, setComentario] = useState("");
  const [prioridad, setPrioridad] = useState<"" | Prioridad>("");
  const [ia, setIa] = useState<Record<"owasp" | "prioridad" | "remediacion" | "alucinacion", Respuesta>>({
    owasp: "nose",
    prioridad: "nose",
    remediacion: "nose",
    alucinacion: "nose",
  });
  const [nota, setNota] = useState("");
  const [resultado, setResultado] = useState<ResultadoDecision | null>(null);
  const [guardando, iniciar] = useTransition();
  const [recargando, recargar] = useTransition();

  const errores = resultado?.tipo === "invalido" ? resultado.errores : {};

  /** Al corregir un campo, su error deja de mostrarse. */
  function corregido(campo: CampoDecision) {
    setResultado((r) => {
      if (r?.tipo !== "invalido" || !r.errores[campo]) return r;
      const resto = { ...r.errores };
      delete resto[campo];
      return { tipo: "invalido", errores: resto };
    });
  }
  const idError = (campo: CampoDecision) => `${base}-error-${campo}`;

  function guardar(e: React.FormEvent) {
    e.preventDefault();
    // Mismas reglas que la acción, para responder sin ir al servidor.
    const locales: Partial<Record<CampoDecision, string>> = {};
    if (!decision) locales.decision = "Elige una decisión.";
    if (!revisor.trim()) locales.revisor = "Escribe tu nombre.";
    if (Object.keys(locales).length > 0) {
      setResultado({ tipo: "invalido", errores: locales });
      return;
    }

    const datos: DatosDecision = {
      decision: decision!,
      revisor,
      comentario: comentario.trim(),
      prioridadCorregida: prioridad || null,
      enrichmentId,
      ai: sugerencia.ok
        ? {
            owaspCorrecto: aBool(ia.owasp),
            prioridadCorrecta: aBool(ia.prioridad),
            remediacionUtil: aBool(ia.remediacion),
            alucinacion: aBool(ia.alucinacion),
            nota: nota.trim(),
          }
        : null,
    };
    setResultado(null);
    iniciar(async () => {
      let r: ResultadoDecision;
      try {
        r = await registrarDecision(hallazgoId, datos);
      } catch {
        r = { tipo: "error", mensaje: "No se pudo contactar al servidor." };
      }
      setResultado(r);
      if (r.tipo === "ok") {
        // Lista para una próxima decisión; el nombre se queda (ya recortado).
        setRevisor((v) => v.trim());
        setDecision(null);
        setComentario("");
        setPrioridad("");
        setIa({ owasp: "nose", prioridad: "nose", remediacion: "nose", alucinacion: "nose" });
        setNota("");
      }
    });
  }

  const placeholder =
    decision === "duplicado"
      ? "¿Duplicado de cuál? Pega el enlace o el título"
      : "Qué miraste y por qué decides esto";

  return (
    <form onSubmit={guardar} noValidate className="flex flex-col gap-5" aria-describedby={`${base}-estado`}>
      {/* Decisión */}
      <fieldset
        className="min-w-0"
        aria-invalid={Boolean(errores.decision)}
        aria-describedby={errores.decision ? idError("decision") : undefined}
      >
        <legend className="mb-2 text-xs font-semibold text-muted-foreground">Decisión</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {PRINCIPALES.map((o) => (
            <OpcionDecision
              key={o.valor}
              nombre={`${base}-decision`}
              valor={o.valor}
              actual={decision}
              onElegir={(v) => {
                setDecision(v);
                corregido("decision");
              }}
            >
              <span className="text-sm font-semibold">{o.etiqueta}</span>
              <span className="text-xs text-muted-foreground">{o.ayuda}</span>
            </OpcionDecision>
          ))}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-2">
          <span className="text-xs text-muted-foreground">También:</span>
          {SECUNDARIAS.map((o) => (
            <OpcionDecision
              key={o.valor}
              nombre={`${base}-decision`}
              valor={o.valor}
              actual={decision}
              onElegir={(v) => {
                setDecision(v);
                corregido("decision");
              }}
              secundaria
            >
              <span className="text-xs font-medium">{o.etiqueta}</span>
            </OpcionDecision>
          ))}
        </div>
        <ErrorCampo id={idError("decision")} mensaje={errores.decision} />
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_11rem]">
        <Campo etiqueta="Comentario" error={errores.comentario} idError={idError("comentario")}>
          {(props) => (
            <textarea
              {...props}
              value={comentario}
              onChange={(e) => {
                setComentario(e.target.value);
                corregido("comentario");
              }}
              rows={3}
              maxLength={4000}
              placeholder={placeholder}
              className={claseControl("resize-y py-2")}
            />
          )}
        </Campo>
        <Campo etiqueta="Prioridad final" error={errores.prioridad} idError={idError("prioridad")}>
          {(props) => (
            <select
              {...props}
              value={prioridad}
              onChange={(e) => setPrioridad(e.target.value as "" | Prioridad)}
              className={claseControl("h-9 font-mono")}
            >
              <option value="">{prioridadRegla ? `${prioridadRegla} (por regla)` : "Sin corregir"}</option>
              {PRIORIDADES.filter((p) => p !== prioridadRegla).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          )}
        </Campo>
      </div>

      {sugerencia.ok && (
        <fieldset
          className="min-w-0 rounded-md border border-ia/20 bg-ia-suave/40 p-3.5"
          aria-describedby={`${base}-ayuda-ia`}
        >
          <legend className="px-1 text-sm font-semibold text-navy">¿Qué tal la sugerencia del modelo?</legend>
          <p id={`${base}-ayuda-ia`} className="mb-3 text-xs text-muted-foreground">
            Esto alimenta las métricas del golden set. Responde por tu cuenta: no se muestran las
            respuestas de otros revisores.
          </p>
          <div className="flex flex-col divide-y divide-ia/10">
            <PreguntaIA
              nombre={`${base}-owasp`}
              pregunta="¿La categoría OWASP es correcta?"
              contexto={`Modelo ${sugerencia.owaspModelo ?? "—"} · tabla ${sugerencia.owaspTabla ?? "—"}`}
              valor={ia.owasp}
              onCambiar={(v) => setIa((a) => ({ ...a, owasp: v }))}
            />
            <PreguntaIA
              nombre={`${base}-prioridad`}
              pregunta="¿La prioridad es correcta?"
              contexto={`Modelo ${sugerencia.prioridadModelo ?? "—"} · regla ${prioridadRegla ?? "—"}`}
              valor={ia.prioridad}
              onCambiar={(v) => setIa((a) => ({ ...a, prioridad: v }))}
            />
            <PreguntaIA
              nombre={`${base}-remediacion`}
              pregunta="¿La remediación es útil?"
              valor={ia.remediacion}
              onCambiar={(v) => setIa((a) => ({ ...a, remediacion: v }))}
            />
            <PreguntaIA
              nombre={`${base}-alucinacion`}
              pregunta="¿Inventó algo?"
              contexto="Datos, rutas o parámetros que no están en la evidencia"
              valor={ia.alucinacion}
              onCambiar={(v) => setIa((a) => ({ ...a, alucinacion: v }))}
            />
          </div>
          <div className="mt-3">
            <Campo etiqueta="Nota sobre la sugerencia (opcional)" error={errores.ai} idError={idError("ai")}>
              {(props) => (
                <input
                  {...props}
                  value={nota}
                  onChange={(e) => setNota(e.target.value)}
                  maxLength={4000}
                  className={claseControl("h-9")}
                />
              )}
            </Campo>
          </div>
        </fieldset>
      )}

      <div className="grid items-end gap-4 sm:grid-cols-[minmax(0,1fr)_auto]">
        <Campo
          etiqueta="Tu nombre"
          ayuda="Sin cuentas: es un laboratorio. Se recuerda en este navegador para la próxima vez."
          error={errores.revisor}
          idError={idError("revisor")}
        >
          {(props) => (
            <input
              {...props}
              value={revisor}
              onChange={(e) => {
                setRevisor(e.target.value);
                corregido("revisor");
              }}
              required
              maxLength={120}
              autoComplete="name"
              className={claseControl("h-9")}
            />
          )}
        </Campo>
        <button
          type="submit"
          disabled={guardando}
          className="inline-flex h-9 items-center justify-center gap-1.5 self-end rounded-lg bg-persona-fuerte px-4 text-sm font-medium text-white transition-colors hover:bg-persona-fuerte/90 focus-visible:ring-3 focus-visible:ring-persona/50 focus-visible:outline-none disabled:opacity-60 sm:mb-[1.375rem]"
        >
          {guardando && <LoaderCircle aria-hidden className="size-4 animate-spin" />}
          {guardando ? "Guardando…" : "Guardar decisión"}
        </button>
      </div>

      <div id={`${base}-estado`} aria-live="polite">
        {!guardando && resultado && (
          <Resultado
            resultado={resultado}
            recargando={recargando}
            onRecargar={() =>
              recargar(() => {
                setResultado(null);
                router.refresh();
              })
            }
          />
        )}
      </div>
    </form>
  );
}

function Resultado({
  resultado: r,
  recargando,
  onRecargar,
}: {
  resultado: ResultadoDecision;
  recargando: boolean;
  onRecargar: () => void;
}) {
  switch (r.tipo) {
    case "ok":
      return (
        <p role="status" className="flex items-center gap-1.5 text-sm font-medium text-persona-fuerte">
          <CircleCheck aria-hidden className="size-4 shrink-0" />
          Decisión registrada. El hallazgo queda como «{ESTADO_HALLAZGO[r.estado]}».
        </p>
      );
    case "sugerencia_cambio":
      return (
        <div role="alert" className="flex flex-wrap items-start gap-x-3 gap-y-2 rounded-md border border-sev-media/25 bg-sev-media-fondo px-3.5 py-3 text-sm text-sev-media">
          <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
          <p className="min-w-0 flex-1 leading-relaxed">
            La sugerencia del modelo cambió mientras decidías: alguien volvió a enriquecer este
            hallazgo. Recarga para ver la nueva antes de decidir. No se guardó nada.
          </p>
          <button
            type="button"
            onClick={onRecargar}
            disabled={recargando}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-sev-media/40 bg-card px-3 text-sm font-medium text-sev-media hover:bg-sev-media-fondo focus-visible:ring-3 focus-visible:ring-sev-media/30 focus-visible:outline-none"
          >
            <RotateCcw aria-hidden className={cn("size-4", recargando && "animate-spin")} />
            Recargar
          </button>
        </div>
      );
    case "invalido":
      return r.errores.general ? <MensajeError>{r.errores.general}</MensajeError> : null;
    case "no_existe":
      return <MensajeError>Este hallazgo ya no existe.</MensajeError>;
    case "api_caida":
      return (
        <MensajeError>
          {r.mensaje}. Revisa que el servicio <code className="font-mono">api</code> esté arriba.
          No se guardó nada.
        </MensajeError>
      );
    case "error":
      return <MensajeError>{r.mensaje}</MensajeError>;
  }
}

function MensajeError({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="flex gap-2 text-sm leading-relaxed text-destructive">
      <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </p>
  );
}

function OpcionDecision({
  nombre,
  valor,
  actual,
  onElegir,
  secundaria = false,
  children,
}: {
  nombre: string;
  valor: DecisionValidacion;
  actual: DecisionValidacion | null;
  onElegir: (v: DecisionValidacion) => void;
  secundaria?: boolean;
  children: React.ReactNode;
}) {
  const elegida = actual === valor;
  return (
    <label
      className={cn(
        "relative flex cursor-pointer rounded-md border bg-card transition-colors hover:border-persona/60",
        "has-[:focus-visible]:ring-3 has-[:focus-visible]:ring-persona/40",
        secundaria ? "items-center gap-1.5 rounded-full px-3 py-1" : "flex-col gap-0.5 px-3 py-2.5",
        elegida && "border-persona bg-persona-suave text-persona-fuerte",
        !elegida && "text-navy",
      )}
    >
      <input
        type="radio"
        name={nombre}
        value={valor}
        checked={elegida}
        onChange={() => onElegir(valor)}
        className="sr-only"
      />
      {children}
    </label>
  );
}

function PreguntaIA({
  nombre,
  pregunta,
  contexto,
  valor,
  onCambiar,
}: {
  nombre: string;
  pregunta: string;
  contexto?: string;
  valor: Respuesta;
  onCambiar: (v: Respuesta) => void;
}) {
  const opciones: { v: Respuesta; t: string }[] = [
    { v: "si", t: "Sí" },
    { v: "no", t: "No" },
    { v: "nose", t: "No sé" },
  ];
  return (
    <fieldset className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 py-2">
      <legend className="sr-only">{pregunta}</legend>
      <div className="min-w-0" aria-hidden>
        <p className="text-sm text-foreground">{pregunta}</p>
        {contexto && <p className="font-mono text-xs text-muted-foreground">{contexto}</p>}
      </div>
      <div className="flex shrink-0 overflow-hidden rounded-md border bg-card">
        {opciones.map((o) => (
          <label
            key={o.v}
            className={cn(
              "cursor-pointer border-l px-3 py-1 text-xs font-medium first:border-l-0 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring/60 has-[:focus-visible]:ring-inset",
              valor === o.v ? "bg-navy text-white" : "text-navy hover:bg-muted",
            )}
          >
            <input
              type="radio"
              name={nombre}
              value={o.v}
              checked={valor === o.v}
              onChange={() => onCambiar(o.v)}
              className="sr-only"
            />
            {o.t}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

const claseControl = (extra: string) =>
  cn(
    "w-full rounded-md border bg-card px-2.5 text-sm text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40 focus-visible:outline-none aria-invalid:border-destructive aria-invalid:ring-destructive/20",
    extra,
  );

function Campo({
  etiqueta,
  ayuda,
  error,
  idError,
  children,
}: {
  etiqueta: string;
  ayuda?: string;
  error?: string;
  idError: string;
  children: (props: { id: string; "aria-invalid": boolean; "aria-describedby"?: string }) => React.ReactNode;
}) {
  const id = useId();
  const idAyuda = `${id}-ayuda`;
  const describe = [ayuda && idAyuda, error && idError].filter(Boolean).join(" ") || undefined;
  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-muted-foreground">
        {etiqueta}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": describe })}
      {ayuda && (
        <p id={idAyuda} className="text-xs text-muted-foreground">
          {ayuda}
        </p>
      )}
      <ErrorCampo id={idError} mensaje={error} />
    </div>
  );
}

function ErrorCampo({ id, mensaje }: { id: string; mensaje?: string }) {
  if (!mensaje) return null;
  return (
    <p id={id} className="mt-1 flex items-center gap-1 text-xs font-medium text-destructive">
      <CircleAlert aria-hidden className="size-3.5 shrink-0" />
      {mensaje}
    </p>
  );
}
