/**
 * Contenedor de cada página: limita el ancho del contenido. Es un div porque
 * el <main> ya lo pone SidebarInset en el layout.
 */
export function Marco({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">{children}</div>;
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
      <h2 className="font-semibold text-tinta">{titulo}</h2>
      {children && <p className="mt-1 text-sm text-muted-foreground">{children}</p>}
      {accion && <div className="mt-3">{accion}</div>}
    </div>
  );
}

/**
 * La API no respondió: el mismo mensaje en todas las pantallas. `mensaje` viene
 * de ErrorApi y nunca trae la URL interna de la API (ver SIN_CONEXION).
 */
export function AvisoApiCaida({ titulo, mensaje }: { titulo: string; mensaje: string }) {
  return (
    <Aviso titulo={titulo}>
      {mensaje}. Revisa que el servicio <code className="font-mono">api</code> esté arriba.
    </Aviso>
  );
}
