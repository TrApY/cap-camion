import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Salida autocontenida para despliegue en contenedor (Docker/Dokploy):
  // genera .next/standalone con un server.js mínimo y solo las dependencias
  // necesarias, sin necesidad de instalar node_modules en la imagen final.
  output: "standalone",
  async headers() {
    return [
      {
        // El service worker no debe cachearse por el navegador: así los
        // usuarios reciben siempre la última versión del SW.
        source: "/sw.js",
        headers: [
          {
            key: "Content-Type",
            value: "application/javascript; charset=utf-8",
          },
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
