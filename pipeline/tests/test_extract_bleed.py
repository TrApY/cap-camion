"""Tests del filtrado de cabecera/pie ("bleed") en la extraccion.

El defecto: en los examenes (sobre todo Granada) el bloque de cabecera
    EXAMEN OBTENCION DEL CAP
    Fecha: ...  Examen: MERCANCIAS A
    Lugar: ... CAMPUS
    UNIV. FUENTE NUEVA, GRANADA, GRANADA
    Duracion: 120 MINUTOS
se repite en la parte superior de CADA pagina. Cuando una pregunta u opcion se
parte entre paginas, ese bloque se incrustaba dentro del enunciado o de una
opcion. Estos tests verifican que ya no ocurre.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cap_pipeline.extract import (
    detect_repeated_lines,
    parse_questions,
    process_pdf,
    read_pdf_pages,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = REPO_ROOT / "data" / "corpus_cap_conductor" / "andalucia"
GRANADA_PDF = _CORPUS / "AND_117_2026_01_examen_mer_gr_cap1_2026.pdf"
# El ejemplo concreto de la auditoria ("...salud del trabajador. UNIV. FUENTE
# NUEVA, GRANADA... MINUTOS") esta en este examen de Granada.
SALUD_PDF = _CORPUS / "AND_108_2026_07_examen_A_mer_gr_cap4_2026.pdf"

# Marcadores INEQUIVOCOS de cabecera/pie (no palabras corrientes como "minutos").
_BLEED_MARKERS = re.compile(
    r"FUENTE\s+NUEVA|\bUNIV\.|Duraci[oó]n\s*:\s*\d|EXAMEN\s+OBTENCI"
    r"|ETIQUETA\s+IDENTIFICATIVA|CENTRO\s+REGIONAL\s+DE\s+TRANSPORTES"
    r"|Examen\s*:\s*MERCANC|P[aá]gina\s+\d+\s+de\s+\d+",
    re.IGNORECASE,
)


def _has_bleed(q) -> bool:
    if _BLEED_MARKERS.search(q.enunciado):
        return True
    return any(v and _BLEED_MARKERS.search(v) for v in q.opciones.values())


def test_detect_repeated_lines_captures_granada_header():
    pages = read_pdf_pages(GRANADA_PDF)
    repeated = detect_repeated_lines(pages)
    # El bloque de cabecera completo debe detectarse como repetido.
    assert "EXAMEN OBTENCIÓN DEL CAP" in repeated
    assert "UNIV. FUENTE NUEVA, GRANADA, GRANADA" in repeated
    assert "Duración: 120 MINUTOS" in repeated


def test_granada_pdf_has_no_header_bleed():
    result, _ = process_pdf(GRANADA_PDF, "andalucia")
    assert result.error is None
    assert result.questions, "el examen de Granada debe aportar preguntas"
    culprits = [q for q in result.questions if _has_bleed(q)]
    assert not culprits, (
        "Ninguna pregunta/opcion debe arrastrar texto de cabecera/pie; "
        f"encontradas {len(culprits)}"
    )


def test_salud_del_trabajador_option_ends_clean():
    """La opcion que antes terminaba en '...salud del trabajador. UNIV. FUENTE
    NUEVA, GRANADA... MINUTOS' debe terminar limpia en '...salud del trabajador.'"""
    result, _ = process_pdf(SALUD_PDF, "andalucia")
    target = None
    for q in result.questions:
        for v in q.opciones.values():
            if v and "salud del trabajador" in v.lower():
                target = v
    assert target is not None, "no se encontro la opcion de referencia"
    assert "FUENTE NUEVA" not in target
    assert "MINUTOS" not in target
    assert target.rstrip().endswith("salud del trabajador.")


def test_detect_repeated_lines_empty_for_single_page():
    assert detect_repeated_lines(["una sola pagina\ncon texto"]) == set()


def test_repeated_noise_filtered_in_parse():
    text = (
        "1. Pregunta de prueba con opciones\n"
        "a) opcion primera\n"
        "CABECERA REPETIDA XYZ\n"  # simula bleed a mitad de opcion
        "b) opcion segunda\n"
        "* c) opcion correcta\n"
        "d) opcion cuarta\n"
        "Referencia: test\n"
    )
    noise = {"CABECERA REPETIDA XYZ"}
    qs, _ = parse_questions(text, "f.pdf", "andalucia", None, None, repeated_noise=noise)
    assert len(qs) == 1
    assert "CABECERA REPETIDA" not in " ".join(qs[0].opciones.values())
    assert qs[0].opciones["a"] == "opcion primera"
