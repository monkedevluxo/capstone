import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // El indicador de desarrollo va a la derecha: abajo a la izquierda tapaba
  // "Laboratorio aislado" en el pie de la barra lateral. Solo existe en dev.
  devIndicators: { position: "bottom-right" },
};

export default nextConfig;
