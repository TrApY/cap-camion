// Tests de las funciones PURAS de la sincronización con la nube (nada de
// Supabase ni de IndexedDB aquí). Se ejecutan con `bun test`.
//
// `lib/supabase.ts` exige las variables NEXT_PUBLIC_* al cargarse y `bun test`
// corre con NODE_ENV=test, que no lee `.env.local`: se rellenan con valores de
// relleno ANTES de importar los módulos (de ahí los imports dinámicos). Ninguna
// de las funciones probadas hace red.
process.env.NEXT_PUBLIC_SUPABASE_URL ??= "http://localhost:54321";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??= "clave-de-relleno-para-tests";

import { describe, expect, test } from "bun:test";
import type { SesionGuardada } from "./stats";
import type { OpcionExamen, PreguntaExamen, ResultadoPregunta } from "./types";

const { construirFilasSync } = await import("./sync");
const { NICK_REGEX } = await import("./auth");

// --- Helpers ---

function sesion(over: Partial<SesionGuardada> = {}): SesionGuardada {
  return {
    fecha: 1_700_000_000_000,
    tipo: "general",
    modo: "real",
    total: 3,
    aciertos: 2,
    fallos: 1,
    enBlanco: 0,
    puntuacionSobre100: 50,
    aprobado: true,
    tiempoMs: 90_000,
    ...over,
  };
}

/** Pregunta de examen con las opciones que se le indiquen (letra original + acierto). */
function pregunta(id: string, opciones: OpcionExamen[]): PreguntaExamen {
  return {
    id,
    enunciado: `Enunciado de ${id}`,
    frecuencia: 1,
    tema: "frenado-seguridad",
    explicacion: null,
    norma: null,
    opciones,
  };
}

function opcion(letra: string, esCorrecta = false): OpcionExamen {
  return { letra, texto: `Texto ${letra}`, esCorrecta };
}

function resultado(
  preguntaExamen: PreguntaExamen,
  elegidaIndex: number | null,
): ResultadoPregunta {
  return {
    pregunta: preguntaExamen,
    elegidaIndex,
    acertada:
      elegidaIndex !== null &&
      preguntaExamen.opciones[elegidaIndex]?.esCorrecta === true,
  };
}

// --- construirFilasSync: intento ---

describe("construirFilasSync (intento)", () => {
  test("mapea la sesión completa al esquema SQL", () => {
    const { intento } = construirFilasSync(
      sesion({
        modo: "practica",
        total: 30,
        aciertos: 20,
        fallos: 6,
        enBlanco: 4,
        puntuacionSobre100: 56.666,
        tiempoMs: 600_000,
      }),
      [],
    );

    expect(intento).toEqual({
      modo: "practica",
      tipo: "general",
      total: 30,
      aciertos: 20,
      fallos: 6,
      en_blanco: 4,
      tiempo_ms: 600_000,
      nota: 56.666,
      started_at: "2023-11-14T22:03:20.000Z",
      finished_at: "2023-11-14T22:13:20.000Z",
    });
  });

  test("la nota es la puntuación sobre 100 del baremo oficial", () => {
    const { intento } = construirFilasSync(
      sesion({ puntuacionSobre100: 33.5 }),
      [],
    );
    expect(intento.nota).toBe(33.5);
  });

  test("started_at = fin − tiempo empleado, finished_at = fin", () => {
    const fecha = Date.UTC(2026, 6, 25, 12, 0, 0);
    const { intento } = construirFilasSync(
      sesion({ fecha, tiempoMs: 3_600_000 }),
      [],
    );
    expect(intento.finished_at).toBe("2026-07-25T12:00:00.000Z");
    expect(intento.started_at).toBe("2026-07-25T11:00:00.000Z");
    expect(
      Date.parse(intento.finished_at) - Date.parse(intento.started_at),
    ).toBe(3_600_000);
  });

  test("incluye el tema solo en los tests de tipo 'tema'", () => {
    const conTema = construirFilasSync(
      sesion({ tipo: "tema", tema: "frenado-seguridad" }),
      [],
    ).intento;
    expect(conTema.tema).toBe("frenado-seguridad");

    // Un tema colado en un test general no debe viajar a la base de datos.
    const general = construirFilasSync(
      sesion({ tipo: "general", tema: "frenado-seguridad" }),
      [],
    ).intento;
    expect("tema" in general).toBe(false);

    const repaso = construirFilasSync(sesion({ tipo: "repaso" }), []).intento;
    expect("tema" in repaso).toBe(false);
  });

  test("un tipo 'tema' sin slug no inventa el campo", () => {
    const { intento } = construirFilasSync(sesion({ tipo: "tema" }), []);
    expect("tema" in intento).toBe(false);
  });
});

