"""Tests del generador de seed de teoría (``db/seed_teoria.py``), sin red.

Se ejercita lo que de verdad importa del generador: que el SQL empiece por el
UPDATE de limpieza (idempotencia real: lo que sale del json deja de estar en la
BD), que los textos vayan escapados por el escapado central de
``seed_supabase`` (comillas simples dobladas), que los lotes se corten donde se
pide, que los temas se carguen con upsert y que dos ejecuciones con la misma
entrada produzcan EXACTAMENTE el mismo SQL.
"""

from __future__ import annotations

import json
from pathlib import Path

import seed_teoria as st

# --- fixtures pequeñas -------------------------------------------------------

EXPLICACIONES = {
    # Con comilla simple en el texto y norma oficial: el caso peligroso.
    "cap-0002": {
        "explicacion": "La pausa es de 45' porque lo fija el reglamento.",
        "norma": "Reglamento Comunitario (CE) 561/2006 Art. 7",
        "con_texto_legal": True,
        "origen_contexto": "match",
    },
    # Sin norma: debe salir NULL, no cadena vacía.
    "cap-0001": {
        "explicacion": "La marcha más larga baja las revoluciones y el consumo.",
        "norma": None,
        "con_texto_legal": False,
        "origen_contexto": "match",
    },
    # Explicación vacía: no aporta nada, se descarta (la limpieza ya la deja a NULL).
    "cap-0003": {"explicacion": "", "norma": "Ley 16/1987 Art. 22"},
    "cap-0004": {
        "explicacion": "El tacógrafo registra los tiempos de conducción.",
        "norma": "  ",  # norma en blanco -> NULL
    },
}

TEMAS = {
    "tiempos-tacografo": {
        "titulo": "Tiempos de conducción y tacógrafo",
        "resumen_md": "- La pausa d'obligado cumplimiento es de 45 minutos.\n- **Ojo** al descanso diario.",
    },
    "motor-transmision": {
        "titulo": "El vehículo: motor y transmisión",
        "resumen_md": "## Par y potencia\nEl motor genera par.",
    },
}


def _escribir_entradas(tmp_path: Path, explicaciones=None, temas=None) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p_expl = tmp_path / "explicaciones.json"
    p_temas = tmp_path / "resumenes_temas.json"
    p_expl.write_text(
        json.dumps(EXPLICACIONES if explicaciones is None else explicaciones, ensure_ascii=False),
        encoding="utf-8",
    )
    p_temas.write_text(
        json.dumps(TEMAS if temas is None else temas, ensure_ascii=False),
        encoding="utf-8",
    )
    return p_expl, p_temas


def _generar(tmp_path: Path, batch: int = 200, **kwargs) -> tuple[Path, list[str]]:
    p_expl, p_temas = _escribir_entradas(tmp_path, **kwargs)
    outdir = tmp_path / "seed_out"
    manifest = st.build_files(
        st.cargar_explicaciones(p_expl),
        st.cargar_temas(p_temas),
        outdir,
        batch=batch,
    )
    return outdir, manifest


def _sql(outdir: Path) -> str:
    """Todo el SQL generado concatenado en orden de fichero."""
    return "".join(
        f.read_text(encoding="utf-8") for f in sorted(outdir.glob("*.sql"))
    )


# --- 1. lectura de las entradas ---------------------------------------------


def test_carga_ordenada_y_sin_entradas_vacias(tmp_path):
    p_expl, _ = _escribir_entradas(tmp_path)
    filas = st.cargar_explicaciones(p_expl)

    # Orden determinista por id y sin la entrada de explicación vacía.
    assert [f[0] for f in filas] == ["cap-0001", "cap-0002", "cap-0004"]
    # La norma se conserva TAL CUAL; en blanco o ausente -> None.
    assert filas[0][2] is None
    assert filas[1][2] == "Reglamento Comunitario (CE) 561/2006 Art. 7"
    assert filas[2][2] is None


def test_carga_temas_ordenada(tmp_path):
    _, p_temas = _escribir_entradas(tmp_path)
    filas = st.cargar_temas(p_temas)
    assert [f[0] for f in filas] == ["motor-transmision", "tiempos-tacografo"]
    assert filas[1][1] == "Tiempos de conducción y tacógrafo"


# --- 2. limpieza previa ------------------------------------------------------


def test_primer_fichero_es_la_limpieza(tmp_path):
    outdir, manifest = _generar(tmp_path)
    assert manifest[0] == "30_teoria_limpieza.sql"
    limpieza = (outdir / "30_teoria_limpieza.sql").read_text(encoding="utf-8")
    assert limpieza.strip() == "update public.preguntas set explicacion = NULL, norma = NULL;"


