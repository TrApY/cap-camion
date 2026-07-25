// Sincronización del progreso con Supabase (CAP-12).
//
// El guardado local (IndexedDB) sigue siendo la fuente de verdad de la app: aquí
// solo se COPIA cada sesión terminada a la nube. Todo pasa por una cola en
// IndexedDB, así que da igual que no haya sesión de usuario, que el toggle de
// cuentas anónimas esté apagado o que el móvil esté sin cobertura: el paquete
// espera y se sube cuando se pueda. Ninguna función de este módulo lanza hacia
// fuera.
//
// `construirFilasSync` es PURA (mapeo del modelo local al esquema SQL) y es lo
// único que se testea; el resto es IO.

import { obtenerSesion } from "./auth";
import {
  STORE_SYNC_COLA,
  idbAddIn,
  idbBorrarEn,
  idbGetAllConClave,
  idbPutConClave,
} from "./idb";
import { supabase } from "./supabase";
import type { SesionGuardada } from "./stats";
import type { ModoExamen, ResultadoPregunta } from "./types";

// --- Modelo de las filas SQL (nombres tal cual la migración 0003) ---

/** Fila de `public.intentos` sin `user_id` (se añade al subir). */
export interface FilaIntento {
  modo: ModoExamen;
  tipo: SesionGuardada["tipo"];
  /** Slug del tema, solo en los tests de tipo "tema". */
  tema?: string;
  total: number;
  aciertos: number;
  fallos: number;
  en_blanco: number;
  tiempo_ms: number;
  /** Nota sobre 100 con el baremo oficial. */
  nota: number;
  started_at: string;
  finished_at: string;
}

/** Fila de `public.respuestas_usuario` sin `intento_id` ni `user_id`. */
export interface FilaRespuesta {
  pregunta_id: string;
  /** Letra ORIGINAL de la opción elegida (no la posición barajada); null si en blanco. */
  letra_elegida: string | null;
  /** null cuando la pregunta se dejó en blanco: no hubo ni acierto ni fallo. */
  correcta: boolean | null;
}

/** Paquete que viaja por la cola: un intento y sus respuestas. */
export interface PaqueteSync {
  intento: FilaIntento;
  respuestas: FilaRespuesta[];
  /**
   * Id del intento ya insertado en la nube. Se anota cuando el insert del
   * intento sale bien pero el de las respuestas no, para que el reintento no
   * duplique el intento (y con él la nota que alimenta el ranking).
   */
  intentoId?: number;
}

// --- Mapeo (puro) ---

/**
 * Traduce una sesión local terminada a las filas que espera la base de datos.
 *
 * Detalles que importan:
 * - `letra_elegida` es la letra ORIGINAL de la opción (a-d del banco), no la
 *   posición en pantalla: las opciones se barajan en cada examen.
 * - Una pregunta en blanco va con `letra_elegida` y `correcta` a null, para no
 *   contarla como fallo en ninguna consulta futura.
 * - `started_at` se deduce restando el tiempo empleado al fin de la sesión: el
 *   modelo local solo guarda el instante final.
 */
export function construirFilasSync(
  sesion: SesionGuardada,
  resultados: readonly ResultadoPregunta[],
): PaqueteSync {
  const intento: FilaIntento = {
    modo: sesion.modo,
    tipo: sesion.tipo,
    total: sesion.total,
    aciertos: sesion.aciertos,
    fallos: sesion.fallos,
    en_blanco: sesion.enBlanco,
    tiempo_ms: sesion.tiempoMs,
    nota: sesion.puntuacionSobre100,
    started_at: new Date(sesion.fecha - sesion.tiempoMs).toISOString(),
    finished_at: new Date(sesion.fecha).toISOString(),
  };
  if (sesion.tipo === "tema" && sesion.tema) intento.tema = sesion.tema;

  const respuestas: FilaRespuesta[] = resultados.map((r) => {
    const elegida = r.elegidaIndex;
    if (elegida === null) {
      return { pregunta_id: r.pregunta.id, letra_elegida: null, correcta: null };
    }
    return {
      pregunta_id: r.pregunta.id,
      letra_elegida: r.pregunta.opciones[elegida]?.letra ?? null,
      correcta: r.acertada,
    };
  });

  return { intento, respuestas };
}

// --- Cola (IO) ---

/** Mete un paquete en la cola de subida. */
export async function encolarSesion(paquete: PaqueteSync): Promise<void> {
  await idbAddIn(STORE_SYNC_COLA, paquete);
}

// Guarda anti-reentrada: dos disparos simultáneos (montaje + evento "online")
// subirían el mismo paquete dos veces.
let sincronizando = false;

/**
 * Sube los paquetes pendientes en orden. Sin sesión de usuario es un no-op
 * silencioso y la cola espera. Al primer error de red o de API se para y deja el
 * resto para el siguiente intento.
 */
export async function sincronizar(): Promise<void> {
  if (sincronizando) return;
  sincronizando = true;
  try {
    const sesion = await obtenerSesion();
    if (!sesion) return;

    const pendientes = await idbGetAllConClave<PaqueteSync>(STORE_SYNC_COLA);
    for (const { clave, valor } of pendientes) {
      const subido = await subirPaquete(valor, sesion.user.id, clave);
      if (!subido) return;
      await idbBorrarEn(STORE_SYNC_COLA, clave);
    }
  } catch (e) {
    // La cola sigue intacta: se reintentará en el próximo arranque o al volver
    // la conexión.
    console.warn("Sincronización con la nube no completada:", e);
  } finally {
    sincronizando = false;
  }
}

/** Sube un paquete. Devuelve false si algo falló (el paquete se queda en la cola). */
async function subirPaquete(
  paquete: PaqueteSync,
  userId: string,
  clave: IDBValidKey,
): Promise<boolean> {
  let intentoId = paquete.intentoId;

  if (intentoId === undefined) {
    const { data, error } = await supabase
      .from("intentos")
      .insert({ ...paquete.intento, user_id: userId })
      .select("id")
      .single<{ id: number }>();
    if (error || !data) return false;
    intentoId = data.id;

    // Se anota en la cola antes de seguir: si las respuestas fallan, el
    // reintento reutiliza este intento en vez de crear otro.
    try {
      await idbPutConClave<PaqueteSync>(STORE_SYNC_COLA, clave, {
        ...paquete,
        intentoId,
      });
    } catch {
      // Si no se puede anotar, se continúa: en el peor caso se reintenta el
      // intento completo.
    }
  }

  if (paquete.respuestas.length > 0) {
    const { error } = await supabase.from("respuestas_usuario").insert(
      paquete.respuestas.map((r) => ({
        ...r,
        intento_id: intentoId,
        user_id: userId,
      })),
    );
    if (error) return false;
  }

  return true;
}

// Arranque idempotente: el componente que lo llama se monta en cada navegación.
let syncArrancado = false;

/**
 * Deja la sincronización funcionando sola: un intento al arrancar y otro cada
 * vez que el dispositivo recupera la conexión.
 */
export function iniciarSyncAutomatico(): void {
  if (syncArrancado || typeof window === "undefined") return;
  syncArrancado = true;

  window.addEventListener("online", () => void sincronizar());
  void sincronizar();
}
