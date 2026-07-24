#!/usr/bin/env python3
"""Genera el SQL de carga del banco de preguntas CAP para Supabase.

Lee ``pipeline/out/banco_preguntas.json`` y produce ficheros SQL por lotes en
``db/seed_out/`` listos para aplicarse (por MCP ``execute_sql`` o por ``psql``).

Idempotente: el primer fichero hace ``TRUNCATE ... RESTART IDENTITY CASCADE``,
por lo que re-sembrar deja la BD en el mismo estado sin duplicados.

El escapado de SQL se genera aquí (nunca a mano):
  * textos      -> literal con comillas simples dobladas; ``NULL`` para nulos.
  * arrays      -> literal postgres ``'{"a","b"}'`` (doble capa de escapado);
                   array vacío -> ``'{}'``.
  * booleanos   -> ``true`` / ``false``.

Uso:
    python3 db/seed_supabase.py                       # genera en db/seed_out/
    python3 db/seed_supabase.py --stdout              # vuelca todo el SQL a stdout
    python3 db/seed_supabase.py --preguntas-batch 400 --opciones-batch 1500
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO / "pipeline" / "out" / "banco_preguntas.json"
DEFAULT_OUTDIR = REPO / "db" / "seed_out"
LETRAS = ("a", "b", "c", "d")

TRUNCATE_SQL = "truncate table public.opciones, public.preguntas restart identity cascade;\n"
PREGUNTAS_COLS = (
    "(id, enunciado, respuesta_correcta, respuesta_correcta_texto, "
    "frecuencia, comunidades, fuentes, conflicto_respuesta)"
)
OPCIONES_COLS = "(pregunta_id, letra, texto, es_correcta)"


# --------------------------------------------------------------------------- #
# Escapado SQL
# --------------------------------------------------------------------------- #
def sql_str(v) -> str:
    """Literal SQL para texto. ``None`` -> ``NULL``. Dobla comillas simples."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def sql_char(v) -> str:
    """Literal SQL para character(1). ``None`` -> ``NULL``."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def sql_int(v, default=None) -> str:
    if v is None:
        v = default
    if v is None:
        return "NULL"
    return str(int(v))


def sql_bool(v) -> str:
    return "true" if v else "false"


def sql_text_array(values) -> str:
    """Literal postgres ``text[]`` -> ``'{"a","b"}'``. Vacío -> ``'{}'``.

    Doble capa de escapado:
      1. Capa del literal de array: cada elemento va entre comillas dobles y se
         escapan la barra invertida y la comilla doble.
      2. Capa de cadena SQL: el literal completo va entre comillas simples, por
         lo que se doblan las comillas simples que contenga.
    """
    if not values:
        return "'{}'"
    elems = []
    for v in values:
        s = str(v).replace("\\", "\\\\").replace('"', '\\"')
        elems.append('"' + s + '"')
    literal = "{" + ",".join(elems) + "}"
    return "'" + literal.replace("'", "''") + "'"


# --------------------------------------------------------------------------- #
# Generación de filas
# --------------------------------------------------------------------------- #
def pregunta_row(d) -> str:
    return "({}, {}, {}, {}, {}, {}, {}, {})".format(
        sql_str(d["id"]),
        sql_str(d.get("enunciado")),
        sql_char(d.get("respuesta_correcta")),
        sql_str(d.get("respuesta_correcta_texto")),
        sql_int(d.get("frecuencia"), default=1),
        sql_text_array(d.get("comunidades") or []),
        sql_text_array(d.get("fuentes") or []),
        sql_bool(d.get("conflicto_respuesta")),
    )


def opcion_rows(d) -> list[str]:
    """Una fila por letra con texto NO nulo; es_correcta = (letra == correcta)."""
    rc = d.get("respuesta_correcta")
    opts = d.get("opciones") or {}
    rows = []
    for letra in LETRAS:
        texto = opts.get(letra)
        if texto is None:
            continue
        rows.append(
            "({}, {}, {}, {})".format(
                sql_str(d["id"]),
                sql_char(letra),
                sql_str(texto),
                sql_bool(letra == rc),
            )
        )
    return rows


# --------------------------------------------------------------------------- #
# Ensamblado
# --------------------------------------------------------------------------- #
def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def preguntas_insert(rows) -> str:
    return (
        "insert into public.preguntas "
        + PREGUNTAS_COLS
        + " values\n"
        + ",\n".join(rows)
        + ";\n"
    )


def opciones_insert(rows) -> str:
    return (
        "insert into public.opciones "
        + OPCIONES_COLS
        + " values\n"
        + ",\n".join(rows)
        + ";\n"
    )


def build_files(data, outdir, preguntas_batch, opciones_batch):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.sql"):
        f.unlink()

    manifest = []

    p0 = outdir / "00_truncate.sql"
    p0.write_text(TRUNCATE_SQL, encoding="utf-8")
    manifest.append(p0.name)

    preg_rows = [pregunta_row(d) for d in data]
    for i, batch in enumerate(chunks(preg_rows, preguntas_batch), 1):
        fn = outdir / f"10_preguntas_{i:03d}.sql"
        fn.write_text(preguntas_insert(batch), encoding="utf-8")
        manifest.append(fn.name)

    opt_rows = []
    for d in data:
        opt_rows.extend(opcion_rows(d))
    for i, batch in enumerate(chunks(opt_rows, opciones_batch), 1):
        fn = outdir / f"20_opciones_{i:03d}.sql"
        fn.write_text(opciones_insert(batch), encoding="utf-8")
        manifest.append(fn.name)

    return manifest, len(preg_rows), len(opt_rows)


def full_sql(data):
    preg_rows = [pregunta_row(d) for d in data]
    opt_rows = []
    for d in data:
        opt_rows.extend(opcion_rows(d))
    parts = [TRUNCATE_SQL, preguntas_insert(preg_rows), opciones_insert(opt_rows)]
    return "\n".join(parts), len(preg_rows), len(opt_rows)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=pathlib.Path, default=DEFAULT_INPUT)
    ap.add_argument("--outdir", type=pathlib.Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--preguntas-batch", type=int, default=400)
    ap.add_argument("--opciones-batch", type=int, default=1500)
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="Vuelca todo el SQL (truncate + inserts) a stdout en vez de a ficheros.",
    )
    args = ap.parse_args(argv)

    with open(args.input, encoding="utf-8") as fh:
        data = json.load(fh)

    if args.stdout:
        sql, n_preg, n_opt = full_sql(data)
        sys.stdout.write(sql)
        sys.stderr.write(
            f"# preguntas={n_preg} opciones={n_opt}\n"
        )
        return

    manifest, n_preg, n_opt = build_files(
        data, args.outdir, args.preguntas_batch, args.opciones_batch
    )
    print(f"Entrada : {args.input}")
    print(f"Salida  : {args.outdir}")
    print(f"Preguntas: {n_preg}")
    print(f"Opciones : {n_opt}")
    print(f"Ficheros ({len(manifest)}):")
    for name in manifest:
        size = (args.outdir / name).stat().st_size
        print(f"  {name:24s} {size:>9,d} bytes")


if __name__ == "__main__":
    main()
