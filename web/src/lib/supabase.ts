import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    "Faltan NEXT_PUBLIC_SUPABASE_URL o NEXT_PUBLIC_SUPABASE_ANON_KEY. " +
      "Copia web/.env.example a web/.env.local y rellena los valores.",
  );
}

// Cliente único de la app: banco público (RLS de solo lectura) y datos del
// usuario (RLS por `auth.uid()`). La sesión SÍ se persiste y se refresca sola:
// la cuenta puede ser anónima (CAP-12) y debe sobrevivir a recargas y a los
// días entre sesiones de estudio.
export const supabase = createClient(url, anonKey, {
  auth: { persistSession: true, autoRefreshToken: true },
});
