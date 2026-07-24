#!/usr/bin/env python3
"""Descarga y parsea el banco oficial de preguntas del CAP del Ministerio.

Fuente: www.transportes.gob.es (área CAP). Su landing de "preguntas específicas
de mercancías" enlaza los ZIP del banco oficial alojados en cdn.mitma.gob.es;
cada ZIP trae un .txt por objetivo (1, 2 y 3 del Anexo I del RD 284/2021) con
el enunciado, las opciones, la respuesta correcta y — lo que nos interesa — la
NORMA que respalda cada respuesta.

Se descargan el ZIP de mercancías y el de preguntas comunes a mercancías y
viajeros; el de viajeros queda fuera de alcance (nuestro banco es de
mercancías).

Dos pasos independientes:

  1. **Descarga** (red). Muy conservadora con el sitio: user-agent de navegador
     real, espera aleatoria de 12-20 s entre peticiones, backoff de 120 s y UN
     reintento ante 403, y parada total si el WAF insiste. Todo lo bajado se
     guarda TAL CUAL en ``data/ministerio/`` con un ``manifest.json``
     (url, fecha, sha256, bytes) — si una URL ya está en el manifest NO se
     vuelve a pedir.
  2. **Parseo** (sin red, ``--solo-parsear``). Convierte el raw a
     ``db/out/ministerio_preguntas.json`` y escribe el informe
     ``db/out/ministerio_report.md``.

Uso:
    python3 db/ministerio_descarga.py                 # descarga + parseo
    python3 db/ministerio_descarga.py --solo-descargar
    python3 db/ministerio_descarga.py --solo-parsear  # re-parsea el raw, sin red
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import html
import json
import pathlib
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from html.parser import HTMLParser

REPO = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = REPO / "data" / "ministerio"
MANIFEST = RAW_DIR / "manifest.json"
OUT_DIR = REPO / "db" / "out"
PREGUNTAS_JSON = OUT_DIR / "ministerio_preguntas.json"
REPORT_MD = OUT_DIR / "ministerio_report.md"

BASE = "https://www.transportes.gob.es"
LANDING_MERCANCIAS = (
    BASE + "/areas-de-actividad/transporte-terrestre/servicios-al-transportista"
    "/cap/preguntas-especificas-mercancias"
)

# Cortesía con un sitio público del Ministerio: pocas peticiones y espaciadas.
ESPERA_MIN, ESPERA_MAX = 12.0, 20.0
ESPERA_403 = 120.0
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
CABECERAS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, identity",
    "Connection": "close",
    "Upgrade-Insecure-Requests": "1",
}
EXT_DESCARGABLES = (".zip", ".pdf", ".xls", ".xlsx", ".csv", ".doc", ".docx", ".ods")


class BloqueoWAF(RuntimeError):
    """El sitio devuelve 403 de forma persistente: se para la descarga."""


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


# --- descarga cortés --------------------------------------------------------


class _Enlaces(HTMLParser):
    """Extrae (href, texto) de todos los <a> del HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.enlaces: list[tuple[str, str]] = []
        self._href: str | None = None
        self._texto: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._texto = []

    def handle_data(self, data):
        if self._href is not None:
            self._texto.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            texto = re.sub(r"\s+", " ", "".join(self._texto)).strip()
            self.enlaces.append((self._href, texto))
            self._href = None
            self._texto = []


def extraer_enlaces(contenido: bytes, url_base: str) -> list[tuple[str, str]]:
    """Devuelve [(url absoluta, texto)] de los <a> de una página."""
    texto = contenido.decode("utf-8", errors="replace")
    p = _Enlaces()
    p.feed(texto)
    salida = []
    for href, txt in p.enlaces:
        href = html.unescape(href.strip())
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        salida.append((urllib.parse.urljoin(url_base, href), txt))
    return salida


