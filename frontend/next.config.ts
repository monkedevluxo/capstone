import type { NextConfig } from "next";

/**
 * Límite del cuerpo de las Server Actions (por defecto 1 MB, medido sobre el
 * multipart completo). El reporte más grande del repo pesa 52 KB
 * (lab/fixtures/zap_juiceshop_ajax_auth_v1.json); 5 MB deja margen para
 * escaneos más largos y para el overhead del multipart. La acción rechaza
 * antes, con un mensaje claro, los archivos de más de 4 MB (lib/limites.ts).
 */
const nextConfig: NextConfig = {
  // El indicador de desarrollo va a la derecha: abajo a la izquierda tapaba
  // "Laboratorio aislado" en el pie de la barra lateral. Solo existe en dev.
  devIndicators: { position: "bottom-right" },
  // En dev, Next bloquea los recursos de desarrollo (HMR, chunks) pedidos
  // desde un hostname distinto de localhost: abierta como 127.0.0.1 la página
  // no hidrata. Solo afecta a `next dev`.
  allowedDevOrigins: ["127.0.0.1"],
  experimental: {
    serverActions: {
      bodySizeLimit: "5mb",
    },
  },
};

export default nextConfig;
