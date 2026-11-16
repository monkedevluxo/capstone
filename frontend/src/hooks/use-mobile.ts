import * as React from "react"

const MOBILE_BREAKPOINT = 768
const CONSULTA = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

// Versión de shadcn reescrita con useSyncExternalStore: la original hacía
// setState dentro de un efecto (regla react-hooks/set-state-in-effect).
function suscribir(avisar: () => void) {
  const mql = window.matchMedia(CONSULTA)
  mql.addEventListener("change", avisar)
  return () => mql.removeEventListener("change", avisar)
}

export function useIsMobile() {
  return React.useSyncExternalStore(
    suscribir,
    () => window.matchMedia(CONSULTA).matches,
    // En el servidor no hay ventana: se asume escritorio, como el original.
    () => false
  )
}
