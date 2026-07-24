// Estadísticas de progreso del usuario. Todo es local al dispositivo
// (IndexedDB): no hay login ni sincronización con el servidor.
//
// Las funciones de cálculo son PURAS y no tocan IndexedDB, para poder testearlas
// con `bun test`. Solo las marcadas como IO abren la base de datos.

import {
  STORE_PROGRESO,
  STORE_SESIONES,
  idbActualizarVarios,
  idbAddIn,
  idbClearStore,
  idbGetAll,
} from "./idb";
import type { Correccion } from "./exam";
import type { ModoExamen } from "./types";

// --- Modelo ---

export interface ProgresoPregunta {
  preguntaId: string;
  /** Slug del tema (ver lib/temas.ts). */
  tema: string;
  /** Veces presentada (aciertos + fallos + enBlanco). */
  vistas: number;
  aciertos: number;
  /** Contestadas incorrectas. */
  fallos: number;
  enBlanco: number;
  /** Aciertos consecutivos; un fallo o un blanco la resetean a 0. */
  racha: number;
  /** epoch ms de la última vez que se presentó. */
  ultimaVez: number;
}

export interface SesionGuardada {
  /** epoch ms del fin del test. */
  fecha: number;
  tipo: "general" | "tema";
  /** Slug del tema, solo si tipo === "tema". */
  tema?: string;
  modo: ModoExamen;
  total: number;
  aciertos: number;
  fallos: number;
  enBlanco: number;
  puntuacionSobre100: number;
  aprobado: boolean;
  tiempoMs: number;
}

/** Aciertos consecutivos a partir de los cuales una pregunta se da por dominada. */
export const RACHA_DOMINADA = 2;

/** Nº de sesiones recientes que alimentan la predicción. */
export const SESIONES_PREDICCION = 10;

/** Respuestas mínimas en esas sesiones para que la predicción sea fiable. */
export const RESPUESTAS_MINIMAS_PREDICCION = 50;

/** Resultado de una pregunta concreta dentro de un test corregido. */
export interface ResultadoAgregable {
  preguntaId: string;
  tema: string;
  acertada: boolean;
  enBlanco: boolean;
}

// --- Agregado por pregunta (puro) ---

/**
 * Aplica el resultado de una pregunta sobre su agregado previo.
 * - acierto  → aciertos+1, racha+1
 * - fallo    → fallos+1, racha=0
 * - blanco   → enBlanco+1, racha=0 (dejar en blanco no demuestra dominio)
 * En todos los casos: vistas+1 y ultimaVez=ahora.
 */
export function aplicarResultado(
  previo: ProgresoPregunta | undefined,
  r: ResultadoAgregable,
  ahora: number,
): ProgresoPregunta {
  const base: ProgresoPregunta = previo ?? {
    preguntaId: r.preguntaId,
    tema: r.tema,
    vistas: 0,
    aciertos: 0,
    fallos: 0,
    enBlanco: 0,
    racha: 0,
    ultimaVez: 0,
  };
  const fallada = !r.acertada && !r.enBlanco;

  return {
    preguntaId: base.preguntaId,
    // El tema del banco manda; se conserva el previo si viniera vacío.
    tema: r.tema || base.tema,
    vistas: base.vistas + 1,
    aciertos: base.aciertos + (r.acertada ? 1 : 0),
    fallos: base.fallos + (fallada ? 1 : 0),
    enBlanco: base.enBlanco + (r.enBlanco ? 1 : 0),
    racha: r.acertada ? base.racha + 1 : 0,
    ultimaVez: ahora,
  };
}

// --- Lecturas agregadas (puras) ---

export interface ResumenGlobal {
  tests: number;
  respuestas: number;
  aciertos: number;
  porcentajeAcierto: number;
  tiempoMs: number;
}

