// Cuentas de usuario (CAP-12). La app sigue siendo 100 % usable sin cuenta: la
// sesión es un EXTRA que habilita sincronizar el progreso y salir en el ranking.
//
// Degradación con gracia: mientras los "anonymous sign-ins" estén desactivados
// en el proyecto Supabase (o el dispositivo esté sin red), `obtenerSesion()`
// devuelve null y todo lo que dependa de ella se calla. Cuando el toggle se
// active, empieza a funcionar sin necesidad de redespliegue.

import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

/**
 * Formato del nick público. Es la MISMA expresión que el CHECK
 * `perfiles_nick_formato` de la base de datos (migración 0003): validar en
 * cliente evita un viaje al servidor para el error más común.
 */
export const NICK_REGEX = /^[A-Za-z0-9_-]{3,20}$/;

/** Motivos por los que puede fallar el guardado del nick. */
export type MotivoNick = "formato" | "ocupado" | "sin_sesion" | "error";

/** Resultado de una operación de cuenta con mensaje ya legible para la UI. */
export type ResultadoAuth = { ok: true } | { ok: false; mensaje: string };

/** Mensaje genérico cuando la nube no está disponible (toggle apagado / sin red). */
export const SIN_NUBE = "La sincronización en la nube aún no está disponible";

// Promesa de resolución de sesión en curso. Memoiza SOLO para no lanzar dos
// registros anónimos a la vez (dos componentes montándose en paralelo); si el
// resultado es null se olvida, para poder reintentar más adelante.
let sesionEnCurso: Promise<Session | null> | null = null;

async function resolverSesion(): Promise<Session | null> {
  const { data, error } = await supabase.auth.getSession();
  if (error) return null;
  if (data.session) return data.session;

  // Sin sesión previa: se crea una cuenta anónima. Si el proyecto tiene los
  // registros anónimos desactivados, esto falla y la app sigue siendo local.
  const anonima = await supabase.auth.signInAnonymously();
  if (anonima.error) return null;
  return anonima.data.session ?? null;
}

/**
 * Sesión utilizable (existente o anónima recién creada), o null si no se pudo
 * conseguir. NUNCA lanza: quien la llama debe poder ignorar el null.
 */
export function obtenerSesion(): Promise<Session | null> {
  sesionEnCurso ??= resolverSesion().then(
    (sesion) => {
      if (!sesion) sesionEnCurso = null;
      return sesion;
    },
    () => {
      sesionEnCurso = null;
      return null;
    },
  );
  return sesionEnCurso;
}

/** Nick público del usuario actual, o null si no hay sesión o aún no tiene nick. */
export async function obtenerNick(): Promise<string | null> {
  const sesion = await obtenerSesion();
  if (!sesion) return null;

  const { data, error } = await supabase
    .from("perfiles")
    .select("nick")
    .eq("user_id", sesion.user.id)
    .maybeSingle<{ nick: string }>();

  if (error || !data) return null;
  return data.nick;
}

/**
 * Crea o cambia el nick del usuario actual. El formato se valida en cliente y
 * la unicidad la resuelve el índice `perfiles_nick_unico` (case-insensitive),
 * cuyo error se traduce a "ocupado".
 */
export async function guardarNick(
  nick: string,
): Promise<{ ok: true } | { ok: false; motivo: MotivoNick }> {
  if (!NICK_REGEX.test(nick)) return { ok: false, motivo: "formato" };

  const sesion = await obtenerSesion();
  if (!sesion) return { ok: false, motivo: "sin_sesion" };

  // Upsert por clave primaria: inserta la primera vez y actualiza si el usuario
  // cambia de nick. Las políticas RLS de 0003 permiten ambas sobre la fila propia.
  const { error } = await supabase
    .from("perfiles")
    .upsert({ user_id: sesion.user.id, nick }, { onConflict: "user_id" });

  if (!error) return { ok: true };
  if (error.code === "23505") return { ok: false, motivo: "ocupado" };
  if (error.code === "23514") return { ok: false, motivo: "formato" };
  return { ok: false, motivo: "error" };
}

/**
 * Añade un email a la cuenta actual (anónima o no). Supabase envía un enlace de
 * confirmación; hasta que se abre, la cuenta sigue igual. Es el camino para
 * poder recuperar el progreso en otro dispositivo.
 */
export async function vincularEmail(email: string): Promise<ResultadoAuth> {
  const sesion = await obtenerSesion();
  if (!sesion) return { ok: false, mensaje: SIN_NUBE };

  const { error } = await supabase.auth.updateUser({ email });
  if (error) return { ok: false, mensaje: error.message };
  return { ok: true };
}

/**
 * Entra con una cuenta YA existente mediante enlace mágico. `shouldCreateUser`
 * en false a propósito: si el email no tiene cuenta, se avisa en vez de crear
 * una vacía que perdería el progreso local.
 */
export async function entrarConEmail(email: string): Promise<ResultadoAuth> {
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { shouldCreateUser: false },
  });
  if (error) return { ok: false, mensaje: error.message };
  return { ok: true };
}

/** Email de la cuenta actual, o null si es anónima o no hay sesión. */
export async function emailVinculado(): Promise<string | null> {
  const sesion = await obtenerSesion();
  if (!sesion) return null;

  // Se pregunta al servidor porque el email puede haberse confirmado en otro
  // dispositivo; sin red se cae al que trae la sesión guardada.
  const { data, error } = await supabase.auth.getUser();
  if (error) return sesion.user.email ?? null;
  return data.user?.email ?? null;
}
