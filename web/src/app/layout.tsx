import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { TruckLogo } from "@/components/TruckLogo";
import { ServiceWorkerRegister } from "@/components/ServiceWorkerRegister";
import { SyncInit } from "@/components/SyncInit";

export const metadata: Metadata = {
  title: {
    default: "CAP Camión — Estudio del CAP de mercancías",
    template: "%s · CAP Camión",
  },
  description:
    "Prepara el CAP de mercancías con exámenes simulados a partir de preguntas de exámenes oficiales reales.",
  applicationName: "CAP Camión",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "CAP Camión",
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  themeColor: "#1d4ed8",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="flex min-h-dvh flex-col">
        <header className="sticky top-0 z-10 border-b border-border bg-surface/90 backdrop-blur">
          <div className="mx-auto flex w-full max-w-md items-center gap-2 px-4 py-3">
            <Link href="/" className="flex items-center gap-2">
              <TruckLogo className="h-8 w-8 rounded-lg" />
              <span className="text-base font-bold tracking-tight">
                CAP Camión
              </span>
            </Link>
          </div>
        </header>
        <main className="mx-auto w-full max-w-md flex-1 px-4 py-5">
          {children}
        </main>
        <ServiceWorkerRegister />
        <SyncInit />
      </body>
    </html>
  );
}
