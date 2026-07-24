#!/usr/bin/env python3
"""Cruza nuestro banco canónico con el banco oficial del Ministerio.

Objetivo: asignar a cada una de nuestras preguntas la NORMA que el Ministerio
cita para su respuesta. Nuestro banco viene de exámenes reales (OCR/PDF de
Andalucía y Extremadura), así que el cruce es difuso (rapidfuzz), no exacto.

Algoritmo (cerrado, ver spec CAP-18 Fase 1):

  - Normalización con ``cap_pipeline.normalize.normalize`` (la misma del dedup).
  - Candidato = mejor ``fuzz.token_set_ratio`` entre el enunciado ministerial y
    CADA variante de la nuestra (``enunciado`` + ``variantes_enunciado``).
  - score >= 90            -> match (``metodo: "enunciado"``).
  - 80 <= score < 90       -> match SOLO si además casa el texto de la respuesta
                              correcta (>= 85) -> ``metodo: "enunciado+respuesta"``.
  - score < 80             -> sin match.
  - VETO transversal: si AMBAS preguntas traen respuesta correcta y sus textos
    NO casan (>= 85), no hay match aunque el enunciado sea idéntico. La
    respuesta forma parte de la identidad de la pregunta (lección del dedup de
    la Fase 0: el banco oficial tiene pares de preguntas casi calcadas con
    respuestas distintas).
  - Empates: entre candidatos con el MISMO score máximo se prefiere el que
    supera la comprobación de respuesta (desempate, no relajación del umbral).

Uso:
    python3 db/ministerio_match.py
    python3 db/ministerio_match.py --umbral-alto 90 --umbral-gris 80
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
from collections import Counter, defaultdict

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline"))

from cap_pipeline.normalize import normalize  # noqa: E402
from rapidfuzz import fuzz, process  # noqa: E402

BANCO = REPO / "pipeline" / "out" / "banco_preguntas.json"
OUT_DIR = REPO / "db" / "out"
MINISTERIO = OUT_DIR / "ministerio_preguntas.json"
MATCH_JSON = OUT_DIR / "ministerio_match.json"
REPORT_MD = OUT_DIR / "ministerio_match_report.md"

UMBRAL_ALTO = 90.0
UMBRAL_GRIS = 80.0
UMBRAL_RESPUESTA = 85.0
# Poda de la búsqueda: por debajo de 50 no hay match posible (el umbral más
# permisivo es 80) y el corte acelera el bucle en C de rapidfuzz. Los scores
# por debajo caen todos en el primer cubo del histograma del informe.
CORTE_SCORE = 50.0
# Cuántos candidatos empatados se conservan para el desempate por respuesta.
TOPE_CANDIDATOS = 25


def cargar(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def guardar(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


def variantes(pregunta: dict) -> list[str]:
    """Todas las redacciones conocidas de una pregunta nuestra, normalizadas."""
    textos = [pregunta.get("enunciado") or ""]
    textos.extend(pregunta.get("variantes_enunciado") or [])
    vistos: list[str] = []
    for t in textos:
        n = normalize(t)
        if n and n not in vistos:
            vistos.append(n)
    return vistos


def texto_respuesta_ministerial(pm: dict) -> str | None:
    letra = pm.get("respuesta")
    if not letra:
        return None
    return (pm.get("opciones") or {}).get(letra)


def respuestas_casan(
    nuestra: dict, ministerial: dict, umbral: float
) -> bool | None:
    """¿Casan los textos de la respuesta correcta de ambas preguntas?

    Devuelve None si alguna de las dos no trae respuesta (no se puede juzgar).
    """
    txt_n = nuestra.get("respuesta_correcta_texto")
    txt_m = texto_respuesta_ministerial(ministerial)
    if not txt_n or not txt_m:
        return None
    return fuzz.token_set_ratio(normalize(txt_n), normalize(txt_m)) >= umbral


def candidatos_por_pregunta(
    banco: list[dict], ministerio: list[dict]
) -> list[list[tuple[int, float]]]:
    """Candidatos ministeriales de cada pregunta nuestra, ordenados por score.

    El score de un candidato es el MÁXIMO ``token_set_ratio`` entre su
    enunciado y CADA variante de enunciado de la pregunta nuestra. Se usa
    ``process.extract`` (bucle en C) en lugar de ``process.cdist`` porque este
    último exige numpy y aquí solo hay stdlib + rapidfuzz + pypdf.

    ``CORTE_SCORE`` poda comparaciones sin interés (por debajo no hay match
    posible ni con confirmación de respuesta) y ``TOPE_CANDIDATOS`` acota
    cuántos se conservan por variante.
    """
    enun_min = [normalize(p["enunciado"]) for p in ministerio]
    salida: list[list[tuple[int, float]]] = []

    for n, q in enumerate(banco, 1):
        acumulado: dict[int, float] = {}
        for v in variantes(q):
            for _texto, score, idx in process.extract(
                v,
                enun_min,
                scorer=fuzz.token_set_ratio,
                processor=None,
                limit=TOPE_CANDIDATOS,
                score_cutoff=CORTE_SCORE,
            ):
                if score > acumulado.get(idx, 0.0):
                    acumulado[idx] = float(score)
        salida.append(sorted(acumulado.items(), key=lambda kv: -kv[1]))
        if n % 250 == 0 or n == len(banco):
            print(f"  {n}/{len(banco)} preguntas comparadas", flush=True)
    return salida


def maximo_y_empates(candidatos: list[tuple[int, float]]) -> tuple[float, list[int]]:
    """(mejor score, índices ministeriales que lo empatan)."""
    if not candidatos:
        return 0.0, []
    tope = candidatos[0][1]
    return tope, [idx for idx, s in candidatos if s == tope]


def decidir(
    nuestra: dict,
    ministerio: list[dict],
    score: float,
    candidatos: list[int],
    umbral_alto: float,
    umbral_gris: float,
    umbral_respuesta: float,
) -> tuple[dict | None, str | None]:
    """Aplica las reglas de aceptación. Devuelve (entrada_match|None, motivo)."""
    if score < umbral_gris or not candidatos:
        return None, "score < umbral"

    # Desempate: entre los candidatos con el MISMO score máximo, preferir el
    # que confirma la respuesta (True) antes que el que no permite juzgarla
    # (None) y este antes que el que la contradice (False).
    preferencia = {True: 0, None: 1, False: 2}
    elegido: int | None = None
    casa_elegido: bool | None = None
    for idx in candidatos:
        casa = respuestas_casan(nuestra, ministerio[idx], umbral_respuesta)
        if elegido is None or preferencia[casa] < preferencia[casa_elegido]:
            elegido, casa_elegido = idx, casa
        if casa_elegido is True:
            break

    # VETO: ambas tienen respuesta y NO casan -> no es la misma pregunta.
    if casa_elegido is False:
        return None, "respuesta incompatible"

    if score >= umbral_alto:
        metodo = "enunciado"
    elif casa_elegido is True:
        metodo = "enunciado+respuesta"
    else:
        return None, "zona gris sin confirmación de respuesta"

    pm = ministerio[elegido]
    return (
        {
            "origen": pm["origen"],
            "num": pm["num"],
            "norma": pm["norma"],
            "score": round(score, 1),
            "metodo": metodo,
        },
        None,
    )


# --- informe ----------------------------------------------------------------

_BUCKETS = [
    (0.0, 50.0),
    (50.0, 60.0),
    (60.0, 70.0),
    (70.0, 80.0),
    (80.0, 85.0),
    (85.0, 90.0),
    (90.0, 95.0),
    (95.0, 100.0),
    (100.0, 100.01),
]


def escribir_informe(
    banco: list[dict],
    matches: dict,
    scores: list[float],
    motivos: Counter,
    rescatables: int,
    semilla: int,
) -> None:
    total = len(banco)
    n_match = len(matches)
    pct = (100.0 * n_match / total) if total else 0.0
    con_norma = sum(1 for m in matches.values() if m["norma"])
    pct_norma = (100.0 * con_norma / n_match) if n_match else 0.0

    lineas = [
        "# Matching banco propio ↔ banco oficial del Ministerio — informe\n",
        f"- Preguntas nuestras: **{total}**",
        f"- Con match ministerial: **{n_match}** ({pct:.1f} %)",
        f"- De las emparejadas, con NORMA: **{con_norma}** ({pct_norma:.1f} %)",
        f"- Preguntas nuestras que acaban con norma: "
        f"**{con_norma}** ({100.0 * con_norma / total:.1f} % del banco)\n",
        "## Desglose por método\n",
        "| Método | Nº | Con norma |",
        "| --- | ---: | ---: |",
    ]
    for metodo in ("enunciado", "enunciado+respuesta"):
        sub = [m for m in matches.values() if m["metodo"] == metodo]
        lineas.append(
            f"| {metodo} | {len(sub)} | {sum(1 for m in sub if m['norma'])} |"
        )

    lineas.append("\n## Motivos de no-match\n")
    lineas.append("| Motivo | Nº |")
    lineas.append("| --- | ---: |")
    for motivo, n in motivos.most_common():
        lineas.append(f"| {motivo} | {n} |")
    lineas.append(
        "\nEl veto por respuesta es intencionado: `token_set_ratio` puntúa 100 "
        "cuando el enunciado ministerial es un SUBCONJUNTO del nuestro "
        "(p. ej. «La potencia de un motor es:» dentro de «¿A qué equivale la "
        "potencia de un motor…?»), y esos son pares de preguntas DISTINTAS.\n"
    )
    lineas.append(
        f"Dato para la Fase 2: **{rescatables}** de las vetadas por respuesta "
        "tienen otro candidato con score ≥ umbral alto cuya respuesta sí casa; "
        "el algoritmo cerrado se queda con el candidato de score máximo y no "
        "las recupera.\n"
    )

    lineas.append("\n## Cobertura por tema (nuestro)\n")
    lineas.append("| Tema | Preguntas | Con match | % | Con norma | % |")
    lineas.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    por_tema: dict[str, list[dict]] = defaultdict(list)
    for q in banco:
        por_tema[q.get("tema") or "(sin tema)"].append(q)
    for tema in sorted(por_tema):
        preguntas = por_tema[tema]
        con_m = [matches[q["id"]] for q in preguntas if q["id"] in matches]
        con_n = sum(1 for m in con_m if m["norma"])
        lineas.append(
            f"| {tema} | {len(preguntas)} | {len(con_m)} | "
            f"{100.0 * len(con_m) / len(preguntas):.1f} % | {con_n} | "
            f"{100.0 * con_n / len(preguntas):.1f} % |"
        )

    lineas.append("\n## Distribución del mejor score por pregunta nuestra\n")
    lineas.append("```")
    for lo, hi in _BUCKETS:
        n = sum(1 for s in scores if lo <= s < hi)
        etiqueta = "100" if lo == 100.0 else f"{lo:>5.0f}-{hi:<5.0f}"
        barra = "#" * round(60.0 * n / max(1, total))
        lineas.append(f"{etiqueta:>12} | {n:>5} | {barra}")
    lineas.append("```")

    lineas.append("\n## 10 no-emparejadas al azar (inspección humana)\n")
    sin_match = [q for q in banco if q["id"] not in matches]
    muestra = random.Random(semilla).sample(sin_match, min(10, len(sin_match)))
    for q in muestra:
        lineas.append(f"- `{q['id']}` — {q['enunciado']}")

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Matching con el banco del Ministerio")
    ap.add_argument("--banco", type=pathlib.Path, default=BANCO)
    ap.add_argument("--ministerio", type=pathlib.Path, default=MINISTERIO)
    ap.add_argument("--umbral-alto", type=float, default=UMBRAL_ALTO)
    ap.add_argument("--umbral-gris", type=float, default=UMBRAL_GRIS)
    ap.add_argument("--umbral-respuesta", type=float, default=UMBRAL_RESPUESTA)
    ap.add_argument("--semilla", type=int, default=42)
    args = ap.parse_args()

    banco = cargar(args.banco)
    ministerio = cargar(args.ministerio)
    print(
        f"Banco propio: {len(banco)} preguntas | Ministerio: {len(ministerio)}",
        flush=True,
    )

    candidatos_todos = candidatos_por_pregunta(banco, ministerio)

    matches: dict[str, dict] = {}
    motivos: Counter = Counter()
    scores: list[float] = []
    rescatables = 0
    for q, candidatos in zip(banco, candidatos_todos):
        score, empatados = maximo_y_empates(candidatos)
        scores.append(score)
        entrada, motivo = decidir(
            q,
            ministerio,
            score,
            empatados,
            args.umbral_alto,
            args.umbral_gris,
            args.umbral_respuesta,
        )
        if entrada is not None:
            matches[q["id"]] = entrada
            continue
        motivos[motivo] += 1
        # Métrica informativa (NO cambia la salida): vetados por respuesta que
        # tendrían OTRO candidato por encima del umbral alto cuya respuesta sí
        # casa. Mide lo que cuesta la regla "candidato = score máximo".
        if motivo == "respuesta incompatible" and any(
            s >= args.umbral_alto
            and respuestas_casan(q, ministerio[idx], args.umbral_respuesta) is True
            for idx, s in candidatos
        ):
            rescatables += 1

    guardar(MATCH_JSON, matches)
    escribir_informe(banco, matches, scores, motivos, rescatables, args.semilla)

    con_norma = sum(1 for m in matches.values() if m["norma"])
    print(f"\nCon match: {len(matches)}/{len(banco)} "
          f"({100.0 * len(matches) / len(banco):.1f} %)", flush=True)
    print(f"De ellas con norma: {con_norma} "
          f"({100.0 * con_norma / max(1, len(matches)):.1f} %)", flush=True)
    for metodo, n in Counter(m["metodo"] for m in matches.values()).items():
        print(f"  método {metodo}: {n}", flush=True)
    for motivo, n in motivos.most_common():
        print(f"  sin match ({motivo}): {n}", flush=True)
    print(f"-> {MATCH_JSON.relative_to(REPO)}", flush=True)
    print(f"-> {REPORT_MD.relative_to(REPO)}", flush=True)


if __name__ == "__main__":
    main()
