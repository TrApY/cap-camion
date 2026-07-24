"""Deduplicacion de preguntas y construccion del banco canonico.

Enfoque PoC (sin servicios externos). La IDENTIDAD de una pregunta es el par
(enunciado, respuesta correcta): la respuesta forma parte de la identidad.

Pasos:

1. **Atomo por enunciado exacto.** Se normaliza el enunciado (minusculas, sin
   tildes, sin puntuacion, espacios colapsados) y se agrupan las apariciones
   con enunciado normalizado IDENTICO. Esto colapsa el grueso de repeticiones
   verbatim del banco oficial sin riesgo de fusionar preguntas distintas.

2. **Fusion difusa CONSERVADORA de atomos.** Dos atomos con enunciados
   *casi* identicos (rapidfuzz ``token_set_ratio`` >= umbral) se fusionan
   SOLO si sus respuestas son compatibles (comparten una respuesta parecida, o
   alguno no trae respuesta marcada). Asi se absorben variantes de OCR del
   enunciado sin fusionar preguntas plantilla que solo difieren en una palabra
   clave y tienen respuesta distinta (p.ej. codigos ATP "FRF" vs "FRC").

3. **Resolucion de la respuesta.** Dentro de un cluster se agrupan las
   variantes con respuesta por el TEXTO de su opcion correcta (fusion difusa
   para tolerar diferencias de redaccion; NO por la letra, que los modelos A/B
   barajan). Las variantes sin respuesta (cuadernillos) solo suman frecuencia.
     - 1 texto de respuesta -> 1 pregunta canonica.
     - >=2 textos distintos -> CONFLICTO: no se elige en silencio. Se emite una
       entrada canonica por cada respuesta distinta, marcada con
       ``conflicto_respuesta=True``, y el cluster se cuenta en
       ``clusters_con_conflicto_respuesta``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from .normalize import normalize

DEFAULT_ENUN_THRESHOLD = 90.0
DEFAULT_ANSWER_THRESHOLD = 90.0
# Similitud minima de las OPCIONES para fusionar dos atomos. La identidad de
# una pregunta incluye sus opciones: dos preguntas con el mismo enunciado
# (a menudo generico, p.ej. "Señale la afirmación correcta:") pero opciones
# distintas son preguntas DISTINTAS y no deben fusionarse.
DEFAULT_OPTION_THRESHOLD = 85.0
# Descarte rapido: no comparamos enunciados con longitudes muy dispares.
_LEN_RATIO_CUTOFF = 0.6


# --- Union-Find -------------------------------------------------------------


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


# --- Modelo -----------------------------------------------------------------


@dataclass
class CanonicalQuestion:
    id: str
    enunciado: str
    opciones: dict[str, str | None]
    respuesta_correcta: str | None
    respuesta_correcta_texto: str | None
    frecuencia: int
    fuentes: list[str]
    comunidades: list[str]
    variantes_enunciado: list[str]
    conflicto_respuesta: bool = False
    respuestas_en_conflicto: list[str] = field(default_factory=list)
    fuentes_sin_respuesta: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "enunciado": self.enunciado,
            "opciones": {k: self.opciones.get(k) for k in ("a", "b", "c", "d")},
            "respuesta_correcta": self.respuesta_correcta,
            "respuesta_correcta_texto": self.respuesta_correcta_texto,
            "frecuencia": self.frecuencia,
            "fuentes": self.fuentes,
            "comunidades": self.comunidades,
            "variantes_enunciado": self.variantes_enunciado,
            "conflicto_respuesta": self.conflicto_respuesta,
            "respuestas_en_conflicto": self.respuestas_en_conflicto,
            "fuentes_sin_respuesta": self.fuentes_sin_respuesta,
        }


# --- Atomo (grupo de enunciado exacto) --------------------------------------


@dataclass
class _Atom:
    enun_norm: str
    opt_sig: str  # firma normalizada de las opciones (independiente del orden)
    variants: list[dict]
    answer_norms: set[str]  # textos de respuesta normalizados (no vacios)


def _answer_text(q: dict) -> str | None:
    """Texto (original) de la opcion correcta de una pregunta cruda, o None."""
    letra = q.get("respuesta_correcta")
    if not letra:
        return None
    return (q.get("opciones") or {}).get(letra)


def _options_signature(q: dict) -> str:
    """Firma normalizada de las opciones, independiente del orden de letras.

    Los modelos A/B barajan el orden de las opciones (a/b/c/d), asi que la
    firma ordena los textos normalizados. Preguntas con el mismo enunciado
    generico pero opciones distintas producen firmas distintas y quedan
    separadas; la misma pregunta en modelos A/B produce la misma firma.
    """
    opts = q.get("opciones") or {}
    norms = sorted(n for n in (normalize(v) for v in opts.values() if v) if n)
    return " | ".join(norms)


def _make_id(enunciado_norm: str, answer_norm: str | None, opt_sig: str = "") -> str:
    # La identidad incluye las OPCIONES: dos preguntas con el mismo enunciado
    # (a menudo generico) y la misma respuesta-texto pero opciones distintas son
    # preguntas DISTINTAS y deben tener id distinto (unicidad de clave primaria).
    payload = f"{enunciado_norm}||{answer_norm or ''}||{opt_sig}"
    return "cap-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _build_atoms(raw_questions: list[dict]) -> list[_Atom]:
    # La identidad exacta de una pregunta es (enunciado, opciones). Agrupar solo
    # por enunciado colapsaria preguntas distintas que comparten un enunciado
    # generico y cuyo contenido real vive en las opciones.
    groups: dict[tuple[str, str], list[dict]] = {}
    for q in raw_questions:
        enun_key = normalize(q["enunciado"])
        if not enun_key:
            continue
        groups.setdefault((enun_key, _options_signature(q)), []).append(q)

    atoms: list[_Atom] = []
    for (enun_key, opt_sig), variants in groups.items():
        answers = {
            normalize(a)
            for a in (_answer_text(v) for v in variants)
            if a and normalize(a)
        }
        atoms.append(
            _Atom(
                enun_norm=enun_key,
                opt_sig=opt_sig,
                variants=variants,
                answer_norms=answers,
            )
        )
    return atoms


def _answers_compatible(a: _Atom, b: _Atom, answer_threshold: float) -> bool:
    """Dos atomos son compatibles si pueden ser la misma pregunta.

    - Si alguno no trae respuesta marcada, se permite (el cuadernillo se adhiere
      a la pregunta con respuesta).
    - Si ambos traen respuesta, deben compartir al menos una respuesta parecida.
    """
    if not a.answer_norms or not b.answer_norms:
        return True
    for ta in a.answer_norms:
        for tb in b.answer_norms:
            if fuzz.token_set_ratio(ta, tb) >= answer_threshold:
                return True
    return False


def _merge_atoms(
    atoms: list[_Atom],
    enun_threshold: float,
    answer_threshold: float,
    option_threshold: float = DEFAULT_OPTION_THRESHOLD,
) -> list[list[_Atom]]:
    """Fusion difusa conservadora de atomos.

    Dos atomos se fusionan SOLO si son casi la misma pregunta: enunciado
    similar, OPCIONES similares y respuestas compatibles. Incluir las opciones
    en el criterio evita fusionar preguntas realmente distintas que comparten
    estructura (p.ej. "...denominado TSR?" vs "...SLI?", o los tipos de
    ralentizador electrico/hidrodinamico/freno-en-escape).
    """
    n = len(atoms)
    uf = _UnionFind(n)
    for i in range(n):
        ei = atoms[i].enun_norm
        li = len(ei)
        for j in range(i + 1, n):
            ej = atoms[j].enun_norm
            lj = len(ej)
            if li and lj and min(li, lj) / max(li, lj) < _LEN_RATIO_CUTOFF:
                continue
            if fuzz.token_set_ratio(ei, ej) < enun_threshold:
                continue
            if fuzz.token_set_ratio(atoms[i].opt_sig, atoms[j].opt_sig) < option_threshold:
                continue
            if not _answers_compatible(atoms[i], atoms[j], answer_threshold):
                continue
            uf.union(i, j)

    clusters: dict[int, list[_Atom]] = {}
    for idx in range(n):
        clusters.setdefault(uf.find(idx), []).append(atoms[idx])
    return list(clusters.values())


# --- Resolucion de respuesta dentro de un cluster ---------------------------


def _subgroup_answers(
    answered: list[dict], answer_threshold: float
) -> list[list[dict]]:
    """Agrupa variantes-con-respuesta por texto de respuesta (fusion difusa)."""
    # Representante por texto normalizado exacto primero.
    by_norm: dict[str, list[dict]] = {}
    for q in answered:
        by_norm.setdefault(normalize(_answer_text(q)), []).append(q)

    keys = list(by_norm.keys())
    uf = _UnionFind(len(keys))
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if fuzz.token_set_ratio(keys[i], keys[j]) >= answer_threshold:
                uf.union(i, j)

    merged: dict[int, list[dict]] = {}
    for idx, key in enumerate(keys):
        merged.setdefault(uf.find(idx), []).extend(by_norm[key])
    return list(merged.values())


def _resolve_cluster(
    variants: list[dict], answer_threshold: float
) -> tuple[list[CanonicalQuestion], bool]:
    answered = [q for q in variants if _answer_text(q)]
    no_answer = [q for q in variants if not _answer_text(q)]

    subgroups = _subgroup_answers(answered, answer_threshold) if answered else []

    if len(subgroups) <= 1:
        entry = _make_entry(
            all_variants=variants,
            answered_variants=subgroups[0] if subgroups else [],
            conflict=False,
        )
        return [entry], False

    # Conflicto: una entrada por respuesta distinta.
    entries = [
        _make_entry(
            all_variants=sg,
            answered_variants=sg,
            conflict=True,
            unassigned=no_answer,
        )
        for sg in subgroups
    ]
    # La lista de respuestas en conflicto se deriva de las propias entradas
    # emitidas, garantizando que la respuesta de cada entrada aparece en ella.
    conflict_texts = sorted(
        {e.respuesta_correcta_texto for e in entries if e.respuesta_correcta_texto}
    )
    for e in entries:
        e.respuestas_en_conflicto = conflict_texts
    return entries, True


def _pick_representative(variants: list[dict]) -> dict:
    """Variante mas 'canonica': con respuesta y fecha mas reciente."""

    def sort_key(q: dict):
        return (1 if q.get("respuesta_correcta") else 0, q.get("fecha") or "")

    return sorted(variants, key=sort_key, reverse=True)[0]


def _make_entry(
    all_variants: list[dict],
    answered_variants: list[dict],
    conflict: bool,
    conflict_texts: list[str] | None = None,
    unassigned: list[dict] | None = None,
) -> CanonicalQuestion:
    rep = _pick_representative(answered_variants or all_variants)
    letra = rep.get("respuesta_correcta")
    resp_texto = _answer_text(rep)

    fuentes = sorted({q["fuente"] for q in all_variants})
    comunidades = sorted({q["comunidad"] for q in all_variants})
    variantes = sorted({q["enunciado"] for q in all_variants})

    enun_norm = normalize(rep["enunciado"])
    ans_norm = normalize(resp_texto) if resp_texto else None
    opt_sig = _options_signature(rep)
    fuentes_sin = sorted({q["fuente"] for q in unassigned}) if unassigned else []

    return CanonicalQuestion(
        id=_make_id(enun_norm, ans_norm, opt_sig),
        enunciado=rep["enunciado"],
        opciones={k: (rep.get("opciones") or {}).get(k) for k in ("a", "b", "c", "d")},
        respuesta_correcta=letra if resp_texto else None,
        respuesta_correcta_texto=resp_texto,
        frecuencia=len(fuentes),
        fuentes=fuentes,
        comunidades=comunidades,
        variantes_enunciado=variantes,
        conflicto_respuesta=conflict,
        respuestas_en_conflicto=conflict_texts or [],
        fuentes_sin_respuesta=fuentes_sin,
    )


# --- API principal ----------------------------------------------------------


def build_bank(
    raw_questions: list[dict],
    enun_threshold: float = DEFAULT_ENUN_THRESHOLD,
    answer_threshold: float = DEFAULT_ANSWER_THRESHOLD,
    option_threshold: float = DEFAULT_OPTION_THRESHOLD,
) -> tuple[list[CanonicalQuestion], int]:
    """Construye el banco canonico a partir de preguntas crudas (dicts).

    Devuelve (lista de CanonicalQuestion, clusters_con_conflicto_respuesta).
    """
    atoms = _build_atoms(raw_questions)
    clusters = _merge_atoms(atoms, enun_threshold, answer_threshold, option_threshold)

    canonical: list[CanonicalQuestion] = []
    conflict_clusters = 0
    for atom_group in clusters:
        variants: list[dict] = []
        for atom in atom_group:
            variants.extend(atom.variants)
        entries, is_conflict = _resolve_cluster(variants, answer_threshold)
        canonical.extend(entries)
        if is_conflict:
            conflict_clusters += 1

    canonical.sort(key=lambda c: (-c.frecuencia, c.enunciado))
    return canonical, conflict_clusters
