"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Banco } from "@/lib/types";
import { cargarBanco } from "@/lib/bank";
import { contarAptasPorTema, preguntasAptas } from "@/lib/exam";
import {
  RACHA_DOMINADA,
  borrarProgreso,
  cargarDatosEstadisticas,
  contarDominadas,
  estadisticasPorTema,
  estadoRepaso,
  prediccion,
  resumenGlobal,
  tramoAcierto,
  type ColorSemaforo,
  type DatosEstadisticas,
  type TramoAcierto,
} from "@/lib/stats";
import { TEMAS, temaPorSlug } from "@/lib/temas";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "listo";

/** Nº de sesiones que se dibujan en el gráfico de evolución. */
const SESIONES_GRAFICO = 15;

/** Estilos del semáforo de la predicción. */
const ESTILO_SEMAFORO: Record<
  ColorSemaforo,
  { card: string; punto: string; texto: string }
> = {
  verde: {
    card: "border-emerald-200 bg-emerald-50",
    punto: "bg-success",
    texto: "text-success",
  },
  ambar: {
    card: "border-amber-200 bg-amber-50",
    punto: "bg-amber-500",
    texto: "text-amber-700",
  },
  rojo: {
    card: "border-rose-200 bg-rose-50",
    punto: "bg-danger",
    texto: "text-danger",
  },
  neutro: {
    card: "border-border bg-surface",
    punto: "bg-slate-400",
    texto: "text-muted",
  },
};

/** Estilos y etiqueta textual por tramo de acierto (nunca solo color). */
const ESTILO_TRAMO: Record<
  TramoAcierto,
  { barra: string; texto: string; etiqueta: string }
> = {
  verde: { barra: "bg-success", texto: "text-success", etiqueta: "Dominado" },
  ambar: {
    barra: "bg-amber-500",
    texto: "text-amber-700",
    etiqueta: "Mejorable",
  },
  rojo: { barra: "bg-danger", texto: "text-danger", etiqueta: "Flojo" },
};

function porcentaje(valor: number, decimales = 1): string {
  return valor.toLocaleString("es-ES", { maximumFractionDigits: decimales });
}

/** Tiempo total en formato "X h Y min" (o solo minutos si no llega a una hora). */
function formatoTiempoLargo(ms: number): string {
  const totalMin = Math.round(ms / 60000);
  const horas = Math.floor(totalMin / 60);
  const minutos = totalMin % 60;
  return horas > 0 ? `${horas} h ${minutos} min` : `${minutos} min`;
}

function fechaCorta(epochMs: number): string {
  return new Date(epochMs).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
  });
}

const DATOS_VACIOS: DatosEstadisticas = { sesiones: [], progresos: [] };

