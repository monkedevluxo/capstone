"use client";

import { FileText, House, ListChecks, Radar, type LucideIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface Modulo {
  etiqueta: string;
  icono: LucideIcon;
  /** Sin href: el módulo existe en el plan pero todavía no se puede abrir. */
  href?: string;
  /** Se abre en otra pestaña, fuera del dashboard (el informe es una página aparte). */
  pestanaNueva?: boolean;
}

export const MODULOS: Modulo[] = [
  { etiqueta: "Inicio", icono: House, href: "/" },
  { etiqueta: "Hallazgos", icono: ListChecks, href: "/hallazgos" },
  { etiqueta: "Escaneos", icono: Radar, href: "/escaneos" },
  // T-058 / T-059: vista previa del informe técnico y exportación a PDF, XLSX y CSV.
  { etiqueta: "Informe", icono: FileText, href: "/informe" },
];

/** Módulo al que pertenece una ruta: /hallazgos/<id> es parte de Hallazgos. */
export function moduloActivo(ruta: string): Modulo | undefined {
  return MODULOS.find(
    (m) => m.href && !m.pestanaNueva && (m.href === "/" ? ruta === "/" : ruta === m.href || ruta.startsWith(`${m.href}/`)),
  );
}

export function BarraLateral() {
  const ruta = usePathname();
  const activo = moduloActivo(ruta);
  const { isMobile, setOpenMobile } = useSidebar();

  // En el teléfono la navegación es un panel encima del contenido: se cierra
  // al elegir un módulo.
  const cerrarEnMovil = () => {
    if (isMobile) setOpenMobile(false);
  };

  return (
    <Sidebar collapsible="icon">
      {/* Logo y botón de colapsar en la misma fila; colapsada, uno sobre otro. */}
      <SidebarHeader className="flex-row items-center group-data-[collapsible=icon]:flex-col">
        <SidebarMenu className="min-w-0 flex-1">
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              tooltip="SentinelAI · Inicio"
              render={<Link href="/" onClick={cerrarEnMovil} />}
              className="hover:bg-sidebar-accent/60"
            >
              {/* Logo: casco y texto en cobre. Con la barra colapsada queda solo el casco. */}
              <span className="flex size-8 shrink-0 items-center justify-center">
                <Image src="/marca/casco.png" alt="" width={81} height={96} priority className="h-7.5 w-auto" />
              </span>
              <Image
                src="/marca/texto.png"
                alt="SentinelAI"
                width={294}
                height={48}
                priority
                className="h-3.75 w-auto group-data-[collapsible=icon]:hidden"
              />
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
        <BotonColapsar />
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <nav aria-label="Módulos">
              <SidebarMenu className="gap-1">
                {MODULOS.map((m) => (
                  <SidebarMenuItem key={m.etiqueta}>
                    {m.href && m.pestanaNueva ? (
                      <SidebarMenuButton
                        tooltip={`${m.etiqueta} · se abre en otra pestaña`}
                        render={
                          // <a> y no <Link>: /informe es un route handler, no una página de Next.
                          <a href={m.href} target="_blank" rel="noopener" onClick={cerrarEnMovil} />
                        }
                      >
                        <m.icono aria-hidden />
                        <span>
                          {m.etiqueta}
                          <span className="sr-only"> (se abre en otra pestaña)</span>
                        </span>
                      </SidebarMenuButton>
                    ) : m.href ? (
                      <SidebarMenuButton
                        isActive={m === activo}
                        tooltip={m.etiqueta}
                        render={
                          <Link
                            href={m.href}
                            aria-current={m === activo ? "page" : undefined}
                            onClick={cerrarEnMovil}
                          />
                        }
                      >
                        <m.icono aria-hidden />
                        <span>{m.etiqueta}</span>
                      </SidebarMenuButton>
                    ) : (
                      <ModuloProximamente modulo={m} />
                    )}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </nav>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <IndicadorLaboratorio />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}

/**
 * Colapsa o expande la barra desde la propia barra. En el teléfono la barra es
 * un panel encima del contenido: este botón lo cierra y el de la franja
 * superior lo abre. También responde a Ctrl/⌘ + B (SidebarProvider).
 */
function BotonColapsar() {
  const { state, isMobile } = useSidebar();
  const accion = isMobile ? "Cerrar la navegación" : state === "expanded" ? "Colapsar la navegación" : "Expandir la navegación";

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <SidebarTrigger
            aria-label={accion}
            className="shrink-0 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-sidebar-ring"
          />
        }
      />
      <TooltipContent side="right" align="center">
        {accion}
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * Módulo planificado que todavía no existe. No es enlace ni botón: se ve más
 * tenue y dice "Próximamente", para mostrar el alcance sin parecer roto.
 */
function ModuloProximamente({ modulo: m }: { modulo: Modulo }) {
  return (
    <>
      <SidebarMenuButton
        tooltip={`${m.etiqueta} · próximamente`}
        render={<div />}
        className="cursor-default text-sidebar-foreground/70 hover:bg-transparent hover:text-sidebar-foreground/70 active:bg-transparent active:text-sidebar-foreground/70"
      >
        <m.icono aria-hidden />
        <span>
          {m.etiqueta}
          <span className="sr-only"> (próximamente)</span>
        </span>
      </SidebarMenuButton>
      <SidebarMenuBadge
        aria-hidden
        className="top-1.5 h-5 rounded-full border border-sidebar-foreground/30 px-2 text-[11px] font-medium text-sidebar-foreground/80"
      >
        Próximamente
      </SidebarMenuBadge>
    </>
  );
}

/**
 * Recordatorio de que todo corre en el laboratorio propio (Ley 21.459): la API
 * solo acepta hosts del laboratorio. Con la barra colapsada queda el punto y
 * el texto pasa a un tooltip; los lectores de pantalla lo leen igual.
 */
function IndicadorLaboratorio() {
  const { state, isMobile } = useSidebar();
  const colapsada = state === "collapsed" && !isMobile;

  return (
    <Tooltip>
      <TooltipTrigger
        render={<div />}
        className={cn(
          "flex items-center gap-2 rounded-md px-2 py-2 text-xs text-sidebar-foreground",
          colapsada && "justify-center px-0",
        )}
      >
        <span aria-hidden className="size-2 shrink-0 rounded-full bg-emerald-400" />
        <span className={cn("truncate", colapsada && "sr-only")}>
          Laboratorio aislado · <span className="font-mono text-white">juiceshop</span>
        </span>
      </TooltipTrigger>
      <TooltipContent side="right" align="center" hidden={!colapsada}>
        Laboratorio aislado · juiceshop
      </TooltipContent>
    </Tooltip>
  );
}