# --- 3. lotes de UPDATE ------------------------------------------------------


def test_update_con_values_y_escapado(tmp_path):
    outdir, _ = _generar(tmp_path)
    sql = (outdir / "31_explicaciones_001.sql").read_text(encoding="utf-8")

    assert "update public.preguntas set" in sql
    assert "explicacion = v.explicacion" in sql
    assert "norma = v.norma" in sql
    assert "as v(id, explicacion, norma)" in sql
    assert "where preguntas.id = v.id" in sql

    # Comilla simple del texto doblada (escapado de seed_supabase).
    assert "La pausa es de 45'' porque lo fija el reglamento." in sql
    # Norma ausente -> NULL sin comillas; norma presente -> literal intacto.
    assert "'Reglamento Comunitario (CE) 561/2006 Art. 7'" in sql
    assert "NULL)" in sql
    # La entrada sin explicación no se siembra.
    assert "cap-0003" not in sql


def test_lotes_del_tamano_pedido(tmp_path):
    explicaciones = {
        f"cap-{i:04d}": {"explicacion": f"Explicación {i}.", "norma": None}
        for i in range(1, 6)
    }
    outdir, manifest = _generar(tmp_path, batch=2, explicaciones=explicaciones)

    lotes = [n for n in manifest if n.startswith("31_explicaciones_")]
    assert lotes == [
        "31_explicaciones_001.sql",
        "31_explicaciones_002.sql",
        "31_explicaciones_003.sql",
    ]
    # 5 filas en lotes de 2 -> 2 + 2 + 1; un `values` por fichero.
    primero = (outdir / "31_explicaciones_001.sql").read_text(encoding="utf-8")
    ultimo = (outdir / "31_explicaciones_003.sql").read_text(encoding="utf-8")
    assert primero.count("'cap-") == 2
    assert ultimo.count("'cap-") == 1
    assert primero.count("from (values") == 1


# --- 4. upsert de temas ------------------------------------------------------


def test_upsert_de_temas(tmp_path):
    outdir, manifest = _generar(tmp_path)
    assert "40_temas_teoria.sql" in manifest
    sql = (outdir / "40_temas_teoria.sql").read_text(encoding="utf-8")

    assert sql.startswith("insert into public.temas_teoria (slug, titulo, resumen_md) values")
    assert "on conflict (slug) do update set" in sql
    assert "titulo = excluded.titulo" in sql
    assert "resumen_md = excluded.resumen_md" in sql
    assert "updated_at = now()" in sql
    # Markdown y comillas del resumen viajan escapados pero íntegros.
    assert "La pausa d''obligado cumplimiento" in sql
    assert "**Ojo**" in sql
    assert "## Par y potencia" in sql


# --- 5. idempotencia ---------------------------------------------------------


def test_dos_ejecuciones_mismo_sql(tmp_path):
    outdir1, manifest1 = _generar(tmp_path / "run1")
    outdir2, manifest2 = _generar(tmp_path / "run2")
    assert manifest1 == manifest2
    assert _sql(outdir1) == _sql(outdir2)


def test_regenerar_borra_lotes_huerfanos_y_respeta_el_seed_del_banco(tmp_path):
    p_expl, p_temas = _escribir_entradas(tmp_path)
    outdir = tmp_path / "seed_out"
    outdir.mkdir()
    # Ficheros del otro generador (seed_supabase) que NO deben tocarse.
    (outdir / "10_preguntas_001.sql").write_text("-- banco\n", encoding="utf-8")
    # Lote huérfano de una ejecución anterior con más preguntas.
    (outdir / "31_explicaciones_009.sql").write_text("-- viejo\n", encoding="utf-8")

    st.build_files(st.cargar_explicaciones(p_expl), st.cargar_temas(p_temas), outdir)

    assert (outdir / "10_preguntas_001.sql").exists()
    assert not (outdir / "31_explicaciones_009.sql").exists()


# --- 6. volcado completo -----------------------------------------------------


def test_full_sql_empieza_por_la_limpieza_y_acaba_en_los_temas(tmp_path):
    p_expl, p_temas = _escribir_entradas(tmp_path)
    sql = st.full_sql(st.cargar_explicaciones(p_expl), st.cargar_temas(p_temas))
    assert sql.startswith("update public.preguntas set explicacion = NULL")
    assert sql.index("update public.preguntas set\n") < sql.index("insert into public.temas_teoria")