class Descargador:
    """Cliente HTTP con caché en disco y reglas de cortesía."""

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

    def _peticion(self, url: str, referer: str | None) -> tuple[bytes, str]:
        cabeceras = dict(CABECERAS)
        if referer:
            cabeceras["Referer"] = referer
        req = urllib.request.Request(url, headers=cabeceras)
        with urllib.request.urlopen(req, timeout=120) as resp:
            datos = resp.read()
            if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                datos = gzip.decompress(datos)
            return datos, resp.headers.get("Content-Type", "")

    def obtener(
        self, url: str, destino_rel: str, origen: str, referer: str | None = None
    ) -> pathlib.Path:
        """Devuelve la ruta local del recurso, descargándolo si hace falta.

        Si la URL ya está en el manifest y el fichero existe, NO se pide.
        Ante un 403 espera ``ESPERA_403`` y reintenta UNA vez; si repite lanza
        ``BloqueoWAF`` y el llamante debe parar la descarga.
        """
        entrada = self.manifest.get(url)
        if entrada:
            destino = RAW_DIR / entrada["archivo"]
            if destino.exists():
                print(f"  [caché] {url}", flush=True)
                return destino

        destino = RAW_DIR / destino_rel
        destino.parent.mkdir(parents=True, exist_ok=True)

        for intento in (1, 2):
            self._espera()
            print(f"  [GET] {url}", flush=True)
            self.peticiones += 1
            try:
                datos, ctype = self._peticion(url, referer)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429) and intento == 1:
                    print(
                        f"    HTTP {exc.code} — backoff de {ESPERA_403:.0f}s y "
                        "un único reintento",
                        flush=True,
                    )
                    if self.dormir:
                        time.sleep(ESPERA_403)
                    continue
                if exc.code in (403, 429):
                    raise BloqueoWAF(f"{exc.code} persistente en {url}") from exc
                raise
        else:  # pragma: no cover - el for siempre sale por break o raise
            raise BloqueoWAF(f"sin respuesta para {url}")

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


# --- descubrimiento de las páginas y ficheros del Ministerio ----------------

_RE_OBJETIVO = re.compile(r"objetivo[-_ ]*([123])", re.IGNORECASE)


def _slug(url: str) -> str:
    return urllib.parse.urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]


def _num_objetivo(*textos: str) -> str | None:
    for t in textos:
        m = _RE_OBJETIVO.search(t or "")
        if m:
            return m.group(1)
    return None


def _es_descargable(url: str) -> bool:
    return urllib.parse.urlparse(url).path.lower().endswith(EXT_DESCARGABLES)


def _nombre_fichero(url: str) -> str:
    nombre = urllib.parse.unquote(_slug(url)) or "descarga"
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)


def clasificar_familia(url: str, texto: str) -> str | None:
    """Familia de un enlace descargable de la landing CAP.

    La landing de "preguntas específicas de mercancías" enlaza los tres ZIP del
    banco oficial (mercancías, comunes y viajeros). Solo nos interesan los dos
    primeros: nuestro banco es de MERCANCÍAS, así que el de viajeros queda
    fuera de alcance y no se descarga (una petición menos al Ministerio).
    """
    pista = f"{_slug(url)} {texto}".lower()
    # OJO al orden: el enlace de comunes se titula "Preguntas comunes a
    # mercancías y viajeros", así que "comunes" debe comprobarse ANTES que
    # "viajeros" (si no, se descartaría precisamente el que sí queremos).
    if "comun" in pista:
        return "comunes"
    if "viajero" in pista:
        return None
    if "mercanc" in pista:
        return "especificas-mercancias"
    return None


def descubrir_y_descargar(dl: Descargador) -> list[dict]:
    """Baja la landing del CAP y, de ella, los ZIP del banco oficial.

    La landing de mercancías enlaza directamente los ZIP (alojados en
    ``cdn.mitma.gob.es``), incluido el de preguntas comunes a mercancías y
    viajeros, así que no hace falta crawlear páginas por objetivo: 1 petición
    de landing + 2 de ZIP.

    Devuelve la lista de descargas [{url, archivo, origen}] (incluye las que ya
    estaban en caché). Un ``BloqueoWAF`` se propaga al llamante.
    """
    ruta_landing = dl.obtener(
        LANDING_MERCANCIAS,
        "html/especificas-mercancias.html",
        "landing:especificas-mercancias",
        referer=BASE,
    )
    enlaces = extraer_enlaces(ruta_landing.read_bytes(), LANDING_MERCANCIAS)

    descargas: list[dict] = []
    vistos: set[str] = set()
    for url, texto in enlaces:
        if not _es_descargable(url) or url in vistos:
            continue
        familia = clasificar_familia(url, texto)
        if familia is None:
            continue
        vistos.add(url)
        obj = _num_objetivo(_slug(url), texto)
        origen = f"{familia}-objetivo-{obj}" if obj else familia
        descargas.append({"url": url, "origen": origen})

    if not descargas:
        raise BloqueoWAF(
            "la landing no enlaza ningún fichero descargable reconocible"
        )

    resultado: list[dict] = []
    for d in descargas:
        ruta = dl.obtener(
            d["url"],
            f"descargas/{d['origen']}__{_nombre_fichero(d['url'])}",
            d["origen"],
            referer=LANDING_MERCANCIAS,
        )
        resultado.append(
            {"url": d["url"], "archivo": str(ruta.relative_to(RAW_DIR)), "origen": d["origen"]}
        )
    return resultado