/** Totales de todo el histórico de sesiones. */
export function resumenGlobal(sesiones: SesionGuardada[]): ResumenGlobal {
  let respuestas = 0;
  let aciertos = 0;
  let tiempoMs = 0;
  for (const s of sesiones) {
    respuestas += s.total;
    aciertos += s.aciertos;
    tiempoMs += s.tiempoMs;
  }
  return {
    tests: sesiones.length,
    respuestas,
    aciertos,
    porcentajeAcierto: respuestas > 0 ? (aciertos / respuestas) * 100 : 0,
    tiempoMs,
  };
}

/** Color del semáforo de la predicción; "neutro" cuando no hay datos suficientes. */
export type ColorSemaforo = "verde" | "ambar" | "rojo" | "neutro";

export interface Prediccion {
  estado: "insuficiente" | "listo";
  /** Nota estimada sobre 100 (0 si estado === "insuficiente"). */
  nota: number;
  color: ColorSemaforo;
  /** Texto ya resuelto para la UI. */
  mensaje: string;
  /** Nº de sesiones consideradas (máx. SESIONES_PREDICCION). */
  sesiones: number;
  /** Respuestas acumuladas en esas sesiones. */
  respuestas: number;
  /** Respuestas que faltan para activar la predicción (0 si ya está activa). */
  faltan: number;
}

/**
 * Estima si el usuario aprobaría hoy a partir de sus últimas sesiones, con el
 * baremo oficial (fallo −0,5) y el umbral de 50/100.
 */
export function prediccion(sesiones: SesionGuardada[]): Prediccion {
  const ultimas = [...sesiones]
    .sort((a, b) => a.fecha - b.fecha)
    .slice(-SESIONES_PREDICCION);

  let total = 0;
  let aciertos = 0;
  let fallos = 0;
  for (const s of ultimas) {
    total += s.total;
    aciertos += s.aciertos;
    fallos += s.fallos;
  }

  if (total < RESPUESTAS_MINIMAS_PREDICCION) {
    const faltan = RESPUESTAS_MINIMAS_PREDICCION - total;
    return {
      estado: "insuficiente",
      nota: 0,
      color: "neutro",
      mensaje: `Te faltan ${faltan.toLocaleString("es-ES")} respuestas para estimar tu nota`,
      sesiones: ultimas.length,
      respuestas: total,
      faltan,
    };
  }

  const bruta = ((aciertos - 0.5 * fallos) / total) * 100;
  const nota = Math.min(100, Math.max(0, bruta));

  let color: ColorSemaforo;
  let mensaje: string;
  if (nota >= 55) {
    color = "verde";
    mensaje = "Hoy aprobarías";
  } else if (nota >= 45) {
    color = "ambar";
    mensaje = "Al límite — sigue practicando";
  } else {
    color = "rojo";
    const puntos = (50 - nota).toLocaleString("es-ES", {
      maximumFractionDigits: 1,
    });
    mensaje = `Te faltan ${puntos} puntos`;
  }

  return {
    estado: "listo",
    nota,
    color,
    mensaje,
    sesiones: ultimas.length,
    respuestas: total,
    faltan: 0,
  };
}

export interface EstadisticaTema {
  slug: string;
  respuestas: number;
  aciertos: number;
  porcentaje: number;
}

/**
 * Acierto acumulado por tema. Solo incluye temas con al menos una respuesta y
 * los ordena de PEOR a MEJOR porcentaje (lo que más conviene repasar primero).
 */
export function estadisticasPorTema(
  progresos: ProgresoPregunta[],
): EstadisticaTema[] {
  const porSlug = new Map<string, EstadisticaTema>();
  for (const p of progresos) {
    if (!p.tema) continue;
    const acc = porSlug.get(p.tema) ?? {
      slug: p.tema,
      respuestas: 0,
      aciertos: 0,
      porcentaje: 0,
    };
    acc.respuestas += p.vistas;
    acc.aciertos += p.aciertos;
    porSlug.set(p.tema, acc);
  }

  return [...porSlug.values()]
    .filter((t) => t.respuestas > 0)
    .map((t) => ({ ...t, porcentaje: (t.aciertos / t.respuestas) * 100 }))
    .sort(
      (a, b) =>
        a.porcentaje - b.porcentaje || a.slug.localeCompare(b.slug, "es-ES"),
    );
}

