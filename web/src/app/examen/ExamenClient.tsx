"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type {
  Banco,
  ConfigExamen,
  PreguntaExamen,
} from "@/lib/types";
import { cargarBanco } from "@/lib/bank";
import { construirExamen, corregirExamen, type Correccion } from "@/lib/exam";
import { ExamConfig } from "@/components/exam/ExamConfig";
import { ExamRunner } from "@/components/exam/ExamRunner";
import { ExamResults } from "@/components/exam/ExamResults";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "config" | "examen" | "resultados";

export function ExamenClient() {
  const router = useRouter();
  const [fase, setFase] = useState<Fase>("cargando");
  const [banco, setBanco] = useState<Banco | null>(null);
  const [progreso, setProgreso] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const [config, setConfig] = useState<ConfigExamen | null>(null);
  const [preguntas, setPreguntas] = useState<PreguntaExamen[]>([]);
  const [correccion, setCorreccion] = useState<Correccion | null>(null);
  const [tiempoMs, setTiempoMs] = useState(0);

  const cargar = useCallback(async (forzar = false) => {
    try {
      const b = await cargarBanco({
        forzar,
        onProgreso: (n) => setProgreso(n),
      });
      setBanco(b);
      setFase("config");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error desconocido.");
      setFase("error");
    }
  }, []);

  useEffect(() => {
    void cargar(false);
  }, [cargar]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    setProgreso(0);
    try {
      const b = await cargarBanco({
        forzar: true,
        onProgreso: (n) => setProgreso(n),
      });
      setBanco(b);
    } catch {
      // Se conserva el banco actual si la actualización falla.
    } finally {
      setRefreshing(false);
    }
  }, []);

  function empezar(cfg: ConfigExamen) {
    if (!banco) return;
    const ex = construirExamen(banco, cfg);
    setConfig(cfg);
    setPreguntas(ex);
    setFase("examen");
  }

  function finalizar(respuestas: (number | null)[], elapsed: number) {
    if (!config) return;
    setCorreccion(corregirExamen(preguntas, respuestas, config.umbral));
    setTiempoMs(elapsed);
    setFase("resultados");
    window.scrollTo(0, 0);
  }

  function repetir() {
    setCorreccion(null);
    setPreguntas([]);
    setFase("config");
    window.scrollTo(0, 0);
  }

  if (fase === "cargando") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <TruckLogo className="h-16 w-16 animate-pulse rounded-2xl" />
        <div>
          <p className="font-semibold">Descargando banco de preguntas…</p>
          <p className="mt-1 text-sm text-muted">
            {progreso > 0
              ? `${progreso.toLocaleString("es-ES")} preguntas`
              : "Preparando…"}
          </p>
          <p className="mt-2 text-xs text-muted">
            Solo la primera vez. Luego funciona sin conexión.
          </p>
        </div>
      </div>
    );
  }

  if (fase === "error") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <p className="text-4xl" aria-hidden>
          ⚠️
        </p>
        <div>
          <p className="font-semibold">No se pudo cargar el banco</p>
          <p className="mt-1 text-sm text-muted">{errorMsg}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setFase("cargando");
            void cargar(false);
          }}
          className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white shadow-sm"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (fase === "config" && banco) {
    return (
      <ExamConfig
        banco={banco}
        onStart={empezar}
        onRefresh={onRefresh}
        refreshing={refreshing}
      />
    );
  }

  if (fase === "examen") {
    return (
      <ExamRunner
        preguntas={preguntas}
        onFinish={finalizar}
        onCancel={() => setFase("config")}
      />
    );
  }

  if (fase === "resultados" && correccion && config) {
    return (
      <ExamResults
        correccion={correccion}
        config={config}
        tiempoMs={tiempoMs}
        onRepetir={repetir}
        onInicio={() => router.push("/")}
      />
    );
  }

  return null;
}
