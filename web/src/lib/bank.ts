import { supabase } from "./supabase";
import { idbGet, idbSet } from "./idb";
import type { Banco, Pregunta, Opcion, TeoriaTema } from "./types";

// Sube este número si cambia la forma de los datos cacheados para invalidar
// cachés antiguas en el cliente.
// v2: se incorpora la columna `tema` (práctica por temas).
// v3: se incorporan `explicacion` y `norma` por pregunta y la teoría por tema.
const BANCO_VERSION = 3;
const CACHE_KEY = "banco";
const PAGE_SIZE = 1000;

// Fila cruda tal cual la devuelve Supabase con el embed de opciones.
interface FilaPregunta {
  id: string;
  enunciado: string;
  respuesta_correcta: string | null;
  frecuencia: number | null;
  conflicto_respuesta: boolean | null;
  tema: string | null;
  explicacion: string | null;
  norma: string | null;
  opciones: {
    letra: string;
    texto: string | null;
    es_correcta: boolean | null;
  }[];
}

// Fila cruda de la teoría por tema.
interface FilaTeoria {
  slug: string;
  titulo: string | null;
  resumen_md: string | null;
}

function mapFila(fila: FilaPregunta): Pregunta {
  const opciones: Opcion[] = (fila.opciones ?? [])
    .map((o) => ({
      letra: (o.letra ?? "").trim().toLowerCase(),
      texto: o.texto ?? "",
      esCorrecta: o.es_correcta === true,
    }))
    .sort((a, b) => a.letra.localeCompare(b.letra));

  return {
    id: fila.id,
    enunciado: fila.enunciado,
    opciones,
    respuestaCorrecta: fila.respuesta_correcta
      ? fila.respuesta_correcta.trim().toLowerCase()
      : null,
    frecuencia: fila.frecuencia ?? 0,
    conflicto: fila.conflicto_respuesta === true,
    tema: (fila.tema ?? "").trim(),
    explicacion: fila.explicacion?.trim() ? fila.explicacion : null,
    norma: fila.norma?.trim() ? fila.norma : null,
  };
}

export type ProgresoDescarga = (cargadas: number) => void;

/** Descarga el banco entero desde Supabase (paginado, con opciones embebidas). */
async function descargarBanco(onProgreso?: ProgresoDescarga): Promise<Pregunta[]> {
  const preguntas: Pregunta[] = [];
  let desde = 0;

  for (;;) {
    const { data, error } = await supabase
      .from("preguntas")
      .select(
        "id,enunciado,respuesta_correcta,frecuencia,conflicto_respuesta,tema,explicacion,norma,opciones(letra,texto,es_correcta)",
      )
      .order("id", { ascending: true })
      .range(desde, desde + PAGE_SIZE - 1);

    if (error) {
      throw new Error(`Error descargando el banco: ${error.message}`);
    }
    const filas = (data ?? []) as unknown as FilaPregunta[];
    for (const fila of filas) preguntas.push(mapFila(fila));
    onProgreso?.(preguntas.length);

    if (filas.length < PAGE_SIZE) break;
    desde += PAGE_SIZE;
  }

  return preguntas;
}

/**
 * Descarga la teoría por tema (11 filas: no hace falta paginar). Es material de
 * apoyo, no el banco: si la consulta falla se devuelve `undefined` y la app
 * sigue funcionando sin la card de teoría.
 */
async function descargarTeoria(): Promise<
  Record<string, TeoriaTema> | undefined
> {
  try {
    const { data, error } = await supabase
      .from("temas_teoria")
      .select("slug,titulo,resumen_md");

    if (error || !data) return undefined;

    const teoria: Record<string, TeoriaTema> = {};
    for (const fila of data as unknown as FilaTeoria[]) {
      const resumen = fila.resumen_md?.trim();
      if (!fila.slug || !resumen) continue;
      teoria[fila.slug] = { titulo: fila.titulo ?? "", resumen };
    }
    return Object.keys(teoria).length > 0 ? teoria : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Devuelve el banco. Usa la caché de IndexedDB si existe y es de la versión
 * actual; si no, lo descarga y lo cachea. Con `forzar` re-descarga siempre.
 */
export async function cargarBanco(
  opts: { forzar?: boolean; onProgreso?: ProgresoDescarga } = {},
): Promise<Banco> {
  const { forzar = false, onProgreso } = opts;

  if (!forzar) {
    try {
      const cache = await idbGet<Banco>(CACHE_KEY);
      if (cache && cache.version === BANCO_VERSION && cache.preguntas?.length) {
        return cache;
      }
    } catch {
      // IndexedDB puede fallar (modo privado, etc.): seguimos a la descarga.
    }
  }

  const preguntas = await descargarBanco(onProgreso);
  const teoria = await descargarTeoria();
  const banco: Banco = {
    version: BANCO_VERSION,
    descargadoEn: Date.now(),
    preguntas,
    teoria,
  };

  try {
    await idbSet(CACHE_KEY, banco);
  } catch {
    // Si no se puede cachear, el banco sigue siendo utilizable en memoria.
  }

  return banco;
}
