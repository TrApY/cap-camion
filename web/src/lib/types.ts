// Modelo de dominio del banco de preguntas del CAP.

export type Letra = "a" | "b" | "c" | "d";

export interface Opcion {
  letra: string;
  texto: string;
  esCorrecta: boolean;
}

export interface Pregunta {
  id: string;
  enunciado: string;
  opciones: Opcion[];
  /** Letra de la opción correcta (a-d) o null si no consta. */
  respuestaCorrecta: string | null;
  /** Nº de exámenes oficiales en los que aparece la pregunta. */
  frecuencia: number;
  /** true si el banco detectó respuestas contradictorias entre fuentes. */
  conflicto: boolean;
  /** Slug del tema al que pertenece la pregunta (ver lib/temas.ts). */
  tema: string;
  /** Por qué la respuesta correcta lo es; null si la pregunta no la tiene. */
  explicacion: string | null;
  /** Referencia normativa oficial del Ministerio, literal. null si no consta. */
  norma: string | null;
}

/** Resumen de teoría de un tema (slug -> resumen), tal como llega del banco. */
export interface TeoriaTema {
  titulo: string;
  /** Markdown sencillo (ver lib/markdown.ts). */
  resumen: string;
}

/** Snapshot completo cacheado en el cliente. */
export interface Banco {
  version: number;
  descargadoEn: number; // epoch ms
  preguntas: Pregunta[];
  /** Teoría por tema. Opcional: si la consulta falla, la app funciona igual. */
  teoria?: Record<string, TeoriaTema>;
}

// --- Estructuras de un examen en curso ---

export interface OpcionExamen {
  letra: string;
  texto: string;
  esCorrecta: boolean;
}

export interface PreguntaExamen {
  id: string;
  enunciado: string;
  frecuencia: number;
  /** Slug del tema de la pregunta (se propaga para las estadísticas). */
  tema: string;
  /** Explicación de la respuesta correcta (se propaga para mostrarla al corregir). */
  explicacion: string | null;
  /** Referencia normativa oficial, literal. */
  norma: string | null;
  /** Opciones ya barajadas para presentación. */
  opciones: OpcionExamen[];
}

/**
 * Modo de examen:
 * - "real": sin feedback hasta el final; corrige y muestra resultados al terminar.
 * - "practica": corrección inmediata al marcar cada opción; la respuesta queda fijada.
 */
export type ModoExamen = "real" | "practica";

export interface ConfigExamen {
  numPreguntas: number;
  altaProbabilidad: boolean;
  /** Modo de examen. Por defecto "real". */
  modo: ModoExamen;
  /**
   * Slug del tema al que restringir el examen. Si se omite, se usan todas las
   * preguntas aptas del banco (examen general).
   */
  tema?: string;
}

export interface ResultadoPregunta {
  pregunta: PreguntaExamen;
  /** Índice de la opción elegida dentro de pregunta.opciones, o null si en blanco. */
  elegidaIndex: number | null;
  acertada: boolean;
}
