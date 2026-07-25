// Markdown MINIMALISTA para los resúmenes de teoría (lib de terceros: ninguna).
//
// Solo se soporta lo que de verdad usan los resúmenes generados:
//   * `## Subtítulo`      -> subtítulo (también `#`, `###`… se tratan igual)
//   * `- item` / `* item` -> ítems de una lista; líneas seguidas = una lista
//   * línea en blanco     -> separa bloques
//   * `**negrita**`       -> énfasis dentro de cualquier bloque
// Cualquier otra cosa se muestra como texto plano: nunca se interpreta HTML,
// así que el resumen no puede inyectar marcado en la página.

/** Trozo de texto de un bloque, con o sin énfasis. */
export interface Fragmento {
  texto: string;
  negrita: boolean;
}

export type Bloque =
  | { tipo: "subtitulo"; contenido: Fragmento[] }
  | { tipo: "parrafo"; contenido: Fragmento[] }
  | { tipo: "lista"; items: Fragmento[][] };

const RE_SUBTITULO = /^#{1,6}\s+(.*)$/;
const RE_ITEM = /^[-*]\s+(.*)$/;

/**
 * Parte el texto en fragmentos con y sin negrita (`**así**`).
 * Los `**` sin pareja se dejan tal cual como texto: no se pierde contenido.
 */
export function parseNegritas(texto: string): Fragmento[] {
  const fragmentos: Fragmento[] = [];
  let resto = texto;

  for (;;) {
    const abre = resto.indexOf("**");
    if (abre === -1) break;
    const cierra = resto.indexOf("**", abre + 2);
    if (cierra === -1) break;

    const previo = resto.slice(0, abre);
    const dentro = resto.slice(abre + 2, cierra);
    // `****` (marca vacía) no aporta nada: se ignora el par.
    if (previo) fragmentos.push({ texto: previo, negrita: false });
    if (dentro) fragmentos.push({ texto: dentro, negrita: true });
    resto = resto.slice(cierra + 2);
  }

  if (resto) fragmentos.push({ texto: resto, negrita: false });
  return fragmentos;
}

/**
 * Convierte markdown sencillo en bloques listos para pintar. Función PURA:
 * misma entrada, misma salida, sin tocar el DOM.
 */
export function parseMarkdownSencillo(md: string): Bloque[] {
  const bloques: Bloque[] = [];
  // Párrafo en construcción: sus líneas se unen con un espacio.
  let parrafo: string[] = [];
  // Lista en construcción.
  let items: string[] = [];

  function cerrarParrafo() {
    if (parrafo.length === 0) return;
    bloques.push({
      tipo: "parrafo",
      contenido: parseNegritas(parrafo.join(" ")),
    });
    parrafo = [];
  }

  function cerrarLista() {
    if (items.length === 0) return;
    bloques.push({ tipo: "lista", items: items.map(parseNegritas) });
    items = [];
  }

  function cerrarTodo() {
    cerrarParrafo();
    cerrarLista();
  }

  for (const linea of (md ?? "").split("\n")) {
    const texto = linea.trim();

    if (!texto) {
      cerrarTodo();
      continue;
    }

    const subtitulo = RE_SUBTITULO.exec(texto);
    if (subtitulo) {
      cerrarTodo();
      const contenido = parseNegritas(subtitulo[1].trim());
      if (contenido.length > 0) bloques.push({ tipo: "subtitulo", contenido });
      continue;
    }

    const item = RE_ITEM.exec(texto);
    if (item) {
      // Un ítem interrumpe el párrafo, pero continúa la lista abierta.
      cerrarParrafo();
      items.push(item[1].trim());
      continue;
    }

    // Línea normal: cierra una lista abierta y alimenta el párrafo.
    cerrarLista();
    parrafo.push(texto);
  }

  cerrarTodo();
  return bloques;
}
