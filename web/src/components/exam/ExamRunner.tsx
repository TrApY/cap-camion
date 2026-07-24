"use client";

import { useEffect, useRef, useState } from "react";
import type { PreguntaExamen } from "@/lib/types";

const LETRAS = ["A", "B", "C", "D", "E", "F"];

function formatoTiempo(segundos: number): string {
  const m = Math.floor(segundos / 60);
  const s = segundos % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function ExamRunner({
  preguntas,
  onFinish,
  onCancel,
}: {
  preguntas: PreguntaExamen[];
  onFinish: (respuestas: (number | null)[], elapsedMs: number) => void;
  onCancel: () => void;
}) {
  const total = preguntas.length;
  const inicioRef = useRef<number>(Date.now());
  const [indice, setIndice] = useState(0);
  const [respuestas, setRespuestas] = useState<(number | null)[]>(
    () => Array(total).fill(null),
  );
  const [segundos, setSegundos] = useState(0);
  const [navegador, setNavegador] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  useEffect(() => {
    const id = setInterval(() => {
      setSegundos(Math.floor((Date.now() - inicioRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const pregunta = preguntas[indice];
  const contestadas = respuestas.filter((r) => r !== null).length;
  const enBlanco = total - contestadas;
  const esUltima = indice === total - 1;

  function elegir(opIndex: number) {
    setRespuestas((prev) => {
      const copia = prev.slice();
      copia[indice] = copia[indice] === opIndex ? null : opIndex;
      return copia;
    });
  }

  function finalizar() {
    onFinish(respuestas, Date.now() - inicioRef.current);
  }

  function intentarFinalizar() {
    if (enBlanco > 0) setConfirmando(true);
    else finalizar();
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Cabecera: progreso y cronómetro */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onCancel}
          className="text-sm font-medium text-muted underline underline-offset-2"
        >
          Salir
        </button>
        <div
          className="flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 text-sm font-semibold tabular-nums shadow-sm ring-1 ring-border"
          aria-label="Tiempo transcurrido"
        >
          <span aria-hidden>⏱</span>
          {formatoTiempo(segundos)}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between text-sm">
          <span className="font-semibold">
            Pregunta {indice + 1}
            <span className="text-muted"> / {total}</span>
          </span>
          <button
            type="button"
            onClick={() => setNavegador(true)}
            className="font-medium text-brand"
          >
            Índice ({contestadas}/{total})
          </button>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand transition-all"
            style={{ width: `${((indice + 1) / total) * 100}%` }}
          />
        </div>
      </div>

      {/* Enunciado */}
      <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <p className="text-base font-medium leading-relaxed">
          {pregunta.enunciado}
        </p>
      </div>

      {/* Opciones */}
      <div className="flex flex-col gap-2.5" role="radiogroup" aria-label="Opciones">
        {pregunta.opciones.map((op, i) => {
          const elegida = respuestas[indice] === i;
          return (
            <button
              key={i}
              type="button"
              role="radio"
              aria-checked={elegida}
              onClick={() => elegir(i)}
              className={`flex items-start gap-3 rounded-xl border p-3.5 text-left transition ${
                elegida
                  ? "border-brand bg-blue-50 ring-1 ring-brand"
                  : "border-border bg-surface active:scale-[0.995]"
              }`}
            >
              <span
                className={`flex h-7 w-7 flex-none items-center justify-center rounded-full text-sm font-bold ${
                  elegida
                    ? "bg-brand text-white"
                    : "bg-slate-100 text-muted"
                }`}
              >
                {LETRAS[i]}
              </span>
              <span className="pt-0.5 text-[15px] leading-snug">{op.texto}</span>
            </button>
          );
        })}
      </div>

      {/* Navegación */}
      <div className="mt-1 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setIndice((i) => Math.max(0, i - 1))}
          disabled={indice === 0}
          className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-semibold disabled:opacity-40"
        >
          Anterior
        </button>
        {esUltima ? (
          <button
            type="button"
            onClick={intentarFinalizar}
            className="flex-1 rounded-xl bg-success px-4 py-3 text-sm font-semibold text-white shadow-sm active:scale-[0.99]"
          >
            Finalizar
          </button>
        ) : (
          <button
            type="button"
            onClick={() => setIndice((i) => Math.min(total - 1, i + 1))}
            className="flex-1 rounded-xl bg-brand px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-brand-strong active:scale-[0.99]"
          >
            Siguiente
          </button>
        )}
      </div>

      {/* Overlay: navegador de preguntas */}
      {navegador && (
        <Overlay onClose={() => setNavegador(false)} titulo="Índice de preguntas">
          <div className="grid grid-cols-6 gap-2">
            {preguntas.map((_, i) => {
              const contestada = respuestas[i] !== null;
              const actual = i === indice;
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    setIndice(i);
                    setNavegador(false);
                  }}
                  className={`flex h-10 items-center justify-center rounded-lg text-sm font-semibold ${
                    actual
                      ? "bg-brand text-white ring-2 ring-brand-strong"
                      : contestada
                        ? "bg-blue-100 text-brand-strong"
                        : "border border-border bg-surface text-muted"
                  }`}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-muted">
            {contestadas} contestadas · {enBlanco} en blanco
          </p>
        </Overlay>
      )}

      {/* Overlay: confirmar finalizar con preguntas en blanco */}
      {confirmando && (
        <Overlay onClose={() => setConfirmando(false)} titulo="Finalizar examen">
          <p className="text-sm leading-relaxed">
            Tienes <strong>{enBlanco}</strong>{" "}
            {enBlanco === 1 ? "pregunta sin contestar" : "preguntas sin contestar"}.
            Contarán como falladas. ¿Seguro que quieres finalizar?
          </p>
          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setConfirmando(false)}
              className="flex-1 rounded-xl border border-border bg-surface px-4 py-3 text-sm font-semibold"
            >
              Seguir
            </button>
            <button
              type="button"
              onClick={finalizar}
              className="flex-1 rounded-xl bg-success px-4 py-3 text-sm font-semibold text-white shadow-sm"
            >
              Finalizar
            </button>
          </div>
        </Overlay>
      )}
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
