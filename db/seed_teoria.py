#!/usr/bin/env python3
"""Genera el SQL de carga de la teoría del CAP para Supabase.

Lee ``db/out/explicaciones.json`` (explicación + norma por pregunta) y
``db/out/resumenes_temas.json`` (resumen de teoría por tema) y produce ficheros
SQL por lotes en ``db/seed_out/``, listos para aplicarse (por MCP ``execute_sql``
o por ``psql``). Requiere la migración ``0002_teoria.sql`` aplicada.

Idempotente en dos sentidos:
  * El primer fichero pone ``explicacion`` y ``norma`` a NULL en toda la tabla,
    de modo que una pregunta que desaparezca del json en una regeneración no
    conserve texto viejo.
  * Los temas se cargan con ``insert ... on conflict (slug) do update``.
  * La salida es determinista (preguntas ordenadas por id, temas por slug):
    dos ejecuciones con la misma entrada producen exactamente el mismo SQL.

El escapado SQL se reutiliza de ``seed_supabase`` (nunca se escribe a mano).
La ``norma`` se siembra TAL CUAL viene del json: es la referencia oficial del
Ministerio y no se transforma.

Uso:
    python3 db/seed_teoria.py                 # genera en db/seed_out/
    python3 db/seed_teoria.py --stdout        # vuelca todo el SQL a stdout
    python3 db/seed_teoria.py --batch 400
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from seed_supabase import chunks, sql_str

REPO = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_EXPLICACIONES = REPO / "db" / "out" / "explicaciones.json"
DEFAULT_RESUMENES = REPO / "db" / "out" / "resumenes_temas.json"
DEFAULT_OUTDIR = REPO / "db" / "seed_out"
DEFAULT_BATCH = 200

# Ficheros que gestiona ESTE generador. Se borran antes de regenerar para no
# dejar lotes huérfanos de una ejecución anterior (y para no tocar los ficheros
# del seed del banco, que son de seed_supabase.py).
PATRONES_PROPIOS = ("30_teoria_limpieza.sql", "31_explicaciones_*.sql", "40_temas_teoria.sql")

LIMPIEZA_SQL = "update public.preguntas set explicacion = NULL, norma = NULL;\n"


# --------------------------------------------------------------------------- #
# Lectura de entradas
# --------------------------------------------------------------------------- #
def cargar_explicaciones(path: pathlib.Path) -> list[tuple[str, str, str | None]]:
    """Devuelve ``[(id, explicacion, norma)]`` ordenado por id.

    Se descartan las entradas sin explicación: no aportan nada a la app y el
    UPDATE de limpieza ya deja esas preguntas a NULL.
    """
    with open(path, encoding="utf-8") as fh:
        datos = json.load(fh)

    filas: list[tuple[str, str, str | None]] = []
    for pid in sorted(datos):
        entrada = datos[pid] or {}
        explicacion = (entrada.get("explicacion") or "").strip()
        if not explicacion:
            continue
        norma = entrada.get("norma")
        norma = norma.strip() if isinstance(norma, str) and norma.strip() else None
        filas.append((pid, explicacion, norma))
    return filas


def cargar_temas(path: pathlib.Path) -> list[tuple[str, str, str]]:
    """Devuelve ``[(slug, titulo, resumen_md)]`` ordenado por slug."""
    with open(path, encoding="utf-8") as fh:
        datos = json.load(fh)

    filas: list[tuple[str, str, str]] = []
    for slug in sorted(datos):
        entrada = datos[slug] or {}
        titulo = (entrada.get("titulo") or "").strip()
        resumen = (entrada.get("resumen_md") or "").strip()
        if not titulo or not resumen:
            continue
        filas.append((slug, titulo, resumen))
    return filas


# --------------------------------------------------------------------------- #
# Generación de SQL
# --------------------------------------------------------------------------- #
def explicacion_row(fila: tuple[str, str, str | None]) -> str:
    pid, explicacion, norma = fila
    return f"({sql_str(pid)}, {sql_str(explicacion)}, {sql_str(norma)})"


def explicaciones_update(rows: list[str]) -> str:
    """UPDATE masivo con una tabla derivada VALUES.

    Los ``::text`` explicitan el tipo de las columnas de la VALUES (los
    literales llegan como ``unknown``), evitando sorpresas cuando un lote lleva
    la norma a NULL en todas sus filas.
    """
    return (
        "update public.preguntas set\n"
        "    explicacion = v.explicacion::text,\n"
        "    norma = v.norma::text\n"
        "from (values\n"
        + ",\n".join(rows)
        + "\n) as v(id, explicacion, norma)\n"
        "where preguntas.id = v.id::text;\n"
    )


def temas_upsert(filas: list[tuple[str, str, str]]) -> str:
    rows = [
        f"({sql_str(slug)}, {sql_str(titulo)}, {sql_str(resumen)})"
        for slug, titulo, resumen in filas
    ]
    return (
        "insert into public.temas_teoria (slug, titulo, resumen_md) values\n"
        + ",\n".join(rows)
        + "\non conflict (slug) do update set\n"
        "    titulo = excluded.titulo,\n"
        "    resumen_md = excluded.resumen_md,\n"
        "    updated_at = now();\n"
    )


# --------------------------------------------------------------------------- #
# Ensamblado
# --------------------------------------------------------------------------- #
def build_files(
    explicaciones: list[tuple[str, str, str | None]],
    temas: list[tuple[str, str, str]],
    outdir: pathlib.Path,
    batch: int = DEFAULT_BATCH,
) -> list[str]:
    outdir.mkdir(parents=True, exist_ok=True)
    for patron in PATRONES_PROPIOS:
        for f in outdir.glob(patron):
            f.unlink()

    manifest: list[str] = []

    p0 = outdir / "30_teoria_limpieza.sql"
    p0.write_text(LIMPIEZA_SQL, encoding="utf-8")
    manifest.append(p0.name)

    rows = [explicacion_row(f) for f in explicaciones]
    for i, lote in enumerate(chunks(rows, batch), 1):
        fn = outdir / f"31_explicaciones_{i:03d}.sql"
        fn.write_text(explicaciones_update(lote), encoding="utf-8")
        manifest.append(fn.name)

    if temas:
        fn = outdir / "40_temas_teoria.sql"
        fn.write_text(temas_upsert(temas), encoding="utf-8")
        manifest.append(fn.name)

    return manifest


def full_sql(
    explicaciones: list[tuple[str, str, str | None]],
    temas: list[tuple[str, str, str]],
    batch: int = DEFAULT_BATCH,
) -> str:
    partes = [LIMPIEZA_SQL]
    rows = [explicacion_row(f) for f in explicaciones]
    for lote in chunks(rows, batch):
        partes.append(explicaciones_update(lote))
    if temas:
        partes.append(temas_upsert(temas))
    return "\n".join(partes)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--explicaciones", type=pathlib.Path, default=DEFAULT_EXPLICACIONES)
    ap.add_argument("--resumenes", type=pathlib.Path, default=DEFAULT_RESUMENES)
    ap.add_argument("--outdir", type=pathlib.Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    ap.add_argument(
        "--stdout",
        action="store_true",
        help="Vuelca todo el SQL (limpieza + updates + temas) a stdout.",
    )
    args = ap.parse_args(argv)

    explicaciones = cargar_explicaciones(args.explicaciones)
    temas = cargar_temas(args.resumenes)

    if args.stdout:
        sys.stdout.write(full_sql(explicaciones, temas, args.batch))
        sys.stderr.write(f"# explicaciones={len(explicaciones)} temas={len(temas)}\n")
        return

    manifest = build_files(explicaciones, temas, args.outdir, args.batch)
    con_norma = sum(1 for f in explicaciones if f[2])
    print(f"Explicaciones : {args.explicaciones}")
    print(f"Resúmenes     : {args.resumenes}")
    print(f"Salida        : {args.outdir}")
    print(f"Preguntas con explicación: {len(explicaciones)} (con norma: {con_norma})")
    print(f"Temas con resumen        : {len(temas)}")
    print(f"Ficheros ({len(manifest)}):")
    for name in manifest:
        size = (args.outdir / name).stat().st_size
        print(f"  {name:28s} {size:>9,d} bytes")


if __name__ == "__main__":
    main()
