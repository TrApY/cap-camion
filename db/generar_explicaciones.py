#!/usr/bin/env python3
"""Genera con Gemini las explicaciones del banco CAP y los resúmenes por tema.

Tres etapas, todas reanudables (re-ejecutar NO repite trabajo hecho):

1. ``--explicaciones``  una explicación breve por pregunta (2.636), con el
   contexto que haya: banco → match ministerial → norma oficial → texto legal.
2. ``--resumenes``      11 resúmenes de teoría anclados en el Anexo I del
   RD 284/2021 y en las 20 preguntas más frecuentes de cada tema.
3. ``--qa``             segundo pase con Gemini de crítico sobre una muestra
   determinista de 60 explicaciones.

Principios NO negociables (validados automáticamente, §5):

* La cita normativa que ve el usuario es SIEMPRE la del Ministerio (campo
  ``norma`` del match) tal cual: el modelo nunca la redacta ni la reescribe.
* El modelo tiene PROHIBIDO citar normas que no estén en su contexto. Si no se
  le da norma, cero citas legales; si se le da una, no puede mencionar otra.
* Las explicaciones no pueden referirse a las opciones por LETRA: la app las
  baraja al presentarlas, así que sólo vale referirse al CONTENIDO.

Requiere ``GEMINI_API_KEY`` en el entorno. Sólo stdlib (+ el parseo de
referencias normativas, que se importa de ``normativa_textos``).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import normativa_textos as nt  # noqa: E402  (mismo directorio, tras ajustar sys.path)

REPO = pathlib.Path(__file__).resolve().parent.parent
BANCO = REPO / "pipeline" / "out" / "banco_preguntas.json"
TEMAS_JSON = REPO / "db" / "temas.json"
OUT_DIR = REPO / "db" / "out"
MATCH_JSON = OUT_DIR / "ministerio_match.json"
MINISTERIO_JSON = OUT_DIR / "ministerio_preguntas.json"
NORMATIVA_JSON = OUT_DIR / "normativa_cache.json"

CACHE_EXPL = OUT_DIR / "explicaciones_cache.json"
CACHE_QA = OUT_DIR / "qa_explicaciones_cache.json"
ANEXO_JSON = OUT_DIR / "rd284_anexo_i.json"
EXPLICACIONES_JSON = OUT_DIR / "explicaciones.json"
RESUMENES_JSON = OUT_DIR / "resumenes_temas.json"
USO_JSON = OUT_DIR / "explicaciones_uso.json"
REPORT_MD = OUT_DIR / "explicaciones_report.md"

MODEL = "gemini-2.5-flash"
ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
)
# Tarifa pública de gemini-2.5-flash (texto), $ por millón de tokens. Las
# "thoughts" se facturan como salida. Ajustable por CLI si la tarifa cambia.
PRECIO_ENTRADA = 0.30
PRECIO_SALIDA = 2.50

LIMITE_TEXTO_LEGAL = 8000  # caracteres del bloque de artículo en el contexto
LONGITUD_MIN, LONGITUD_MAX = 120, 900  # caracteres "sanos" de una explicación
MAX_REGENERACIONES = 2  # reintentos por violar una regla dura (§5)
SEMILLA_QA = 20260724
MUESTRA_QA = {"norma+texto": 30, "norma-o-match": 15, "solo-banco": 15}
UMBRAL_QA_MALA = 0.05  # > 5 % de "mala" en la muestra ⇒ bloqueo
PROYECCION_MAX = 15.0  # $ — guardarraíl de coste antes de la pasada completa

# El RD 284/2021 (programa formativo del CAP) es la fuente de los resúmenes.
RD284_BASE = "RD 284/2021"
RD284_NUMERO, RD284_RANGO = "284/2021", "Real Decreto"
RD284_ID_ESPERADO = "BOE-A-2021-6624"

# Mapa slug de tema -> objetivos del Anexo I del RD 284/2021 (programa de
# cualificación inicial, apartado A). Hecho a mano leyendo el anexo: sección 1.ª
# (común a todos los permisos) y sección 2.ª (específica de mercancías C/C+E).
# Se excluyen a propósito 1.6, 1.7, 2.3 y 3.8, que son de viajeros.
TEMA_A_OBJETIVOS: dict[str, list[str]] = {
    "motor-transmision": ["1.1"],  # cadena cinemática
    "frenado-seguridad": ["1.2"],  # dispositivos de seguridad
    "conduccion-eficiente": ["1.3"],  # optimizar el consumo
    "carga-estiba": ["1.5"],  # operación de carga (sección 2.ª, mercancías)
    "tiempos-tacografo": ["2.1"],  # entorno social: tiempos y tacógrafo
    "reglamentacion-documentos": ["2.2"],  # reglamentación del transporte de mercancías
    "seguridad-vial-accidentes": ["1.4", "3.1", "3.5"],  # riesgos, accidentes, emergencias
    "salud-ergonomia": ["3.3", "3.4"],  # riesgos físicos/ergonómicos y aptitud
    "prevencion-riesgos": ["3.2"],  # delincuencia y tráfico de inmigrantes
    "calidad-servicio": ["3.6"],  # imagen de marca de la empresa
    "entorno-economico": ["3.7"],  # entorno económico del transporte de mercancías
}
PREGUNTAS_POR_RESUMEN = 20


# --- disco -------------------------------------------------------------------


def cargar(path: pathlib.Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def guardar(path: pathlib.Path, obj) -> None:
    nt.guardar(path, obj)


# =============================================================================
# 1. Construcción del contexto de una pregunta
# =============================================================================

MARCA_CORRECTA = "[RESPUESTA CORRECTA]"


def _normaliza(texto: str) -> str:
    """Minúsculas sin acentos ni puntuación, para comparar textos de opción."""
    plano = unicodedata.normalize("NFD", (texto or "").lower())
    plano = "".join(c for c in plano if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", plano).strip()


# 78 preguntas del banco tienen opciones que se remiten a otras POR LETRA
# ("Las respuestas A y B son correctas"). Presentadas en lista neutra serían
# irresolubles: el modelo no sabría de qué contenido habla. Se sustituyen por el
# CONTENIDO de las opciones referidas, que es justo lo que pide el principio.
RE_COMBINADA_TOTAL = re.compile(
    r"^\s*(?:Las\s+)?(?:respuestas?|opciones?)\s+(?P<a>[A-Da-d])\s*(?:,|y|e)\s*"
    r"(?P<b>[A-Da-d])\s+(?:son|con)\s+correctas\.?\s*$",
    re.IGNORECASE,
)
RE_COMBINADA_INLINE = re.compile(
    r"\b(?:l[ao]s\s+)?(?:respuestas?|opciones?)\s+(?P<a>[A-Da-d])\s*(?:,|y|e)\s*"
    r"(?P<b>[A-Da-d])\b"
)


def expandir_referencias(texto: str | None, opciones: dict, profundidad: int = 2) -> str:
    """Cambia «las respuestas A y B» por el contenido de esas dos opciones.

    ``opciones`` tiene que ser el diccionario letra->texto AL QUE se refiere el
    texto: el banco del Ministerio ordena las opciones a su manera, así que un
    texto ministerial sólo puede expandirse con opciones ministeriales. Se
    resuelve en cascada (una opción referida puede referirse a otras) con tope
    de ``profundidad`` para no entrar en bucle si el banco se auto-referencia.
    """
    texto = (texto or "").strip()
    if not texto:
        return texto

    def contenido(letra: str) -> str:
        bruto = (opciones.get(letra.lower()) or "").strip()
        if bruto and profundidad > 0:
            bruto = expandir_referencias(bruto, opciones, profundidad - 1)
        return bruto.rstrip(".")

    m = RE_COMBINADA_TOTAL.match(texto)
    if m:
        a, b = contenido(m.group("a")), contenido(m.group("b"))
        if a and b:
            return f"Son correctas a la vez «{a}» y «{b}»."
        return texto

    def sustituir(m):
        a, b = contenido(m.group("a")), contenido(m.group("b"))
        return f"«{a}» y «{b}»" if a and b else m.group(0)

    return RE_COMBINADA_INLINE.sub(sustituir, texto)


def texto_legal(norma: str | None, cache_normativa: dict) -> str | None:
    """Bloque(s) de artículo que respaldan ``norma``, o None si no hay texto.

    Reutiliza el parseo referencia -> (norma_base, localizador) y el mapeo
    localizador -> objetivos de ``normativa_textos``: aquí no se reimplementa
    nada de eso. Se trunca a ``LIMITE_TEXTO_LEGAL`` caracteres con marca.
    """
    if not norma:
        return None
    base, localizador = nt.parsear_referencia(norma)
    entrada = cache_normativa.get(base)
    if not entrada or entrada.get("estado") != "ok":
        return None
    articulos = entrada.get("articulos") or {}

    trozos = [
        (obj, articulos[obj])
        for obj in nt.objetivos_de_localizador(localizador)
        if obj in articulos
    ]
    if not trozos and nt.CLAVE_COMPLETO in articulos:
        trozos = [(nt.CLAVE_COMPLETO, articulos[nt.CLAVE_COMPLETO])]
    if not trozos:
        return None

    texto = "\n\n".join(f"[{obj}]\n{cuerpo}" for obj, cuerpo in trozos)
    if len(texto) > LIMITE_TEXTO_LEGAL:
        texto = texto[:LIMITE_TEXTO_LEGAL].rstrip() + "\n[…texto truncado…]"
    return texto


def construir_contexto(
    pregunta: dict,
    entrada_match: dict | None,
    pregunta_ministerio: dict | None,
    cache_normativa: dict,
) -> dict:
    """Contexto textual de una pregunta + los metadatos de su procedencia.

    Devuelve ``{"texto", "norma", "con_texto_legal", "origen_contexto",
    "respuesta_texto"}``. ``respuesta_texto`` es None cuando no hay forma de
    saber cuál es la correcta (ni en el banco ni en el Ministerio): esas
    preguntas no se mandan a generar.
    """
    norma = (entrada_match or {}).get("norma") or None
    bloque_legal = texto_legal(norma, cache_normativa)

    if norma and bloque_legal:
        origen = "norma+texto"
    elif norma:
        origen = "norma"
    elif entrada_match:
        origen = "match"
    else:
        origen = "solo-banco"

    # Respuesta correcta: la del banco y, si el banco no la tiene, la oficial.
    # Cada texto se expande con las opciones de SU banco (los órdenes difieren).
    opciones_propias = pregunta["opciones"]
    respuesta_banco = pregunta.get("respuesta_correcta_texto") or None
    respuesta_oficial = None
    opciones_ministerio: dict = {}
    if pregunta_ministerio:
        opciones_ministerio = pregunta_ministerio.get("opciones") or {}
        letra = (pregunta_ministerio.get("respuesta") or "").strip().lower()
        respuesta_oficial = opciones_ministerio.get(letra) or None
    respuesta = respuesta_banco or respuesta_oficial

    lineas = [
        "PREGUNTA DEL EXAMEN:",
        pregunta["enunciado"].strip(),
        "",
        "OPCIONES (en orden aleatorio; NO tienen letra):",
    ]
    # Sólo se marca la correcta cuando el texto viene de NUESTRO banco: si sólo
    # la tiene el Ministerio y además se remite a letras, sus letras no son las
    # nuestras y marcar una opción propia sería inventarse la correspondencia.
    marcable = bool(respuesta) and (
        respuesta_banco is not None or not RE_COMBINADA_INLINE.search(respuesta)
    )
    clave_correcta = _normaliza(respuesta) if marcable else None
    for opcion in opciones_propias.values():
        if not opcion:
            continue
        marca = (
            f"  {MARCA_CORRECTA}"
            if clave_correcta and _normaliza(opcion) == clave_correcta
            else ""
        )
        lineas.append(f"- {expandir_referencias(opcion, opciones_propias)}{marca}")
    if respuesta:
        fuente = opciones_propias if respuesta_banco else opciones_ministerio
        lineas += ["", f"RESPUESTA CORRECTA: {expandir_referencias(respuesta, fuente)}"]

    if entrada_match:
        lineas += ["", "DATOS OFICIALES DEL MINISTERIO PARA ESTA PREGUNTA:"]
        if respuesta_oficial:
            lineas.append(
                "- Respuesta oficial: "
                + expandir_referencias(respuesta_oficial, opciones_ministerio)
            )
        if norma:
            lineas.append(f"- Norma citada por el Ministerio: {norma}")
    if bloque_legal:
        lineas += [
            "",
            f"TEXTO LEGAL LITERAL DE «{norma}» (única base legal que puedes usar):",
            bloque_legal,
        ]

    # Normas que la PROPIA pregunta pone sobre la mesa (enunciado, opciones o
    # respuesta): repetirlas no es inventar. No se miran ni el texto legal ni la
    # norma del match, que van por su cuenta en el validador.
    propio = " ".join(
        [pregunta["enunciado"], *[o or "" for o in opciones_propias.values()], respuesta or ""]
    )

    return {
        "texto": "\n".join(lineas),
        "norma": norma,
        "identificadores_dados": sorted(set(RE_IDENTIFICADOR.findall(propio))),
        "con_texto_legal": bool(bloque_legal),
        "origen_contexto": origen,
        "respuesta_texto": (
            expandir_referencias(
                respuesta, opciones_propias if respuesta_banco else opciones_ministerio
            )
            if respuesta
            else None
        ),
    }


# =============================================================================
# 2. Validadores §5
# =============================================================================

# --- 5a. referencias a las opciones por letra --------------------------------

# La regla de la spec: «opción b», «respuesta a», «letra d», «opción A)». No se
# persigue una letra suelta entre paréntesis ("c)"): el modelo NUNCA ve las
# letras de las opciones (se las damos en lista neutra), así que un "c)" suelto
# sólo puede venir de un apartado del texto legal, y perseguirlo cuesta
# explicaciones buenas sin proteger de nada.
RE_LETRA_PALABRA = re.compile(
    r"\b(?:opci[óo]n|opciones|respuesta|respuestas|letra|letras)\s+"
    r"[«\"'(]?(?P<letra>[a-dA-D])(?![\wáéíóúüñÁÉÍÓÚÜÑ])"
)

# Única excepción a la regla de la spec, y sólo para la letra "a": en español
# "respuesta a <determinante>" es la preposición, no una letra de opción
# ("la respuesta a esta situación"). No debilita el principio —ninguna
# referencia real a una letra pasa por aquí—, evita rechazos falsos.
_A_PREPOSICION = {
    "la", "las", "el", "los", "un", "una", "unos", "unas", "lo", "este", "esta",
    "estos", "estas", "ese", "esa", "esos", "esas", "aquel", "aquella", "cual",
    "cuales", "que", "qué", "quien", "quienes", "su", "sus", "nuestro", "nuestra",
    "cada", "todo", "toda", "todos", "todas", "otro", "otra", "otros", "otras",
    "ello", "ella", "él", "ambos", "cualquier", "dicha", "dicho", "tal", "tales",
    "ninguno", "ninguna", "partir", "menudo", "veces", "nivel", "efectos", "fin",
    "falta", "pesar", "través", "cambio", "diferencia", "bordo", "mano", "priori",
    "posteriori", "corto", "largo", "medio", "causa", "raíz", "base", "salvo",
    "mayor", "menor", "distancia", "velocidad", "plena", "fondo", "tiempo",
}


def cita_letra_de_opcion(texto: str) -> bool:
    """¿La explicación se refiere a una opción por su letra?"""
    for m in RE_LETRA_PALABRA.finditer(texto or ""):
        if m.group("letra").lower() != "a":
            return True
        siguiente = re.match(r"\W*(\w+)", (texto or "")[m.end() :])
        palabra = siguiente.group(1).lower() if siguiente else ""
        if palabra not in _A_PREPOSICION:
            return True
    return False


# --- 5b. citas normativas inventadas -----------------------------------------

# Sin norma en el contexto: cualquier apariencia de cita legal con número.
RE_CITA_LEGAL = re.compile(
    r"(?:Ley|Real Decreto|RD|Reglamento|Directiva|Orden|Convenio|[Aa]rt(?:ículo)?\.?)"
    r"\s*(?:\(?[A-Z]{2}\)?\s*)?\d"
)
RE_IDENTIFICADOR = re.compile(r"\d+/\d{4}")


def cita_normativa_prohibida(
    texto: str, norma: str | None, dados: frozenset | set | tuple = ()
) -> bool:
    """¿Cita normativa que no se le ha dado?

    Permitido: el identificador N/AAAA de la norma del Ministerio y los que la
    propia pregunta pone sobre la mesa (``dados``) — hay preguntas cuya
    respuesta correcta ES una norma («¿qué norma regula el CAP?»), y repetir un
    dato del enunciado no es inventar nada. Todo lo demás está prohibido:
    sin nada dado, cualquier cita legal numerada; con algo dado, cualquier
    identificador distinto y cualquier artículo que nadie haya facilitado.
    """
    texto = texto or ""
    permitidos = set(RE_IDENTIFICADOR.findall(norma or "")) | set(dados)
    if set(RE_IDENTIFICADOR.findall(texto)) - permitidos:
        return True
    if norma:
        return False
    limpio = texto
    for identificador in permitidos:
        limpio = limpio.replace(identificador, "")
    return bool(RE_CITA_LEGAL.search(limpio))


def validar(
    texto: str, norma: str | None, dados: frozenset | set | tuple = ()
) -> list[str]:
    """Reglas duras violadas por ``texto`` (lista vacía = explicación válida)."""
    fallos = []
    if cita_letra_de_opcion(texto):
        fallos.append("letras")
    if cita_normativa_prohibida(texto, norma, dados):
        fallos.append("cita-otra-norma" if norma else "cita-inventada")
    return fallos


def longitud_outlier(texto: str) -> bool:
    """Fuera de 120-900 caracteres: se lista en el informe, no se rechaza."""
    return not (LONGITUD_MIN <= len(texto or "") <= LONGITUD_MAX)


# =============================================================================
# 3. Cliente Gemini
# =============================================================================


class Uso:
    """Contabilidad de tokens y coste, persistente para poder reanudar."""

    def __init__(self, datos: dict | None = None):
        datos = datos or {}
        self.etapas: dict[str, Counter] = defaultdict(Counter)
        for etapa, valores in (datos.get("etapas") or {}).items():
            self.etapas[etapa] = Counter(valores)

    def anotar(self, etapa: str, uso_api: dict) -> None:
        c = self.etapas[etapa]
        c["llamadas"] += 1
        c["entrada"] += int(uso_api.get("promptTokenCount") or 0)
        c["salida"] += int(uso_api.get("candidatesTokenCount") or 0)
        c["pensamiento"] += int(uso_api.get("thoughtsTokenCount") or 0)
        c["total"] += int(uso_api.get("totalTokenCount") or 0)

    def totales(self) -> Counter:
        acumulado: Counter = Counter()
        for c in self.etapas.values():
            acumulado.update(c)
        return acumulado

    @staticmethod
    def coste(c: Counter, p_entrada: float, p_salida: float) -> float:
        salida = c["salida"] + c["pensamiento"]
        return (c["entrada"] * p_entrada + salida * p_salida) / 1_000_000

    def a_json(self) -> dict:
        return {"etapas": {k: dict(v) for k, v in self.etapas.items()}}


class ErrorGemini(RuntimeError):
    pass


def llamar_gemini(
    prompt: str,
    key: str,
    schema: dict,
    uso: Uso,
    etapa: str,
    temperatura: float = 0.0,
    pensamiento: int | None = 0,
    intentos: int = 6,
) -> dict:
    """Una llamada con responseSchema; reintenta con backoff ante errores."""
    config: dict = {
        "responseMimeType": "application/json",
        "responseSchema": schema,
        "temperature": temperatura,
    }
    if pensamiento is not None:
        config["thinkingConfig"] = {"thinkingBudget": pensamiento}
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    ultimo = ""
    for intento in range(intentos):
        try:
            req = urllib.request.Request(
                ENDPOINT + "?key=" + key,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                respuesta = json.load(resp)
            uso.anotar(etapa, respuesta.get("usageMetadata") or {})
            partes = respuesta["candidates"][0]["content"]["parts"]
            return json.loads("".join(p.get("text", "") for p in partes))
        except urllib.error.HTTPError as exc:
            cuerpo = exc.read()[:200].decode("utf-8", "replace")
            ultimo = f"HTTP {exc.code}: {cuerpo}"
            if exc.code in (400, 403, 404) and "quota" not in cuerpo.lower():
                raise ErrorGemini(ultimo) from exc
            espera = min(60, 5 * (2**intento))
            print(f"    {ultimo[:110]} — espera {espera}s", flush=True)
            time.sleep(espera)
        except Exception as exc:  # noqa: BLE001
            ultimo = f"{type(exc).__name__}: {exc}"
            print(f"    {ultimo[:110]} — reintento", flush=True)
            time.sleep(3)
    raise ErrorGemini(f"agotados {intentos} intentos ({ultimo})")


# =============================================================================
# 4. Prompts
# =============================================================================

REGLAS_COMUNES = """REGLAS OBLIGATORIAS (su incumplimiento invalida la respuesta):
1. NUNCA te refieras a una opción por su letra («la opción b», «la respuesta a», «c)»).
   Al alumno se le presentan barajadas: refiérete siempre al CONTENIDO de la opción.
   Tampoco menciones apartados de una ley por su letra («la letra c) del artículo»):
   di lo que dicen, no cómo están numerados.
