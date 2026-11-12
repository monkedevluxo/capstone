import type { Metadata } from "next";
import localFont from "next/font/local";
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

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="es"
      className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