# --- parseo -----------------------------------------------------------------
#
# Formato REAL del banco oficial (verificado sobre los 6 .txt de los dos ZIP):
# ficheros de texto plano en cp1252, con saltos \r\n mezclados, y un bloque por
# pregunta con esta plantilla EXACTA:
#
#     COD: 48
#     ¿Cómo debe ser un contenedor que transporte mercancías de la Clase 4.3?
#     A Isotermo.
#     B Sin aristas.
#     C Impermeable al agua.
#     D Reforzado.
#     RESPUESTA: C
#     NORMA: Acuerdo
#      ADR 2015
#      7.3.2.4
#
# Notas del formato que condicionan el parser:
#   - La línea que sigue a "COD:" es SIEMPRE el enunciado, aunque empiece por
#     "A " ("A mayor altura del centro de gravedad…"); por eso se toma sin
#     mirar su forma y las opciones se exigen en orden A→B→C→D.
#   - La NORMA puede ocupar varias líneas hasta el siguiente "COD:"; se unen y
#     se colapsan los espacios.
#   - "Sin referencia" significa que la fuente no cita norma -> null.

RE_SIN_REF = re.compile(
    r"^\s*(sin\s+referencia|n/?a|-+|no\s+consta|no\s+procede)\s*$", re.IGNORECASE
)
_RE_COD = re.compile(r"^COD\s*:\s*(\d+)", re.IGNORECASE)
_RE_OPCION = re.compile(r"^([A-Da-d])\s+(\S.*)$")
_RE_RESPUESTA = re.compile(r"^RESPUESTA\s*:\s*\(?([A-Da-d])\)?\s*$", re.IGNORECASE)
_RE_NORMA = re.compile(r"^NORMA\s*:\s*(.*)$", re.IGNORECASE)
_LETRAS = ("a", "b", "c", "d")


def normalizar_norma(valor: str | None) -> str | None:
    """Trim + espacios colapsados; 'Sin referencia'/vacío -> None."""
    if valor is None:
        return None
    texto = re.sub(r"\s+", " ", str(valor).replace("\xa0", " ")).strip()
    texto = texto.strip(" .;:-–—")
    if not texto or RE_SIN_REF.match(texto):
        return None
    return texto


def _limpiar(texto: str) -> str:
    return re.sub(r"\s+", " ", (texto or "").replace("\xa0", " ")).strip()


