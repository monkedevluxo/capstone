/** Contenedor de cada página, bajo la barra superior. */
export function Marco({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>;
}

/** Mensaje en una tarjeta: errores, estados vacíos, páginas en construcción. */
export function Aviso({
  titulo,
  children,
  accion,
}: {
  titulo: string;
  children?: React.ReactNode;
  accion?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border bg-card p-6">
      <h2 className="font-semibold text-navy">{titulo}</h2>
      {children && <p className="mt-1 text-sm text-muted-foreground">{children}</p>}
      {accion && <div className="mt-3">{accion}</div>}
    </div>
  );
}