2. {regla_normativa}
3. Español llano y directo, de formador que explica a un conductor. Sin florituras,
   sin fórmulas de cortesía, sin «como hemos visto» ni «en este caso».
4. No repitas el enunciado ni enumeres todas las opciones."""

REGLA_SIN_NORMA = (
    "En esta pregunta NO se te da ninguna norma. Por tanto NO puedes hacer NINGUNA "
    "cita legal: ni números de ley o real decreto, ni artículos, ni reglamentos, ni "
    "directivas, ni convenios. Explica el fundamento técnico o práctico, sin derecho."
)
REGLA_CON_NORMA = (
    "La ÚNICA referencia normativa que puedes mencionar es «{norma}», y sólo si "
    "aporta algo. Está prohibido citar cualquier otra norma, número o artículo que "
    "no aparezca literalmente en este contexto."
)

PROMPT_EXPLICACION = """Eres formador de conductores profesionales y preparas a alumnos para el examen del CAP de mercancías en España.

TAREA: explica en 2 a 4 frases POR QUÉ la respuesta correcta es la correcta. Si alguna de las opciones incorrectas es un error típico, desmóntala en UNA sola frase.

{reglas}
{aviso}
{contexto}

Devuelve un JSON con el campo "explicacion"."""

AVISOS_REGENERACION = {
    "letras": (
        "AVISO: tu intento anterior se RECHAZÓ por referirse a algo por su letra. "
        "No escribas «opción a», «respuesta b», «letra c» ni nada parecido, ni "
        "para las opciones ni para los apartados de una ley; tampoco la "
        "construcción «la respuesta a …». Habla siempre del contenido."
    ),
    "cita-inventada": (
        "AVISO: tu intento anterior se RECHAZÓ por citar normativa que no se te ha "
        "dado. Aquí no dispones de ninguna norma: no escribas ningún número de ley, "
        "real decreto, reglamento, directiva ni artículo."
    ),
    "cita-otra-norma": (
        "AVISO: tu intento anterior se RECHAZÓ por citar una norma distinta de la "
        "única permitida («{norma}»). No menciones ningún otro identificador del "
        "tipo N/AAAA ni ninguna otra ley."
    ),
}

ESQUEMA_EXPLICACION = {
    "type": "OBJECT",
    "properties": {"explicacion": {"type": "STRING"}},
    "required": ["explicacion"],
}
ESQUEMA_RESUMEN = {
    "type": "OBJECT",
    "properties": {"resumen_md": {"type": "STRING"}},
    "required": ["resumen_md"],
}
ESQUEMA_QA = {
    "type": "OBJECT",
    "properties": {
        "veredicto": {"type": "STRING", "enum": ["ok", "dudosa", "mala"]},
        "motivo": {"type": "STRING"},
    },
    "required": ["veredicto", "motivo"],
}


def prompt_explicacion(contexto: dict, avisos: list[str]) -> str:
    norma = contexto["norma"]
    regla = REGLA_CON_NORMA.format(norma=norma) if norma else REGLA_SIN_NORMA
    texto_avisos = ""
    if avisos:
        texto_avisos = "\n" + "\n".join(
            AVISOS_REGENERACION[a].format(norma=norma or "") for a in avisos
        ) + "\n"
    return PROMPT_EXPLICACION.format(
        reglas=REGLAS_COMUNES.format(regla_normativa=regla),
        aviso=texto_avisos,
        contexto="\n" + contexto["texto"],
    )


# =============================================================================
# 5. Etapa 1 — explicaciones
# =============================================================================


def cargar_fuentes() -> dict:
    banco = cargar(BANCO, [])
    match = cargar(MATCH_JSON, {})
    ministerio = cargar(MINISTERIO_JSON, [])
    indice = {(q["origen"], q["num"]): q for q in ministerio}
    return {
        "banco": banco,
        "match": match,
        "indice_ministerio": indice,
        "normativa": cargar(NORMATIVA_JSON, {}),
    }


def contexto_de(pregunta: dict, fuentes: dict) -> dict:
    entrada = fuentes["match"].get(pregunta["id"])
    ministerial = None
    if entrada:
        ministerial = fuentes["indice_ministerio"].get((entrada["origen"], entrada["num"]))
    return construir_contexto(pregunta, entrada, ministerial, fuentes["normativa"])


def _proyeccion(uso: Uso, etapa: str, llamadas_totales: int, args) -> tuple[float, float]:
    """(coste medio por llamada, proyección del total) según lo gastado ya."""
    c = uso.etapas[etapa]
    if not c["llamadas"]:
        return 0.0, 0.0
    medio = Uso.coste(c, args.precio_entrada, args.precio_salida) / c["llamadas"]
    return medio, medio * llamadas_totales


def generar_explicaciones(args, key: str, fuentes: dict, uso: Uso) -> dict:
    cache = cargar(CACHE_EXPL, {})
    banco = fuentes["banco"]
    pendientes = [q for q in banco if q["id"] not in cache]
    print(
        f"Explicaciones: {len(banco)} preguntas, {len(cache)} en caché, "
        f"{len(pendientes)} pendientes.",
        flush=True,
    )
    if args.limite:
        pendientes = pendientes[: args.limite]
        print(f"  (--limite {args.limite}: sólo se procesan {len(pendientes)})", flush=True)

    nuevas = 0
    # El guardarraíl se evalúa una vez por proceso, en cuanto hay 10 llamadas
    # medidas: en la primera pasada tras las 10 primeras preguntas, y en las
    # pasadas reanudadas ya en la primera vuelta (el uso viene del disco).
    guardarrail_hecho = False
    fallos_api: dict[str, str] = {}
    try:
        for i, pregunta in enumerate(pendientes, 1):
            contexto = contexto_de(pregunta, fuentes)
            base = {
                "norma": contexto["norma"],
                "con_texto_legal": contexto["con_texto_legal"],
                "origen_contexto": contexto["origen_contexto"],
            }
            if not contexto["respuesta_texto"]:
                cache[pregunta["id"]] = {
                    **base,
                    "explicacion": None,
                    "estado": "sin-respuesta-correcta",
                    "intentos": 0,
                    "rechazos": [],
                }
                continue

            avisos: list[str] = []
            resultado = None
            rechazos: list[str] = []
            error = None
            for intento in range(MAX_REGENERACIONES + 1):
                try:
                    salida = llamar_gemini(
                        prompt_explicacion(contexto, avisos),
                        key,
                        ESQUEMA_EXPLICACION,
                        uso,
                        "explicaciones",
                        temperatura=0.0 if intento == 0 else 0.6,
                        pensamiento=args.pensamiento,
                    )
                except ErrorGemini as exc:
                    # Una pregunta que la API no digiere no puede tumbar una
                    # pasada de 2.636: se anota y se sigue (re-ejecutar la
                    # reintenta, porque no queda cacheada como definitiva).
                    error = str(exc)[:200]
                    print(f"  [{pregunta['id']}] ERROR API: {error}", flush=True)
                    break
                nuevas += 1
                texto = (salida.get("explicacion") or "").strip()
                fallos = validar(
                    texto, contexto["norma"], contexto["identificadores_dados"]
                )
                if not fallos:
                    resultado = texto
                    break
                rechazos.extend(fallos)
                avisos = fallos
                print(
                    f"  [{pregunta['id']}] rechazo {fallos} (intento {intento + 1})",
                    flush=True,
                )
                time.sleep(args.pausa)

            if error and not resultado:
                # No se cachea como definitiva: la próxima pasada la reintenta.
                fallos_api[pregunta["id"]] = error
            else:
                cache[pregunta["id"]] = {
                    **base,
                    "explicacion": resultado,
                    "estado": "ok" if resultado else "rechazada",
                    "intentos": len(rechazos) + (1 if resultado else 0),
                    "rechazos": rechazos,
                }

            if i % 20 == 0 or i == len(pendientes):
                guardar(CACHE_EXPL, cache)
                guardar(USO_JSON, uso.a_json())
                medio, proy = _proyeccion(
                    uso, "explicaciones", len(banco) + 11 + 60, args
                )
                print(
                    f"  {i}/{len(pendientes)} · caché {len(cache)}/{len(banco)} · "
                    f"{uso.etapas['explicaciones']['llamadas']} llamadas · "
                    f"proyección ~{proy:.2f} $",
                    flush=True,
                )

            if not guardarrail_hecho and uso.etapas["explicaciones"]["llamadas"] >= 10:
                guardarrail_hecho = True
                medio, proy = _proyeccion(uso, "explicaciones", len(banco) + 11 + 60, args)
                print(
                    f"\n=== GUARDARRAÍL DE COSTE ===\n"
                    f"  coste medio por llamada: {medio * 1000:.4f} $/1000 llamadas\n"
                    f"  proyección de la pasada completa: {proy:.2f} $ "
                    f"(límite {args.proyeccion_max:.2f} $)\n",
                    flush=True,
                )
                if proy > args.proyeccion_max:
                    guardar(CACHE_EXPL, cache)
                    guardar(USO_JSON, uso.a_json())
                    raise SystemExit(
                        f"PARADA: la proyección ({proy:.2f} $) supera el límite "
                        f"({args.proyeccion_max:.2f} $). No se sigue."
                    )

            time.sleep(args.pausa)
    finally:
        guardar(CACHE_EXPL, cache)
        guardar(USO_JSON, uso.a_json())

    print(f"Explicaciones: {nuevas} llamadas nuevas en esta pasada.", flush=True)
    if fallos_api:
        print(
            f"AVISO: {len(fallos_api)} preguntas fallaron en la API y quedan "
            "pendientes (re-ejecuta para completarlas): "
            + ", ".join(sorted(fallos_api)[:10]),
            flush=True,
        )
    return cache


def escribir_explicaciones(cache: dict, banco: list) -> dict:
    """``explicaciones.json`` con los 4 campos de la spec, en orden del banco.

    Toda explicación con veredicto "mala" en el caché de QA queda EXCLUIDA del
    artefacto final: mejor una pregunta sin explicación que una explicación
    falsa. Las "dudosa" (imprecisas sin ser falsas) se mantienen.
    """
    malas_qa = {
        pid
        for pid, r in cargar(CACHE_QA, {}).items()
        if r.get("veredicto") == "mala"
    }
    salida = {}
    for pregunta in banco:
        entrada = cache.get(pregunta["id"])
        if not entrada or not entrada.get("explicacion"):
            continue
        if pregunta["id"] in malas_qa:
            continue
        salida[pregunta["id"]] = {
            "explicacion": entrada["explicacion"],
            "norma": entrada["norma"],
            "con_texto_legal": entrada["con_texto_legal"],
            "origen_contexto": entrada["origen_contexto"],
        }
    guardar(EXPLICACIONES_JSON, salida)
    return salida


# =============================================================================
# 6. Etapa 2 — resúmenes por tema (§6)
# =============================================================================

RE_OBJETIVO = re.compile(r"^(?:[a-z]\)\s*)?Objetivo\s+(?P<id>\d\.\d)\s*:")
RE_CORTE_ANEXO = re.compile(r"^(?:Secci[óo]n\b|\d\.\s+[A-ZÁÉÍÓÚ]|[A-Z]\)\s)")
RE_DURACION = re.compile(r"^(?:Duraci[óo]n:|Cuando se trate de un curso)")


def extraer_epigrafes_anexo_i(texto_anexo: str) -> dict[str, str]:
    """Objetivos (1.x/2.x/3.x) del programa de cualificación inicial del Anexo I.

    Se queda con el apartado «A) Programa de los cursos de cualificación
    inicial» y trocea por «Objetivo N.M:». Se descartan las líneas de duración
    del curso: son administrativas y no aportan teoría al resumen.
    """
    lineas = texto_anexo.split("\n")
    inicio = next((i for i, l in enumerate(lineas) if l.startswith("A) Programa")), 0)
    fin = next(
        (i for i, l in enumerate(lineas) if l.startswith("B) Programa")), len(lineas)
    )
    epigrafes: dict[str, list[str]] = {}
    actual: str | None = None
    for linea in lineas[inicio:fin]:
        m = RE_OBJETIVO.match(linea)
        if m:
            actual = m.group("id")
            epigrafes.setdefault(actual, [re.sub(r"^[a-z]\)\s*", "", linea)])
            continue
        if actual and RE_CORTE_ANEXO.match(linea):
            actual = None
            continue
        if actual and not RE_DURACION.match(linea):
            epigrafes[actual].append(linea)
    return {k: "\n".join(v).strip() for k, v in epigrafes.items()}


def preparar_anexo_i(sin_red: bool = False) -> dict:
    """Descarga (una vez) el RD 284/2021 del BOE y cachea sus epígrafes."""
    cacheado = cargar(ANEXO_JSON, None)
    if cacheado and cacheado.get("epigrafes"):
        return cacheado
    if sin_red:
        raise SystemExit(f"falta {ANEXO_JSON.name} y se pidió no usar red")

    manifest = cargar(nt.MANIFEST, {})
    descargador = nt.Descargador(manifest)
    resolucion = nt.resolver_espanola(
        descargador, RD284_BASE, {"numero_oficial": RD284_NUMERO, "rango": RD284_RANGO}
    )
    if resolucion.get("estado") != "ok":
        raise SystemExit(f"no se pudo resolver {RD284_BASE}: {resolucion.get('motivo')}")
    if resolucion["id"] != RD284_ID_ESPERADO:
        raise SystemExit(
            f"el BOE resuelve {RD284_BASE} a {resolucion['id']}, se esperaba "
            f"{RD284_ID_ESPERADO}: no se sigue sin revisar"
        )

    datos = (nt.RAW_DIR / resolucion["archivo"]).read_bytes()
    # Mismo criterio que normativa_textos.py: stdlib (la fase no admite
    # dependencias nuevas), XML traído por HTTPS de la API oficial del BOE y
    # guardado bajo nuestro control, y ElementTree no resuelve entidades
    # externas ni expande entidades internas recursivas.
    raiz = ET.fromstring(datos)
    bloques = list(raiz.iter("bloque"))
    anexo = next(
        (b for b in bloques if nt._casa_titulo(b.get("titulo") or "", "Anexo I")), None
    )
    if anexo is None:
        raise SystemExit("no se encontró el Anexo I en el XML del RD 284/2021")

    epigrafes = extraer_epigrafes_anexo_i(nt._texto_bloque(anexo))
    faltan = sorted(
        {o for objetivos in TEMA_A_OBJETIVOS.values() for o in objetivos}
        - set(epigrafes)
    )
    if faltan:
        raise SystemExit(f"objetivos del Anexo I no extraídos: {faltan}")

    resultado = {
        "id": resolucion["id"],
        "titulo": resolucion["titulo"],
        "url": resolucion["url"],
        "epigrafes": epigrafes,
    }
    guardar(ANEXO_JSON, resultado)
    print(f"Anexo I del RD 284/2021: {len(epigrafes)} objetivos extraídos.", flush=True)
    return resultado


PROMPT_RESUMEN = """Eres formador de conductores profesionales y preparas a alumnos para el examen del CAP de mercancías en España.

