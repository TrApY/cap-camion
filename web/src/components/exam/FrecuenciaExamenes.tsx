// Texto discreto con el nº de exámenes oficiales distintos en los que ha caído
// una pregunta. Lo comparten la práctica (ExamRunner, solo tras responder) y el
// listado de resultados (ExamResults) para que el formato sea idéntico.
// Nunca debe mostrarse durante un examen en modo real: revelaría de antemano qué
// preguntas son las más repetidas y sesgaría el simulacro.
export function FrecuenciaExamenes({
  frecuencia,
  className = "",
}: {
  frecuencia: number;
  className?: string;
}) {
  // Toda pregunta del banco viene de al menos un examen; un valor menor solo
  // puede ser un dato corrupto, y en ese caso no se afirma nada.
  if (frecuencia < 1) return null;
  return (
    <p className={`text-xs leading-relaxed text-muted ${className}`}>
      Ha caído en {frecuencia.toLocaleString("es-ES")}{" "}
      {frecuencia === 1 ? "examen oficial" : "exámenes oficiales"}
    </p>
  );
}