def decodificar(datos: bytes) -> str:
    """Texto de un .txt del Ministerio (cp1252, con utf-8 como primera opción)."""
    for codec in ("utf-8-sig", "cp1252"):
        try:
            texto = datos.decode(codec)
        except UnicodeDecodeError:
            continue
        return texto.replace("\r\n", "\n").replace("\r", "\n")
    return datos.decode("cp1252", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def parsear_texto(
    texto: str, origen: str, incidencias: list[str] | None = None
) -> list[dict]:
    """Convierte el texto de un cuadernillo oficial en preguntas del contrato.

    Máquina de estados línea a línea (mismo enfoque que
    ``pipeline/cap_pipeline/extract.py``), tolerante a enunciados, opciones y
    normas multilínea. Los bloques que no llegan a tener enunciado + 4 opciones
    + respuesta se descartan y se anotan en ``incidencias``.
    """
    preguntas: list[dict] = []
    actual: dict | None = None
    foco: str | None = None  # None=enunciado, "a".."d" o "norma"

    def siguiente_letra() -> str | None:
        for letra in _LETRAS:
            if letra not in actual["opciones"]:
                return letra
        return None

    def cerrar() -> None:
        nonlocal actual
        if actual is None:
            return
        enunciado = _limpiar(" ".join(actual["enunciado"]))
        opciones = {k: _limpiar(" ".join(v)) for k, v in actual["opciones"].items()}
        completa = (
            enunciado
            and len(opciones) == 4
            and all(opciones.values())
            and actual["respuesta"] in _LETRAS
        )
        if completa:
            preguntas.append(
                {
                    "origen": origen,
                    "num": actual["num"],
                    "enunciado": enunciado,
                    "opciones": {k: opciones[k] for k in _LETRAS},
                    "respuesta": actual["respuesta"],
                    "norma": normalizar_norma(" ".join(actual["norma"])),
                }
            )
        elif incidencias is not None:
            incidencias.append(
                f"{origen}: bloque COD {actual['num']} incompleto "
                f"({len(opciones)} opciones, respuesta={actual['respuesta']!r})"
            )
        actual = None

    for bruto in texto.split("\n"):
        linea = bruto.strip()
        if not linea:
            continue

        m_cod = _RE_COD.match(linea)
        if m_cod:
            cerrar()
            actual = {
                "num": int(m_cod.group(1)),
                "enunciado": [],
                "opciones": {},
                "respuesta": None,
                "norma": [],
            }
            foco = None
            continue

        if actual is None:
            continue

        # Primera línea tras COD: enunciado, sea cual sea su forma.
        if not actual["enunciado"]:
            actual["enunciado"].append(linea)
            continue

        m_resp = _RE_RESPUESTA.match(linea)
        if m_resp:
            actual["respuesta"] = m_resp.group(1).lower()
            foco = "respuesta"
            continue

        m_norma = _RE_NORMA.match(linea)
        if m_norma:
            actual["norma"] = [m_norma.group(1)]
            foco = "norma"
            continue

        m_opt = _RE_OPCION.match(linea)
        if m_opt and m_opt.group(1).lower() == siguiente_letra():
            letra = m_opt.group(1).lower()
            actual["opciones"][letra] = [m_opt.group(2)]
            foco = letra
            continue

        # Continuación de lo último abierto.
        if foco == "norma":
            actual["norma"].append(linea)
        elif foco in _LETRAS:
            actual["opciones"][foco].append(linea)
        elif foco is None:
            actual["enunciado"].append(linea)

    cerrar()
    return preguntas


def _objetivo_de_nombre(nombre: str) -> str | None:
    """Objetivo (1/2/3) a partir del nombre del fichero del ZIP.

    Los ficheros se llaman ``CAPMercancias1.txt`` … ``CAPComunes3.txt``: el
    dígito final es el objetivo del Anexo I del RD 284/2021.
    """
    tallo = pathlib.PurePosixPath(nombre).stem
    m = _RE_OBJETIVO.search(tallo)
    if m:
        return m.group(1)
    m = re.search(r"([123])\s*$", tallo)
    return m.group(1) if m else None


def _familia(origen: str) -> str:
    """Quita el sufijo -objetivo-N de una etiqueta de origen."""
    return re.sub(r"-objetivo-[123]$", "", origen)


def parsear_fichero(ruta: pathlib.Path, origen: str) -> tuple[list[dict], list[str]]:
    """Parsea un fichero descargado (ZIP de .txt, o .txt suelto).

    Devuelve (preguntas, incidencias). Cualquier otro formato se reporta como
    incidencia en lugar de intentar adivinarlo.
    """
    incidencias: list[str] = []

    if zipfile.is_zipfile(ruta):
        preguntas: list[dict] = []
        with zipfile.ZipFile(ruta) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                if info.is_dir():
                    continue
                nombre = info.filename
                if not nombre.lower().endswith((".txt", ".csv")):
                    incidencias.append(
                        f"{ruta.name}::{nombre}: formato no soportado dentro del ZIP"
                    )
                    continue
                objetivo = _objetivo_de_nombre(nombre)
                sub_origen = (
                    f"{_familia(origen)}-objetivo-{objetivo}" if objetivo else origen
                )
                pgs = parsear_texto(
                    decodificar(zf.read(info)), sub_origen, incidencias
                )
                print(f"  {ruta.name}::{nombre} -> {len(pgs)} preguntas", flush=True)
                if not pgs:
                    incidencias.append(f"{ruta.name}::{nombre}: 0 preguntas parseadas")
                preguntas.extend(pgs)
        return preguntas, incidencias

    if ruta.suffix.lower() in (".txt", ".csv"):
        objetivo = _objetivo_de_nombre(ruta.name)
        sub_origen = f"{_familia(origen)}-objetivo-{objetivo}" if objetivo else origen
        pgs = parsear_texto(decodificar(ruta.read_bytes()), sub_origen, incidencias)
        print(f"  {ruta.name} -> {len(pgs)} preguntas", flush=True)
        return pgs, incidencias

    incidencias.append(f"{ruta.name}: formato no soportado ({ruta.suffix or 'sin ext'})")
    return [], incidencias


def parsear_todo(manifest: dict) -> tuple[list[dict], list[str]]:
    """Parsea todo lo que hay en el manifest (menos las páginas HTML)."""
    preguntas: list[dict] = []
    incidencias: list[str] = []
    for _url, meta in sorted(manifest.items(), key=lambda kv: kv[1]["archivo"]):
        rel = meta["archivo"]
        if rel.startswith("html/"):
            continue
        ruta = RAW_DIR / rel
        if not ruta.exists():
            incidencias.append(f"{rel}: falta el fichero en disco")
            continue
        pgs, incs = parsear_fichero(ruta, meta.get("origen") or "desconocido")
        incidencias.extend(incs)
        preguntas.extend(pgs)
    return preguntas, incidencias


# --- informe ----------------------------------------------------------------


def escribir_informe(
    preguntas: list[dict], incidencias: list[str], no_descargado: list[str]
) -> None:
    por_origen = Counter(p["origen"] for p in preguntas)
    lineas = [
        "# Banco oficial del Ministerio — informe de descarga y parseo\n",
        f"Total de preguntas parseadas: **{len(preguntas)}**.\n",
        "Fuente: www.transportes.gob.es (área CAP), reutilización con atribución.\n",
        "## Conteo por origen\n",
        "| Origen | Preguntas | Con norma | % con norma |",
        "| --- | ---: | ---: | ---: |",
    ]
    for origen, n in sorted(por_origen.items()):
        con = sum(1 for p in preguntas if p["origen"] == origen and p["norma"])
        lineas.append(f"| {origen} | {n} | {con} | {100.0 * con / n:.1f} % |")
    total_con = sum(1 for p in preguntas if p["norma"])
    pct = (100.0 * total_con / len(preguntas)) if preguntas else 0.0
    lineas.append(f"| **TOTAL** | **{len(preguntas)}** | **{total_con}** | **{pct:.1f} %** |")

    lineas.append("\n## Top 15 normas más citadas\n")
    lineas.append("| Norma | Citas |")
    lineas.append("| --- | ---: |")
    for norma, n in Counter(p["norma"] for p in preguntas if p["norma"]).most_common(15):
        lineas.append(f"| {norma} | {n} |")

    lineas.append("\n## Incidencias\n")
    if not incidencias and not no_descargado:
        lineas.append("Ninguna: todo lo enlazado se descargó y se parseó.\n")
    for item in no_descargado:
        lineas.append(f"- NO DESCARGADO: {item}")
    for item in incidencias:
        lineas.append(f"- {item}")

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# --- main -------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="Banco oficial CAP del Ministerio")
    ap.add_argument("--solo-descargar", action="store_true")
    ap.add_argument("--solo-parsear", action="store_true", help="no toca la red")
    ap.add_argument("--sin-espera", action="store_true", help="solo para tests")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = cargar(MANIFEST, {})
    no_descargado: list[str] = []

    if not args.solo_parsear:
        dl = Descargador(manifest, dormir=not args.sin_espera)
        print("== Descarga (cortesía: 12-20 s entre peticiones) ==", flush=True)
        try:
            descargas = descubrir_y_descargar(dl)
            print(f"Ficheros disponibles: {len(descargas)}", flush=True)
        except BloqueoWAF as exc:
            no_descargado.append(f"WAF: {exc} — descarga interrumpida")
            print(f"BLOQUEO WAF: {exc}. Se conserva lo ya descargado.", flush=True)
        finally:
            guardar(MANIFEST, manifest)
        print(f"Peticiones de red realizadas: {dl.peticiones}", flush=True)

    if args.solo_descargar:
        return

    print("\n== Parseo ==", flush=True)
    preguntas, incidencias = parsear_todo(manifest)
    guardar(PREGUNTAS_JSON, preguntas)
    escribir_informe(preguntas, incidencias, no_descargado)

    por_origen = Counter(p["origen"] for p in preguntas)
    con_norma = sum(1 for p in preguntas if p["norma"])
    print(f"\nTotal: {len(preguntas)} preguntas ministeriales", flush=True)
    for origen, n in sorted(por_origen.items()):
        print(f"  {origen}: {n}", flush=True)
    pct = (100.0 * con_norma / len(preguntas)) if preguntas else 0.0
    print(f"Con norma: {con_norma} ({pct:.1f} %)", flush=True)
    print(f"-> {PREGUNTAS_JSON.relative_to(REPO)}", flush=True)
    print(f"-> {REPORT_MD.relative_to(REPO)}", flush=True)


if __name__ == "__main__":
    main()
