// Tests de las funciones PURAS de estadísticas (nada de IndexedDB aquí).
// Se ejecutan con el runner integrado de bun: `bun test`.

import { describe, expect, test } from "bun:test";
import {
  EF_INICIAL,
  EF_MAX,
  EF_MIN,
  MS_DIA,
  aplicarResultado,
  contarDominadas,
  estadisticasPorTema,
  estadoRepaso,
  prediccion,
  resumenGlobal,
  type ProgresoPregunta,
  type SesionGuardada,
} from "./stats";
import { prepararPreguntas } from "./exam";
import type { Pregunta } from "./types";

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
      ef: EF_INICIAL,
      intervaloDias: 1,
      vencimiento: 1_000 + MS_DIA,
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

// --- aplicarResultado: programación SM-2 ---

describe("aplicarResultado (SM-2)", () => {
  const acierto = {
    preguntaId: "p1",
    tema: "frenado-seguridad",
    acertada: true,
    enBlanco: false,
  };
  const fallo = { ...acierto, acertada: false };
  const blanco = { ...acierto, acertada: false, enBlanco: true };

  test("el primer acierto programa la pregunta a 1 día", () => {
    const r = aplicarResultado(undefined, acierto, 1_000);
    expect(r.racha).toBe(1);
    expect(r.intervaloDias).toBe(1);
    expect(r.vencimiento).toBe(1_000 + MS_DIA);
  });

  test("el segundo acierto seguido la programa a 6 días", () => {
    const primero = aplicarResultado(undefined, acierto, 1_000);
    const r = aplicarResultado(primero, acierto, 2_000);
    expect(r.racha).toBe(2);
    expect(r.intervaloDias).toBe(6);
    expect(r.vencimiento).toBe(2_000 + 6 * MS_DIA);
  });

  test("del tercer acierto en adelante el intervalo se multiplica por el ef", () => {
    let r = aplicarResultado(undefined, acierto, 0);
    r = aplicarResultado(r, acierto, 0);
    r = aplicarResultado(r, acierto, 0);
    expect(r.racha).toBe(3);
    expect(r.ef).toBe(EF_MAX);
    // round(6 × 2,5) = 15
    expect(r.intervaloDias).toBe(15);
    expect(r.vencimiento).toBe(15 * MS_DIA);
  });

  test("un fallo devuelve la pregunta a la cola y baja el ef 0,2", () => {
    const previo = progreso({
      vistas: 2,
      aciertos: 2,
      racha: 2,
      ef: EF_INICIAL,
      intervaloDias: 6,
      vencimiento: 6 * MS_DIA,
    });
    const r = aplicarResultado(previo, fallo, 9_000);
    expect(r.intervaloDias).toBe(0);
    expect(r.vencimiento).toBe(9_000);
    expect(r.ef).toBeCloseTo(EF_INICIAL - 0.2, 10);
  });

  test("un blanco reprograma igual que un fallo", () => {
    const previo = progreso({
      vistas: 2,
      aciertos: 2,
      racha: 2,
      ef: EF_INICIAL,
      intervaloDias: 6,
      vencimiento: 6 * MS_DIA,
    });
    const r = aplicarResultado(previo, blanco, 9_000);
    expect(r.intervaloDias).toBe(0);
    expect(r.vencimiento).toBe(9_000);
    expect(r.ef).toBeCloseTo(EF_INICIAL - 0.2, 10);
  });

  test("el ef nunca baja del suelo por muchos fallos que haya", () => {
    let r = aplicarResultado(undefined, fallo, 0);
    for (let i = 0; i < 20; i++) r = aplicarResultado(r, fallo, 0);
    expect(r.ef).toBe(EF_MIN);
  });

  test("el ef nunca sube del techo por muchos aciertos que haya", () => {
    let r = aplicarResultado(progreso({ ef: 2.4 }), acierto, 0);
    expect(r.ef).toBeCloseTo(2.45, 10);
    for (let i = 0; i < 20; i++) r = aplicarResultado(r, acierto, 0);
    expect(r.ef).toBe(EF_MAX);
  });

  test("un registro sin campos SM-2 se trata como ef inicial e intervalo 0", () => {
    // Registros guardados antes de existir el repaso (sin ef/intervalo/vencimiento).
    const legacy = progreso({ vistas: 4, aciertos: 1, fallos: 3, racha: 0 });
    expect(legacy.ef).toBeUndefined();

    const conAcierto = aplicarResultado(legacy, acierto, 5_000);
    expect(conAcierto.ef).toBe(EF_INICIAL);
    expect(conAcierto.intervaloDias).toBe(1);
    expect(conAcierto.vencimiento).toBe(5_000 + MS_DIA);

    const conFallo = aplicarResultado(legacy, fallo, 5_000);
    expect(conFallo.ef).toBeCloseTo(EF_INICIAL - 0.2, 10);
    expect(conFallo.intervaloDias).toBe(0);
    expect(conFallo.vencimiento).toBe(5_000);
  });

  test("el intervalo multiplicado nunca cae por debajo de 1 día", () => {
    // racha alta pero intervalo previo 0 (venía de un fallo): round(0 × ef) = 0.
    const previo = progreso({
      racha: 5,
      ef: EF_MIN,
      intervaloDias: 0,
      vencimiento: 0,
    });
    const r = aplicarResultado(previo, acierto, 0);
    expect(r.intervaloDias).toBe(1);
  });
});

