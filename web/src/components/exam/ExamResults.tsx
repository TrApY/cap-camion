"use client";

import type { Correccion } from "@/lib/exam";
import { ExplicacionPregunta } from "./ExplicacionPregunta";
import { FrecuenciaExamenes } from "./FrecuenciaExamenes";

const LETRAS = ["A", "B", "C", "D", "E", "F"];

function formatoTiempo(ms: number): string {
  const totalSeg = Math.round(ms / 1000);
  const m = Math.floor(totalSeg / 60);
  const s = totalSeg % 60;
  return `${m} min ${String(s).padStart(2, "0")} s`;
}

export function ExamResults({
  correccion,
  tiempoMs,
  onRepetir,
  onInicio,
}: {
  correccion: Correccion;
  tiempoMs: number;
  onRepetir: () => void;
  onInicio: () => void;
}) {
  const {
    total,
    aciertos,
    fallos,
    enBlanco,
    puntuacionSobre100,
    aprobado,
    falladas,
  } = correccion;
  const nota = puntuacionSobre100.toLocaleString("es-ES", {
    maximumFractionDigits: 1,
  });

  return (
    <div className="flex flex-col gap-5">
      {/* Nota (baremo oficial del CAP) */}
      <div
        className={`rounded-2xl border p-5 text-center shadow-sm ${
          aprobado
            ? "border-emerald-200 bg-emerald-50"
            : "border-rose-200 bg-rose-50"
        }`}
      >
        <span
          className={`inline-block rounded-full px-3 py-1 text-sm font-bold ${
            aprobado
              ? "bg-success text-white"
              : "bg-danger text-white"
          }`}
        >
          {aprobado ? "Aprobado" : "Suspenso"}
        </span>
        <p className="mt-3 text-4xl font-extrabold tabular-nums">
          {nota}
          <span className="text-2xl text-muted"> / 100 pts</span>
        </p>
        <p className="mt-1 text-sm font-semibold tabular-nums text-muted">
          {aciertos} de {total} aciertos
        </p>
        <p className="mt-3 text-xs text-muted">
          Baremo oficial: acierto +1, fallo −0,5, en blanco 0. Se aprueba con ≥ 50
          / 100.
        </p>
      </div>

      {/* Desglose */}
      <div className="grid grid-cols-3 gap-2">
        <Stat etiqueta="Aciertos (+1)" valor={aciertos} color="text-success" />
        <Stat etiqueta="Fallos (−0,5)" valor={fallos} color="text-danger" />
        <Stat etiqueta="En blanco (0)" valor={enBlanco} color="text-muted" />
      </div>

      {/* Consejo de estrategia */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-relaxed text-amber-900">
        💡 En el examen real, si dudas es mejor dejar en blanco que fallar: un
        fallo resta 0,5 puntos, el blanco no penaliza.
      </div>

      <div className="rounded-2xl border border-border bg-surface p-4 text-center text-sm shadow-sm">
        <span className="text-muted">Tiempo empleado: </span>
        <span className="font-semibold">{formatoTiempo(tiempoMs)}</span>
      </div>

      {/* Falladas */}
      {falladas.length > 0 ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
            Preguntas falladas ({falladas.length})
          </h2>
          {falladas.map((r) => {
            const correctaIndex = r.pregunta.opciones.findIndex(
              (o) => o.esCorrecta,
            );
            return (
              <div
                key={r.pregunta.id}
                className="rounded-2xl border border-border bg-surface p-4 shadow-sm"
              >
                <p className="text-sm font-medium leading-relaxed">
                  {r.pregunta.enunciado}
                </p>
                <FrecuenciaExamenes
                  frecuencia={r.pregunta.frecuencia}
                  className="mt-1.5"
                />
                <div className="mt-3 space-y-2 text-sm">
                  {r.elegidaIndex === null ? (
                    <p className="text-muted">Sin responder</p>
                  ) : (
                    <p className="flex gap-2">
                      <span className="font-semibold text-danger">
                        Tu respuesta ({LETRAS[r.elegidaIndex]}):
                      </span>
                      <span>{r.pregunta.opciones[r.elegidaIndex]?.texto}</span>
                    </p>
                  )}
                  {correctaIndex >= 0 && (
                    <p className="flex gap-2">
                      <span className="font-semibold text-success">
                        Correcta ({LETRAS[correctaIndex]}):
                      </span>
                      <span>{r.pregunta.opciones[correctaIndex]?.texto}</span>
                    </p>
                  )}
                  {r.pregunta.explicacion && (
                    <ExplicacionPregunta
                      explicacion={r.pregunta.explicacion}
                      norma={r.pregunta.norma}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-center text-sm font-medium text-success">
          ¡Perfecto! No has fallado ninguna pregunta.
        </div>
      )}

      {/* Acciones */}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={onRepetir}
          className="rounded-xl bg-brand px-5 py-4 text-base font-semibold text-white shadow-sm hover:bg-brand-strong active:scale-[0.99]"
        >
          Nuevo examen
        </button>
        <button
          type="button"
          onClick={onInicio}
          className="rounded-xl border border-border bg-surface px-5 py-3.5 text-base font-semibold"
        >
          Volver al inicio
        </button>
      </div>
    </div>
  );
}

function Stat({
  etiqueta,
  valor,
  color,
}: {
  etiqueta: string;
  valor: number;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-3 text-center shadow-sm">
      <p className={`text-2xl font-extrabold tabular-nums ${color}`}>{valor}</p>
      <p className="mt-0.5 text-xs text-muted">{etiqueta}</p>
    </div>
  );
}
