#!/usr/bin/env python3
"""Recupera el TEXTO REAL de los artículos citados por el banco oficial del CAP.

Fase 2 de CAP-18. El campo ``norma`` de ``db/out/ministerio_match.json`` trae 709
referencias normativas ("Ley 16/1987 Art. 22", "RD 773/1997 Anexo I", …). Aquí se
resuelve cada NORMA BASE con al menos ``MIN_REFS`` referencias contra su fuente
oficial y se cachea el texto limpio de los artículos/anexos citados, que en la
Fase 3 irá al prompt como ancla anti-alucinación.

La cita que ve el usuario es SIEMPRE la del Ministerio tal cual: esto solo mejora
el CONTEXTO. Una norma que no se pueda resolver limpiamente se marca
``no-resuelta`` y se sigue; no hay heroicidades con fuentes difíciles.

Fuentes (contrato verificado contra la documentación oficial, no contra memoria):

  * **BOE, API de legislación consolidada** (``https://www.boe.es/datosabiertos``,
    documento ``APIconsolidada.pdf`` de 2025-09-02):
      - Búsqueda ``GET /datosabiertos/api/legislacion-consolidada?query={json}``
        con ``Accept: application/json``; el ``query`` es
        ``{"query":{"query_string":{"query":"campo:valor"}}}`` sobre los campos
        permitidos (``numero_oficial``, ``titulo``, ``rango@codigo``…). Responde
        ``{"status":…,"data":[{identificador,titulo,rango,ambito,numero_oficial…}]}``.
      - Texto ``GET /datosabiertos/api/legislacion-consolidada/id/{id}/texto`` con
        ``Accept: application/xml``: ``<bloque id tipo titulo>`` con una o varias
        ``<version fecha_publicacion fecha_vigencia>`` y el texto en ``<p>``.
        El atributo ``titulo`` del bloque ("Artículo 22", "ANEXO I") es lo que
        permite extraer justo lo citado.
  * **EUR-Lex** para los reglamentos comunitarios: CELEX determinista y HTML en
    ``https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:…``. El HTML
    trae anclas ``<div class="eli-subdivision" id="art_34">`` y
    ``<div class="eli-container" id="anx_I">``; si faltasen se cae a regex sobre
    el texto plano.

Convenios internacionales, acuerdos, directivas y resoluciones quedan FUERA DE
ALCANCE en v1: se marcan ``no-resuelta`` sin gastar una sola petición.

Dos pasos independientes, como en ``ministerio_descarga.py``:

  1. **Descarga** (red), cortés: user-agent de navegador, espera aleatoria de
     3-6 s entre peticiones, backoff de 60 s y UN reintento ante 403/429. Todo lo
     bajado se guarda TAL CUAL en ``data/normativa/`` con un ``manifest.json``
     (url, fecha, sha256, bytes); si una URL ya está en el manifest NO se repite,
     así que re-ejecutar cuesta 0 peticiones.
  2. **Extracción** (sin red, ``--solo-extraer``). Escribe
     ``db/out/normativa_cache.json`` y ``db/out/normativa_report.md``.

Uso:
    python3 db/normativa_textos.py                  # descarga + extracción
    python3 db/normativa_textos.py --solo-descargar
    python3 db/normativa_textos.py --solo-extraer   # re-extrae del raw, sin red
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import random
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO / "data" / "normativa"
MANIFEST = RAW_DIR / "manifest.json"
OUT_DIR = REPO / "db" / "out"
MATCH_JSON = OUT_DIR / "ministerio_match.json"
CACHE_JSON = OUT_DIR / "normativa_cache.json"
REPORT_MD = OUT_DIR / "normativa_report.md"

# Universo: normas base con al menos estas referencias en el match. El resto es
# cola larga y ni se intenta (se lista en el informe).
MIN_REFS = 4

# Límites de texto (§4 de la spec).
LIMITE_BLOQUE = 20 * 1024  # bytes utf-8 por artículo/anexo extraído
LIMITE_NORMA_COMPLETA = 50 * 1024  # por debajo de esto se guarda la norma entera
CLAVE_COMPLETO = "[texto completo]"

# Cortesía: dos servicios públicos, pocas peticiones y espaciadas.
ESPERA_MIN, ESPERA_MAX = 3.0, 6.0
ESPERA_BLOQUEO = 60.0
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
CABECERAS = {
    "User-Agent": UA,
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, identity",
    "Connection": "close",
}

BOE_API = "https://www.boe.es/datosabiertos/api/legislacion-consolidada"
EURLEX_HTML = "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:{celex}"


class DescargaFallida(RuntimeError):
    """Una URL concreta no se pudo traer: la norma se marca no-resuelta."""


# --- utilidades de disco ----------------------------------------------------


def cargar(path: pathlib.Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def guardar(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


# --- 1. parseo de referencias (funciones puras) -----------------------------
#
# "Ley 16/1987 Art. 22" -> ("Ley 16/1987", "Art. 22")
# El localizador es la cola "Art. N" / "Anexo X, apartado …" de la referencia;
# la norma base es todo lo anterior.

_TIPOS_ESTRUCTURADOS = r"""
      Reglamento\s+Comunitario\s+\((?:CE|UE|CEE)\)\s+\d+/\d+
    | Directiva\s+\d+/\d+/(?:CE|UE|CEE)
    | (?:Ley\s+Org[áa]nica|Ley|RD\s+Legislativo|RD)\s+\d+/\d{4}
    | OM\s+[A-Z]{2,5}/\d+/\d{4}
    | (?:OM|Orden)\s+\d{2}/\d{2}/\d{4}