// --- estadoRepaso ---

describe("estadoRepaso", () => {
  const AHORA = 1_000_000;

  test("solo entran en el repaso las preguntas falladas alguna vez", () => {
    const e = estadoRepaso(
      [
        progreso({ preguntaId: "a", fallos: 1, vencimiento: AHORA - 1 }),
        progreso({ preguntaId: "b", fallos: 0, vencimiento: AHORA - 1 }),
        progreso({
          preguntaId: "c",
          fallos: 0,
          enBlanco: 3,
          vencimiento: AHORA - 1,
        }),
      ],
      AHORA,
    );
    expect(e.falladas).toBe(1);
    expect(e.vencidas.map((v) => v.preguntaId)).toEqual(["a"]);
  });

  test("una fallada sin vencimiento (registro antiguo) cuenta como vencida", () => {
    const legacy = progreso({ preguntaId: "a", fallos: 2 });
    expect(legacy.vencimiento).toBeUndefined();
    const e = estadoRepaso([legacy], AHORA);
    expect(e.vencidas.map((v) => v.preguntaId)).toEqual(["a"]);
    expect(e.proximoVencimiento).toBeNull();
  });

  test("las vencidas salen de la más atrasada a la menos, con desempate por id", () => {
    const e = estadoRepaso(
      [
        progreso({ preguntaId: "z", fallos: 1, vencimiento: AHORA - 10 }),
        progreso({ preguntaId: "m", fallos: 1, vencimiento: AHORA - 500 }),
        progreso({ preguntaId: "a", fallos: 1, vencimiento: AHORA - 10 }),
        progreso({ preguntaId: "legacy", fallos: 1 }),
        progreso({ preguntaId: "futura", fallos: 1, vencimiento: AHORA + 5 }),
      ],
      AHORA,
    );
    expect(e.vencidas.map((v) => v.preguntaId)).toEqual([
      "legacy", // sin vencimiento → 0, la más atrasada
      "m",
      "a", // mismo vencimiento que "z": desempate por id
      "z",
    ]);
  });

  test("una vencida justo en el instante actual entra en la cola", () => {
    const e = estadoRepaso(
      [progreso({ preguntaId: "a", fallos: 1, vencimiento: AHORA })],
      AHORA,
    );
    expect(e.vencidas).toHaveLength(1);
    expect(e.proximoVencimiento).toBeNull();
  });

  test("proximoVencimiento es el mínimo futuro de las falladas", () => {
    const e = estadoRepaso(
      [
        progreso({ preguntaId: "a", fallos: 1, vencimiento: AHORA + 3 * MS_DIA }),
        progreso({ preguntaId: "b", fallos: 1, vencimiento: AHORA + MS_DIA }),
        progreso({ preguntaId: "c", fallos: 1, vencimiento: AHORA + 9 * MS_DIA }),
        // No fallada nunca: no cuenta aunque venza antes.
        progreso({ preguntaId: "d", fallos: 0, vencimiento: AHORA + 1 }),
      ],
      AHORA,
    );
    expect(e.vencidas).toHaveLength(0);
    expect(e.proximoVencimiento).toBe(AHORA + MS_DIA);
  });

  test("sin progreso no hay falladas, ni cola, ni próximo vencimiento", () => {
    const e = estadoRepaso([], AHORA);
    expect(e).toEqual({ falladas: 0, vencidas: [], proximoVencimiento: null });
  });

  test("una fallada ya acertada y programada a futuro no está vencida", () => {
    const e = estadoRepaso(
      [
        progreso({
          preguntaId: "a",
          vistas: 4,
          aciertos: 3,
          fallos: 1,
          racha: 3,
          ef: EF_MAX,
          intervaloDias: 15,
          vencimiento: AHORA + 15 * MS_DIA,
        }),
      ],
      AHORA,
    );
    expect(e.falladas).toBe(1);
    expect(e.vencidas).toHaveLength(0);
    expect(e.proximoVencimiento).toBe(AHORA + 15 * MS_DIA);
  });
});

