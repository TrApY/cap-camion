// Panel con la explicación de una pregunta ("¿por qué?") y, si consta, la
// referencia normativa oficial. Lo comparten la práctica (ExamRunner) y el
// listado de falladas (ExamResults) para que el formato sea idéntico.
export function ExplicacionPregunta({
  explicacion,
  norma,
}: {
  explicacion: string;
  norma: string | null;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-3.5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-wide text-muted">
        ¿Por qué?
      </p>
      <p className="mt-1.5 text-sm leading-relaxed">{explicacion}</p>
      {norma && (
        <p className="mt-2 text-xs leading-relaxed text-muted">
          Norma: {norma} · banco oficial del Ministerio
        </p>
      )}
    </div>
  );
}
