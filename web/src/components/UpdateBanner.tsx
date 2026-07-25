"use client";

import { useCallback, useEffect, useState } from "react";
import { BUILD_VERSION } from "@/lib/version";

/** Tiempo mínimo entre dos comprobaciones de versión. */
const MS_ENTRE_CHEQUEOS = 60_000;

/** Espera máxima a que el service worker confirme el re-precache. */
const MS_ESPERA_SHELL = 5_000;

/**
 * Pide al service worker que vuelva a precachear el app shell y espera su
 * confirmación. Sin este paso la recarga volvería a pintar los documentos
 * viejos que la caché stale-while-revalidate sigue guardando.
 * Resuelve siempre (sin SW, con error o por timeout) para no bloquear nunca la
 * recarga: en el peor caso se recarga con la copia stale, como hasta ahora.
 */
function refrescarShell(): Promise<void> {
  if (!("serviceWorker" in navigator)) return Promise.resolve();

  const controlador = navigator.serviceWorker.controller;
  if (!controlador) return Promise.resolve();

  return new Promise<void>((resolve) => {
    const alRecibir = (evento: MessageEvent) => {
      const datos = evento.data as { tipo?: string } | null;
      if (datos?.tipo === "SHELL_REFRESCADO") finalizar();
    };

    const finalizar = () => {
      window.clearTimeout(temporizador);
      navigator.serviceWorker.removeEventListener("message", alRecibir);
      resolve();
    };

    const temporizador = window.setTimeout(finalizar, MS_ESPERA_SHELL);
    navigator.serviceWorker.addEventListener("message", alRecibir);
    controlador.postMessage({ tipo: "REFRESCAR_SHELL" });
  });
}

/**
 * Aviso de versión nueva (CAP-13). Compara la versión empaquetada en el bundle
 * con la que sirve el servidor en /version.json: si no coinciden, este cliente
 * está corriendo un despliegue anterior y se le ofrece actualizar.
 */
export function UpdateBanner() {
  const [hayVersionNueva, setHayVersionNueva] = useState(false);
  const [actualizando, setActualizando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    let ultimoChequeo = 0;

    const comprobar = () => {
      const ahora = Date.now();
      if (ahora - ultimoChequeo < MS_ENTRE_CHEQUEOS) return;
      ultimoChequeo = ahora;

      // El estado se aplica en el callback de la promesa, nunca de forma
      // sincrónica dentro del efecto (react-hooks/set-state-in-effect).
      fetch("/version.json", { cache: "no-store" })
        .then((res) => (res.ok ? (res.json() as Promise<unknown>) : null))
        .then((datos) => {
          if (cancelado) return;
          const version = (datos as { version?: string } | null)?.version;
          if (version && version !== BUILD_VERSION) setHayVersionNueva(true);
        })
        .catch(() => {
          // Sin red o endpoint caído: no se avisa de nada.
        });
    };

    comprobar();

    // Al volver a la app (típico en PWA instalada) se vuelve a comprobar.
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") comprobar();
    };
    document.addEventListener("visibilitychange", alCambiarVisibilidad);

    return () => {
      cancelado = true;
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, []);

  const actualizar = useCallback(() => {
    setActualizando(true);
    refrescarShell().then(
      () => window.location.reload(),
      () => window.location.reload(),
    );
  }, []);

  if (!hayVersionNueva) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-30 flex justify-center px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-4">
      <div
        role="status"
        className="flex w-full max-w-md items-center gap-3 rounded-2xl border border-brand bg-surface p-4 shadow-xl"
      >
        <p className="min-w-0 flex-1 text-sm font-semibold leading-snug">
          Hay una versión nueva de la app
        </p>
        <button
          type="button"
          onClick={actualizar}
          disabled={actualizando}
          className="flex-none rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {actualizando ? "Actualizando…" : "Actualizar"}
        </button>
      </div>
    </div>
  );
}