// --- prepararPreguntas (lib/exam) ---

describe("prepararPreguntas", () => {
  function pregunta(id: string, textos: string[]): Pregunta {
    return {
      id,
      enunciado: `Enunciado de ${id}`,
      opciones: textos.map((texto, i) => ({
        letra: "abcd"[i],
        texto,
        esCorrecta: i === 0,
      })),
      respuestaCorrecta: "a",
      frecuencia: 3,
      conflicto: false,
      tema: "carga-estiba",
    };
  }

  const seleccion = [
    pregunta("p1", ["uno", "dos", "tres", "cuatro"]),
    pregunta("p2", ["alfa", "beta", "gamma", "delta"]),
    pregunta("p3", ["rojo", "verde", "azul", "gris"]),
  ];

  test("conserva las mismas preguntas (sin asumir orden)", () => {
    const preparadas = prepararPreguntas(seleccion);
    expect(preparadas).toHaveLength(3);
    expect(preparadas.map((p) => p.id).sort()).toEqual(["p1", "p2", "p3"]);
  });

  test("conserva todas las opciones de cada pregunta y la correcta", () => {
    const preparadas = prepararPreguntas(seleccion);
    for (const original of seleccion) {
      const p = preparadas.find((x) => x.id === original.id);
      expect(p).toBeDefined();
      expect(p!.enunciado).toBe(original.enunciado);
      expect(p!.tema).toBe(original.tema);
      expect(p!.opciones.map((o) => o.texto).sort()).toEqual(
        original.opciones.map((o) => o.texto).sort(),
      );
      expect(p!.opciones.filter((o) => o.esCorrecta)).toHaveLength(1);
      expect(p!.opciones.find((o) => o.esCorrecta)!.texto).toBe(
        original.opciones.find((o) => o.esCorrecta)!.texto,
      );
    }
  });

  test("no muta la selección de entrada", () => {
    const antes = seleccion.map((p) => p.opciones.map((o) => o.texto));
    prepararPreguntas(seleccion);
    expect(seleccion.map((p) => p.opciones.map((o) => o.texto))).toEqual(antes);
  });

  test("con una selección vacía devuelve un array vacío", () => {
    expect(prepararPreguntas([])).toEqual([]);
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
