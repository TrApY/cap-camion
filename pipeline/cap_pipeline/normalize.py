"""Normalizacion de texto para la deduplicacion.

La normalizacion es deliberadamente agresiva: pasa a minusculas, elimina
tildes y signos de puntuacion y colapsa espacios. El objetivo es que dos
redacciones "iguales" de una pregunta (con diferencias de OCR, espaciado o
acentos) produzcan la misma cadena canonica.
"""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """Elimina tildes/diacriticos (a->a, n~->n) via descomposicion NFKD."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Devuelve la forma canonica de un texto para comparar por igualdad/similitud.

    minusculas -> sin tildes -> sin puntuacion -> espacios colapsados.
    """
    if not text:
        return ""
    t = strip_accents(text.lower())
    t = _NON_ALNUM.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    return t
