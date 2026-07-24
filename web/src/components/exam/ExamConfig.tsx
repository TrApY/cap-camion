"use client";

import { useMemo, useState } from "react";
import type { Banco, ConfigExamen } from "@/lib/types";
import { preguntasAptas } from "@/lib/exam";

const OPCIONES_NUM = [
  { valor: 30, etiqueta: "30", sub: "Rápido" },
  { valor: 100, etiqueta: "100", sub: "Completo" },
];

const OPCIONES_UMBRAL = [0.5, 0.55, 0.6, 0.65];

export function ExamConfig({
  banco,
  onStart,
  onRefresh,
  refreshing,
}: {
  banco: Banco;
  onStart: (config: ConfigExamen) => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  const numAptas = useMemo(() => preguntasAptas(banco).length, [banco]);

  const [numPreguntas, setNumPreguntas] = useState(30);
  const [altaProbabilidad, setAltaProbabilidad] = useState(false);
  const [umbral, setUmbral] = useState(0.5);

  const descargado = new Date(banco.descargadoEn).toLocaleDateString("es-ES", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">
          Configura tu examen
        </h1>
        <p className="mt-1 text-sm text-muted">
          {numAptas.toLocaleString("es-ES")} preguntas disponibles para examen.
        </p>
      </div>

      {/* Número de preguntas */}
      <fieldset className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <legend className="px-1 text-sm font-semibold">Nº de preguntas</legend>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {OPCIONES_NUM.map((op) => {
            const activo = numPreguntas === op.valor;
            return (
              <button
                key={op.valor}
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
        {numPreguntas > numAptas && (
          <p className="mt-2 text-xs text-muted">
            Solo hay {numAptas.toLocaleString("es-ES")} preguntas aptas; el
            examen tendrá esas.
          </p>
        )}
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
      </div>

      {/* Umbral de aprobado */}
      <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <label
          htmlFor="umbral"
          className="block text-sm font-semibold"
        >
          Umbral de aprobado
        </label>
        <div className="mt-2 flex items-center gap-3">
          <select
            id="umbral"
            value={umbral}
            onChange={(e) => setUmbral(Number(e.target.value))}
            className="flex-1 rounded-xl border border-border bg-surface px-3 py-2.5 text-base font-semibold"
          >
            {OPCIONES_UMBRAL.map((u) => (
              <option key={u} value={u}>
                {Math.round(u * 100)}%
              </option>
            ))}
          </select>
        </div>
        <p className="mt-2 text-xs text-muted">
          Orientativo y ajustable. No es la nota oficial exacta del examen del
          CAP.
        </p>
      </div>

      <button
        type="button"
        onClick={() =>
          onStart({ numPreguntas, altaProbabilidad, umbral })
        }
        className="rounded-xl bg-brand px-5 py-4 text-base font-semibold text-white shadow-sm transition hover:bg-brand-strong active:scale-[0.99]"
      >
        Empezar examen
      </button>

      <div className="flex items-center justify-between text-xs text-muted">
        <span>
          Banco: {banco.preguntas.length.toLocaleString("es-ES")} · {descargado}
        </span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="font-medium text-brand underline underline-offset-2 disabled:opacity-50"
        >
          {refreshing ? "Actualizando…" : "Actualizar banco"}
        </button>
      </div>
    </div>
  );
}
