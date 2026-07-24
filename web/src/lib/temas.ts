// Catálogo de temas del CAP. Copia estática de db/temas.json para tener
// etiquetas y secciones sin depender de la base de datos. La columna `tema`
// de cada pregunta guarda el `slug` correspondiente.

export interface Tema {
  slug: string;
  label: string;
  seccion: string;
  orden: number;
}

export const TEMAS: Tema[] = [
  {
    slug: "motor-transmision",
    label: "El vehículo: motor y transmisión",
    seccion: "Conducción racional y seguridad",
    orden: 1,
  },
  {
    slug: "frenado-seguridad",
    label: "Frenado y dispositivos de seguridad",
    seccion: "Conducción racional y seguridad",
    orden: 2,
  },
  {
    slug: "conduccion-eficiente",
    label: "Conducción eficiente y consumo",
    seccion: "Conducción racional y seguridad",
    orden: 3,
  },
  {
    slug: "carga-estiba",
    label: "Carga, estiba y masas",
    seccion: "Conducción racional y seguridad",
    orden: 4,
  },
  {
    slug: "tiempos-tacografo",
    label: "Tiempos de conducción y tacógrafo",
    seccion: "Reglamentación",
    orden: 5,
  },
  {
    slug: "reglamentacion-documentos",
    label: "Documentos y reglamentación del transporte",
    seccion: "Reglamentación",
    orden: 6,
  },
  {
    slug: "seguridad-vial-accidentes",
    label: "Seguridad vial, accidentes y primeros auxilios",
    seccion: "Salud, seguridad y servicio",
    orden: 7,
  },
  {
    slug: "salud-ergonomia",
    label: "Salud, ergonomía y aptitud",
    seccion: "Salud, seguridad y servicio",
    orden: 8,
  },
  {
    slug: "prevencion-riesgos",
    label: "Prevención de riesgos (robos, tráfico ilegal)",
    seccion: "Salud, seguridad y servicio",
    orden: 9,
  },
  {
    slug: "calidad-servicio",
    label: "Calidad del servicio e imagen de empresa",
    seccion: "Salud, seguridad y servicio",
    orden: 10,
  },
  {
    slug: "entorno-economico",
    label: "Entorno económico y organización",
    seccion: "Salud, seguridad y servicio",
    orden: 11,
  },
];

/** Mapa slug -> Tema para búsquedas O(1). */
const PORINDICE = new Map(TEMAS.map((t) => [t.slug, t]));

/** Devuelve el tema del catálogo por su slug, o undefined si no existe. */
export function temaPorSlug(slug: string): Tema | undefined {
  return PORINDICE.get(slug);
}

export interface GrupoSeccion {
  seccion: string;
  temas: Tema[];
}

/**
 * Agrupa los temas por sección, conservando el orden de aparición de las
 * secciones y ordenando los temas de cada sección por su campo `orden`.
 */
export function temasPorSeccion(): GrupoSeccion[] {
  const grupos: GrupoSeccion[] = [];
  for (const tema of [...TEMAS].sort((a, b) => a.orden - b.orden)) {
    let grupo = grupos.find((g) => g.seccion === tema.seccion);
    if (!grupo) {
      grupo = { seccion: tema.seccion, temas: [] };
      grupos.push(grupo);
    }
    grupo.temas.push(tema);
  }
  return grupos;
}
