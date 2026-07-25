"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { Banco, ModoExamen, PreguntaExamen } from "@/lib/types";
import { cargarBanco } from "@/lib/bank";
import {
  FRECUENCIA_MINIMA_ALTA_PROB,
  construirExamen,
  contarAltaProbPorTema,
  contarAptasPorTema,
  corregirExamen,
  type Correccion,
} from "@/lib/exam";
import {
  cargarProgresos,
  estadisticasPorTema,
  registrarSesion,
  tramoAcierto,
  type ProgresoPregunta,
  type TramoAcierto,
} from "@/lib/stats";
import { temasPorSeccion, temaPorSlug, type Tema } from "@/lib/temas";
import { ExamRunner } from "@/components/exam/ExamRunner";
import { ExamResults } from "@/components/exam/ExamResults";
import { MarkdownSencillo } from "@/components/MarkdownSencillo";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "temas" | "config" | "examen" | "resultados";

/** Respuestas mínimas en un tema para mostrar su badge de acierto. */
const MIN_RESPUESTAS_BADGE = 5;

/** Clases del badge de acierto según el tramo (color + texto, nunca solo color). */
const CLASES_TRAMO: Record<TramoAcierto, string> = {
  verde: "bg-emerald-100 text-success",
  ambar: "bg-amber-100 text-amber-700",
  rojo: "bg-rose-100 text-danger",
};

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

  const [progresoPreguntas, setProgresoPreguntas] = useState<
    ProgresoPregunta[]
  >([]);

  const [temaSel, setTemaSel] = useState<Tema | null>(null);
  // Card de teoría del tema: cerrada por defecto, se recoge al cambiar de tema.
  const [teoriaAbierta, setTeoriaAbierta] = useState(false);
  const [numPreguntas, setNumPreguntas] = useState(20);
  const [modo, setModo] = useState<ModoExamen>("practica");
  const [altaProbabilidad, setAltaProbabilidad] = useState(false);
  const [preguntas, setPreguntas] = useState<PreguntaExamen[]>([]);
  const [correccion, setCorreccion] = useState<Correccion | null>(null);
  const [tiempoMs, setTiempoMs] = useState(0);

  // El estado se actualiza en los callbacks de la promesa, no con `await` en el
  // cuerpo: así el efecto de montaje no aplica estado de forma sincrónica y no
  // encadena renders (react-hooks/set-state-in-effect).
  const cargar = useCallback(
    () =>
      // El progreso del usuario es opcional: si IndexedDB falla la pantalla
      // funciona igual, solo que sin badges de acierto.
      Promise.all([
        cargarBanco({ onProgreso: (n) => setProgreso(n) }),
        cargarProgresos().catch(() => [] as ProgresoPregunta[]),
      ])
        .then(([b, progresos]) => {
          setBanco(b);
          setProgresoPreguntas(progresos);
          setFase("temas");
        })
        .catch((e: unknown) => {
          setErrorMsg(e instanceof Error ? e.message : "Error desconocido.");
          setFase("error");
        }),
    [],
  );

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Conteo de preguntas aptas por tema (slug -> nº). Se recalcula solo al
  // cambiar el banco.
  const aptasPorTema = useMemo(
    () => (banco ? contarAptasPorTema(banco) : {}),
    [banco],
  );

  // Acierto del usuario por tema (slug -> estadística), para los badges.
  const aciertoPorTema = useMemo(
    () =>
      new Map(estadisticasPorTema(progresoPreguntas).map((t) => [t.slug, t])),
    [progresoPreguntas],
  );

  // Pool de alta probabilidad por tema (slug -> nº de aptas que han caído en
  // varios exámenes). Igual que `aptasPorTema`: solo depende del banco.
  const altaProbPorTema = useMemo(
    () => (banco ? contarAltaProbPorTema(banco) : {}),
    [banco],
  );

  const secciones = useMemo(() => temasPorSeccion(), []);
  const aptasTemaSel = temaSel ? (aptasPorTema[temaSel.slug] ?? 0) : 0;
  const altaProbTemaSel = temaSel ? (altaProbPorTema[temaSel.slug] ?? 0) : 0;

  function elegirTema(tema: Tema) {
    setTemaSel(tema);
    setModo("practica");
    setNumPreguntas(20);
    setAltaProbabilidad(false);
    setTeoriaAbierta(false);
    setFase("config");
    window.scrollTo(0, 0);
  }

  function empezar() {
    if (!banco || !temaSel) return;
    const ex = construirExamen(banco, {
      numPreguntas,
      altaProbabilidad,
      modo,
      tema: temaSel.slug,
    });
    if (ex.length === 0) return;
    setPreguntas(ex);
    setFase("examen");
    window.scrollTo(0, 0);
  }

  function finalizar(respuestas: (number | null)[], elapsed: number) {
    const corr = corregirExamen(preguntas, respuestas);
    setCorreccion(corr);
    setTiempoMs(elapsed);
    setFase("resultados");
    window.scrollTo(0, 0);

    if (!temaSel) return;
    // Estadísticas: fire-and-forget. Si IndexedDB falla, los resultados se
    // muestran igualmente.
    void registrarSesion({
      tipo: "tema",
      tema: temaSel.slug,
      modo,
      correccion: corr,
      tiempoMs: elapsed,
    }).catch((e) => {
      console.warn("No se pudo guardar la sesión en estadísticas:", e);
    });
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
                const acierto = aciertoPorTema.get(tema.slug);
                const mostrarAcierto =
                  acierto != null &&
                  acierto.respuestas >= MIN_RESPUESTAS_BADGE;
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
                    <span className="flex flex-none items-center gap-1.5">
                      {mostrarAcierto && (
                        <span
                          className={`rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums ${
                            CLASES_TRAMO[tramoAcierto(acierto.porcentaje)]
                          }`}
                        >
                          {acierto.porcentaje.toLocaleString("es-ES", {
                            maximumFractionDigits: 0,
                          })}
                          {" % acierto"}
                        </span>
                      )}
                      <span className="rounded-full bg-brand/10 px-2.5 py-1 text-xs font-semibold text-brand-strong tabular-nums">
                        {n.toLocaleString("es-ES")}
                        <span className="font-medium text-muted"> preg.</span>
                      </span>
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
    // La teoría es material de apoyo: si el banco no la trae, no se muestra.
    const teoria = banco?.teoria?.[temaSel.slug];
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

        {/* Teoría del tema (colapsable, cerrada por defecto) */}
        {teoria && (
          <section className="overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
            <button
              type="button"
              onClick={() => setTeoriaAbierta((v) => !v)}
              aria-expanded={teoriaAbierta}
              className="flex w-full items-center justify-between gap-3 p-4 text-left"
            >
              <span className="text-sm font-semibold">
                <span aria-hidden>📖 </span>
                Teoría del tema
              </span>
              <span className="flex-none text-xs font-semibold text-brand">
                {teoriaAbierta ? "Ocultar" : "Ver"}
              </span>
            </button>
            {teoriaAbierta && (
              <div className="border-t border-border p-4">
                <MarkdownSencillo md={teoria.resumen} />
                <p className="mt-3 text-xs leading-relaxed text-muted">
                  Resumen elaborado a partir del banco oficial de preguntas del
                  Ministerio de Transportes y Movilidad Sostenible y del Anexo I
                  del RD 284/2021 (BOE).
                </p>
              </div>
            )}
          </section>
        )}

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

        {/* Modo alta probabilidad */}
        <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <button
            type="button"
            role="switch"
            aria-checked={altaProbabilidad}
            onClick={() => setAltaProbabilidad((v) => !v)}
            className="flex w-full items-center justify-between gap-3 text-left"
          >
            <span>
              <span className="block text-sm font-semibold">
                Modo alta probabilidad
              </span>
              <span className="mt-0.5 block text-xs text-muted">
                Prioriza las preguntas que más se repiten en los exámenes.
              </span>
            </span>
            <span
              aria-hidden
              className={`relative h-7 w-12 flex-none rounded-full transition ${
                altaProbabilidad ? "bg-brand" : "bg-slate-300"
              }`}
            >
              <span
                className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all ${
                  altaProbabilidad ? "left-[22px]" : "left-0.5"
                }`}
              />
            </span>
          </button>
          {altaProbabilidad && (
            <p className="mt-2 text-xs text-muted">
              {altaProbTemaSel.toLocaleString("es-ES")}{" "}
              {altaProbTemaSel === 1
                ? "pregunta de este tema ha"
                : "preguntas de este tema han"}{" "}
              caído en {FRECUENCIA_MINIMA_ALTA_PROB} o más exámenes; si hacen
              falta más, se completa con el resto.
            </p>
          )}
        </div>

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
