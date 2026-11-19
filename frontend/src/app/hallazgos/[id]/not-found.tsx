import Link from "next/link";

import { Aviso, Marco } from "@/components/marco";
import { claseEnlace } from "@/lib/estilos";

/** Hallazgo inexistente o id que no es un UUID. */
export default function HallazgoNoEncontrado() {
  return (
    <Marco>
      <Aviso
        titulo="Ese hallazgo no existe"
        accion={
          <Link href="/hallazgos" className={claseEnlace}>
            Ir a la lista de hallazgos
          </Link>
        }
      >
        Puede que el enlace esté incompleto o que el hallazgo sea de una base distinta.
      </Aviso>
    </Marco>
  );
}