/** Nº de preguntas dominadas (racha de aciertos >= RACHA_DOMINADA). */
export function contarDominadas(progresos: ProgresoPregunta[]): number {
  return progresos.filter((p) => p.racha >= RACHA_DOMINADA).length;
}

/** Tramo de acierto para colorear (siempre acompañado de texto en la UI). */
export type TramoAcierto = "rojo" | "ambar" | "verde";

/** Tramos comunes a la pantalla de estadísticas y a los badges de temas. */
export function tramoAcierto(porcentaje: number): TramoAcierto {
  if (porcentaje >= 75) return "verde";
  if (porcentaje >= 50) return "ambar";
  return "rojo";
}

// --- IO (IndexedDB) ---

export interface DatosEstadisticas {
  /** Sesiones en orden cronológico (más antigua primero). */
  sesiones: SesionGuardada[];
  progresos: ProgresoPregunta[];
}

/** Lee el agregado por pregunta. */
export async function cargarProgresos(): Promise<ProgresoPregunta[]> {
  return idbGetAll<ProgresoPregunta>(STORE_PROGRESO);
}

/** Lee todo lo necesario para la pantalla de estadísticas. */
export async function cargarDatosEstadisticas(): Promise<DatosEstadisticas> {
  const [sesiones, progresos] = await Promise.all([
    idbGetAll<SesionGuardada>(STORE_SESIONES),
    cargarProgresos(),
  ]);
  return {
    sesiones: sesiones.sort((a, b) => a.fecha - b.fecha),
    progresos,
  };
}

/**
 * Guarda un test terminado: lo añade al histórico y aplica los deltas al
 * agregado por pregunta. Pensada para llamarse fire-and-forget desde la UI.
 */
export async function registrarSesion(entrada: {
  tipo: "general" | "tema";
  tema?: string;
  modo: ModoExamen;
  correccion: Correccion;
  tiempoMs: number;
}): Promise<void> {
  const { tipo, tema, modo, correccion, tiempoMs } = entrada;
  const ahora = Date.now();

  const sesion: SesionGuardada = {
    fecha: ahora,
    tipo,
    modo,
    total: correccion.total,
    aciertos: correccion.aciertos,
    fallos: correccion.fallos,
    enBlanco: correccion.enBlanco,
    puntuacionSobre100: correccion.puntuacionSobre100,
    aprobado: correccion.aprobado,
    tiempoMs,
  };
  if (tipo === "tema" && tema) sesion.tema = tema;

  await idbAddIn(STORE_SESIONES, sesion);

  // Deltas por pregunta. Se agrupan por id por si una pregunta apareciera más
  // de una vez en el mismo test.
  const deltas = new Map<string, ResultadoAgregable[]>();
  for (const r of correccion.resultados) {
    const delta: ResultadoAgregable = {
      preguntaId: r.pregunta.id,
      tema: r.pregunta.tema,
      acertada: r.acertada,
      enBlanco: r.elegidaIndex === null,
    };
    const lista = deltas.get(delta.preguntaId);
    if (lista) lista.push(delta);
    else deltas.set(delta.preguntaId, [delta]);
  }

  await idbActualizarVarios<ProgresoPregunta>(
    STORE_PROGRESO,
    [...deltas.keys()],
    (previo, clave) => {
      let acc = previo;
      for (const delta of deltas.get(clave) ?? []) {
        acc = aplicarResultado(acc, delta, ahora);
      }
      return acc;
    },
  );
}

/**
 * Borra el histórico y el agregado del usuario. NO toca la store "kv": el banco
 * de preguntas descargado se conserva para seguir funcionando sin conexión.
 */
export async function borrarProgreso(): Promise<void> {
  await idbClearStore(STORE_SESIONES);
  await idbClearStore(STORE_PROGRESO);
}