// --- construirFilasSync: respuestas ---

describe("construirFilasSync (respuestas)", () => {
  test("guarda la letra ORIGINAL aunque las opciones estén barajadas", () => {
    // Presentación barajada: la correcta del banco ("c") va en primera posición.
    const p = pregunta("p1", [
      opcion("c", true),
      opcion("a"),
      opcion("d"),
      opcion("b"),
    ]);
    const { respuestas } = construirFilasSync(sesion(), [
      resultado(p, 0), // eligió la primera de la pantalla, que es la "c"
    ]);

    expect(respuestas).toEqual([
      { pregunta_id: "p1", letra_elegida: "c", correcta: true },
    ]);
  });

  test("una elección incorrecta guarda su letra y correcta=false", () => {
    const p = pregunta("p2", [opcion("b"), opcion("a", true)]);
    const { respuestas } = construirFilasSync(sesion(), [resultado(p, 0)]);
    expect(respuestas).toEqual([
      { pregunta_id: "p2", letra_elegida: "b", correcta: false },
    ]);
  });

  test("en blanco → letra_elegida y correcta a null (no es un fallo)", () => {
    const p = pregunta("p3", [opcion("a", true), opcion("b")]);
    const { respuestas } = construirFilasSync(sesion(), [resultado(p, null)]);
    expect(respuestas).toEqual([
      { pregunta_id: "p3", letra_elegida: null, correcta: null },
    ]);
  });

  test("conserva el orden y una fila por pregunta", () => {
    const p1 = pregunta("p1", [opcion("a", true), opcion("b")]);
    const p2 = pregunta("p2", [opcion("d"), opcion("c", true)]);
    const p3 = pregunta("p3", [opcion("a"), opcion("b", true)]);

    const { respuestas } = construirFilasSync(sesion({ total: 3 }), [
      resultado(p1, 0),
      resultado(p2, 1),
      resultado(p3, null),
    ]);

    expect(respuestas.map((r) => r.pregunta_id)).toEqual(["p1", "p2", "p3"]);
    expect(respuestas.map((r) => r.letra_elegida)).toEqual(["a", "c", null]);
    expect(respuestas.map((r) => r.correcta)).toEqual([true, true, null]);
  });

  test("un índice elegido fuera de rango deja la letra en null", () => {
    const p = pregunta("p4", [opcion("a", true)]);
    const { respuestas } = construirFilasSync(sesion(), [resultado(p, 5)]);
    expect(respuestas[0].letra_elegida).toBeNull();
    expect(respuestas[0].correcta).toBe(false);
  });

  test("sin resultados devuelve una lista vacía", () => {
    expect(construirFilasSync(sesion(), []).respuestas).toEqual([]);
  });
});

// --- NICK_REGEX ---

describe("NICK_REGEX", () => {
  test("acepta los nicks válidos", () => {
    for (const nick of [
      "abc",
      "JoTa",
      "JoTa_89",
      "jota-89",
      "___",
      "---",
      "A1b2C3",
      "a".repeat(20),
    ]) {
      expect(NICK_REGEX.test(nick)).toBe(true);
    }
  });

  test("rechaza los nicks inválidos", () => {
    for (const nick of [
      "", // vacío
      "ab", // demasiado corto
      "a".repeat(21), // demasiado largo
      "con espacio",
      " jota",
      "jota ",
      "josé", // acento
      "ñandú", // ñ
      "jota!", // símbolo
      "jota.89", // punto
      "jota@89",
      "jota\n", // salto de línea
    ]) {
      expect(NICK_REGEX.test(nick)).toBe(false);
    }
  });

  test("es la misma expresión que el CHECK de la migración 0003", () => {
    expect(NICK_REGEX.source).toBe("^[A-Za-z0-9_-]{3,20}$");
  });
});
