// Tests del markdown minimalista de los resúmenes de teoría.
// Se ejecutan con el runner integrado de bun: `bun test`.

import { describe, expect, test } from "bun:test";
import { parseMarkdownSencillo, parseNegritas } from "./markdown";

/** Texto plano de un bloque, ignorando el énfasis. */
function texto(fragmentos: { texto: string }[]): string {
  return fragmentos.map((f) => f.texto).join("");
}

describe("parseNegritas", () => {
  test("texto sin marcas es un único fragmento normal", () => {
    expect(parseNegritas("Sin énfasis")).toEqual([
      { texto: "Sin énfasis", negrita: false },
    ]);
  });

  test("parte en fragmentos con y sin negrita", () => {
    expect(parseNegritas("El **tacógrafo** registra")).toEqual([
      { texto: "El ", negrita: false },
      { texto: "tacógrafo", negrita: true },
      { texto: " registra", negrita: false },
    ]);
  });

  test("varias negritas en la misma línea", () => {
    const frags = parseNegritas("**Par** frente a **potencia**.");
    expect(frags.filter((f) => f.negrita).map((f) => f.texto)).toEqual([
      "Par",
      "potencia",
    ]);
    expect(texto(frags)).toBe("Par frente a potencia.");
  });

  test("marca sin cerrar se queda como texto plano", () => {
    expect(parseNegritas("Ojo **con esto")).toEqual([
      { texto: "Ojo **con esto", negrita: false },
    ]);
  });

  test("texto vacío no produce fragmentos", () => {
    expect(parseNegritas("")).toEqual([]);
  });
});

describe("parseMarkdownSencillo", () => {
  test("texto vacío o en blanco no produce bloques", () => {
    expect(parseMarkdownSencillo("")).toEqual([]);
    expect(parseMarkdownSencillo("   \n\n  \n")).toEqual([]);
  });

  test("líneas seguidas forman un solo párrafo", () => {
    const bloques = parseMarkdownSencillo("El motor genera par\ny potencia.");
    expect(bloques).toHaveLength(1);
    expect(bloques[0].tipo).toBe("parrafo");
    if (bloques[0].tipo !== "parrafo") throw new Error("bloque inesperado");
    expect(texto(bloques[0].contenido)).toBe("El motor genera par y potencia.");
  });

  test("una línea en blanco separa párrafos", () => {
    const bloques = parseMarkdownSencillo("Primero.\n\nSegundo.");
    expect(bloques.map((b) => b.tipo)).toEqual(["parrafo", "parrafo"]);
  });

  test("líneas con - o * forman una lista", () => {
    const bloques = parseMarkdownSencillo("- Uno\n* Dos\n- Tres");
    expect(bloques).toHaveLength(1);
    if (bloques[0].tipo !== "lista") throw new Error("se esperaba una lista");
    expect(bloques[0].items.map(texto)).toEqual(["Uno", "Dos", "Tres"]);
  });

  test("una línea en blanco corta la lista en dos", () => {
    const bloques = parseMarkdownSencillo("- Uno\n\n- Dos");
    expect(bloques.map((b) => b.tipo)).toEqual(["lista", "lista"]);
  });

  test("## es un subtítulo y no arrastra el resto", () => {
    const bloques = parseMarkdownSencillo("## Par y potencia\nEl motor genera par.");
    expect(bloques.map((b) => b.tipo)).toEqual(["subtitulo", "parrafo"]);
    if (bloques[0].tipo !== "subtitulo") throw new Error("se esperaba subtítulo");
    expect(texto(bloques[0].contenido)).toBe("Par y potencia");
  });

  test("las negritas se conservan dentro de listas y subtítulos", () => {
    const bloques = parseMarkdownSencillo("## **Ojo**\n- La pausa es de **45 minutos**.");
    if (bloques[0].tipo !== "subtitulo") throw new Error("se esperaba subtítulo");
    expect(bloques[0].contenido).toEqual([{ texto: "Ojo", negrita: true }]);
    if (bloques[1].tipo !== "lista") throw new Error("se esperaba una lista");
    expect(bloques[1].items[0].filter((f) => f.negrita).map((f) => f.texto)).toEqual([
      "45 minutos",
    ]);
  });

  test("mezcla real: párrafo, lista, subtítulo y párrafo final", () => {
    const md = [
      "Introducción del tema.",
      "",
      "- Primer punto",
      "- Segundo punto",
      "## Detalle",
      "Cierre del tema.",
    ].join("\n");
    const bloques = parseMarkdownSencillo(md);
    expect(bloques.map((b) => b.tipo)).toEqual([
      "parrafo",
      "lista",
      "subtitulo",
      "parrafo",
    ]);
    if (bloques[1].tipo !== "lista") throw new Error("se esperaba una lista");
    expect(bloques[1].items).toHaveLength(2);
  });

  test("un párrafo tras una lista sin línea en blanco cierra la lista", () => {
    const bloques = parseMarkdownSencillo("- Uno\nTexto suelto");
    expect(bloques.map((b) => b.tipo)).toEqual(["lista", "parrafo"]);
  });

  test("las marcas se ignoran si no van al principio de la línea", () => {
    const bloques = parseMarkdownSencillo("El eje - trasero ## no es título");
    expect(bloques.map((b) => b.tipo)).toEqual(["parrafo"]);
  });
});
