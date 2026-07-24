import type {
  Banco,
  ConfigExamen,
  Pregunta,
  PreguntaExamen,
  ResultadoPregunta,
} from "./types";

/** Baraja in-place una copia del array (Fisher-Yates). */
function barajar<T>(arr: readonly T[]): T[] {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * Preguntas aptas para examen: con respuesta correcta fiable, sin conflicto y
 * con al menos 2 opciones (idealmente 4). Las demás no tienen respuesta única
 * fiable y se excluyen.
 */
export function preguntasAptas(banco: Banco): Pregunta[] {
  return banco.preguntas.filter(
    (p) =>
      !p.conflicto &&
      p.respuestaCorrecta != null &&
      p.opciones.length >= 2 &&
      // La opción marcada como correcta debe existir entre las opciones.
      p.opciones.some((o) => o.esCorrecta),
  );
}

/**
 * Construye un examen a partir del banco y la configuración.
 * - altaProbabilidad: coge las N preguntas de mayor `frecuencia`.
 * - si no: selección aleatoria.
 * En ambos casos se baraja el orden de las preguntas y de sus opciones.
 */
export function construirExamen(
  banco: Banco,
  config: ConfigExamen,
): PreguntaExamen[] {
  const aptas = preguntasAptas(banco);
  const n = Math.min(config.numPreguntas, aptas.length);

  let seleccion: Pregunta[];
  if (config.altaProbabilidad) {
    // Orden por frecuencia desc; desempate aleatorio para no dar siempre el
    // mismo examen cuando hay muchas preguntas con igual frecuencia.
    seleccion = barajar(aptas)
      .sort((a, b) => b.frecuencia - a.frecuencia)
      .slice(0, n);
  } else {
    seleccion = barajar(aptas).slice(0, n);
  }

  // Barajar el orden de presentación de las preguntas y de sus opciones.
  return barajar(seleccion).map((p) => ({
    id: p.id,
    enunciado: p.enunciado,
    frecuencia: p.frecuencia,
    opciones: barajar(p.opciones).map((o) => ({
      letra: o.letra,
      texto: o.texto,
      esCorrecta: o.esCorrecta,
    })),
  }));
}

export interface Correccion {
  total: number;
  aciertos: number;
  fallos: number;
  porcentaje: number; // 0-100
  aprobado: boolean;
  falladas: ResultadoPregunta[];
  resultados: ResultadoPregunta[];
}

/**
 * Corrige el examen. `respuestas[i]` es el índice de la opción elegida en
 * preguntas[i].opciones, o null si se dejó en blanco (cuenta como fallo).
 */
export function corregirExamen(
  preguntas: PreguntaExamen[],
  respuestas: (number | null)[],
  umbral: number,
): Correccion {
  const resultados: ResultadoPregunta[] = preguntas.map((pregunta, i) => {
    const elegidaIndex = respuestas[i] ?? null;
    const acertada =
      elegidaIndex != null && pregunta.opciones[elegidaIndex]?.esCorrecta === true;
    return { pregunta, elegidaIndex, acertada };
  });

  const total = preguntas.length;
  const aciertos = resultados.filter((r) => r.acertada).length;
  const fallos = total - aciertos;
  const porcentaje = total > 0 ? (aciertos / total) * 100 : 0;

  return {
    total,
    aciertos,
    fallos,
    porcentaje,
    aprobado: porcentaje >= umbral * 100,
    falladas: resultados.filter((r) => !r.acertada),
    resultados,
  };
}
