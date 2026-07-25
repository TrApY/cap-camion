// Tests de la selección de preguntas del examen (funciones PURAS de lib/exam).
// Se ejecutan con el runner integrado de bun: `bun test`.

import { describe, expect, test } from "bun:test";
import {
  FRECUENCIA_MINIMA_ALTA_PROB,
  construirExamen,
  contarAltaProbPorTema,
  muestrearPonderadoPorFrecuencia,
} from "./exam";
import type { Banco, Pregunta } from "./types";

// --- Helpers ---

/** Pregunta apta (sin conflicto, 4 opciones y la correcta presente). */
function pregunta(
  id: string,
  frecuencia: number,
  tema = "carga-estiba",
  over: Partial<Pregunta> = {},
): Pregunta {
  return {
    id,
    enunciado: `Enunciado de ${id}`,
    opciones: ["uno", "dos", "tres", "cuatro"].map((texto, i) => ({
      letra: "abcd"[i],
      texto: `${texto} (${id})`,
      esCorrecta: i === 0,
    })),
    respuestaCorrecta: "a",
    frecuencia,
    conflicto: false,
    tema,
    explicacion: null,
    norma: null,
    ...over,
  };
}

function banco(preguntas: Pregunta[]): Banco {
  return { version: 1, descargadoEn: 0, preguntas };
}

/** `rand` determinista que recorre una secuencia fija y vuelve a empezar. */
function randSecuencia(valores: number[]): () => number {
  let i = 0;
  return () => valores[i++ % valores.length];
}

// --- muestrearPonderadoPorFrecuencia ---

describe("muestrearPonderadoPorFrecuencia", () => {
  const pool = [
    pregunta("p1", 1),
    pregunta("p2", 2),
    pregunta("p3", 3),
    pregunta("p4", 4),
    pregunta("p5", 5),
  ];

  test("devuelve exactamente n preguntas y sin duplicados", () => {
    const m = muestrearPonderadoPorFrecuencia(pool, 3);
    expect(m).toHaveLength(3);
    expect(new Set(m.map((p) => p.id)).size).toBe(3);
    // Todas las devueltas salen del pool.
    for (const p of m) expect(pool).toContain(p);
  });

  test("con n >= tamaño del pool devuelve todo el pool", () => {
    expect(
      muestrearPonderadoPorFrecuencia(pool, pool.length)
        .map((p) => p.id)
        .sort(),
    ).toEqual(["p1", "p2", "p3", "p4", "p5"]);
    expect(muestrearPonderadoPorFrecuencia(pool, 99)).toHaveLength(5);
  });

  test("con n = 0 (o negativo) devuelve un array vacío", () => {
    expect(muestrearPonderadoPorFrecuencia(pool, 0)).toEqual([]);
    expect(muestrearPonderadoPorFrecuencia(pool, -3)).toEqual([]);
  });

  test("con un pool vacío devuelve un array vacío", () => {
    expect(muestrearPonderadoPorFrecuencia([], 5)).toEqual([]);
  });

  test("no muta el pool de entrada", () => {
    const orden = pool.map((p) => p.id);
    muestrearPonderadoPorFrecuencia(pool, 2);
    expect(pool.map((p) => p.id)).toEqual(orden);
  });

  test("con un rand determinista el resultado es reproducible", () => {
    const valores = [0.9, 0.1, 0.5, 0.2, 0.7];
    const a = muestrearPonderadoPorFrecuencia(pool, 3, randSecuencia(valores));
    const b = muestrearPonderadoPorFrecuencia(pool, 3, randSecuencia(valores));
    expect(a.map((p) => p.id)).toEqual(b.map((p) => p.id));
  });

  test("con rand determinista gana la clave mayor (rand ** (1/frecuencia))", () => {
    // Con el mismo rand para todas, la clave crece con la frecuencia:
    // 0,5**(1/1) < 0,5**(1/2) < … < 0,5**(1/5).
    const m = muestrearPonderadoPorFrecuencia(pool, 2, () => 0.5);
    expect(m.map((p) => p.id)).toEqual(["p5", "p4"]);
  });

  test("una frecuencia corrupta (< 1) se trata como 1 y no rompe el muestreo", () => {
    const raro = [
      pregunta("cero", 0),
      pregunta("negativa", -5),
      pregunta("normal", 1),
    ];
    const m = muestrearPonderadoPorFrecuencia(raro, 2, () => 0.5);
    expect(m).toHaveLength(2);
    // Todas con peso 1 ⇒ misma clave, ninguna queda con clave NaN/Infinity.
    expect(m.every((p) => raro.includes(p))).toBe(true);
  });

  test("una pregunta muy frecuente sale casi siempre frente a muchas de frecuencia 1", () => {
    const conFavorita = [
      pregunta("favorita", 40),
      ...Array.from({ length: 19 }, (_, i) => pregunta(`rell${i}`, 1)),
    ];
    let veces = 0;
    for (let i = 0; i < 200; i++) {
      const m = muestrearPonderadoPorFrecuencia(conFavorita, 5);
      if (m.some((p) => p.id === "favorita")) veces++;
    }
    // Margen holgado a propósito: la probabilidad real ronda el 98 %, así que
    // 140/200 no puede fallar por azar sin que el sesgo esté roto de verdad.
    expect(veces).toBeGreaterThan(140);
  });

  test("un pool de frecuencias iguales sigue variando entre muestras", () => {
    // 30 preguntas idénticas en peso: el muestreo no debe ser determinista.
    const iguales = Array.from({ length: 30 }, (_, i) => pregunta(`q${i}`, 2));
    const combinaciones = new Set<string>();
    for (let i = 0; i < 30; i++) {
      combinaciones.add(
        muestrearPonderadoPorFrecuencia(iguales, 5)
          .map((p) => p.id)
          .sort()
          .join(","),
      );
    }
    expect(combinaciones.size).toBeGreaterThan(1);
  });
});