export function EstadisticasClient() {
  const router = useRouter();
  const [fase, setFase] = useState<Fase>("cargando");
  const [banco, setBanco] = useState<Banco | null>(null);
  const [datos, setDatos] = useState<DatosEstadisticas>(DATOS_VACIOS);
  const [progresoDescarga, setProgresoDescarga] = useState(0);
  // Instante de referencia de la cola de repaso; se fija al cargar, no en render.
  const [ahora, setAhora] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");
  const [confirmandoBorrado, setConfirmandoBorrado] = useState(false);
  const [borrando, setBorrando] = useState(false);

  // El estado se actualiza en los callbacks de la promesa, no con `await` en el
  // cuerpo: así el efecto de montaje no aplica estado de forma sincrónica y no
  // encadena renders (react-hooks/set-state-in-effect).
  const cargar = useCallback(
    () =>
      // El banco da los denominadores (preguntas aptas); las stats, el progreso.
      Promise.all([
        cargarBanco({ onProgreso: (n) => setProgresoDescarga(n) }),
        cargarDatosEstadisticas(),
      ])
        .then(([b, d]) => {
          setBanco(b);
          setDatos(d);
          setAhora(Date.now());
          setFase("listo");
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

  const aptasTotales = useMemo(
    () => (banco ? preguntasAptas(banco).length : 0),
    [banco],
  );
  const aptasPorTema = useMemo(
    () => (banco ? contarAptasPorTema(banco) : {}),
    [banco],
  );

  const resumen = useMemo(() => resumenGlobal(datos.sesiones), [datos.sesiones]);
  const pred = useMemo(() => prediccion(datos.sesiones), [datos.sesiones]);
  const porTema = useMemo(
    () => estadisticasPorTema(datos.progresos),
    [datos.progresos],
  );
  const dominadas = useMemo(
    () => contarDominadas(datos.progresos),
    [datos.progresos],
  );
  const paraRepasar = useMemo(
    () => estadoRepaso(datos.progresos, ahora).vencidas.length,
    [datos.progresos, ahora],
  );

  // Temas del catálogo que aún no tienen ninguna respuesta (y sí preguntas
  // disponibles en el banco): se listan al final, atenuados.
  const temasSinDatos = useMemo(() => {
    const conDatos = new Set(porTema.map((t) => t.slug));
    return [...TEMAS]
      .sort((a, b) => a.orden - b.orden)
      .filter((t) => !conDatos.has(t.slug) && (aptasPorTema[t.slug] ?? 0) > 0);
  }, [porTema, aptasPorTema]);

  const ultimasSesiones = useMemo(
    () => datos.sesiones.slice(-SESIONES_GRAFICO),
    [datos.sesiones],
  );

  async function confirmarBorrado() {
    setBorrando(true);
    try {
      await borrarProgreso();
      setDatos(await cargarDatosEstadisticas());
    } catch {
      // Si el borrado falla, se mantiene lo que hubiera en pantalla.
    } finally {
      setBorrando(false);
      setConfirmandoBorrado(false);
      window.scrollTo(0, 0);
    }
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
          <p className="font-semibold">No se pudo cargar tu progreso</p>
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

  const cabecera = (
    <div>
      <h1 className="text-xl font-extrabold tracking-tight">Mi progreso</h1>
      <p className="mt-1 text-sm text-muted">
        Tus estadísticas se guardan solo en este dispositivo.
      </p>
    </div>
  );

  // Estado vacío: aún no se ha terminado ningún test.
  if (datos.sesiones.length === 0) {
    return (
      <div className="flex flex-col gap-5">
        {cabecera}
        <div className="rounded-2xl border border-border bg-surface p-6 text-center shadow-sm">
          <p className="text-4xl" aria-hidden>
            📊
          </p>
          <p className="mt-3 text-base font-bold">Aún no hay datos</p>
          <p className="mt-1 text-sm text-muted">
            Haz tu primer test y aquí verás tu evolución, tus temas flojos y si
            aprobarías hoy.
          </p>
          <Link
            href="/examen"
            className="mt-4 inline-flex items-center justify-center rounded-xl bg-brand px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
          >
            Empezar un examen
          </Link>
        </div>
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

  const semaforo = ESTILO_SEMAFORO[pred.color];

  return (
    <div className="flex flex-col gap-6">
      {cabecera}

      {/* 1. ¿Aprobarías hoy? */}
      <section
        className={`rounded-2xl border p-5 text-center shadow-sm ${semaforo.card}`}
      >
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          ¿Aprobarías hoy?
        </h2>
        <p
          className={`mt-2 flex items-center justify-center gap-2 text-base font-bold ${semaforo.texto}`}
        >
          <span
            aria-hidden
            className={`h-3 w-3 flex-none rounded-full ${semaforo.punto}`}
          />
          {pred.mensaje}
        </p>
        {pred.estado === "listo" ? (
          <>
            <p className="mt-3 text-4xl font-extrabold tabular-nums">
              {porcentaje(pred.nota)}
              <span className="text-2xl text-muted"> / 100 pts</span>
            </p>
            <p className="mt-1 text-xs text-muted">
              Estimación según tus últimas{" "}
              {pred.sesiones.toLocaleString("es-ES")}{" "}
              {pred.sesiones === 1 ? "sesión" : "sesiones"} (
              {pred.respuestas.toLocaleString("es-ES")} respuestas), con el
              baremo oficial.
            </p>
          </>
        ) : (
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Llevas {pred.respuestas.toLocaleString("es-ES")} de{" "}
            {(pred.respuestas + pred.faltan).toLocaleString("es-ES")} respuestas
            recientes. Sigue practicando y activaremos la estimación de nota.
          </p>
        )}
      </section>

      {/* 2. Resumen */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Resumen
        </h2>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <Stat
            etiqueta="Tests hechos"
            valor={resumen.tests.toLocaleString("es-ES")}
          />
          <Stat
            etiqueta="Preguntas respondidas"
            valor={resumen.respuestas.toLocaleString("es-ES")}
          />
          <Stat
            etiqueta="Acierto"
            valor={`${porcentaje(resumen.porcentajeAcierto)} %`}
            color={ESTILO_TRAMO[tramoAcierto(resumen.porcentajeAcierto)].texto}
          />
          <Stat
            etiqueta="Tiempo total"
            valor={formatoTiempoLargo(resumen.tiempoMs)}
          />
        </div>
      </section>

      {/* 3. Acierto por tema */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Acierto por tema
        </h2>
        <p className="mt-1 text-xs text-muted">
          De peor a mejor. Toca un tema para ir a la práctica por temas.
        </p>
        <div className="mt-2 flex flex-col gap-2">
          {porTema.map((t) => {
            const tramo = ESTILO_TRAMO[tramoAcierto(t.porcentaje)];
            const label = temaPorSlug(t.slug)?.label ?? t.slug;
            const aptas = aptasPorTema[t.slug] ?? 0;
            return (
              <Link
                key={t.slug}
                href="/temas"
                className="rounded-2xl border border-border bg-surface p-4 shadow-sm transition active:scale-[0.995]"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-sm font-semibold leading-snug">
                    {label}
                  </span>
                  <span
                    className={`flex-none text-sm font-extrabold tabular-nums ${tramo.texto}`}
                  >
                    {porcentaje(t.porcentaje)} %
                  </span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className={`h-full rounded-full ${tramo.barra}`}
                    style={{
                      width: `${Math.max(0, Math.min(100, t.porcentaje))}%`,
                    }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-muted">
                  <span className={`font-semibold ${tramo.texto}`}>
                    {tramo.etiqueta}
                  </span>{" "}
                  · {t.respuestas.toLocaleString("es-ES")} respuestas ·{" "}
                  {aptas.toLocaleString("es-ES")} preguntas en el banco
                </p>
              </Link>
            );
          })}

          {temasSinDatos.map((tema) => (
            <Link
              key={tema.slug}
              href="/temas"
              className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-surface p-4 opacity-60 shadow-sm transition active:scale-[0.995]"
            >
              <span className="text-sm font-semibold leading-snug">
                {tema.label}
              </span>
              <span className="flex-none text-xs font-medium text-muted">
                Sin datos aún
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* 4. Evolución */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Evolución
        </h2>
        <p className="mt-1 text-xs text-muted">
          Últimos {ultimasSesiones.length.toLocaleString("es-ES")} tests. La
          línea marca los 50 puntos del aprobado.
        </p>
        <div className="mt-2 rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <div className="relative h-28">
            <div
              aria-hidden
              className="absolute inset-x-0 bottom-1/2 border-t border-dashed border-slate-400"
            />
            <div className="flex h-full items-end gap-1">
              {ultimasSesiones.map((s, i) => {
                const nota = Math.max(0, Math.min(100, s.puntuacionSobre100));
                return (
                  <div
                    key={`${s.fecha}-${i}`}
                    role="img"
                    aria-label={`${fechaCorta(s.fecha)}: ${porcentaje(
                      s.puntuacionSobre100,
                    )} puntos, ${s.aprobado ? "aprobado" : "suspenso"}`}
                    className={`flex-1 rounded-t ${
                      s.aprobado ? "bg-success" : "bg-danger"
                    }`}
                    style={{ height: `${Math.max(nota, 2)}%` }}
                  />
                );
              })}
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-muted">
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="h-2 w-2 rounded-full bg-success" />
              Aprobado
            </span>
            <span className="flex items-center gap-1.5">
              <span aria-hidden className="h-2 w-2 rounded-full bg-danger" />
              Suspenso
            </span>
            <span className="tabular-nums">
              Último: {porcentaje(
                ultimasSesiones[ultimasSesiones.length - 1].puntuacionSobre100,
              )}{" "}
              pts
            </span>
          </div>
        </div>
      </section>

      {/* 5. Preguntas dominadas */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Preguntas dominadas
        </h2>
        <div className="mt-2 rounded-2xl border border-border bg-surface p-4 shadow-sm">
          <p className="text-sm font-semibold tabular-nums">
            {dominadas.toLocaleString("es-ES")} de{" "}
            {aptasTotales.toLocaleString("es-ES")} preguntas dominadas
          </p>
          <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-brand"
              style={{
                width: `${
                  aptasTotales > 0
                    ? Math.min(100, (dominadas / aptasTotales) * 100)
                    : 0
                }%`,
              }}
            />
          </div>
          <p className="mt-2 text-xs leading-relaxed text-muted">
            Una pregunta cuenta como dominada cuando la aciertas{" "}
            {RACHA_DOMINADA} veces seguidas. Fallarla o dejarla en blanco
            reinicia la racha.
          </p>
        </div>
        {paraRepasar > 0 && (
          <Link
            href="/repaso"
            className="mt-2 flex items-center justify-between gap-3 rounded-2xl border border-border bg-surface p-4 text-sm font-semibold shadow-sm transition active:scale-[0.995]"
          >
            <span>
              Tienes {paraRepasar.toLocaleString("es-ES")} para repasar hoy
            </span>
            <span aria-hidden className="flex-none text-brand-strong">
              →
            </span>
          </Link>
        )}
      </section>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => router.push("/")}
          className="rounded-xl border border-border bg-surface px-5 py-3.5 text-base font-semibold"
        >
          Volver al inicio
        </button>

        {/* 6. Borrar progreso */}
        <button
          type="button"
          onClick={() => setConfirmandoBorrado(true)}
          className="self-center px-3 py-2 text-xs font-medium text-muted underline underline-offset-2"
        >
          Borrar mi progreso
        </button>
      </div>

      {confirmandoBorrado && (
        <Overlay
          onClose={() => setConfirmandoBorrado(false)}
          titulo="Borrar mi progreso"
        >
          <p className="text-sm leading-relaxed">
            Se borrarán todas tus estadísticas de este dispositivo: histórico de
            tests, acierto por tema y preguntas dominadas.{" "}
            <strong>Esta acción no se puede deshacer.</strong> El banco de
            preguntas descargado se conserva.
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setConfirmandoBorrado(false)}
              className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-semibold"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => void confirmarBorrado()}
              disabled={borrando}
              className="flex-1 rounded-xl bg-danger px-4 py-3 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
            >
              {borrando ? "Borrando…" : "Borrar"}
            </button>
          </div>
        </Overlay>
      )}
    </div>
  );
}

function Stat({
  etiqueta,
  valor,
  color = "",
}: {
  etiqueta: string;
  valor: string;
  color?: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-3 text-center shadow-sm">
      <p className={`text-2xl font-extrabold tabular-nums ${color}`}>{valor}</p>
      <p className="mt-0.5 text-xs text-muted">{etiqueta}</p>
    </div>
  );
}

function Overlay({
  children,
  onClose,
  titulo,
}: {
  children: React.ReactNode;
  onClose: () => void;
  titulo: string;
}) {
  return (
    <div
      className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 p-4 sm:items-center"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-bold">{titulo}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="flex h-8 w-8 items-center justify-center rounded-full text-muted hover:bg-slate-100"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
