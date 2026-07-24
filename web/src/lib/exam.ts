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
 * Cuenta las preguntas aptas de cada tema (slug -> nº de aptas). Útil para la
 * pantalla de práctica por temas sin recalcular por cada tema.
 */
export function contarAptasPorTema(banco: Banco): Record<string, number> {
  const conteo: Record<string, number> = {};
  for (const p of preguntasAptas(banco)) {
    if (!p.tema) continue;
    conteo[p.tema] = (conteo[p.tema] ?? 0) + 1;
  }
  return conteo;
}

/**
 * Construye un examen a partir del banco y la configuración.
 * - altaProbabilidad: coge las N preguntas de mayor `frecuencia`.
 * - si no: selección aleatoria.
 * - tema: si se indica, restringe la selección a ese tema (práctica por temas).
 * En todos los casos se baraja el orden de las preguntas y de sus opciones.
 */
export function construirExamen(
  banco: Banco,
  config: ConfigExamen,
): PreguntaExamen[] {
  const aptas = config.tema
    ? preguntasAptas(banco).filter((p) => p.tema === config.tema)
    : preguntasAptas(banco);
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
  /** Contestadas incorrectas (penalizan -0,5 c/u). */
  fallos: number;
  /** No contestadas (no penalizan). */
  enBlanco: number;
  /** Nota neta = aciertos - 0,5*fallos. */
  puntuacion: number;
  /** Nota escalada a 100 (marco del examen oficial). */
  puntuacionSobre100: number;
  /** Puntos netos necesarios para aprobar (= total * 0,5). */
  umbralPuntos: number;
  aprobado: boolean;
  /** Porcentaje de aciertos (informativo). */
  porcentajeAciertos: number;
  falladas: ResultadoPregunta[];
  resultados: ResultadoPregunta[];
}

/**
 * Corrige el examen con el BAREMO OFICIAL del CAP:
 *   acierto = +1, fallo (contestada e incorrecta) = -0,5, en blanco = 0.
 *   nota = aciertos - 0,5*fallos ; se aprueba con >= 50 puntos sobre 100.
 * El umbral se escala al nº de preguntas del test (50% de la puntuación máxima,
 * que es `total`), de modo que un test de 30 preguntas aprueba con >= 15 puntos
 * netos (equivalente a 50/100).
 *
 * `respuestas[i]` es el índice de la opción elegida en preguntas[i].opciones,
 * o null si se dejó en blanco.
 */
export function corregirExamen(
  preguntas: PreguntaExamen[],
  respuestas: (number | null)[],
): Correccion {
  const resultados: ResultadoPregunta[] = preguntas.map((pregunta, i) => {
    const elegidaIndex = respuestas[i] ?? null;
    const acertada =
      elegidaIndex != null && pregunta.opciones[elegidaIndex]?.esCorrecta === true;
    return { pregunta, elegidaIndex, acertada };
  });

  const total = preguntas.length;
  const aciertos = resultados.filter((r) => r.acertada).length;
  const enBlanco = resultados.filter((r) => r.elegidaIndex === null).length;
  const fallos = total - aciertos - enBlanco; // contestadas e incorrectas

  const puntuacion = aciertos - 0.5 * fallos;
  const puntuacionSobre100 = total > 0 ? (puntuacion / total) * 100 : 0;
  const umbralPuntos = total * 0.5;

  return {
    total,
    aciertos,
    fallos,
    enBlanco,
    puntuacion,
    puntuacionSobre100,
    umbralPuntos,
    aprobado: puntuacion >= umbralPuntos,
    porcentajeAciertos: total > 0 ? (aciertos / total) * 100 : 0,
    falladas: resultados.filter((r) => !r.acertada),
    resultados,
  };
}