TAREA: redacta un resumen de teoría del tema «{titulo}» de 300 a 500 palabras, en markdown sencillo, con esta estructura exacta:
- entre 4 y 6 puntos clave en lista con viñetas «-», cada uno de 1 a 3 frases;
- después, un único párrafo que empiece por «**Lo que más cae:**» y resuma qué se pregunta una y otra vez en el examen.
No pongas título ni encabezados de nivel superior.

{reglas}
{aviso}
PROGRAMA OFICIAL DEL CAP PARA ESTE TEMA (Anexo I del {norma}, literal):
{epigrafes}

PREGUNTAS MÁS FRECUENTES DEL TEMA EN LOS EXÁMENES REALES, con su respuesta correcta:
{preguntas}

Devuelve un JSON con el campo "resumen_md"."""


def generar_resumenes(args, key: str, fuentes: dict, uso: Uso) -> dict:
    anexo = preparar_anexo_i()
    temas = cargar(TEMAS_JSON, [])
    cache = cargar(RESUMENES_JSON, {})
    banco = fuentes["banco"]

    por_tema: dict[str, list] = defaultdict(list)
    for pregunta in banco:
        if pregunta.get("tema"):
            por_tema[pregunta["tema"]].append(pregunta)

    regla = REGLA_CON_NORMA.format(norma=RD284_BASE)
    for tema in temas:
        slug = tema["slug"]
        if slug in cache and cache[slug].get("resumen_md"):
            continue
        objetivos = TEMA_A_OBJETIVOS[slug]
        epigrafes = "\n\n".join(anexo["epigrafes"][o] for o in objetivos)

        seleccion = sorted(
            por_tema.get(slug, []),
            key=lambda q: (-int(q.get("frecuencia") or 0), q["id"]),
        )[:PREGUNTAS_POR_RESUMEN]
        lineas = []
        for pregunta in seleccion:
            contexto = contexto_de(pregunta, fuentes)
            if not contexto["respuesta_texto"]:
                continue
            lineas.append(
                f"- {pregunta['enunciado'].strip()}\n"
                f"  Respuesta correcta: {contexto['respuesta_texto'].strip()}"
            )

        avisos: list[str] = []
        resumen = None
        rechazos: list[str] = []
        for intento in range(MAX_REGENERACIONES + 1):
            texto_avisos = ""
            if avisos:
                texto_avisos = "\n" + "\n".join(
                    AVISOS_REGENERACION[a].format(norma=RD284_BASE) for a in avisos
                ) + "\n"
            prompt = PROMPT_RESUMEN.format(
                titulo=tema["label"],
                reglas=REGLAS_COMUNES.format(regla_normativa=regla),
                aviso=texto_avisos,
                norma=RD284_BASE,
                epigrafes=epigrafes,
                preguntas="\n".join(lineas),
            )
            try:
                salida = llamar_gemini(
                    prompt,
                    key,
                    ESQUEMA_RESUMEN,
                    uso,
                    "resumenes",
                    temperatura=0.2 if intento == 0 else 0.6,
                    pensamiento=args.pensamiento_resumen,
                )
            except ErrorGemini as exc:
                print(f"  [{slug}] ERROR API: {str(exc)[:160]}", flush=True)
                break
            texto = (salida.get("resumen_md") or "").strip()
            fallos = validar(texto, RD284_BASE)
            if not fallos:
                resumen = texto
                break
            rechazos.extend(fallos)
            avisos = fallos
            print(f"  [{slug}] rechazo {fallos} (intento {intento + 1})", flush=True)

        cache[slug] = {
            "titulo": tema["label"],
            "resumen_md": resumen,
            "objetivos_rd284": objetivos,
            "preguntas_usadas": len(lineas),
            "palabras": len((resumen or "").split()),
            "rechazos": rechazos,
        }
        guardar(RESUMENES_JSON, cache)
        print(
            f"  {slug}: {cache[slug]['palabras']} palabras "
            f"({len(lineas)} preguntas, objetivos {objetivos})",
            flush=True,
        )
    guardar(USO_JSON, uso.a_json())
    return cache


# =============================================================================
# 7. Etapa 3 — QA muestral (§7)
# =============================================================================


def estrato(origen: str) -> str:
    if origen == "norma+texto":
        return "norma+texto"
    if origen in ("norma", "match"):
        return "norma-o-match"
    return "solo-banco"


def seleccionar_muestra_qa(cache: dict, cuotas: dict | None = None) -> list[str]:
    """Muestra determinista y estratificada de ids con explicación.

    Determinista de verdad: se ordenan los ids de cada estrato y se muestrea con
    una semilla fija, así que la misma caché da siempre la misma muestra.
    """
    cuotas = cuotas or MUESTRA_QA
    grupos: dict[str, list[str]] = defaultdict(list)
    for pid, entrada in cache.items():
        if entrada.get("explicacion"):
            grupos[estrato(entrada["origen_contexto"])].append(pid)

    muestra: list[str] = []
    for nombre in ("norma+texto", "norma-o-match", "solo-banco"):
        candidatos = sorted(grupos.get(nombre, []))
        cuota = min(cuotas[nombre], len(candidatos))
        rng = random.Random(f"{SEMILLA_QA}:{nombre}")
        muestra.extend(sorted(rng.sample(candidatos, cuota)))
    return muestra


PROMPT_QA = """Eres un revisor experto e independiente de material formativo del CAP de mercancías en España. NO has escrito la explicación que vas a juzgar.