// --- construirExamen con altaProbabilidad ---

describe("construirExamen (modo alta probabilidad)", () => {
  test("el umbral del pool son 2 exámenes", () => {
    expect(FRECUENCIA_MINIMA_ALTA_PROB).toBe(2);
  });

  test("si el pool de repetidas cubre n, todas las elegidas tienen frecuencia >= 2", () => {
    const b = banco([
      ...Array.from({ length: 10 }, (_, i) => pregunta(`alta${i}`, 2 + (i % 4))),
      ...Array.from({ length: 10 }, (_, i) => pregunta(`baja${i}`, 1)),
    ]);
    const ex = construirExamen(b, {
      numPreguntas: 8,
      altaProbabilidad: true,
      modo: "real",
    });
    expect(ex).toHaveLength(8);
    expect(
      ex.every((p) => p.frecuencia >= FRECUENCIA_MINIMA_ALTA_PROB),
    ).toBe(true);
  });

  test("si el pool no cubre n, completa con las de frecuencia 1 sin duplicados", () => {
    const b = banco([
      pregunta("alta1", 3),
      pregunta("alta2", 5),
      ...Array.from({ length: 10 }, (_, i) => pregunta(`baja${i}`, 1)),
    ]);
    const ex = construirExamen(b, {
      numPreguntas: 6,
      altaProbabilidad: true,
      modo: "real",
    });
    expect(ex).toHaveLength(6);
    expect(new Set(ex.map((p) => p.id)).size).toBe(6);
    // Las 2 del pool entran siempre; el resto sale del relleno.
    expect(ex.map((p) => p.id)).toContain("alta1");
    expect(ex.map((p) => p.id)).toContain("alta2");
    expect(ex.filter((p) => p.frecuencia === 1)).toHaveLength(4);
  });

  test("sin ninguna pregunta repetida cae entero en el relleno", () => {
    const b = banco(
      Array.from({ length: 5 }, (_, i) => pregunta(`baja${i}`, 1)),
    );
    const ex = construirExamen(b, {
      numPreguntas: 3,
      altaProbabilidad: true,
      modo: "real",
    });
    expect(ex).toHaveLength(3);
    expect(new Set(ex.map((p) => p.id)).size).toBe(3);
  });

  test("nunca devuelve más preguntas que aptas hay, aunque se pidan más", () => {
    const b = banco([
      pregunta("alta1", 4),
      pregunta("baja1", 1),
      // No aptas: no deben contarse ni aparecer.
      pregunta("conflictiva", 9, "carga-estiba", { conflicto: true }),
      pregunta("sinCorrecta", 9, "carga-estiba", {
        respuestaCorrecta: null,
        opciones: [
          { letra: "a", texto: "uno", esCorrecta: false },
          { letra: "b", texto: "dos", esCorrecta: false },
        ],
      }),
    ]);
    const ex = construirExamen(b, {
      numPreguntas: 50,
      altaProbabilidad: true,
      modo: "real",
    });
    expect(ex.map((p) => p.id).sort()).toEqual(["alta1", "baja1"]);
  });

  test("respeta el filtro por tema", () => {
    const b = banco([
      pregunta("t1a", 4, "tiempos-tacografo"),
      pregunta("t1b", 3, "tiempos-tacografo"),
      pregunta("t1c", 1, "tiempos-tacografo"),
      pregunta("t2a", 9, "carga-estiba"),
      pregunta("t2b", 8, "carga-estiba"),
    ]);
    const ex = construirExamen(b, {
      numPreguntas: 3,
      altaProbabilidad: true,
      modo: "practica",
      tema: "tiempos-tacografo",
    });
    expect(ex).toHaveLength(3);
    expect(ex.every((p) => p.tema === "tiempos-tacografo")).toBe(true);
    // El relleno también respeta el tema: la de frecuencia 1 entra, las de otro
    // tema no, por muy frecuentes que sean.
    expect(ex.map((p) => p.id).sort()).toEqual(["t1a", "t1b", "t1c"]);
  });

  test("con un banco sin preguntas aptas devuelve un examen vacío", () => {
    const b = banco([pregunta("mala", 5, "carga-estiba", { conflicto: true })]);
    expect(
      construirExamen(b, {
        numPreguntas: 10,
        altaProbabilidad: true,
        modo: "real",
      }),
    ).toEqual([]);
  });

  test("sin alta probabilidad puede devolver preguntas de frecuencia 1", () => {
    // Con 1 sola repetida y 30 de frecuencia 1, en modo normal es casi seguro
    // que aparecen preguntas de frecuencia 1 en un test de 10.
    const b = banco([
      pregunta("alta1", 9),
      ...Array.from({ length: 30 }, (_, i) => pregunta(`baja${i}`, 1)),
    ]);
    const ex = construirExamen(b, {
      numPreguntas: 10,
      altaProbabilidad: false,
      modo: "real",
    });
    expect(ex).toHaveLength(10);
    expect(ex.some((p) => p.frecuencia === 1)).toBe(true);
  });
});

// --- contarAltaProbPorTema ---

describe("contarAltaProbPorTema", () => {
  test("cuenta solo las aptas con frecuencia >= 2, agrupadas por tema", () => {
    const b = banco([
      pregunta("a", 2, "carga-estiba"),
      pregunta("b", 7, "carga-estiba"),
      pregunta("c", 1, "carga-estiba"),
      pregunta("d", 3, "tiempos-tacografo"),
      pregunta("e", 1, "tiempos-tacografo"),
      pregunta("f", 1, "salud-ergonomia"),
    ]);
    expect(contarAltaProbPorTema(b)).toEqual({
      "carga-estiba": 2,
      "tiempos-tacografo": 1,
    });
  });

  test("excluye las no aptas y las preguntas sin tema", () => {
    const b = banco([
      pregunta("conflictiva", 9, "carga-estiba", { conflicto: true }),
      pregunta("sinTema", 9, ""),
      pregunta("buena", 4, "carga-estiba"),
    ]);
    expect(contarAltaProbPorTema(b)).toEqual({ "carga-estiba": 1 });
  });

  test("con un banco vacío devuelve un objeto vacío", () => {
    expect(contarAltaProbPorTema(banco([]))).toEqual({});
  });
});
