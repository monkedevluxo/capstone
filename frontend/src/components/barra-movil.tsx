"use client";

import Image from "next/image";
import Link from "next/link";

import { SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Solo en el teléfono: ahí la barra lateral es un panel escondido y esta barra
 * es la única forma de abrirlo. En pantallas grandes no existe; el contenido
 * empieza arriba y la navegación vive en la barra lateral.
 */
export function BarraMovil() {
  return (
    <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-sidebar px-2 md:hidden">
      <SidebarTrigger
        aria-label="Abrir la navegación"
        className="text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring"
      />
      <Link href="/" className="flex items-center gap-2 rounded-md px-1 py-1 focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none">
        <Image src="/marca/casco.png" alt="" width={81} height={96} className="h-6 w-auto" />
        <Image src="/marca/texto.png" alt="SentinelAI · Inicio" width={294} height={48} className="h-3.5 w-auto" />
      </Link>
    </header>
  );
}
