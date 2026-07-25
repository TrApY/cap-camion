"use client";

import { useEffect, useState } from "react";
import {
  NICK_REGEX,
  guardarNick,
  obtenerNick,
  obtenerSesion,
  type MotivoNick,
} from "@/lib/auth";

/**
 * Marca de "no volver a proponerlo". Vive en localStorage y no en IndexedDB
 * porque es una preferencia trivial de UI y hay que leerla al pintar.
 */
const CLAVE_DESCARTADO = "nick-prompt-descartado";

/** Mensajes de error del nick, ya en el idioma del usuario. */
export const MENSAJE_ERROR_NICK: Record<MotivoNick, string> = {
  formato: "3-20 caracteres: letras, números, guiones",
  ocupado: "Ese nick ya está cogido",
  sin_sesion: "La sincronización en la nube aún no está disponible",
  error: "No se pudo guardar. Inténtalo de nuevo",
};

type Estado = "oculto" | "pidiendo" | "guardado";

/**
 * Banner autocontenido para el final de los resultados: propone elegir nick a
 * quien tenga cuenta y aún no lo haya hecho. Sin cuenta (o si ya se descartó una
 * vez) no pinta nada; la opción sigue estando siempre en /estadisticas.
 */
export function NickPrompt() {
  const [estado, setEstado] = useState<Estado>("oculto");
  const [nick, setNick] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (localStorage.getItem(CLAVE_DESCARTADO) === "1") return;
    let cancelado = false;

    // El estado se aplica en el callback de la promesa, nunca de forma
    // sincrónica dentro del efecto (react-hooks/set-state-in-effect).
    Promise.resolve()
      .then(async () => {
        const sesion = await obtenerSesion();
        if (!sesion) return false;
        return (await obtenerNick()) === null;
      })
      .then((procede) => {
        if (!cancelado && procede) setEstado("pidiendo");
      })
      .catch(() => {
        // Sin nube: el banner simplemente no aparece.
      });

    return () => {
      cancelado = true;
    };
  }, []);

  function descartar() {
    localStorage.setItem(CLAVE_DESCARTADO, "1");
    setEstado("oculto");
  }

  async function guardar() {
    setGuardando(true);
    setError("");
    try {
      const res = await guardarNick(nick.trim());
      if (res.ok) setEstado("guardado");
      else setError(MENSAJE_ERROR_NICK[res.motivo]);
    } catch {
      setError(MENSAJE_ERROR_NICK.error);
    } finally {
      setGuardando(false);
    }
  }

  if (estado === "oculto") return null;

  if (estado === "guardado") {
    return (
      <div className="rounded-2xl border border-border bg-surface p-4 text-center text-sm shadow-sm">
        <p className="font-semibold text-success">
          Listo, saldrás en el ranking como {nick.trim()}
        </p>
        <p className="mt-1 text-xs text-muted">
          Puedes cambiarlo cuando quieras en Mi progreso.
        </p>
      </div>
    );
  }

  const idInput = "nick-prompt-input";
  const idError = "nick-prompt-error";
  const valido = NICK_REGEX.test(nick.trim());

  return (
    <div className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-bold leading-snug">
            ¿Quieres guardar tu progreso y salir en el ranking?
          </p>
          <label htmlFor={idInput} className="mt-1 block text-xs text-muted">
            Elige un nick
          </label>
        </div>
        <button
          type="button"
          onClick={descartar}
          aria-label="No, gracias"
          className="-mr-1 -mt-1 flex h-8 w-8 flex-none items-center justify-center rounded-full text-muted"
        >
          ✕
        </button>
      </div>

      <div className="mt-3 flex gap-2">
        <input
          id={idInput}
          type="text"
          value={nick}
          onChange={(e) => setNick(e.target.value)}
          maxLength={20}
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="p. ej. JoTa_89"
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? idError : undefined}
          className="min-w-0 flex-1 rounded-xl border border-border bg-surface px-3 py-2.5 text-sm"
        />
        <button
          type="button"
          onClick={() => void guardar()}
          disabled={guardando || !valido}
          className="flex-none rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-60"
        >
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </div>

      {error ? (
        <p id={idError} role="alert" className="mt-2 text-xs font-medium text-danger">
          {error}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">
          3-20 caracteres: letras, números, guiones. Es público en el ranking.
        </p>
      )}
    </div>
  );
}
