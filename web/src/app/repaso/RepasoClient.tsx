"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Banco, Pregunta, PreguntaExamen } from "@/lib/types";
import { cargarBanco } from "@/lib/bank";
import {
  corregirExamen,
  preguntasAptas,
  prepararPreguntas,
  type Correccion,
} from "@/lib/exam";
import {
  cargarProgresos,
  estadoRepaso,
  registrarSesion,
  type ProgresoPregunta,
} from "@/lib/stats";
import { ExamRunner } from "@/components/exam/ExamRunner";
import { ExamResults } from "@/components/exam/ExamResults";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "resumen" | "examen" | "resultados";

/** Tamaño de tanda por defecto (se recorta si hay menos preguntas vencidas). */
const TANDA_POR_DEFECTO = 20;

/** Tamaños ofrecidos además de "Todas". */
const TAMANOS_TANDA = [10, 20];

/** Fecha corta es-ES (sin hora): "próxima tanda: 03/08/2026". */
function fechaCorta(epochMs: number): string {
  return new Date(epochMs).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function RepasoClient() {
  const router = useRouter();
  const [fase, setFase] = useState<Fase>("cargando");
  const [banco, setBanco] = useState<Banco | null>(null);
  const [progresos, setProgresos] = useState<ProgresoPregunta[]>([]);
  // Instante de referencia de la cola. Se fija al cargar y no durante el
  // render, para no depender de un reloj impuro en cada repintado.
  const [ahora, setAhora] = useState(0);
  const [progresoDescarga, setProgresoDescarga] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const [tanda, setTanda] = useState(TANDA_POR_DEFECTO);
  const [preguntas, setPreguntas] = useState<PreguntaExamen[]>([]);
  const [correccion, setCorreccion] = useState<Correccion | null>(null);
  const [tiempoMs, setTiempoMs] = useState(0);

  // Guardado en curso de la última sesión: al volver al resumen hay que
  // esperarlo para releer una cola ya actualizada.
  const guardadoRef = useRef<Promise<void> | null>(null);

  const cargar = useCallback(async () => {
    try {
      // Aquí el progreso NO es opcional: sin él no hay nada que repasar, así
      // que un fallo de IndexedDB lleva a la pantalla de error.
      const [b, p] = await Promise.all([
        cargarBanco({ onProgreso: (n) => setProgresoDescarga(n) }),
        cargarProgresos(),
      ]);
      setBanco(b);
      setProgresos(p);
      setAhora(Date.now());
      setFase("resumen");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error desconocido.");
      setFase("error");
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Preguntas aptas del banco indexadas por id, para cruzarlas con la cola.
  const aptasPorId = useMemo(() => {
    if (!banco) return new Map<string, Pregunta>();
    return new Map(preguntasAptas(banco).map((p) => [p.id, p]));
  }, [banco]);

  const estado = useMemo(
    () => estadoRepaso(progresos, ahora),
    [progresos, ahora],
  );

  // Cola efectiva: vencidas que siguen existiendo en el banco y son aptas.
  const cola = useMemo(
    () => estado.vencidas.filter((v) => aptasPorId.has(v.preguntaId)),
    [estado.vencidas, aptasPorId],
  );

  const pendientes = cola.length;
  // La tanda elegida nunca puede superar lo que hay en la cola.
  const tandaEfectiva = Math.min(tanda, pendientes);

  const opcionesTanda = useMemo(() => {
    const opciones = TAMANOS_TANDA.filter((n) => n < pendientes).map((n) => ({
      valor: n,
      etiqueta: String(n),
    }));
    opciones.push({ valor: pendientes, etiqueta: "Todas" });
    return opciones;
  }, [pendientes]);

  function empezar() {
    const seleccion: Pregunta[] = [];
    for (const p of cola.slice(0, tandaEfectiva)) {
      const pregunta = aptasPorId.get(p.preguntaId);
      if (pregunta) seleccion.push(pregunta);
    }
    if (seleccion.length === 0) return;
    setPreguntas(prepararPreguntas(seleccion));
    setFase("examen");
    window.scrollTo(0, 0);
  }

  function finalizar(respuestas: (number | null)[], elapsed: number) {
    const corr = corregirExamen(preguntas, respuestas);
    setCorreccion(corr);
    setTiempoMs(elapsed);
    setFase("resultados");
    window.scrollTo(0, 0);

    // Estadísticas: fire-and-forget. Si IndexedDB falla, los resultados se
    // muestran igualmente.
    guardadoRef.current = registrarSesion({
      tipo: "repaso",
      modo: "practica",
      correccion: corr,
      tiempoMs: elapsed,
    }).catch((e) => {
      console.warn("No se pudo guardar la sesión en estadísticas:", e);
    });
  }

  async function volverAlResumen() {
    try {
      // El repaso acaba de reprogramar las preguntas: hay que releer la cola.
      await guardadoRef.current;
      setProgresos(await cargarProgresos());
    } catch {
      // Si la relectura falla se mantiene la cola anterior en pantalla.
    }
    guardadoRef.current = null;
    setAhora(Date.now());
    setCorreccion(null);
    setPreguntas([]);
    setFase("resumen");
    window.scrollTo(0, 0);
  }

  if (fase === "cargando") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <TruckLogo className="h-16 w-16 animate-pulse rounded-2xl" />
        <div>
          <p className="font-semibold">Descargando banco de preguntas…</p>
          <p className="mt-1 text-sm text-muted">
            {progresoDescarga > 0
              ? `${progresoDescarga.toLocaleString("es-ES")} preguntas`
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
          <p className="font-semibold">No se pudo cargar tu repaso</p>
          <p className="mt-1 text-sm text-muted">{errorMsg}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setFase("cargando");
            void cargar();
          }}
          className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white shadow-sm"
        >
          Reintentar
        </button>
      </div>
    );
  }

  if (fase === "examen") {
    return (
      <ExamRunner
        preguntas={preguntas}
        modo="practica"
        onFinish={finalizar}
        onCancel={() => void volverAlResumen()}
      />
    );
  }

  if (fase === "resultados" && correccion) {
    return (
      <ExamResults
        correccion={correccion}
        tiempoMs={tiempoMs}
        onRepetir={() => void volverAlResumen()}
        onInicio={() => router.push("/")}
      />
    );
  }

  // Fase resumen: la "home" del repaso.
  const explicacion = (
    <div className="rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed text-muted shadow-sm">
      <span className="font-semibold text-foreground">
        Cómo funciona el repaso:
      </span>{" "}
      cada pregunta que fallas vuelve enseguida; cada vez que la aciertas tarda
      más en volver (1 día, 6 días, y a partir de ahí cada vez más espaciada).
      Así repasas justo antes de olvidarla y dedicas el tiempo a lo que de verdad
      te cuesta.
    </div>
  );

  const volverAlInicio = (
    <button
      type="button"
      onClick={() => router.push("/")}
      className="rounded-xl border border-border bg-surface px-5 py-3.5 text-base font-semibold"
    >
      Volver al inicio
    </button>
  );

  const cabecera = (
    <div>
      <h1 className="text-xl font-extrabold tracking-tight">
        Repasar mis falladas
      </h1>
      <p className="mt-1 text-sm text-muted">
        Repetición espaciada: te devolvemos las preguntas que fallaste justo
        cuando toca.
      </p>
    </div>
  );

  // Aún no hay ninguna fallada: nada que programar.
  if (estado.falladas === 0) {
    return (
      <div className="flex flex-col gap-5">
        {cabecera}
        <div className="rounded-2xl border border-border bg-surface p-6 text-center shadow-sm">
          <p className="text-4xl" aria-hidden>
            🎯
          </p>
          <p className="mt-3 text-base font-bold">Todavía no hay falladas</p>
          <p className="mt-1 text-sm text-muted">
            Aquí aparecerán las preguntas que falles, para que las repases antes
            de que se te olviden.
          </p>
          <Link
            href="/examen"
            className="mt-4 inline-flex items-center justify-center rounded-xl bg-brand px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
          >
            Empezar un examen
          </Link>
        </div>
        {explicacion}
        {volverAlInicio}
      </div>
    );
  }

  // Hay falladas pero ninguna vencida: todo al día.
  if (pendientes === 0) {
    return (
      <div className="flex flex-col gap-5">
        {cabecera}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 text-center shadow-sm">
          <p className="text-4xl" aria-hidden>
            ✅
          </p>
          <p className="mt-3 text-base font-bold text-success">Todo al día</p>
          <p className="mt-1 text-sm text-muted">
            {estado.proximoVencimiento !== null
              ? `No te toca repasar nada ahora mismo. Próxima tanda: ${fechaCorta(
                  estado.proximoVencimiento,
                )}.`
              : "No te toca repasar nada ahora mismo."}
          </p>
          <p className="mt-3 text-xs text-muted">
            Llevas {estado.falladas.toLocaleString("es-ES")}{" "}
            {estado.falladas === 1
              ? "pregunta fallada alguna vez"
              : "preguntas falladas alguna vez"}{" "}
            en seguimiento.
          </p>
        </div>
        {explicacion}
        <Link
          href="/temas"
          className="flex items-center justify-center rounded-xl border border-border bg-surface px-5 py-3.5 text-center text-base font-semibold text-foreground shadow-sm transition hover:border-brand active:scale-[0.99]"
        >
          Practicar por temas mientras tanto
        </Link>
        {volverAlInicio}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {cabecera}

      {/* Cola de hoy */}
      <section className="rounded-2xl border border-border bg-surface p-5 text-center shadow-sm">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          Para repasar hoy
        </h2>
        <p className="mt-2 text-4xl font-extrabold tabular-nums text-brand-strong">
          {pendientes.toLocaleString("es-ES")}
        </p>
        <p className="mt-1 text-sm font-semibold">
          {pendientes === 1
            ? "Tienes 1 pregunta para repasar hoy"
            : `Tienes ${pendientes.toLocaleString("es-ES")} preguntas para repasar hoy`}
        </p>
        <p className="mt-1 text-xs text-muted">
          De {estado.falladas.toLocaleString("es-ES")}{" "}
          {estado.falladas === 1 ? "fallada" : "falladas"} en seguimiento.
          Empezamos por las que llevan más tiempo esperando.
        </p>
      </section>

      {/* Tamaño de la tanda */}
      <fieldset className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <legend className="px-1 text-sm font-semibold">
          Preguntas de esta tanda
        </legend>
        <div
          className={`mt-2 grid gap-2 ${
            opcionesTanda.length === 1
              ? "grid-cols-1"
              : opcionesTanda.length === 2
                ? "grid-cols-2"
                : "grid-cols-3"
          }`}
        >
          {opcionesTanda.map((op) => {
            const activo = tandaEfectiva === op.valor;
            return (
              <button
                key={op.etiqueta}
                type="button"
                onClick={() => setTanda(op.valor)}
                aria-pressed={activo}
                className={`flex flex-col items-center rounded-xl border px-3 py-3 transition ${
                  activo
                    ? "border-brand bg-brand text-white shadow-sm"
                    : "border-border bg-surface text-foreground active:scale-[0.99]"
                }`}
              >
                <span className="text-2xl font-extrabold leading-none">
                  {op.etiqueta}
                </span>
                <span
                  className={`mt-1 text-xs ${activo ? "text-white/80" : "text-muted"}`}
                >
                  {op.etiqueta === "Todas"
                    ? pendientes.toLocaleString("es-ES")
                    : "preguntas"}
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {explicacion}

      <button
        type="button"
        onClick={empezar}
        className="rounded-xl bg-brand px-5 py-4 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
      >
        Repasar ahora
      </button>

      {volverAlInicio}
    </div>
  );
}
