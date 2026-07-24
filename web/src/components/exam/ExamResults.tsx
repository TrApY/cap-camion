"use client";

import type { Correccion } from "@/lib/exam";
import type { ConfigExamen } from "@/lib/types";

const LETRAS = ["A", "B", "C", "D", "E", "F"];

function formatoTiempo(ms: number): string {
  const totalSeg = Math.round(ms / 1000);
  const m = Math.floor(totalSeg / 60);
  const s = totalSeg % 60;
  return `${m} min ${String(s).padStart(2, "0")} s`;
}

export function ExamResults({
  correccion,
  config,
  tiempoMs,
  onRepetir,
  onInicio,
}: {
  correccion: Correccion;
  config: ConfigExamen;
  tiempoMs: number;
  onRepetir: () => void;
  onInicio: () => void;
}) {
  const { total, aciertos, fallos, porcentaje, aprobado, falladas } =
    correccion;
  const enBlanco = falladas.filter((f) => f.elegidaIndex === null).length;

  return (
    <div className="flex flex-col gap-5">
      {/* Nota */}
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
          {aciertos}
          <span className="text-2xl text-muted"> / {total}</span>
        </p>
        <p className="mt-1 text-lg font-semibold tabular-nums text-muted">
          {porcentaje.toFixed(0)}% de aciertos
        </p>
        <p className="mt-3 text-xs text-muted">
          Umbral aplicado: {Math.round(config.umbral * 100)}% (orientativo, no es
          la nota oficial exacta).
        </p>
      </div>

      {/* Estadísticas */}
      <div className="grid grid-cols-3 gap-2">
        <Stat etiqueta="Aciertos" valor={aciertos} color="text-success" />
        <Stat etiqueta="Fallos" valor={fallos} color="text-danger" />
        <Stat etiqueta="En blanco" valor={enBlanco} color="text-muted" />
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
