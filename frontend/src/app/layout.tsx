import type { Metadata } from "next";
import localFont from "next/font/local";
import { cookies } from "next/headers";

import { BarraLateral } from "@/components/barra-lateral";
import { BarraMovil } from "@/components/barra-movil";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { COOKIE_TEMA, leerTema } from "@/lib/tema";
import "./globals.css";

// Fuentes empaquetadas (Fontsource), no Google Fonts: el dashboard tiene que
// compilar y verse igual sin internet, por ejemplo en la sala de la defensa.
const plexSans = localFont({
  variable: "--font-plex-sans",
  src: "../../node_modules/@fontsource-variable/ibm-plex-sans/files/ibm-plex-sans-latin-wght-normal.woff2",
  weight: "100 700",
  style: "normal",
});

const plexMono = localFont({
  variable: "--font-plex-mono",
  src: [
    {
      path: "../../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "../../node_modules/@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2",
      weight: "500",
      style: "normal",
    },
  ],
});

export const metadata: Metadata = {
  title: "SentinelAI",
  description:
    "Hallazgos de OWASP ZAP normalizados, enriquecidos con IA local y validados por una persona.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  // La barra lateral recuerda si quedó colapsada (cookie que escribe
  // SidebarProvider). Leerla acá evita que parpadee al recargar.
  const galletas = await cookies();
  const abierta = galletas.get("sidebar_state")?.value !== "false";
  // Tema elegido (cookie que escribe el botón de tema): la página sale del
  // servidor ya con la clase puesta, sin destello al cargar.
  const tema = leerTema(galletas.get(COOKIE_TEMA)?.value);

  return (
    <html
      lang="es"
      className={`${plexSans.variable} ${plexMono.variable} h-full antialiased${tema === "oscuro" ? " dark" : ""}`}
    >
      <body className="min-h-full">
        <TooltipProvider>
          <SidebarProvider defaultOpen={abierta}>
            <BarraLateral tema={tema} />
            <SidebarInset className="min-w-0">
              <BarraMovil />
              {children}
            </SidebarInset>
          </SidebarProvider>
        </TooltipProvider>
      </body>
    </html>
  );
}
