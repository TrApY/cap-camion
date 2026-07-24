"""Extraccion de preguntas desde los PDF de examenes CAP.

Formato del corpus (validado sobre los 56 PDF reales de Andalucia y
Extremadura). Todos comparten la misma plantilla textual:

    EXAMEN OBTENCION DEL CAP
    Fecha: 18-07-2025 09:00 AM Examen: MERCANCIAS A
    Lugar: ... Duracion: 120 MINUTOS
    1. <enunciado, puede ocupar varias lineas>
    a) <opcion, puede ocupar varias lineas>
    b) ...
    * c) <la opcion correcta va marcada con un asterisco delante>
    d) ...
    Referencia Legal: ...        <- linea de cierre de la pregunta
    2. ...

Variantes reales contempladas:
  - Asterisco con o sin espacio: "* c)" y "*c)".
  - Cabecera con o sin espacios: "Fecha: 14-03-2026" y "Fecha:14-03-2026".
  - Cuadernillos sin respuesta marcada (ningun asterisco) -> respuesta null.
  - Plantillas OMR de 1 pagina (hoja de respuestas en blanco, sin preguntas)
    -> el PDF se procesa pero no aporta preguntas.

La extraccion usa pypdf (rapido y con buena fidelidad de layout en este
corpus). El parseo es una maquina de estados linea a linea, robusta a
enunciados y opciones multilinea.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

# --- Anclas de parseo -------------------------------------------------------

# Inicio de pregunta: "12." o "12 ." al principio de linea, seguido de texto.
_RE_QUESTION = re.compile(r"^\s*(\d{1,3})\s*\.\s*(.*)$")
# Opcion: letra a-d seguida de ")", con asterisco opcional delante (correcta).
_RE_OPTION = re.compile(r"^\s*(\*?)\s*([a-dA-D])\)\s?(.*)$")
# Cierre de pregunta (linea de referencia legal/doctrinal).
_RE_REFERENCE = re.compile(r"^\s*Referencia\b", re.IGNORECASE)

# Ruido de cabecera/pie que debe descartarse.
#
# Estas lineas de cabecera/pie se repiten en la parte superior de CADA pagina
# del PDF. Cuando una pregunta u opcion se parte entre dos paginas, el bloque
# de cabecera se incrusta en medio del texto ("bleed"). Se filtran por dos
# mecanismos complementarios (ver ``parse_questions``):
#   1. Patrones regex (anclados a inicio de linea) para marcadores conocidos.
#   2. Deteccion de lineas repetidas en la mayoria de las paginas (generico).
_NOISE_PATTERNS = [
    re.compile(r"^\s*EXAMEN\s+OBTENCI", re.IGNORECASE),
    re.compile(r"^\s*EXAMEN\s+DE\b", re.IGNORECASE),
    re.compile(r"^\s*EXAMEN\s*:", re.IGNORECASE),
    re.compile(r"^\s*CUALIFICACI", re.IGNORECASE),
    re.compile(r"^\s*Fecha\s*:", re.IGNORECASE),
    re.compile(r"^\s*Lugar\s*:", re.IGNORECASE),
    re.compile(r"^\s*Duraci[oó]n\s*:", re.IGNORECASE),
    re.compile(r"^\s*CENTRO\s+REGIONAL\s+DE\s+TRANSPORTES", re.IGNORECASE),
    re.compile(r"^\s*ETIQUETA\s+IDENTIFICATIVA", re.IGNORECASE),
    re.compile(r"^\s*P[aá]gina\s+\d+\s+de\s+\d+", re.IGNORECASE),
    # Continuacion tipica de la linea "Lugar:" en los examenes de Granada:
    #   "... CAMPUS \n UNIV. FUENTE NUEVA, GRANADA, GRANADA".
    re.compile(r"^\s*UNIV\.\s+FUENTE\s+NUEVA", re.IGNORECASE),
]

# Umbral (fraccion de paginas) para considerar una linea como cabecera/pie
# repetida. La cabecera aparece en el 100% de las paginas; el contenido real
# (enunciados/opciones) no se repite entre paginas.
_REPEATED_LINE_RATIO = 0.6
# Solo se buscan lineas repetidas en la zona superior/inferior de cada pagina,
# para no eliminar por error contenido del cuerpo que pudiera coincidir.
_HEADER_ZONE_LINES = 6
_FOOTER_ZONE_LINES = 4

# Metadatos dentro del texto.
_RE_META_FECHA = re.compile(r"Fecha\s*:\s*(\d{2}-\d{2}-\d{4})")
_RE_META_MODELO = re.compile(r"Examen\s*:\s*MERCANC[IÍ]AS\s*([AB])", re.IGNORECASE)
# Fecha en el nombre de fichero tipo AND_01_2025_01_...  -> (2025, 01)
_RE_FILE_DATE = re.compile(r"_(\d{4})_(\d{2})_")
_RE_FILE_MODELO = re.compile(r"MODELO\s*([AB])|modelo\s*([ab])", re.IGNORECASE)


@dataclass
class RawQuestion:
    """Una pregunta tal cual se extrae de un PDF (antes de deduplicar)."""

    enunciado: str
    opciones: dict[str, str | None]
    respuesta_correcta: str | None  # letra "a".."d" o None
    fuente: str
    comunidad: str
    fecha: str | None
    modelo: str | None

    def to_dict(self) -> dict:
        return {
            "enunciado": self.enunciado,
            "opciones": {k: self.opciones.get(k) for k in ("a", "b", "c", "d")},
            "respuesta_correcta": self.respuesta_correcta,
            "fuente": self.fuente,
            "comunidad": self.comunidad,
            "fecha": self.fecha,
            "modelo": self.modelo,
        }


@dataclass
class PdfResult:
    """Resultado de procesar un PDF."""

    fuente: str
    comunidad: str
    questions: list[RawQuestion] = field(default_factory=list)
    error: str | None = None


# --- Utilidades -------------------------------------------------------------


def _is_noise(line: str) -> bool:
    return any(pat.search(line) for pat in _NOISE_PATTERNS)


def _clean(text: str) -> str:
    """Colapsa espacios internos y recorta; conserva el contenido literal."""
    return re.sub(r"\s+", " ", text).strip()


def read_pdf_pages(path: str | Path) -> list[str]:
    """Devuelve el texto de cada pagina del PDF por separado."""
    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def read_pdf_text(path: str | Path) -> str:
    """Devuelve todo el texto del PDF (paginas unidas por salto de linea)."""
    return "\n".join(read_pdf_pages(path))


def detect_repeated_lines(pages: list[str]) -> set[str]:
    """Detecta lineas de cabecera/pie que se repiten entre paginas.

    Una linea es cabecera/pie si aparece (en la zona superior o inferior de la
    pagina) en al menos ``_REPEATED_LINE_RATIO`` de las paginas del PDF. Se
    devuelve el conjunto de esas lineas ya recortadas (``strip``), para
    filtrarlas literalmente antes de parsear.

    Con un solo folio no hay repeticion posible: se devuelve conjunto vacio y
    el filtrado recae en los patrones regex.
    """
    n = len(pages)
    if n < 2:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        plines = [ln.strip() for ln in page.split("\n") if ln.strip()]
        if not plines:
            continue
        zone = set(plines[:_HEADER_ZONE_LINES]) | set(plines[-_FOOTER_ZONE_LINES:])
        for ln in zone:
            counts[ln] += 1

    threshold = max(2, math.ceil(n * _REPEATED_LINE_RATIO))
    return {ln for ln, c in counts.items() if c >= threshold}


def _extract_metadata(text: str, filename: str) -> tuple[str | None, str | None]:
    """Extrae (fecha ISO YYYY-MM-DD, modelo 'A'/'B') del texto o del nombre."""
    fecha = None
    m = _RE_META_FECHA.search(text)
    if m:
        d, mth, y = m.group(1).split("-")
        fecha = f"{y}-{mth}-{d}"
    else:
        m = _RE_FILE_DATE.search(filename)
        if m:
            fecha = f"{m.group(1)}-{m.group(2)}-01"

    modelo = None
    m = _RE_META_MODELO.search(text)
    if m:
        modelo = m.group(1).upper()
    else:
        m = _RE_FILE_MODELO.search(filename)
        if m:
            modelo = (m.group(1) or m.group(2)).upper()
    return fecha, modelo


# --- Parser de preguntas ----------------------------------------------------


class _QuestionBuilder:
    """Acumulador mutable de una pregunta durante el parseo."""

    def __init__(self, numero: int, primer_texto: str):
        self.numero = numero
        self.enunciado_parts: list[str] = [primer_texto] if primer_texto else []
        self.opciones: dict[str, list[str]] = {}
        self.orden: list[str] = []
        self.correcta: str | None = None
        self._current: str | None = None  # None=enunciado, o letra de opcion

    def add_option(self, letra: str, starred: bool, texto: str) -> None:
        letra = letra.lower()
        if letra not in self.opciones:
            self.orden.append(letra)
        self.opciones[letra] = [texto] if texto else []
        self._current = letra
        if starred and self.correcta is None:
            self.correcta = letra

    def add_continuation(self, texto: str) -> None:
        if self._current is None:
            self.enunciado_parts.append(texto)
        elif self._current == "__done__":
            # Estamos tras la linea de Referencia: ignorar continuaciones
            # (referencias multilinea) hasta la siguiente pregunta.
            return
        else:
            self.opciones[self._current].append(texto)

    def close_options(self) -> None:
        # Llega la linea de "Referencia": dejamos de acumular texto.
        self._current = "__done__"

    @property
    def n_options(self) -> int:
        return len(self.opciones)

    def build(self, fuente, comunidad, fecha, modelo) -> RawQuestion | None:
        enunciado = _clean(" ".join(self.enunciado_parts))
        if not enunciado or self.n_options < 2:
            return None
        opciones = {
            k: _clean(" ".join(v)) for k, v in self.opciones.items()
        }
        return RawQuestion(
            enunciado=enunciado,
            opciones=opciones,
            respuesta_correcta=self.correcta,
            fuente=fuente,
            comunidad=comunidad,
            fecha=fecha,
            modelo=modelo,
        )


def parse_questions(
    text: str,
    fuente: str,
    comunidad: str,
    fecha: str | None,
    modelo: str | None,
    repeated_noise: set[str] | None = None,
) -> tuple[list[RawQuestion], int]:
    """Parsea el texto de un examen y devuelve (preguntas, descartadas).

    'descartadas' cuenta bloques que empezaron como pregunta pero no llegaron
    a tener enunciado + >=2 opciones (parseo incompleto).

    ``repeated_noise`` es el conjunto de lineas de cabecera/pie detectadas por
    repeticion entre paginas (ver ``detect_repeated_lines``); se filtran ademas
    de los patrones regex, evitando el "bleed" de cabecera dentro de
    enunciados/opciones cuando una pregunta se parte entre paginas.
    """
    repeated_noise = repeated_noise or set()
    questions: list[RawQuestion] = []
    descartadas = 0
    builder: _QuestionBuilder | None = None

    def flush() -> None:
        nonlocal descartadas
        if builder is None:
            return
        q = builder.build(fuente, comunidad, fecha, modelo)
        if q is None:
            descartadas += 1
        else:
            questions.append(q)

    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.strip() in repeated_noise:
            continue
        if _is_noise(line):
            continue

        m_q = _RE_QUESTION.match(line)
        # Solo tratamos "N." como nueva pregunta si no estamos a mitad de un
        # enunciado sin opciones (evita falsos positivos por texto que empieza
        # con un numero y punto dentro del enunciado/opcion).
        if m_q and (builder is None or builder.n_options >= 2):
            flush()
            builder = _QuestionBuilder(int(m_q.group(1)), m_q.group(2).strip())
            continue

        if builder is None:
            continue

        m_ref = _RE_REFERENCE.match(line)
        if m_ref:
            builder.close_options()
            continue

        m_opt = _RE_OPTION.match(line)
        if m_opt:
            builder.add_option(
                m_opt.group(2), bool(m_opt.group(1)), m_opt.group(3).strip()
            )
            continue

        builder.add_continuation(line.strip())

    flush()
    return questions, descartadas


def process_pdf(path: str | Path, comunidad: str) -> tuple[PdfResult, int]:
    """Procesa un PDF completo. Devuelve (PdfResult, preguntas_descartadas)."""
    path = Path(path)
    fuente = path.name
    try:
        pages = read_pdf_pages(path)
    except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo de PDF
        return PdfResult(fuente=fuente, comunidad=comunidad, error=str(exc)), 0

    text = "\n".join(pages)
    repeated_noise = detect_repeated_lines(pages)
    fecha, modelo = _extract_metadata(text, fuente)
    questions, descartadas = parse_questions(
        text, fuente, comunidad, fecha, modelo, repeated_noise=repeated_noise
    )
    return (
        PdfResult(fuente=fuente, comunidad=comunidad, questions=questions),
        descartadas,
    )
