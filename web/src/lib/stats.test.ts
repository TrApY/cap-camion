// Tests de las funciones PURAS de estadísticas (nada de IndexedDB aquí).
// Se ejecutan con el runner integrado de bun: `bun test`.

import { describe, expect, test } from "bun:test";
import {
  aplicarResultado,
  contarDominadas,
  estadisticasPorTema,
  prediccion,
  resumenGlobal,
  type ProgresoPregunta,
  type SesionGuardada,
} from "./stats";

// --- Helpers ---

function progreso(over: Partial<ProgresoPregunta> = {}): ProgresoPregunta {
  return {
    preguntaId: "p1",
    tema: "frenado-seguridad",
    vistas: 0,
    aciertos: 0,
    fallos: 0,
    enBlanco: 0,
    racha: 0,
    ultimaVez: 0,
    ...over,
  };
}

/** Sesión con `total` respuestas de las que `aciertos` son buenas y `fallos` malas. */
function sesion(
  fecha: number,
  total: number,
  aciertos: number,
  fallos: number,
  over: Partial<SesionGuardada> = {},
): SesionGuardada {
  return {
    fecha,
    tipo: "general",
    modo: "real",
    total,
    aciertos,
    fallos,
    enBlanco: total - aciertos - fallos,
    puntuacionSobre100:
      total > 0 ? ((aciertos - 0.5 * fallos) / total) * 100 : 0,
    aprobado: aciertos - 0.5 * fallos >= total * 0.5,
    tiempoMs: 60_000,
    ...over,
  };
}

// --- aplicarResultado ---

describe("aplicarResultado", () => {
  const acierto = {
    preguntaId: "p1",
    tema: "frenado-seguridad",
    acertada: true,
    enBlanco: false,
  };
  const fallo = { ...acierto, acertada: false };
  const blanco = { ...acierto, acertada: false, enBlanco: true };

  test("crea el registro cuando no había previo", () => {
    const r = aplicarResultado(undefined, acierto, 1_000);
    expect(r).toEqual({
      preguntaId: "p1",
      tema: "frenado-seguridad",
      vistas: 1,
      aciertos: 1,
      fallos: 0,
      enBlanco: 0,
      racha: 1,
      ultimaVez: 1_000,
    });
  });

  test("un acierto suma a la racha", () => {
    const r = aplicarResultado(
      progreso({ vistas: 3, aciertos: 2, racha: 2 }),
      acierto,
      2_000,
    );
    expect(r.aciertos).toBe(3);
    expect(r.racha).toBe(3);
    expect(r.vistas).toBe(4);
  });

  test("un fallo resetea la racha y cuenta como fallo", () => {
    const r = aplicarResultado(
      progreso({ vistas: 5, aciertos: 4, racha: 4 }),
      fallo,
      3_000,
    );
    expect(r.racha).toBe(0);
    expect(r.fallos).toBe(1);
    expect(r.enBlanco).toBe(0);
    expect(r.aciertos).toBe(4);
  });

  test("un blanco resetea la racha y cuenta como en blanco (no como fallo)", () => {
    const r = aplicarResultado(
      progreso({ vistas: 2, aciertos: 2, racha: 2 }),
      blanco,
      4_000,
    );
    expect(r.racha).toBe(0);
    expect(r.enBlanco).toBe(1);
    expect(r.fallos).toBe(0);
  });

  test("vistas y ultimaVez avanzan siempre", () => {
    let r = aplicarResultado(undefined, acierto, 10);
    r = aplicarResultado(r, fallo, 20);
    r = aplicarResultado(r, blanco, 30);
    expect(r.vistas).toBe(3);
    expect(r.ultimaVez).toBe(30);
    expect(r.aciertos + r.fallos + r.enBlanco).toBe(r.vistas);
  });
});

// --- prediccion ---

