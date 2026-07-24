"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Banco, ModoExamen, PreguntaExamen } from "@/lib/types";
import { cargarBanco } from "@/lib/bank";
import {
  construirExamen,
  contarAptasPorTema,
  corregirExamen,
  type Correccion,
} from "@/lib/exam";
import { temasPorSeccion, temaPorSlug, type Tema } from "@/lib/temas";
import { ExamRunner } from "@/components/exam/ExamRunner";
import { ExamResults } from "@/components/exam/ExamResults";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "temas" | "config" | "examen" | "resultados";

const OPCIONES_MODO: {
  valor: ModoExamen;
  icono: string;
  titulo: string;
  sub: string;
}[] = [
  {
    valor: "practica",
    icono: "🎓",
    titulo: "Práctica",
    sub: "Corrección inmediata",
  },
  {
    valor: "real",
    icono: "📝",
    titulo: "Examen",
    sub: "Corrección al final",
  },
];

export function TemasClient() {
  const router = useRouter();
  const [fase, setFase] = useState<Fase>("cargando");
  const [banco, setBanco] = useState<Banco | null>(null);
  const [progreso, setProgreso] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const [temaSel, setTemaSel] = useState<Tema | null>(null);
  const [numPreguntas, setNumPreguntas] = useState(20);
  const [modo, setModo] = useState<ModoExamen>("practica");
  const [preguntas, setPreguntas] = useState<PreguntaExamen[]>([]);
  const [correccion, setCorreccion] = useState<Correccion | null>(null);
  const [tiempoMs, setTiempoMs] = useState(0);

  const cargar = useCallback(async () => {
    try {
      const b = await cargarBanco({ onProgreso: (n) => setProgreso(n) });
      setBanco(b);
      setFase("temas");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Error desconocido.");
      setFase("error");
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Conteo de preguntas aptas por tema (slug -> nº). Se recalcula solo al
  // cambiar el banco.
  const aptasPorTema = useMemo(
    () => (banco ? contarAptasPorTema(banco) : {}),
    [banco],
  );

  const secciones = useMemo(() => temasPorSeccion(), []);
  const aptasTemaSel = temaSel ? (aptasPorTema[temaSel.slug] ?? 0) : 0;

  function elegirTema(tema: Tema) {
    setTemaSel(tema);
    setModo("practica");
    setNumPreguntas(20);
    setFase("config");
    window.scrollTo(0, 0);
  }

  function empezar() {
    if (!banco || !temaSel) return;
    const ex = construirExamen(banco, {
      numPreguntas,
      altaProbabilidad: false,
      modo,
      tema: temaSel.slug,
    });
    if (ex.length === 0) return;
    setPreguntas(ex);
    setFase("examen");
    window.scrollTo(0, 0);
  }

  function finalizar(respuestas: (number | null)[], elapsed: number) {
    setCorreccion(corregirExamen(preguntas, respuestas));
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

  function volverATemas() {
    setCorreccion(null);
    setPreguntas([]);
    setTemaSel(null);
    setFase("temas");
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
            void cargar();
          }}
          className="rounded-xl bg-brand px-5 py-3 text-sm font-semibold text-white shadow-sm"
        >
          Reintentar
        </button>
      </div>
    );
  }

  // Selección de tema, agrupado por sección.
  if (fase === "temas") {
    return (
      <div className="flex flex-col gap-5">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">
            Práctica por temas
          </h1>
          <p className="mt-1 text-sm text-muted">
            Elige un tema para practicar solo esas preguntas. Por defecto con
            corrección inmediata.
          </p>
        </div>

        {secciones.map((grupo) => (
          <section key={grupo.seccion} className="flex flex-col gap-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
              {grupo.seccion}
            </h2>
            <div className="flex flex-col gap-2">
              {grupo.temas.map((tema) => {
                const n = aptasPorTema[tema.slug] ?? 0;
                const disponible = n > 0;
                return (
                  <button
                    key={tema.slug}
                    type="button"
                    disabled={!disponible}
                    onClick={() => elegirTema(tema)}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-surface p-4 text-left shadow-sm transition active:scale-[0.995] disabled:opacity-50 disabled:active:scale-100"
                  >
                    <span className="text-sm font-semibold leading-snug">
                      {tema.label}
                    </span>
                    <span className="flex-none rounded-full bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand-strong tabular-nums">
                      {n.toLocaleString("es-ES")}
                      <span className="font-medium text-muted"> preg.</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
        ))}

        <button
          type="button"
          onClick={() => router.push("/")}
          className="rounded-xl border border-border bg-surface px-5 py-3.5 text-base font-semibold"
        >
          Volver al inicio
        </button>
      </div>
    );
  }

  // Configuración de la sesión para el tema elegido.
  if (fase === "config" && temaSel) {
    const seccion = temaPorSlug(temaSel.slug)?.seccion ?? temaSel.seccion;
    const opcionesNum = [
      { valor: 20, etiqueta: "20", sub: "Rápido" },
      { valor: aptasTemaSel, etiqueta: "Todas", sub: `${aptasTemaSel}` },
    ];
    return (
      <div className="flex flex-col gap-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            {seccion}
          </p>
          <h1 className="mt-1 text-xl font-extrabold tracking-tight">
            {temaSel.label}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {aptasTemaSel.toLocaleString("es-ES")} preguntas disponibles de este
            tema.
          </p>
        </div>

        {/* Modo */}
        <fieldset className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <legend className="px-1 text-sm font-semibold">Modo</legend>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {OPCIONES_MODO.map((op) => {
              const activo = modo === op.valor;
              return (
                <button
                  key={op.valor}
                  type="button"
                  onClick={() => setModo(op.valor)}
                  aria-pressed={activo}
                  className={`flex flex-col items-center gap-1 rounded-xl border px-3 py-3 text-center transition ${
                    activo
                      ? "border-brand bg-brand text-white shadow-sm"
                      : "border-border bg-surface text-foreground active:scale-[0.99]"
                  }`}
                >
                  <span className="text-2xl leading-none" aria-hidden>
                    {op.icono}
                  </span>
                  <span className="text-sm font-bold leading-tight">
                    {op.titulo}
                  </span>
                  <span
                    className={`text-xs leading-tight ${activo ? "text-white/80" : "text-muted"}`}
                  >
                    {op.sub}
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted">
            {modo === "practica"
              ? "Aprende: cada respuesta se corrige al instante para memorizarla."
              : "Ponte a prueba: sin pistas hasta el final del test del tema."}
          </p>
        </fieldset>

        {/* Nº de preguntas */}
        <fieldset className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <legend className="px-1 text-sm font-semibold">Nº de preguntas</legend>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {opcionesNum.map((op) => {
              const activo = numPreguntas === op.valor;
              return (
                <button
                  key={op.etiqueta}
                  type="button"
                  onClick={() => setNumPreguntas(op.valor)}
                  aria-pressed={activo}
                  className={`flex flex-col items-center rounded-xl border px-4 py-3 transition ${
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
                    {op.sub}
                  </span>
                </button>
              );
            })}
          </div>
        </fieldset>

        {/* Baremo oficial */}
        <div className="rounded-2xl border border-border bg-surface p-4 text-xs leading-relaxed text-muted shadow-sm">
          <span className="font-semibold text-foreground">
            Baremo oficial del CAP:
          </span>{" "}
          acierto +1, fallo −0,5, en blanco 0. Se aprueba con ≥ 50 puntos sobre
          100 (escalado al nº de preguntas de este test).
        </div>

        <button
          type="button"
          onClick={empezar}
          disabled={aptasTemaSel === 0}
          className="rounded-xl bg-brand px-5 py-4 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99] disabled:opacity-50"
        >
          Empezar práctica
        </button>

        <button
          type="button"
          onClick={volverATemas}
          className="rounded-xl border border-border bg-surface px-5 py-3.5 text-base font-semibold"
        >
          Elegir otro tema
        </button>
      </div>
    );
  }

  if (fase === "examen") {
    return (
      <ExamRunner
        preguntas={preguntas}
        modo={modo}
        onFinish={finalizar}
        onCancel={volverATemas}
      />
    );
  }

  if (fase === "resultados" && correccion) {
    return (
      <ExamResults
        correccion={correccion}
        tiempoMs={tiempoMs}
        onRepetir={repetir}
        onInicio={() => router.push("/")}
      />
    );
  }

  return null;
}