"""
# La norma base va al principio y ha de terminar en frontera de palabra: así
# "…(UE) 165/2014 Anexo IB, apartado II, 3 (3821/85)" corta en el sitio correcto
# y las referencias combinadas ("…952/2013;(UE) 2015/2446 …") NO se atribuyen a
# la primera norma (caen al camino genérico y quedan como base propia).
RE_BASE_ESTRUCTURADA = re.compile(
    rf"^(?P<base>{_TIPOS_ESTRUCTURADOS})(?=\s|$)", re.VERBOSE
)

# Camino genérico para lo que no encaja en un tipo conocido (convenios,
# acuerdos, resoluciones…): el localizador empieza en la primera palabra clave
# de localización.
RE_INICIO_LOCALIZADOR = re.compile(
    r"\b(?:Arts?\.?|Art[íi]culos?|Anexos?|Anejos?|Ap[ée]ndices?|T[íi]tulos?"
    r"|Cap[íi]tulos?|Disposici[óo]n|Pre[áa]mbulo|Considerandos?|Introducci[óo]n)\b"
)


def parsear_referencia(referencia: str) -> tuple[str, str | None]:
    """Parte una referencia ministerial en (norma_base, localizador | None)."""
    texto = re.sub(r"\s+", " ", (referencia or "").replace("\xa0", " ")).strip()
    if not texto:
        return "", None

    m = RE_BASE_ESTRUCTURADA.match(texto)
    if m:
        base = m.group("base")
        resto = texto[m.end() :].strip()
        return base, (resto or None)

    m = RE_INICIO_LOCALIZADOR.search(texto)
    if m and m.start() > 0:
        base = texto[: m.start()].strip().rstrip(".,;:")
        return base, texto[m.start() :].strip()
    return texto, None


# --- clasificación de la norma base -----------------------------------------
#
# Solo dos clases se intentan resolver:
#   * "espanola": norma estatal CON número oficial N/AAAA (o SIGLAS/N/AAAA), que
#     es lo único que permite verificar la identidad contra el título del BOE.
#   * "ue": reglamentos comunitarios, con CELEX determinista.
# Todo lo demás -> "fuera-alcance" (v1), sin gastar peticiones.

RANGOS_ESPANOLES: tuple[tuple[str, str], ...] = (
    # (patrón sobre la norma base, rango tal y como lo publica el BOE)
    (r"^Ley\s+Org[áa]nica\s+(?P<num>\d+/\d{4})$", "Ley Orgánica"),
    (r"^RD\s+Legislativo\s+(?P<num>\d+/\d{4})$", "Real Decreto Legislativo"),
    (r"^RD\s+(?P<num>\d+/\d{4})$", "Real Decreto"),
    (r"^Ley\s+(?P<num>\d+/\d{4})$", "Ley"),
    (r"^(?:OM|Orden)\s+(?P<num>[A-Z]{2,5}/\d+/\d{4})$", "Orden"),
)
RE_REGLAMENTO_UE = re.compile(
    r"^Reglamento\s+Comunitario\s+\((?P<mercado>CE|UE|CEE)\)\s+(?P<a>\d+)/(?P<b>\d+)$"
)


def clasificar_norma(base: str) -> dict:
    """Clasifica una norma base: cómo (y si) se puede resolver.

    Devuelve ``{"clase": "espanola"|"ue"|"fuera-alcance", …}``. Para las
    españolas incluye ``numero_oficial`` y ``rango``; para las comunitarias,
    ``celex``. Las de fuera de alcance llevan ``motivo``.
    """
    texto = re.sub(r"\s+", " ", (base or "")).strip()

    for patron, rango in RANGOS_ESPANOLES:
        m = re.match(patron, texto)
        if m:
            return {
                "clase": "espanola",
                "numero_oficial": m.group("num"),
                "rango": rango,
            }

    m = RE_REGLAMENTO_UE.match(texto)
    if m:
        return {
            "clase": "ue",
            "celex": celex_reglamento(m.group("a"), m.group("b")),
            "numero": _numero_y_anio(m.group("a"), m.group("b"))[0],
            "anio": _numero_y_anio(m.group("a"), m.group("b"))[1],
        }

    if re.match(r"^(?:OM|Orden|Resoluci[óo]n)\b", texto):
        return {
            "clase": "fuera-alcance",
            "motivo": "norma identificada por fecha, sin número oficial verificable",
        }
    if re.match(r"^Directiva\b", texto):
        return {"clase": "fuera-alcance", "motivo": "directiva: fuera de alcance v1"}
    return {
        "clase": "fuera-alcance",
        "motivo": "convenio/acuerdo/otros: fuera de alcance v1",
    }


def _numero_y_anio(a: str, b: str) -> tuple[int, int]:
    """De "561/2006" o "2015/2446" saca (número, año).

    En las citas ministeriales el patrón habitual es ``numero/año`` (561/2006 ->
    número 561, año 2006). Pero la UE numera año/número desde 2015 y el
    Ministerio copia ese formato tal cual ("(UE) 2015/2446"), así que se toma
    como año la parte que lo parece; si ninguna lo parece, manda ``numero/año``.
    """
    na, nb = int(a), int(b)
    a_es_anio = 1950 <= na <= 2099
    b_es_anio = 1950 <= nb <= 2099
    if a_es_anio and not b_es_anio:
        return nb, na
    return na, nb


def celex_reglamento(a: str, b: str) -> str:
    """CELEX de un reglamento comunitario: ``3{AAAA}R{NNNN}``."""
    numero, anio = _numero_y_anio(a, b)
    return f"3{anio:04d}R{numero:04d}"


# --- localizador -> objetivos de extracción ---------------------------------
#
# "Art. 143.4"                       -> ["143"]
# "Arts. 17 y 18"                    -> ["17", "18"]
# "Art. 157;Art. 316"                -> ["157", "316"]
# "Anexo IB, apartado II, 3 (3821/85)" -> ["Anexo IB"]
# "Art. 2 y Anexos I y II"           -> ["2", "Anexo I", "Anexo II"]

RE_ARTICULOS = re.compile(
    r"(?:\bArts?\b\.?|\bArt[íi]culos?\b)\s+"
    r"(?P<lista>\d+[\w.ºª]*(?:\s+(?:bis|ter|quater))?"
    r"(?:\s*(?:,|y)\s*\d+[\w.ºª]*(?:\s+(?:bis|ter|quater))?)*)",
    re.IGNORECASE,
)
RE_ANEXOS = re.compile(
    r"\b(?P<clase>Anexos?|Anejos?)\b"
    r"(?:\s+(?P<lista>[IVXLC]+[A-Z]?(?:\s*y\s*[IVXLC]+[A-Z]?)*))?",
    re.IGNORECASE,
)


def _normalizar_articulo(bruto: str) -> str | None:
    """"143.4" -> "143"; "10 bis 3" -> "10 bis"; "Preliminar" -> None."""
    m = re.match(r"^(\d+)(?:\s+(bis|ter|quater))?", bruto.strip(), re.IGNORECASE)
    if not m:
        return None
    return m.group(1) if not m.group(2) else f"{m.group(1)} {m.group(2).lower()}"


def objetivos_de_localizador(localizador: str | None) -> list[str]:
    """Artículos y anexos concretos que cita un localizador (sin duplicados)."""
    if not localizador:
        return []
    objetivos: list[str] = []

    for m in RE_ARTICULOS.finditer(localizador):
        for trozo in re.split(r"\s*(?:,|y)\s*", m.group("lista")):
            art = _normalizar_articulo(trozo)
            if art and art not in objetivos:
                objetivos.append(art)

    for m in RE_ANEXOS.finditer(localizador):
        clase = "Anejo" if m.group("clase").lower().startswith("anejo") else "Anexo"
        lista = m.group("lista")
        if not lista:
            if clase not in objetivos:
                objetivos.append(clase)
            continue
        for trozo in re.split(r"\s*y\s*", lista):
            clave = f"{clase} {trozo.strip().upper()}"
            if clave not in objetivos:
                objetivos.append(clave)

    return objetivos


# --- limpieza y recorte de texto --------------------------------------------


def limpiar(texto: str) -> str:
    """Espacios colapsados por línea, sin líneas vacías de más."""
    texto = (texto or "").replace("\xa0", " ").replace(" ", " ")
    lineas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in texto.split("\n")]
    return "\n".join(ln for ln in lineas if ln).strip()


def recortar(texto: str, limite: int = LIMITE_BLOQUE) -> str:
    """Corta a ``limite`` bytes utf-8 dejando marca explícita del truncado."""
    crudo = texto.encode("utf-8")
    if len(crudo) <= limite:
        return texto
    recorte = crudo[:limite].decode("utf-8", errors="ignore")
    return recorte.rstrip() + f"\n[…truncado a {limite // 1024} KB]"


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _normalizar_titulo(titulo: str) -> str:
    """Título de bloque comparable: sin acentos, mayúsculas, sin puntuación."""
    limpio = re.sub(r"\s+", " ", (titulo or "").replace("\xa0", " ")).strip()
    return _sin_acentos(limpio).upper().strip(" .:,")


# Las normas anteriores a los años 90 numeran sus artículos con LETRA
# ("Artículo dieciséis" en la Ley 50/1980, no "Artículo 16"), mientras el banco
# del Ministerio siempre cita en cifras. Sin esta equivalencia esas normas se
# resuelven pero no se les extrae ni un artículo.
_ORDINALES = (
    "",
    "primero",
    "segundo",
    "tercero",
    "cuarto",
    "quinto",
    "sexto",
    "séptimo",
    "octavo",
    "noveno",
    "décimo",
)
_CARDINALES = (
    "",
    "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve",
    "diez", "once", "doce", "trece", "catorce", "quince", "dieciséis",
    "diecisiete", "dieciocho", "diecinueve", "veinte", "veintiuno",
    "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
    "veintisiete", "veintiocho", "veintinueve",
)
_DECENAS = {
    3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta", 7: "setenta",
    8: "ochenta", 9: "noventa",
}


def _cardinal(n: int) -> str:
    """Número en letra tal y como lo escribe el BOE ("treinta y uno")."""
    if n <= 0:
        return ""
    if n < len(_CARDINALES):
        return _CARDINALES[n]
    if n < 100:
        decena, unidad = divmod(n, 10)
        palabra = _DECENAS[decena]
        return palabra if unidad == 0 else f"{palabra} y {_CARDINALES[unidad]}"
    if n < 200:
        resto = n - 100
        return "ciento" if resto == 0 else f"ciento {_cardinal(resto)}"
    return ""


_ROMANOS = (("C", 100), ("XC", 90), ("L", 50), ("XL", 40), ("X", 10), ("IX", 9),
            ("V", 5), ("IV", 4), ("I", 1))


def romano_a_entero(texto: str) -> int | None:
    valores = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    if not texto or any(c not in valores for c in texto.upper()):
        return None
    total = 0
    previo = 0
    for c in reversed(texto.upper()):
        valor = valores[c]
        total += -valor if valor < previo else valor
        previo = max(previo, valor)
    return total or None


def entero_a_romano(n: int) -> str:
    salida = []
    for simbolo, valor in _ROMANOS:
        while n >= valor:
            salida.append(simbolo)
            n -= valor
    return "".join(salida)


def variantes_titulo(objetivo: str) -> list[str]:
    """Títulos de bloque (normalizados) que pueden corresponder al objetivo."""
    m = re.match(r"^(?P<clase>Anexo|Anejo)(?:\s+(?P<id>\S+))?$", objetivo, re.IGNORECASE)
    if m:
        clase = m.group("clase")
        ident = (m.group("id") or "").upper()
        if not ident:
            return [_normalizar_titulo(clase)]
        variantes = [f"{clase} {ident}"]
        # Los anexos se citan en romanos y algunas normas los titulan en cifras.
        if ident.isdigit():
            variantes.append(f"{clase} {entero_a_romano(int(ident))}")
        else:
            numero = romano_a_entero(ident)
            if numero:
                variantes.append(f"{clase} {numero}")
        return [_normalizar_titulo(v) for v in variantes]

    m = re.match(r"^(?P<num>\d+)(?:\s+(?P<sufijo>bis|ter|quater))?$", objetivo)
    if not m:
        return [_normalizar_titulo(f"Artículo {objetivo}")]
    numero = int(m.group("num"))
    sufijo = f" {m.group('sufijo')}" if m.group("sufijo") else ""
    formas = [str(numero)]
    if 1 <= numero <= 10:
        formas.append(_ORDINALES[numero])
    palabra = _cardinal(numero)
    if palabra:
        formas.append(palabra)
    return [_normalizar_titulo(f"Artículo {f}{sufijo}") for f in formas]


def _casa_titulo(titulo_bloque: str, objetivo: str) -> bool:
    """¿El bloque titulado ``titulo_bloque`` es el objetivo citado?

    Exige frontera: "ANEXO I" no puede casar con "ANEXO II", ni "Artículo 14"
    con "Artículo 14 bis".
    """
    real = _normalizar_titulo(titulo_bloque)
    for esperado in variantes_titulo(objetivo):
        if real == esperado:
            return True
        if not real.startswith(esperado):
            continue
        resto = real[len(esperado) :]
        if resto[:1].isalnum():
            continue  # "Artículo 14" no es el "Artículo 1"
        if re.match(r"^\s*(?:BIS|TER|QUATER)\b", resto):
            continue  # "Artículo 10 bis" no es el "Artículo 10"
        return True
    return False


# --- 4a. extracción sobre el XML consolidado del BOE ------------------------


def _texto_de_version(version: ET.Element) -> str:
    """Texto plano de una <version>, sin las notas de modificación."""
    partes: list[str] = []
    for hijo in version:
        etiqueta = hijo.tag.lower()
        if etiqueta in ("blockquote", "img"):
            continue  # notas al pie y facsímiles: ruido para el RAG
        trozo = limpiar(" ".join(hijo.itertext()))
        if trozo:
            partes.append(trozo)
    return "\n".join(partes)


def _version_vigente(bloque: ET.Element) -> ET.Element | None:
    """La versión más reciente del bloque (el texto consolidado de hoy)."""
    versiones = list(bloque.findall("version"))
    if not versiones:
        return None

    def clave(v: ET.Element) -> str:
        return v.get("fecha_vigencia") or v.get("fecha_publicacion") or ""

    return max(versiones, key=clave)


def extraer_articulos_boe(xml_datos: bytes, objetivos: list[str]) -> dict[str, str]:
    """Texto de cada objetivo a partir del XML de ``/id/{id}/texto``.

    Usa la estructura del XML consolidado: cada ``<bloque>`` trae el atributo
    ``titulo`` ("Artículo 22", "ANEXO I") y una o varias ``<version>``; se toma
    la más reciente.

    Se parsea con ``xml.etree`` de la stdlib (la fase no admite dependencias
    nuevas): el XML viene por HTTPS de la API oficial del BOE y se guarda bajo
    nuestro control, y ElementTree no resuelve entidades externas.
    """
    raiz = ET.fromstring(xml_datos)
    bloques = list(raiz.iter("bloque"))
    extraidos: dict[str, str] = {}
    for objetivo in objetivos:
        for i, bloque in enumerate(bloques):
            if not (bloque.get("titulo") or ""):
                continue
            if not _casa_titulo(bloque.get("titulo"), objetivo):
                continue
            texto = _texto_bloque(bloque)
            # Un anexo del BOE es un bloque tipo="encabezado" que solo lleva el
            # rótulo: su contenido va en los bloques siguientes, hasta el
            # próximo encabezado (otro anexo, un título, la firma…).
            if bloque.get("tipo") == "encabezado":
                for siguiente in bloques[i + 1 :]:
                    if _abre_bloque_nuevo(siguiente):
                        break
                    trozo = _texto_bloque(siguiente)
                    if trozo:
                        texto = f"{texto}\n{trozo}" if texto else trozo
                    if len(texto.encode("utf-8")) >= LIMITE_BLOQUE:
                        break
            if texto:
                extraidos[objetivo] = recortar(texto)
            break
    return extraidos


RE_ENCABEZADO = re.compile(
    r"^(?:ANEXO|ANEJO|TITULO|CAPITULO|SECCION|LIBRO|PARTE|ARTICULO|DISPOSICION)\b"
)


def _abre_bloque_nuevo(bloque: ET.Element) -> bool:
    """¿Este bloque ya no pertenece al anexo anterior?"""
    if bloque.get("tipo") in ("firma", "nota_inicial"):
        return True
    return bool(RE_ENCABEZADO.match(_normalizar_titulo(bloque.get("titulo") or "")))


def _texto_bloque(bloque: ET.Element) -> str:
    version = _version_vigente(bloque)
    return _texto_de_version(version) if version is not None else ""


def texto_completo_boe(xml_datos: bytes) -> str:
    """Todo el texto consolidado (versión vigente de cada bloque)."""
    raiz = ET.fromstring(xml_datos)
    partes = []
    for bloque in raiz.iter("bloque"):
        version = _version_vigente(bloque)
        if version is None:
            continue
        trozo = _texto_de_version(version)
        if trozo:
            partes.append(trozo)
    return "\n".join(partes)


# --- 4b. extracción sobre el HTML de EUR-Lex --------------------------------

RE_ETIQUETA = re.compile(r"<[^>]+>")
RE_SCRIPT = re.compile(r"<(script|style)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
# Fin de un bloque: la siguiente subdivisión/contenedor/separador/encabezado.
RE_FIN_BLOQUE = re.compile(
    r'<div class="eli-(?:subdivision|container)"'
    r'|<hr class="oj-doc-sep"'
    r'|<p class="oj-ti-section',
)


def html_a_texto(html: str) -> str:
    """Texto plano de un fragmento HTML (entidades resueltas, sin etiquetas)."""
    sin_scripts = RE_SCRIPT.sub(" ", html)
    con_saltos = re.sub(r"(?i)</(p|div|tr|h\d|li)>", "\n", sin_scripts)
    plano = RE_ETIQUETA.sub(" ", con_saltos)
    import html as _html

    return limpiar(_html.unescape(plano))


def _ancla_eurlex(objetivo: str) -> str | None:
    """Id del ancla EUR-Lex de un objetivo: "34" -> art_34; "Anexo I" -> anx_I."""
    m = re.match(r"^(?:Anexo|Anejo)\s+(?P<r>[IVXLC]+[A-Z]?)$", objetivo, re.IGNORECASE)
    if m:
        return f"anx_{m.group('r').upper()}"
    if re.fullmatch(r"\d+", objetivo):
        return f"art_{objetivo}"
    return None


def _bloque_por_ancla(html: str, ancla: str) -> str | None:
    m = re.search(rf'<div class="eli-(?:subdivision|container)" id="{re.escape(ancla)}">', html)
    if not m:
        return None
    inicio = m.end()
    fin = RE_FIN_BLOQUE.search(html, inicio)
    return html[m.start() : (fin.start() if fin else len(html))]


def _bloque_por_texto(plano: str, objetivo: str) -> str | None:
    """Plan B: regex sobre el texto plano (documentos sin anclas ELI)."""
    if re.fullmatch(r"\d+", objetivo):
        inicio = re.search(rf"^Artículo\s+{objetivo}\b", plano, re.MULTILINE)
        if not inicio:
            return None
        siguiente = re.search(r"^Artículo\s+\d+\b", plano[inicio.end() :], re.MULTILINE)
    else:
        etiqueta = _normalizar_titulo(objetivo)
        inicio = None
        for m in re.finditer(r"^(?:ANEXO|ANEJO)\s+[IVXLC]+[A-Z]?", plano, re.MULTILINE):
            if _normalizar_titulo(m.group(0)) == etiqueta:
                inicio = m
                break
        if not inicio:
            return None
        siguiente = re.search(
            r"^(?:ANEXO|ANEJO)\s+[IVXLC]+[A-Z]?", plano[inicio.end() :], re.MULTILINE
        )
    corte = inicio.end() + siguiente.start() if siguiente else len(plano)
    return plano[inicio.start() : corte]


def extraer_articulos_eurlex(html: str, objetivos: list[str]) -> dict[str, str]:
    """Texto de cada objetivo en el HTML de EUR-Lex.

    Primero por las anclas ``id="art_N"`` / ``id="anx_X"`` del marcado ELI, que
    delimitan el artículo exacto; si el documento no las trae, regex sobre el
    texto plano.
    """
    extraidos: dict[str, str] = {}
    plano: str | None = None
    for objetivo in objetivos:
        fragmento = None
        ancla = _ancla_eurlex(objetivo)
        if ancla:
            trozo_html = _bloque_por_ancla(html, ancla)
            if trozo_html:
                fragmento = html_a_texto(trozo_html)
        if not fragmento:
            if plano is None:
                plano = html_a_texto(html)
            fragmento = _bloque_por_texto(plano, objetivo)
        if fragmento:
            fragmento = limpiar(fragmento)
        if fragmento:
            extraidos[objetivo] = recortar(fragmento)
    return extraidos


# --- descarga cortés --------------------------------------------------------


class Descargador:
    """Cliente HTTP con caché en disco y reglas de cortesía (3-6 s)."""

    def __init__(self, manifest: dict, dormir: bool = True):
        self.manifest = manifest
        self.dormir = dormir
        self._primera = True
        self.peticiones = 0

    def _espera(self) -> None:
        if self._primera:
            self._primera = False
            return
        if not self.dormir:
            return
        segundos = random.uniform(ESPERA_MIN, ESPERA_MAX)
        print(f"    (cortesía: esperando {segundos:.1f}s)", flush=True)
        time.sleep(segundos)

    def _peticion(self, url: str, accept: str) -> tuple[bytes, str]:
        cabeceras = dict(CABECERAS)
        cabeceras["Accept"] = accept
        req = urllib.request.Request(url, headers=cabeceras)
        with urllib.request.urlopen(req, timeout=120) as resp:
            datos = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                datos = gzip.decompress(datos)
            return datos, resp.headers.get("Content-Type", "")

    def obtener(
        self, url: str, destino_rel: str, origen: str, accept: str = "*/*"
    ) -> pathlib.Path:
        """Ruta local del recurso, descargándolo solo si no está en el manifest.

        Ante 403/429 espera ``ESPERA_BLOQUEO`` y reintenta UNA vez; si repite (o
        el servidor da otro error) lanza ``DescargaFallida`` y el llamante marca
        la norma ``no-resuelta`` y sigue.
        """
        entrada = self.manifest.get(url)
        if entrada:
            destino = RAW_DIR / entrada["archivo"]
            if destino.exists():
                print(f"  [caché] {url}", flush=True)
                return destino

        destino = RAW_DIR / destino_rel
        destino.parent.mkdir(parents=True, exist_ok=True)

        datos = ctype = None
        for intento in (1, 2):
            self._espera()
            print(f"  [GET] {url}", flush=True)
            self.peticiones += 1
            try:
                datos, ctype = self._peticion(url, accept)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and intento == 1:
                    print(
                        f"    HTTP {exc.code} — backoff de {ESPERA_BLOQUEO:.0f}s y "
                        "un único reintento",
                        flush=True,
                    )
                    if self.dormir:
                        time.sleep(ESPERA_BLOQUEO)
                    continue
                raise DescargaFallida(f"HTTP {exc.code} en {url}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                raise DescargaFallida(f"{exc} en {url}") from exc
        if datos is None:  # pragma: no cover - el bucle sale por break o raise
            raise DescargaFallida(f"sin respuesta para {url}")

        destino.write_bytes(datos)
        self.manifest[url] = {
            "archivo": str(destino.relative_to(RAW_DIR)),
            "fecha": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "sha256": hashlib.sha256(datos).hexdigest(),
            "bytes": len(datos),
            "content_type": ctype,
            "origen": origen,
        }
        guardar(MANIFEST, self.manifest)
        print(f"    -> {destino.relative_to(REPO)} ({len(datos)} bytes)", flush=True)
        return destino


# --- 3. resolución de la norma ----------------------------------------------


def _slug(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_")


def url_busqueda_boe(numero_oficial: str) -> str:
    """URL de búsqueda de la API consolidada por número oficial."""
    consulta = {"query": {"query_string": {"query": f'numero_oficial:"{numero_oficial}"'}}}
    parametros = {
        "query": json.dumps(consulta, ensure_ascii=False, separators=(",", ":")),
        "limit": "50",
    }
    return f"{BOE_API}?{urllib.parse.urlencode(parametros)}"


def candidato_verificado(items: list[dict], numero_oficial: str, rango: str) -> dict | None:
    """El ÚNICO item que es sin duda la norma citada, o None.

    Nunca se acepta un identificador sin verificar: se exige ámbito estatal, el
    rango esperado, el ``numero_oficial`` exacto y que el título empiece por
    "<rango> <numero/año>". Si sobreviven 0 o más de 1, no-resuelta.
    """
    esperado = _normalizar_titulo(f"{rango} {numero_oficial}")
    validos = []
    for item in items:
        if (item.get("ambito") or {}).get("codigo") != "1":
            continue
        if _normalizar_titulo((item.get("rango") or {}).get("texto", "")) != _normalizar_titulo(rango):
            continue
        if (item.get("numero_oficial") or "").strip() != numero_oficial:
            continue
        titulo = item.get("titulo") or ""
        if numero_oficial not in titulo:
            continue
        if not _normalizar_titulo(titulo).startswith(esperado):
            continue
        validos.append(item)
    return validos[0] if len(validos) == 1 else None


def resolver_espanola(dl: Descargador, base: str, info: dict) -> dict:
    """Busca la norma en la API del BOE, la descarga y devuelve id/url/título."""
    numero, rango = info["numero_oficial"], info["rango"]
    url = url_busqueda_boe(numero)
    ruta = dl.obtener(
        url,
        f"boe/busqueda__{_slug(base)}.json",
        f"boe-busqueda:{base}",
        accept="application/json",
    )
    respuesta = json.loads(ruta.read_text(encoding="utf-8"))
    items = respuesta.get("data") or []
    if isinstance(items, dict):
        items = []
    item = candidato_verificado(items, numero, rango)
    if item is None:
        return {
            "estado": "no-resuelta",
            "motivo": (
                f"la búsqueda BOE por numero_oficial={numero!r} no da un único "
                f"resultado estatal de rango {rango!r} cuyo título verifique "
                f"({len(items)} candidatos)"
            ),
        }

    identificador = item["identificador"]
    url_texto = f"{BOE_API}/id/{identificador}/texto"
    ruta_texto = dl.obtener(
        url_texto,
        f"boe/{identificador}__texto.xml",
        f"boe-texto:{base}",
        accept="application/xml",
    )
    return {
        "estado": "ok",
        "fuente": "boe",
        "id": identificador,
        "url": item.get("url_html_consolidada") or url_texto,
        "titulo": (item.get("titulo") or "").strip(),
        "archivo": str(ruta_texto.relative_to(RAW_DIR)),
    }


# El título propio del acto va en VERSALES al principio del documento
# ("REGLAMENTO (UE) N o 165/2014 DEL PARLAMENTO…", "REGLAMENTO DELEGADO (UE)
# 2015/2446 DE LA COMISIÓN"); las normas que cita después aparecen en minúsculas
# ("…se modifica el Reglamento (CE) n o 561/2006…"). Por eso la verificación es
# sensible a mayúsculas y solo mira la PRIMERA aparición: si no, el título de
# 165/2014 acreditaría por error al 561/2006 que menciona.
RE_TITULO_UE = re.compile(r"REGLAMENTO\b[^()]{0,40}\((?:CE|UE|CEE)\)(?P<cola>.{0,60})")


def _cabecera(html: str) -> str:
    """Primeras líneas del documento, con los espacios colapsados."""
    return re.sub(r"\s+", " ", html_a_texto(html[:200_000])[:4000]).strip()


def verificar_eurlex(html: str, numero: int, anio: int) -> bool:
    """¿El HTML descargado es de verdad ese reglamento?

    Se exige que el título propio del acto lleve el número y el año exactos, en
    cualquiera de los dos órdenes que usa el DOUE ("n.o 165/2014" hasta 2014,
    "2015/2446" desde 2015).
    """
    m = RE_TITULO_UE.search(_cabecera(html))
    if not m:
        return False
    cola = m.group("cola")
    return bool(
        re.search(rf"\b{numero}\s*/\s*{anio}\b", cola)
        or re.search(rf"\b{anio}\s*/\s*{numero}\b", cola)
    )


def resolver_ue(dl: Descargador, base: str, info: dict) -> dict:
    celex = info["celex"]
    url = EURLEX_HTML.format(celex=celex)
    ruta = dl.obtener(
        url, f"eurlex/{celex}.html", f"eurlex:{base}", accept="text/html,*/*;q=0.8"
    )
    html = ruta.read_text(encoding="utf-8", errors="replace")
    if not verificar_eurlex(html, info["numero"], info["anio"]):
        return {
            "estado": "no-resuelta",
            "motivo": (
                f"el HTML de CELEX {celex} no acredita en su título el número "
                f"{info['numero']}/{info['anio']}"
            ),
        }
    return {
        "estado": "ok",
        "fuente": "eurlex",
        "id": celex,
        "url": url,
        "titulo": _titulo_eurlex(html) or f"Reglamento (UE) {info['numero']}/{info['anio']}",
        "archivo": str(ruta.relative_to(RAW_DIR)),
    }


def _titulo_eurlex(html: str) -> str | None:
    """Título oficial del acto, tomado de la cabecera del documento."""
    cabecera = _cabecera(html)
    m = RE_TITULO_UE.search(cabecera)
    if not m:
        return None
    return cabecera[m.start() : m.start() + 300].strip()


# --- orquestación -----------------------------------------------------------


def universo(match: dict, min_refs: int = MIN_REFS) -> tuple[dict, dict]:
    """Referencias del match agrupadas por norma base.

    Devuelve (universo, cola_larga): dos dicts ``base -> [localizador|None, …]``,
    el primero con las normas de ``>= min_refs`` referencias.
    """
    por_base: dict[str, list[str | None]] = {}
    for entrada in match.values():
        referencia = entrada.get("norma")
        if not referencia:
            continue
        base, localizador = parsear_referencia(referencia)
        por_base.setdefault(base, []).append(localizador)

    def por_frecuencia(grupo: dict) -> dict:
        return dict(sorted(grupo.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    dentro = {b: locs for b, locs in por_base.items() if len(locs) >= min_refs}
    fuera = {b: locs for b, locs in por_base.items() if len(locs) < min_refs}
    return por_frecuencia(dentro), por_frecuencia(fuera)


def descargar_universo(dl: Descargador, dentro: dict) -> dict:
    """Resuelve y descarga cada norma del universo. Devuelve base -> resolución."""
    resoluciones: dict[str, dict] = {}
    for base, localizadores in dentro.items():
        info = clasificar_norma(base)
        print(f"\n== {base} ({len(localizadores)} refs) [{info['clase']}]", flush=True)
        if info["clase"] == "fuera-alcance":
            print(f"  fuera de alcance: {info['motivo']}", flush=True)
            resoluciones[base] = {"estado": "no-resuelta", "motivo": info["motivo"]}
            continue
        try:
            if info["clase"] == "espanola":
                resoluciones[base] = resolver_espanola(dl, base, info)
            else:
                resoluciones[base] = resolver_ue(dl, base, info)
        except DescargaFallida as exc:
            print(f"  descarga fallida: {exc}", flush=True)
            resoluciones[base] = {"estado": "no-resuelta", "motivo": str(exc)}
        estado = resoluciones[base]
        if estado["estado"] == "ok":
            print(f"  -> {estado['id']} · {estado['titulo'][:80]}", flush=True)
        else:
            print(f"  -> no-resuelta: {estado.get('motivo')}", flush=True)
    return resoluciones


def _resoluciones_desde_manifest(manifest: dict, dentro: dict) -> dict:
    """Reconstruye las resoluciones a partir del raw ya descargado (sin red)."""
    por_origen: dict[str, dict] = {}
    for url, meta in manifest.items():
        por_origen.setdefault(meta.get("origen", ""), {"url": url, **meta})

    resoluciones: dict[str, dict] = {}
    for base in dentro:
        info = clasificar_norma(base)
        if info["clase"] == "fuera-alcance":
            resoluciones[base] = {"estado": "no-resuelta", "motivo": info["motivo"]}
            continue
        if info["clase"] == "ue":
            meta = por_origen.get(f"eurlex:{base}")
            if not meta:
                resoluciones[base] = {"estado": "no-resuelta", "motivo": "sin raw descargado"}
                continue
            ruta = RAW_DIR / meta["archivo"]
            html = ruta.read_text(encoding="utf-8", errors="replace")
            if not verificar_eurlex(html, info["numero"], info["anio"]):
                resoluciones[base] = {
                    "estado": "no-resuelta",
                    "motivo": f"el HTML de CELEX {info['celex']} no verifica el número/año",
                }
                continue
            resoluciones[base] = {
                "estado": "ok",
                "fuente": "eurlex",
                "id": info["celex"],
                "url": meta["url"],
                "titulo": _titulo_eurlex(html) or base,
                "archivo": meta["archivo"],
            }
            continue

        busqueda = por_origen.get(f"boe-busqueda:{base}")
        texto = por_origen.get(f"boe-texto:{base}")
        if not busqueda or not texto:
            resoluciones[base] = {"estado": "no-resuelta", "motivo": "sin raw descargado"}
            continue
        respuesta = json.loads((RAW_DIR / busqueda["archivo"]).read_text(encoding="utf-8"))
        items = respuesta.get("data") or []
        item = candidato_verificado(
            items if isinstance(items, list) else [], info["numero_oficial"], info["rango"]
        )
        if item is None:
            resoluciones[base] = {
                "estado": "no-resuelta",
                "motivo": "la búsqueda BOE cacheada no verifica un único candidato",
            }
            continue
        resoluciones[base] = {
            "estado": "ok",
            "fuente": "boe",
            "id": item["identificador"],
            "url": item.get("url_html_consolidada"),
            "titulo": (item.get("titulo") or "").strip(),
            "archivo": texto["archivo"],
        }
    return resoluciones


def construir_cache(dentro: dict, resoluciones: dict) -> dict:
    """De las resoluciones + el raw al ``normativa_cache.json``."""
    cache: dict[str, dict] = {}
    for base, localizadores in dentro.items():
        resolucion = resoluciones.get(base) or {
            "estado": "no-resuelta",
            "motivo": "no resuelta",
        }
        entrada = {
            "estado": resolucion["estado"],
            "fuente": resolucion.get("fuente"),
            "id": resolucion.get("id"),
            "url": resolucion.get("url"),
            "titulo": resolucion.get("titulo"),
            "referencias": len(localizadores),
            "articulos": {},
        }
        if resolucion["estado"] != "ok":
            entrada["motivo"] = resolucion.get("motivo", "")
            cache[base] = entrada
            continue

        objetivos: list[str] = []
        for localizador in localizadores:
            for objetivo in objetivos_de_localizador(localizador):
                if objetivo not in objetivos:
                    objetivos.append(objetivo)

        ruta = RAW_DIR / resolucion["archivo"]
        datos = ruta.read_bytes()
        if resolucion["fuente"] == "boe":
            articulos = extraer_articulos_boe(datos, objetivos)
            completo = texto_completo_boe(datos)
        else:
            html = datos.decode("utf-8", errors="replace")
            articulos = extraer_articulos_eurlex(html, objetivos)
            completo = html_a_texto(html)

        # Referencia sin localizador: solo se guarda texto si la norma entera es
        # pequeña (§4), y entonces sirve de contexto para toda la norma.
        if len(completo.encode("utf-8")) < LIMITE_NORMA_COMPLETA:
            articulos[CLAVE_COMPLETO] = recortar(completo, LIMITE_NORMA_COMPLETA)

        entrada["articulos"] = articulos
        entrada["estado"] = "ok" if articulos else "sin-texto"
        if not articulos:
            entrada["motivo"] = "norma resuelta pero ningún artículo citado es extraíble"
        cache[base] = entrada
    return cache


# --- cobertura e informe ----------------------------------------------------


def cobertura(match: dict, cache: dict) -> dict:
    """¿Cuántas de las referencias del match acaban con texto disponible?"""
    total = 0
    cubiertas = 0
    parciales = 0
    motivos: Counter = Counter()
    huecos: Counter = Counter()  # (norma, objetivo citado) sin texto

    def anotar(motivo: str, base: str, faltan) -> None:
        motivos[motivo] += 1
        for objetivo in faltan:
            huecos[(base, objetivo)] += 1

    for entrada in match.values():
        referencia = entrada.get("norma")
        if not referencia:
            continue
        total += 1
        base, localizador = parsear_referencia(referencia)
        norma = cache.get(base)
        if norma is None:
            motivos["cola larga (norma con < 4 referencias)"] += 1
            continue
        if norma["estado"] != "ok":
            motivos[f"norma {norma['estado']}"] += 1
            continue
        articulos = norma["articulos"]
        if CLAVE_COMPLETO in articulos:
            cubiertas += 1
            continue
        objetivos = objetivos_de_localizador(localizador)
        if not objetivos:
            anotar("referencia sin localizador extraíble", base, [localizador or "—"])
            continue
        presentes = [o for o in objetivos if o in articulos]
        faltan = [o for o in objetivos if o not in articulos]
        if len(presentes) == len(objetivos):
            cubiertas += 1
        elif presentes:
            parciales += 1
            anotar("artículo citado solo parcialmente extraído", base, faltan)
        else:
            anotar("artículo citado no extraíble del texto", base, faltan)
    return {
        "total": total,
        "cubiertas": cubiertas,
        "parciales": parciales,
        "motivos": dict(motivos.most_common()),
        "huecos": huecos.most_common(10),
    }


def escribir_informe(match: dict, dentro: dict, fuera: dict, cache: dict) -> dict:
    cob = cobertura(match, cache)
    pct = 100.0 * cob["cubiertas"] / cob["total"] if cob["total"] else 0.0
    pct_flex = (
        100.0 * (cob["cubiertas"] + cob["parciales"]) / cob["total"] if cob["total"] else 0.0
    )

    lineas = [
        "# Textos normativos para el RAG — informe\n",
        f"Universo: normas base con **>= {MIN_REFS} referencias** en "
        "`ministerio_match.json`.\n",
        f"- Referencias normativas del match: **{cob['total']}**",
        f"- Normas base distintas: **{len(dentro) + len(fuera)}** "
        f"({len(dentro)} en el universo, {len(fuera)} de cola larga)",
        f"- Referencias del universo: **{sum(len(v) for v in dentro.values())}**\n",
        "## Número clave\n",
        f"De las **{cob['total']}** referencias del banco oficial, "
        f"**{cob['cubiertas']}** ({pct:.1f} %) quedan con el texto de su artículo "
        "disponible para el RAG.",
        f"Contando también las que tienen extraído solo parte de los artículos que "
        f"citan: {cob['cubiertas'] + cob['parciales']} ({pct_flex:.1f} %).\n",
        "### Desglose de las no cubiertas\n",
        "| Motivo | Referencias |",
        "| --- | ---: |",
    ]
    for motivo, n in cob["motivos"].items():
        lineas.append(f"| {motivo} | {n} |")

    if cob["huecos"]:
        lineas += [
            "\n### Huecos concretos: qué artículo citado falta y en qué norma\n",
            "| Norma resuelta | Objetivo citado | Referencias afectadas |",
            "| --- | --- | ---: |",
        ]
        for (base, objetivo), n in cob["huecos"]:
            lineas.append(f"| {base} | {objetivo} | {n} |")
        lineas.append(
            "\nEl objetivo citado no está en el documento resuelto: o la cita "
            "ministerial apunta a una parte de OTRA norma (las que llevan la "
            "norma derogada entre paréntesis, p. ej. `(3821/85)`), o es un tipo "
            "de localizador que esta fase no extrae (títulos, capítulos, "
            "considerandos, disposiciones).\n"
        )

    lineas += [
        "\n## Normas del universo\n",
        "| Norma | Refs | Estado | Fuente | Id | Arts. citados | Extraídos |",
        "| --- | ---: | --- | --- | --- | ---: | ---: |",
    ]
    for base, localizadores in dentro.items():
        entrada = cache.get(base, {})
        objetivos = []
        for localizador in localizadores:
            for objetivo in objetivos_de_localizador(localizador):
                if objetivo not in objetivos:
                    objetivos.append(objetivo)
        articulos = entrada.get("articulos", {})
        extraidos = len([o for o in objetivos if o in articulos])
        marca = "*" if CLAVE_COMPLETO in articulos else ""
        lineas.append(
            f"| {base} | {len(localizadores)} | {entrada.get('estado', '?')} | "
            f"{entrada.get('fuente') or '—'} | {entrada.get('id') or '—'} | "
            f"{len(objetivos)} | {extraidos}{marca} |"
        )
    lineas.append(
        f"\n`*` = además se guardó el texto completo de la norma "
        f"(< {LIMITE_NORMA_COMPLETA // 1024} KB), que cubre cualquier referencia a ella.\n"
    )

    no_ok = [(b, e) for b, e in cache.items() if e["estado"] != "ok"]
    lineas.append("## Normas del universo no resueltas\n")
    if not no_ok:
        lineas.append("Ninguna.\n")
    else:
        lineas.append("| Norma | Refs | Estado | Motivo |")
        lineas.append("| --- | ---: | --- | --- |")
        for base, entrada in sorted(no_ok, key=lambda kv: -kv[1]["referencias"]):
            lineas.append(
                f"| {base} | {entrada['referencias']} | {entrada['estado']} | "
                f"{entrada.get('motivo', '')} |"
            )

    lineas += [
        f"\n## Cola larga (< {MIN_REFS} referencias, sin texto)\n",
        f"{len(fuera)} normas base, {sum(len(v) for v in fuera.values())} referencias. "
        "No se intenta resolverlas en esta fase.\n",
        "| Norma | Refs |",
        "| --- | ---: |",
    ]
    for base, localizadores in fuera.items():
        lineas.append(f"| {base} | {len(localizadores)} |")

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return cob


# --- main -------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Textos normativos (BOE/EUR-Lex) del CAP")
    ap.add_argument("--solo-descargar", action="store_true")
    ap.add_argument("--solo-extraer", action="store_true", help="no toca la red")
    ap.add_argument("--sin-espera", action="store_true", help="solo para tests")
    ap.add_argument("--min-refs", type=int, default=MIN_REFS)
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    match = cargar(MATCH_JSON, {})
    manifest = cargar(MANIFEST, {})
    dentro, fuera = universo(match, args.min_refs)
    print(
        f"Universo: {len(dentro)} normas base con >= {args.min_refs} refs "
        f"({sum(len(v) for v in dentro.values())} referencias); "
        f"cola larga: {len(fuera)} normas ({sum(len(v) for v in fuera.values())} refs)",
        flush=True,
    )

    if args.solo_extraer:
        resoluciones = _resoluciones_desde_manifest(manifest, dentro)
    else:
        dl = Descargador(manifest, dormir=not args.sin_espera)
        print(f"\n== Descarga (cortesía: {ESPERA_MIN:.0f}-{ESPERA_MAX:.0f} s) ==", flush=True)
        try:
            resoluciones = descargar_universo(dl, dentro)
        finally:
            guardar(MANIFEST, manifest)
        print(f"\nPeticiones de red realizadas: {dl.peticiones}", flush=True)
        if args.solo_descargar:
            return

    print("\n== Extracción ==", flush=True)
    cache = construir_cache(dentro, resoluciones)
    guardar(CACHE_JSON, cache)
    cob = escribir_informe(match, dentro, fuera, cache)

    estados = Counter(e["estado"] for e in cache.values())
    for estado, n in sorted(estados.items()):
        print(f"  {estado}: {n} normas", flush=True)
    pct = 100.0 * cob["cubiertas"] / cob["total"] if cob["total"] else 0.0
    print(
        f"\nReferencias con texto de su artículo: {cob['cubiertas']}/{cob['total']} "
        f"({pct:.1f} %)",
        flush=True,
    )
    print(f"-> {CACHE_JSON.relative_to(REPO)}", flush=True)
    print(f"-> {REPORT_MD.relative_to(REPO)}", flush=True)


if __name__ == "__main__":
    main()