describe("prediccion", () => {
  test("sin sesiones el estado es insuficiente y faltan 50 respuestas", () => {
    const p = prediccion([]);
    expect(p.estado).toBe("insuficiente");
    expect(p.faltan).toBe(50);
    expect(p.color).toBe("neutro");
    expect(p.nota).toBe(0);
  });

  test("con menos de 50 respuestas sigue siendo insuficiente", () => {
    const p = prediccion([sesion(1, 30, 30, 0), sesion(2, 19, 19, 0)]);
    expect(p.estado).toBe("insuficiente");
    expect(p.respuestas).toBe(49);
    expect(p.faltan).toBe(1);
  });

  test("con 50 respuestas ya calcula la nota penalizando los fallos", () => {
    // 30 aciertos, 20 fallos → (30 - 10) / 50 * 100 = 40
    const p = prediccion([sesion(1, 50, 30, 20)]);
    expect(p.estado).toBe("listo");
    expect(p.nota).toBeCloseTo(40, 10);
    expect(p.respuestas).toBe(50);
    expect(p.color).toBe("rojo");
    expect(p.mensaje).toBe("Te faltan 10 puntos");
  });

  test("solo tiene en cuenta las últimas 10 sesiones", () => {
    // 5 sesiones antiguas perfectas + 10 recientes mediocres: solo cuentan estas.
    const antiguas = [1, 2, 3, 4, 5].map((i) => sesion(i, 20, 20, 0));
    const recientes = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map((i) =>
      sesion(i, 10, 6, 4),
    );
    const p = prediccion([...recientes, ...antiguas]); // desordenadas a propósito
    expect(p.sesiones).toBe(10);
    expect(p.respuestas).toBe(100);
    // 60 aciertos, 40 fallos → (60 - 20) / 100 * 100 = 40
    expect(p.nota).toBeCloseTo(40, 10);
  });

  test("frontera verde: 55 puntos exactos", () => {
    // 100 respuestas: 70 aciertos, 30 fallos → 70 - 15 = 55
    const p = prediccion([sesion(1, 100, 70, 30)]);
    expect(p.nota).toBeCloseTo(55, 10);
    expect(p.color).toBe("verde");
    expect(p.mensaje).toBe("Hoy aprobarías");
  });

  test("frontera ámbar: 45 puntos exactos", () => {
    // 100 respuestas: 63 aciertos, 36 fallos, 1 en blanco → 63 - 18 = 45
    const p = prediccion([sesion(1, 100, 63, 36)]);
    expect(p.nota).toBeCloseTo(45, 10);
    expect(p.color).toBe("ambar");
    expect(p.mensaje).toBe("Al límite — sigue practicando");
  });

  test("frontera roja: 44,9 puntos", () => {
    // 1000 respuestas: 633 aciertos, 366 fallos → 633 - 183 = 450 → 45,0... ajustamos
    // 1000 respuestas: 632 aciertos, 366 fallos → 632 - 183 = 449 → 44,9
    const p = prediccion([sesion(1, 1000, 632, 366)]);
    expect(p.nota).toBeCloseTo(44.9, 10);
    expect(p.color).toBe("rojo");
    expect(p.mensaje).toBe("Te faltan 5,1 puntos");
  });

  test("la nota se recorta a 0 cuando el neto es negativo", () => {
    // 60 respuestas: 10 aciertos, 50 fallos → 10 - 25 = -15 → -25 sobre 100
    const p = prediccion([sesion(1, 60, 10, 50)]);
    expect(p.nota).toBe(0);
    expect(p.color).toBe("rojo");
    expect(p.mensaje).toBe("Te faltan 50 puntos");
  });
});

// --- estadisticasPorTema ---

describe("estadisticasPorTema", () => {
  test("agrega por tema y ordena de peor a mejor porcentaje", () => {
    const stats = estadisticasPorTema([
      progreso({ preguntaId: "a", tema: "carga-estiba", vistas: 4, aciertos: 3 }),
      progreso({ preguntaId: "b", tema: "carga-estiba", vistas: 6, aciertos: 6 }),
      progreso({
        preguntaId: "c",
        tema: "tiempos-tacografo",
        vistas: 10,
        aciertos: 2,
      }),
      progreso({
        preguntaId: "d",
        tema: "salud-ergonomia",
        vistas: 2,
        aciertos: 1,
      }),
    ]);

    expect(stats.map((s) => s.slug)).toEqual([
      "tiempos-tacografo", // 20 %
      "salud-ergonomia", // 50 %
      "carga-estiba", // 90 %
    ]);
    const cargaEstiba = stats[2];
    expect(cargaEstiba.respuestas).toBe(10);
    expect(cargaEstiba.aciertos).toBe(9);
    expect(cargaEstiba.porcentaje).toBeCloseTo(90, 10);
  });

  test("excluye temas sin respuestas y preguntas sin tema", () => {
    const stats = estadisticasPorTema([
      progreso({ preguntaId: "a", tema: "carga-estiba", vistas: 0, aciertos: 0 }),
      progreso({ preguntaId: "b", tema: "", vistas: 5, aciertos: 5 }),
      progreso({
        preguntaId: "c",
        tema: "motor-transmision",
        vistas: 1,
        aciertos: 0,
      }),
    ]);
    expect(stats.map((s) => s.slug)).toEqual(["motor-transmision"]);
  });
});

// --- contarDominadas ---

describe("contarDominadas", () => {
  test("cuenta solo las preguntas con racha >= 2", () => {
    const n = contarDominadas([
      progreso({ preguntaId: "a", racha: 2 }),
      progreso({ preguntaId: "b", racha: 5 }),
      progreso({ preguntaId: "c", racha: 1 }),
      progreso({ preguntaId: "d", racha: 0 }),
    ]);
    expect(n).toBe(2);
  });

  test("sin progreso devuelve 0", () => {
    expect(contarDominadas([])).toBe(0);
  });
});

// --- resumenGlobal ---

describe("resumenGlobal", () => {
  test("suma tests, respuestas, aciertos y tiempo", () => {
    const r = resumenGlobal([
      sesion(1, 30, 20, 8, { tiempoMs: 600_000 }),
      sesion(2, 20, 15, 5, { tiempoMs: 300_000 }),
      sesion(3, 50, 25, 20, { tiempoMs: 900_000 }),
    ]);
    expect(r.tests).toBe(3);
    expect(r.respuestas).toBe(100);
    expect(r.aciertos).toBe(60);
    expect(r.porcentajeAcierto).toBeCloseTo(60, 10);
    expect(r.tiempoMs).toBe(1_800_000);
  });

  test("sin sesiones devuelve ceros sin dividir por cero", () => {
    const r = resumenGlobal([]);
    expect(r).toEqual({
      tests: 0,
      respuestas: 0,
      aciertos: 0,
      porcentajeAcierto: 0,
      tiempoMs: 0,
    });
  });
});
