"use client";

import { useEffect } from "react";
import { iniciarSyncAutomatico } from "@/lib/sync";

// Arranca la sincronización del progreso con la nube (CAP-12). No pinta nada y
// no guarda estado: si no hay cuenta o no hay red, la cola simplemente espera.
export function SyncInit() {
  useEffect(() => {
    iniciarSyncAutomatico();
  }, []);

  return null;
}
