"use client";

import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { COOKIE_TEMA, type Tema } from "@/lib/tema";

const UN_ANO = 60 * 60 * 24 * 365;

/**
 * Alterna entre el tema claro y el oscuro. El ícono muestra el tema actual
 * (sol o luna) y el cambio se ve al instante. Queda en la cookie "tema", que
 * el layout lee para pintar la página ya en el tema elegido.
 */
export function BotonTema({ inicial }: { inicial: Tema }) {
  const [tema, setTema] = useState<Tema>(inicial);
  const otro: Tema = tema === "claro" ? "oscuro" : "claro";
  const Icono = tema === "claro" ? Sun : Moon;

  function alternar() {
    setTema(otro);
    document.documentElement.classList.toggle("dark", otro === "oscuro");
    document.cookie = `${COOKIE_TEMA}=${otro}; path=/; max-age=${UN_ANO}; samesite=lax`;
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          onClick={alternar}
          tooltip={`Cambiar a tema ${otro}`}
          aria-label={`Tema ${tema}. Cambiar a tema ${otro}`}
        >
          <Icono aria-hidden />
          <span>Tema {tema}</span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
