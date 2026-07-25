"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { obtenerNick } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { TruckLogo } from "@/components/TruckLogo";

type Fase = "cargando" | "error" | "listo";

/** Ventana de días que se mide en el ranking (parámetro de la RPC). */
const DIAS = 14;

/** Tests mínimos en la ventana para aparecer (parámetro de la RPC). */
const MIN_SESIONES = 3;

/** Distintivo de los tres primeros puestos; el resto va con su número. */
const MEDALLAS = ["🥇", "🥈", "🥉"];

/**
 * Fila tal cual llega de `ranking_activos`. `sesiones` es un bigint y
 * `nota_media` un numeric: PostgREST puede serializar ambos como cadena, así que
 * aquí se aceptan las dos formas y se normalizan en `mapFila`.
 */
interface FilaRanking {
  nick: string | null;
  sesiones: number | string | null;
  nota_media: number | string | null;
}

/** Puesto ya normalizado para pintar. */
interface Puesto {
  nick: string;
  sesiones: number;
  notaMedia: number;
}

/** Número seguro a partir de lo que traiga la API (string, number, null…). */
function aNumero(valor: number | string | null | undefined): number {
  const n = Number(valor);
  return Number.isFinite(n) ? n : 0;
}

function mapFila(fila: FilaRanking): Puesto {
  return {
    nick: fila.nick ?? "",
    sesiones: aNumero(fila.sesiones),
    notaMedia: aNumero(fila.nota_media),
  };
}

/** Nota con un decimal en formato español (8,3). */
function formatoNota(valor: number): string {
  return valor.toLocaleString("es-ES", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

/**
 * Descarga el ranking. La RPC es `security definer` y ejecutable como `anon`:
 * funciona sin sesión y ya devuelve las filas ordenadas y limitadas.
 */
async function cargarRanking(): Promise<Puesto[]> {
  const { data, error } = await supabase.rpc("ranking_activos", {
    dias: DIAS,
    min_sesiones: MIN_SESIONES,
  });

  if (error) throw new Error(error.message);
  const filas = (data ?? []) as FilaRanking[];
  return filas.map(mapFila).filter((p) => p.nick.length > 0);
}

export function RankingClient() {
  const [fase, setFase] = useState<Fase>("cargando");
  const [puestos, setPuestos] = useState<Puesto[]>([]);
  // Nick propio: null si no hay sesión o si el usuario aún no ha elegido uno.
  const [nick, setNick] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  // El estado se actualiza en los callbacks de la promesa, no con `await` en el
  // cuerpo: así el efecto de montaje no aplica estado de forma sincrónica y no
  // encadena renders (react-hooks/set-state-in-effect).
  const cargar = useCallback(
    () =>
      // El nick propio es un EXTRA (solo sirve para resaltar tu fila): si no se
      // puede resolver, el ranking se ve igual.
      Promise.all([cargarRanking(), obtenerNick().catch(() => null)])
        .then(([filas, nickActual]) => {
          setPuestos(filas);
          setNick(nickActual);
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

  if (fase === "cargando") {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <TruckLogo className="h-16 w-16 animate-pulse rounded-2xl" />
        <div>
          <p className="font-semibold">Cargando el ranking…</p>
          <p className="mt-1 text-sm text-muted">
            Nota media de los últimos {DIAS} días.
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
          <p className="font-semibold">No se pudo cargar el ranking</p>
          <p className="mt-1 text-sm leading-relaxed text-muted">
            El ranking se calcula en la nube, así que necesita conexión: no
            funciona sin internet. Comprueba tu red y vuelve a intentarlo.
          </p>
          <p className="mt-2 text-xs text-muted">{errorMsg}</p>
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
      <h1 className="text-xl font-extrabold tracking-tight">Ranking</h1>
      <p className="mt-1 text-sm text-muted">
        Nota media de los últimos {DIAS} días · mínimo {MIN_SESIONES} tests
      </p>
    </div>
  );

  const avisoSinNick =
    nick === null ? (
      <p className="text-center text-xs leading-relaxed text-muted">
        <Link href="/estadisticas" className="underline underline-offset-2">
          Elige un nick en Mi progreso
        </Link>{" "}
        para salir aquí.
      </p>
    ) : null;

  const volver = (
    <Link
      href="/"
      className="flex items-center justify-center rounded-xl border border-border bg-surface px-5 py-3.5 text-center text-base font-semibold text-foreground"
    >
      Volver al inicio
    </Link>
  );

  // Estado vacío: nadie cumple todavía el mínimo de tests en la ventana.
  if (puestos.length === 0) {
    return (
      <div className="flex flex-col gap-5">
        {cabecera}
        <div className="rounded-2xl border border-border bg-surface p-6 text-center shadow-sm">
          <p className="text-4xl" aria-hidden>
            🏆
          </p>
          <p className="mt-3 text-base font-bold">Aún no hay nadie</p>
          <p className="mt-1 text-sm text-muted">
            Aún no hay nadie en el ranking: haz tests y estrena el tuyo.
          </p>
          <Link
            href="/examen"
            className="mt-4 inline-flex items-center justify-center rounded-xl bg-brand px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
          >
            Empezar un examen
          </Link>
        </div>
        {avisoSinNick}
        {volver}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {cabecera}

      <ol className="flex flex-col gap-2">
        {puestos.map((p, i) => {
          const posicion = i + 1;
          const medalla = MEDALLAS[i];
          const propio = nick !== null && p.nick === nick;
          return (
            <li
              key={p.nick}
              className={`flex items-center gap-3 rounded-2xl border p-4 shadow-sm ${
                propio ? "border-brand bg-brand/10" : "border-border bg-surface"
              }`}
            >
              <span className="flex w-8 flex-none justify-center text-lg font-extrabold tabular-nums text-muted">
                <span className="sr-only">{`Puesto ${posicion}: `}</span>
                <span aria-hidden>{medalla ?? posicion}</span>
              </span>

              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold leading-snug">
                  {p.nick}
                  {propio && (
                    <span className="font-bold text-brand-strong"> (tú)</span>
                  )}
                </span>
                <span className="mt-0.5 block text-xs text-muted tabular-nums">
                  {p.sesiones.toLocaleString("es-ES")}{" "}
                  {p.sesiones === 1 ? "test" : "tests"}
                </span>
              </span>

              <span className="flex-none text-right">
                <span className="block text-lg font-extrabold tabular-nums">
                  {formatoNota(p.notaMedia)}
                </span>
                <span className="block text-xs text-muted">pts</span>
              </span>
            </li>
          );
        })}
      </ol>

      <p className="text-center text-xs leading-relaxed text-muted">
        Nota media sobre 100 con el baremo oficial, contando solo los tests de
        los últimos {DIAS} días. Se ordena por nota, no por número de tests.
      </p>

      {avisoSinNick}
      {volver}
    </div>
  );
}
