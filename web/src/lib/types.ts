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
}

/** Snapshot completo cacheado en el cliente. */
export interface Banco {
  version: number;
  descargadoEn: number; // epoch ms
  preguntas: Pregunta[];
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
  /** Opciones ya barajadas para presentación. */
  opciones: OpcionExamen[];
}

export interface ConfigExamen {
  numPreguntas: number;
  altaProbabilidad: boolean;
  /** Umbral de aprobado (0-1), por defecto 0.5. */
  umbral: number;
}

export interface ResultadoPregunta {
  pregunta: PreguntaExamen;
  /** Índice de la opción elegida dentro de pregunta.opciones, o null si en blanco. */
  elegidaIndex: number | null;
  acertada: boolean;
}