Juzga si la EXPLICACIÓN es correcta y útil para el alumno, atendiendo a:
- ¿Es fiel a la respuesta correcta indicada?
- ¿Contradice el texto legal aportado (si lo hay)?
- ¿Cita alguna norma, ley, artículo o número que NO aparezca en los datos dados?
- ¿Induce a error o afirma algo falso?
- ¿Se refiere a alguna opción por su letra («la opción b»)? Eso es inaceptable.

Veredicto: "ok" si es fiel y no tiene problemas; "dudosa" si es imprecisa, incompleta o ambigua sin llegar a ser falsa; "mala" si es falsa, contradice el texto legal, cita algo no dado o induce a error. El motivo, en una frase.

{contexto}

EXPLICACIÓN A JUZGAR:
{explicacion}

Devuelve un JSON con los campos "veredicto" y "motivo"."""


def ejecutar_qa(args, key: str, fuentes: dict, cache: dict, uso: Uso) -> dict:
    if getattr(args, "qa_estrato", None):
        # Auditoría COMPLETA de un estrato (no muestreo): todas sus explicaciones.
        muestra = sorted(
            pid
            for pid, e in cache.items()
            if e.get("explicacion") and estrato(e["origen_contexto"]) == args.qa_estrato
        )
    else:
        muestra = seleccionar_muestra_qa(cache)
    resultados = cargar(CACHE_QA, {})
    banco = {q["id"]: q for q in fuentes["banco"]}
    print(f"QA: muestra de {len(muestra)}; {len(resultados)} ya juzgadas.", flush=True)

    try:
        for i, pid in enumerate(muestra, 1):
            if pid in resultados:
                continue
            contexto = contexto_de(banco[pid], fuentes)
            try:
                salida = llamar_gemini(
                    PROMPT_QA.format(
                        contexto=contexto["texto"], explicacion=cache[pid]["explicacion"]
                    ),
                    key,
                    ESQUEMA_QA,
                    uso,
                    "qa",
                    temperatura=0.0,
                    pensamiento=args.pensamiento_qa,
                )
            except ErrorGemini as exc:
                print(f"  [{pid}] ERROR API en QA: {str(exc)[:160]}", flush=True)
                continue
            resultados[pid] = {
                "veredicto": salida.get("veredicto", "dudosa"),
                "motivo": (salida.get("motivo") or "").strip(),
                "estrato": estrato(cache[pid]["origen_contexto"]),
            }
            if i % 10 == 0:
                guardar(CACHE_QA, resultados)
                guardar(USO_JSON, uso.a_json())
            time.sleep(args.pausa)
    finally:
        guardar(CACHE_QA, resultados)
        guardar(USO_JSON, uso.a_json())

    juzgadas = {p: r for p, r in resultados.items() if p in set(muestra)}
    malas = sum(1 for r in juzgadas.values() if r["veredicto"] == "mala")
    ratio = malas / len(juzgadas) if juzgadas else 0.0
    print(
        f"QA: {len(juzgadas)} juzgadas · "
        f"{Counter(r['veredicto'] for r in juzgadas.values())} · "
        f"malas {ratio:.1%}",
        flush=True,
    )
    if ratio > UMBRAL_QA_MALA:
        print(
            f"\nBLOQUEO: {ratio:.1%} de explicaciones 'mala' supera el umbral del "
            f"{UMBRAL_QA_MALA:.0%}. Se para (no se regenera en bucle).",
            flush=True,
        )
    return juzgadas


# =============================================================================
# 8. Informe (§8)
# =============================================================================


def escribir_informe(args, fuentes, cache, resumenes, qa, uso: Uso) -> None:
    banco = fuentes["banco"]
    total = len(banco)
    origenes = Counter(e["origen_contexto"] for e in cache.values())
    con_expl = Counter(
        e["origen_contexto"] for e in cache.values() if e.get("explicacion")
    )
    rechazos = Counter(r for e in cache.values() for r in e.get("rechazos", []))
    regeneradas = sum(1 for e in cache.values() if e.get("rechazos"))
    recuperadas = sum(
        1 for e in cache.values() if e.get("rechazos") and e.get("explicacion")
    )
    sin_expl = [
        (pid, e.get("estado", "?"))
        for pid, e in cache.items()
        if not e.get("explicacion")
    ]
    outliers = [
        (pid, len(e["explicacion"]))
        for pid, e in cache.items()
        if e.get("explicacion") and longitud_outlier(e["explicacion"])
    ]
    longitudes = sorted(len(e["explicacion"]) for e in cache.values() if e.get("explicacion"))

    L = ["# Explicaciones y resúmenes (Gemini) — informe\n"]
    L.append(
        f"Banco: **{total}** preguntas · con explicación: **{sum(con_expl.values())}** "
        f"({100.0 * sum(con_expl.values()) / total:.1f} %) · modelo `{MODEL}`.\n"
    )

    L.append("## Cobertura por origen de contexto\n")
    L.append("| Origen | Preguntas | % del banco | Con explicación | % del origen |")
    L.append("| --- | ---: | ---: | ---: | ---: |")
    for origen in ("norma+texto", "norma", "match", "solo-banco"):
        n, ok = origenes.get(origen, 0), con_expl.get(origen, 0)
        pct_origen = 100.0 * ok / n if n else 0.0
        L.append(
            f"| `{origen}` | {n} | {100.0 * n / total:.1f} % | {ok} | {pct_origen:.1f} % |"
        )
    L.append(f"| **TOTAL** | **{total}** | **100.0 %** | **{sum(con_expl.values())}** | "
             f"**{100.0 * sum(con_expl.values()) / total:.1f} %** |\n")

    combinadas = sum(
        1
        for q in banco
        if any(RE_COMBINADA_INLINE.search(o or "") for o in q["opciones"].values())
    )
    L.append(
        f"En **{combinadas}** preguntas alguna opción se remite a otras por letra "
        "(«Las respuestas A y B son correctas»). Como la lista va sin letras, esas "
        "referencias se sustituyen por el CONTENIDO de las opciones referidas antes "
        "de mandar el contexto al modelo.\n"
    )

    L.append("## Validación automática (§5)\n")
    L.append("| Regla violada | Rechazos |")
    L.append("| --- | ---: |")
    for regla in ("letras", "cita-inventada", "cita-otra-norma"):
        L.append(f"| `{regla}` | {rechazos.get(regla, 0)} |")
    L.append(f"| **total de rechazos** | **{sum(rechazos.values())}** |\n")
    L.append(
        f"- Preguntas que necesitaron regenerar: **{regeneradas}** "
        f"({100.0 * regeneradas / total:.2f} % del banco); de ellas **{recuperadas}** "
        f"acabaron con explicación válida.\n"
    )

    L.append("## Preguntas sin explicación final\n")
    motivos = Counter(estado for _, estado in sin_expl)
    if not sin_expl:
        L.append("Ninguna.\n")
    else:
        L.append("| Motivo | Preguntas |")
        L.append("| --- | ---: |")
        for motivo, n in motivos.most_common():
            L.append(f"| `{motivo}` | {n} |")
        L.append("")
        rechazadas = [pid for pid, estado in sin_expl if estado == "rechazada"]
        if rechazadas:
            L.append(
                "Rechazadas tras "
                f"{MAX_REGENERACIONES} regeneraciones: "
                + ", ".join(f"`{p}`" for p in sorted(rechazadas))
                + "\n"
            )
        L.append(
            "`sin-respuesta-correcta`: el banco no tiene respuesta correcta y el "
            "Ministerio tampoco la aporta (sin match). No se genera nada: una "
            "explicación sin respuesta que explicar sería inventada.\n"
        )

    L.append("## Longitud de las explicaciones\n")
    if longitudes:
        mediana = longitudes[len(longitudes) // 2]
        L.append(
            f"- Rango sano {LONGITUD_MIN}–{LONGITUD_MAX} caracteres · mediana "
            f"**{mediana}** · mínimo {longitudes[0]} · máximo {longitudes[-1]}."
        )
    L.append(
        f"- Outliers (fuera de rango, no se rechazan): **{len(outliers)}**"
        + (
            " → " + ", ".join(f"`{p}` ({n})" for p, n in sorted(outliers)[:20])
            + (" …" if len(outliers) > 20 else "")
            if outliers
            else ""
        )
        + "\n"
    )

    L.append("## Resúmenes por tema (§6)\n")
    if resumenes:
        L.append(
            f"Fuente normativa: Anexo I del {RD284_BASE} ({RD284_ID_ESPERADO}), "
            "programa de cualificación inicial.\n"
        )
        L.append("| Tema | Objetivos Anexo I | Preguntas en contexto | Palabras | Rechazos |")
        L.append("| --- | --- | ---: | ---: | ---: |")
        for slug, datos in resumenes.items():
            L.append(
                f"| {datos['titulo']} (`{slug}`) | "
                f"{', '.join(datos['objetivos_rd284'])} | "
                f"{datos['preguntas_usadas']} | {datos['palabras']} | "
                f"{len(datos.get('rechazos', []))} |"
            )
        fuera = [s for s, d in resumenes.items() if not 300 <= d["palabras"] <= 500]
        L.append(
            f"\nFuera del rango 300–500 palabras: "
            + (", ".join(f"`{s}`" for s in fuera) if fuera else "ninguno")
            + ".\n"
        )
    else:
        L.append("No generados.\n")

    L.append("## QA muestral (§7)\n")
    if qa:
        veredictos = Counter(r["veredicto"] for r in qa.values())
        malas = veredictos.get("mala", 0)
        ratio = malas / len(qa)
        L.append(
            f"Muestra determinista (semilla `{SEMILLA_QA}`) de **{len(qa)}** "
            "explicaciones, juzgadas por Gemini en una llamada independiente.\n"
        )
        L.append("| Estrato | ok | dudosa | mala |")
        L.append("| --- | ---: | ---: | ---: |")
        for nombre in ("norma+texto", "norma-o-match", "solo-banco"):
            del_estrato = [r for r in qa.values() if r["estrato"] == nombre]
            c = Counter(r["veredicto"] for r in del_estrato)
            L.append(
                f"| `{nombre}` | {c.get('ok', 0)} | {c.get('dudosa', 0)} | "
                f"{c.get('mala', 0)} |"
            )
        L.append(
            f"| **TOTAL** | **{veredictos.get('ok', 0)}** | "
            f"**{veredictos.get('dudosa', 0)}** | **{malas}** |\n"
        )
        estado = "BLOQUEO" if ratio > UMBRAL_QA_MALA else "por debajo del umbral"
        L.append(
            f"Malas: **{ratio:.1%}** (umbral {UMBRAL_QA_MALA:.0%}) → **{estado}**.\n"
        )
        problemas = [
            (p, r) for p, r in sorted(qa.items()) if r["veredicto"] in ("mala", "dudosa")
        ]
        if problemas:
            L.append("### Motivos de las dudosas y malas\n")
            for pid, r in problemas:
                L.append(f"- `{pid}` — **{r['veredicto']}** ({r['estrato']}): {r['motivo']}")
            L.append("")
    else:
        L.append("No ejecutado.\n")

    L.append("## Tokens y coste\n")
    L.append("| Etapa | Llamadas | Entrada | Salida | Pensamiento | Coste $ |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for etapa in ("explicaciones", "resumenes", "qa"):
        c = uso.etapas.get(etapa)
        if not c:
            continue
        L.append(
            f"| {etapa} | {c['llamadas']} | {c['entrada']:,} | {c['salida']:,} | "
            f"{c['pensamiento']:,} | "
            f"{Uso.coste(c, args.precio_entrada, args.precio_salida):.4f} |"
        )
    t = uso.totales()
    L.append(
        f"| **TOTAL** | **{t['llamadas']}** | **{t['entrada']:,}** | "
        f"**{t['salida']:,}** | **{t['pensamiento']:,}** | "
        f"**{Uso.coste(t, args.precio_entrada, args.precio_salida):.4f}** |\n"
    )
    L.append(
        f"Tarifa aplicada: {args.precio_entrada:.2f} $/M entrada y "
        f"{args.precio_salida:.2f} $/M salida (las *thoughts* se facturan como "
        "salida). El coste incluye las llamadas rechazadas y regeneradas.\n"
    )

    REPORT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"Informe -> {REPORT_MD.relative_to(REPO)}", flush=True)


# =============================================================================
# 9. main
# =============================================================================


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--explicaciones", action="store_true", help="sólo etapa 1")
    ap.add_argument("--resumenes", action="store_true", help="sólo etapa 2")
    ap.add_argument("--qa", action="store_true", help="sólo etapa 3")
    ap.add_argument(
        "--qa-estrato",
        choices=("norma+texto", "norma-o-match", "solo-banco"),
        help="con --qa: auditar TODAS las explicaciones del estrato (no la muestra)",
    )
    ap.add_argument("--informe", action="store_true", help="sólo reescribir el informe")
    ap.add_argument("--limite", type=int, default=0, help="máximo de preguntas nuevas")
    ap.add_argument("--pausa", type=float, default=0.2, help="segundos entre llamadas")
    ap.add_argument("--pensamiento", type=int, default=0, help="thinkingBudget explicaciones")
    ap.add_argument("--pensamiento-resumen", type=int, default=None)
    ap.add_argument("--pensamiento-qa", type=int, default=None)
    ap.add_argument("--precio-entrada", type=float, default=PRECIO_ENTRADA)
    ap.add_argument("--precio-salida", type=float, default=PRECIO_SALIDA)
    ap.add_argument("--proyeccion-max", type=float, default=PROYECCION_MAX)
    args = ap.parse_args()

    etapas = (args.explicaciones, args.resumenes, args.qa, args.informe)
    todo = not any(etapas)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key and not args.informe:
        raise SystemExit("falta GEMINI_API_KEY en el entorno")

    fuentes = cargar_fuentes()
    uso = Uso(cargar(USO_JSON, {}))

    cache = cargar(CACHE_EXPL, {})
    if todo or args.explicaciones:
        cache = generar_explicaciones(args, key, fuentes, uso)
    if todo or args.explicaciones or args.informe:
        escribir_explicaciones(cache, fuentes["banco"])

    resumenes = cargar(RESUMENES_JSON, {})
    if todo or args.resumenes:
        resumenes = generar_resumenes(args, key, fuentes, uso)

    qa = {}
    if todo or args.qa:
        qa = ejecutar_qa(args, key, fuentes, cache, uso)
        # Los veredictos frescos pueden excluir explicaciones: re-exportar.
        escribir_explicaciones(cache, fuentes["banco"])
    elif args.informe:
        muestra = set(seleccionar_muestra_qa(cache))
        qa = {p: r for p, r in cargar(CACHE_QA, {}).items() if p in muestra}

    if todo or args.informe or args.qa or args.explicaciones or args.resumenes:
        if args.informe or todo or args.qa:
            if not qa:
                muestra = set(seleccionar_muestra_qa(cache))
                qa = {p: r for p, r in cargar(CACHE_QA, {}).items() if p in muestra}
        escribir_informe(args, fuentes, cache, resumenes, qa, uso)


if __name__ == "__main__":
    main()
