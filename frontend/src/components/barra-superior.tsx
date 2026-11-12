"use client";

import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const SECCIONES = [
  { href: "/hallazgos", etiqueta: "Hallazgos" },
  { href: "/escaneos", etiqueta: "Escaneos" },
];

export function BarraSuperior() {
  const ruta = usePathname();

  return (
    <header className="bg-navy text-white">
      <div className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3 sm:px-6">
        <Link
          href="/hallazgos"
          className="flex items-center gap-2 rounded-sm font-semibold tracking-tight focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none"
        >
          <ShieldCheck aria-hidden className="size-5 text-persona" />
          SentinelAI
        </Link>

        <nav aria-label="Secciones" className="flex items-center gap-1">
          {SECCIONES.map((s) => {
            const activa = ruta === s.href || ruta.startsWith(`${s.href}/`);
            return (
              <Link
                key={s.href}
                href={s.href}
                aria-current={activa ? "page" : undefined}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm font-medium text-white/75 transition-colors hover:bg-white/10 hover:text-white focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:outline-none",
                  activa && "bg-white/15 text-white",
                )}
              >
                {s.etiqueta}
              </Link>
            );
          })}
        </nav>

        <p className="flex basis-full items-center gap-2 text-xs text-white/75 sm:ml-auto sm:basis-auto">
          <span aria-hidden className="size-2 rounded-full bg-emerald-400" />
          Laboratorio aislado · <span className="font-mono text-white">juiceshop</span>
        </p>
      </div>
    </header>
  );
}
