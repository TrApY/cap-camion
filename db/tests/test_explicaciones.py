"""Tests de la generación de explicaciones (Gemini), sin red.

Todo lo que toca la red vive en ``llamar_gemini``; aquí se ejercitan las piezas
puras que sostienen los principios anti-alucinación de la fase: construcción del
contexto (cita oficial como dato, correcta marcada, cero letras), validadores de
§5 y selección determinista de la muestra de QA.
"""

from __future__ import annotations

import re

import generar_explicaciones as ge

# --- material de apoyo -------------------------------------------------------

PREGUNTA = {
    "id": "cap-0001",
    "enunciado": "¿Cada cuánto debe hacerse la pausa de conducción?",
    "opciones": {
        "a": "Cada cuatro horas y media de conducción.",
        "b": "Cada seis horas de conducción.",
        "c": "Cada dos horas de conducción.",
        "d": "No es obligatoria ninguna pausa.",
    },
    "respuesta_correcta": "a",
    "respuesta_correcta_texto": "Cada cuatro horas y media de conducción.",
    "frecuencia": 9,
    "tema": "tiempos-tacografo",
}

MATCH_CON_NORMA = {
    "origen": "comunes-objetivo-2",
    "num": 12,
    "norma": "Reglamento Comunitario (CE) 561/2006 Art. 7",
    "score": 100.0,
    "metodo": "enunciado",
}
MATCH_SIN_NORMA = {**MATCH_CON_NORMA, "norma": None}

MINISTERIAL = {
    "origen": "comunes-objetivo-2",
    "num": 12,
    "enunciado": "¿Cada cuánto debe hacerse la pausa de conducción?",
    "opciones": {
        "a": "Cada dos horas de conducción.",
        "b": "Cada cuatro horas y media de conducción.",
        "c": "Cada seis horas de conducción.",
        "d": "No es obligatoria ninguna pausa.",
    },
    "respuesta": "b",
    "norma": "Reglamento Comunitario (CE) 561/2006 Art. 7",
}

TEXTO_ART7 = (
    "Artículo 7\nTras un período de conducción de cuatro horas y media, el "
    "conductor hará una pausa ininterrumpida de al menos 45 minutos."
)
NORMATIVA = {
    "Reglamento Comunitario (CE) 561/2006": {
        "estado": "ok",
        "fuente": "eurlex",
        "articulos": {"7": TEXTO_ART7, "8": "Artículo 8 …"},
    },
    "Ley 16/1987": {"estado": "no-resuelta", "articulos": {}},
    "OM FOM/1882/2012": {
        "estado": "ok",
        "fuente": "boe",
        "articulos": {ge.nt.CLAVE_COMPLETO: "Texto completo de la orden."},
    },
}


def contexto(match=None, ministerial=None, pregunta=None):
    return ge.construir_contexto(
        pregunta or PREGUNTA, match, ministerial, NORMATIVA
    )


# --- 1. construcción del contexto -------------------------------------------


def test_contexto_norma_mas_texto():
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL)
    assert ctx["origen_contexto"] == "norma+texto"
    assert ctx["con_texto_legal"] is True
    # La cita es LITERALMENTE la del Ministerio, no una redactada por nosotros.
    assert ctx["norma"] == "Reglamento Comunitario (CE) 561/2006 Art. 7"
    assert "Reglamento Comunitario (CE) 561/2006 Art. 7" in ctx["texto"]
    assert "pausa ininterrumpida de al menos 45 minutos" in ctx["texto"]
    # La respuesta oficial del Ministerio va como dato aparte.
    assert "Respuesta oficial: Cada cuatro horas y media de conducción." in ctx["texto"]


def test_contexto_solo_norma_sin_texto_disponible():
    match = {**MATCH_CON_NORMA, "norma": "Ley 16/1987 Art. 22"}
    ctx = contexto(match, {**MINISTERIAL, "norma": "Ley 16/1987 Art. 22"})
    assert ctx["origen_contexto"] == "norma"
    assert ctx["con_texto_legal"] is False
    assert "Ley 16/1987 Art. 22" in ctx["texto"]
    assert "TEXTO LEGAL LITERAL" not in ctx["texto"]


def test_contexto_solo_match():
    ctx = contexto(MATCH_SIN_NORMA, MINISTERIAL)
    assert ctx["origen_contexto"] == "match"
    assert ctx["norma"] is None
    assert ctx["con_texto_legal"] is False
    assert "DATOS OFICIALES DEL MINISTERIO" in ctx["texto"]


def test_contexto_solo_banco():
    ctx = contexto(None, None)
    assert ctx["origen_contexto"] == "solo-banco"
    assert ctx["norma"] is None
    assert "DATOS OFICIALES DEL MINISTERIO" not in ctx["texto"]
    assert "TEXTO LEGAL LITERAL" not in ctx["texto"]


def test_contexto_marca_la_correcta_y_lleva_las_cuatro_opciones():
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL)
    for opcion in PREGUNTA["opciones"].values():
        assert opcion in ctx["texto"]
    marcadas = [ln for ln in ctx["texto"].split("\n") if ge.MARCA_CORRECTA in ln]
    assert len(marcadas) == 1
    assert "Cada cuatro horas y media de conducción." in marcadas[0]
    assert "RESPUESTA CORRECTA: Cada cuatro horas y media de conducción." in ctx["texto"]


def test_contexto_no_lleva_letras_de_opcion():
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL)
    for linea in ctx["texto"].split("\n"):
        # Ninguna opción se presenta rotulada con su letra.
        assert not re.match(r"^\s*[a-dA-D]\s*[).\-:]", linea)
    assert not re.search(r"\b(?:opci[óo]n|respuesta|letra)\s+[a-dA-D]\b", ctx["texto"])
    # Y las letras del banco (a/b/c/d) no viajan al prompt como claves.
    assert "'a'" not in ctx["texto"] and '"a":' not in ctx["texto"]


def test_contexto_usa_la_respuesta_oficial_si_el_banco_no_la_tiene():
    huerfana = {**PREGUNTA, "respuesta_correcta": None, "respuesta_correcta_texto": None}
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL, huerfana)
    assert ctx["respuesta_texto"] == "Cada cuatro horas y media de conducción."
    assert ge.MARCA_CORRECTA in ctx["texto"]


def test_contexto_sin_respuesta_correcta_ni_oficial():
    huerfana = {**PREGUNTA, "respuesta_correcta": None, "respuesta_correcta_texto": None}
    ctx = contexto(None, None, huerfana)
    assert ctx["respuesta_texto"] is None
    assert ge.MARCA_CORRECTA not in ctx["texto"]
    assert "RESPUESTA CORRECTA:" not in ctx["texto"]


# --- 1 bis. opciones que se remiten a otras por letra ------------------------

COMBINADA = {
    "id": "cap-0002",
    "enunciado": "En caso de auxiliar en un accidente, conviene hacerlo:",
    "opciones": {
        "a": "Con guantes.",
        "b": "Con mascarilla.",
        "c": "Las respuestas A y B son correctas.",
        "d": "Sin protección, para no perder tiempo.",
    },
    "respuesta_correcta": "c",
    "respuesta_correcta_texto": "Las respuestas A y B son correctas.",
}


def test_expandir_referencias_a_otras_opciones():
    ops = COMBINADA["opciones"]
    assert (
        ge.expandir_referencias("Las respuestas A y B son correctas.", ops)
        == "Son correctas a la vez «Con guantes» y «Con mascarilla»."
    )
    # Variante inline (referencia en medio de la frase).
    planas = {"a": "Con guantes.", "b": "Con mascarilla.", "c": "En seco.", "d": "Nunca."}
    assert ge.expandir_referencias(
        "Deberá efectuar controles en los casos descritos en las respuestas B y C.",
        planas,
    ) == "Deberá efectuar controles en los casos descritos en «Con mascarilla» y «En seco»."
    # La errata real del banco ("con correctas" en vez de "son correctas").
    assert (
        ge.expandir_referencias("Las respuestas A y B con correctas.", ops)
        == "Son correctas a la vez «Con guantes» y «Con mascarilla»."
    )
    # Referencia en cascada: la opción referida se remite a su vez a otras.
    assert "Las respuestas" not in ge.expandir_referencias(
        "Deberá actuar como dicen las respuestas B y C.", ops
    )
    # Sin referencias, no toca nada.
    assert ge.expandir_referencias("Con guantes.", ops) == "Con guantes."
    assert ge.expandir_referencias(None, ops) == ""


def test_contexto_de_opcion_combinada_no_deja_letras_sueltas():
    ctx = ge.construir_contexto(COMBINADA, None, None, NORMATIVA)
    assert "Las respuestas A y B" not in ctx["texto"]
    assert "Son correctas a la vez «Con guantes» y «Con mascarilla»." in ctx["texto"]
    assert not re.search(r"\brespuestas?\s+[A-D]\b", ctx["texto"])
    # Y la correcta sigue marcada una sola vez.
    assert ctx["texto"].count(ge.MARCA_CORRECTA) == 1


def test_no_se_marca_si_la_correcta_solo_la_da_el_ministerio_y_usa_letras():
    # Las letras del Ministerio no son las nuestras: marcar sería inventar.
    huerfana = {**COMBINADA, "respuesta_correcta": None, "respuesta_correcta_texto": None}
    ministerial = {
        "origen": "x",
        "num": 1,
        "opciones": {
            "a": "Sin protección, para no perder tiempo.",
            "b": "Con guantes.",
            "c": "Con mascarilla.",
            "d": "Las respuestas B y C son correctas.",
        },
        "respuesta": "d",
    }
    ctx = ge.construir_contexto(huerfana, MATCH_SIN_NORMA, ministerial, NORMATIVA)
    assert ge.MARCA_CORRECTA not in ctx["texto"]
    # Pero la respuesta oficial sí se da, expandida con las opciones DEL MINISTERIO.
    assert "Son correctas a la vez «Con guantes» y «Con mascarilla»." in ctx["texto"]


# --- 2. texto legal: resolución y truncado ----------------------------------


def test_texto_legal_trunca_a_8000_caracteres():
    largo = {
        "Ley 16/1987": {
            "estado": "ok",
            "articulos": {"22": "x" * 20_000},
        }
    }
    texto = ge.texto_legal("Ley 16/1987 Art. 22", largo)
    assert len(texto) <= ge.LIMITE_TEXTO_LEGAL + len("\n[…texto truncado…]")
    assert texto.endswith("[…texto truncado…]")
    # Justo por debajo del límite NO se trunca.
    corto = {"Ley 16/1987": {"estado": "ok", "articulos": {"22": "y" * 100}}}
    assert "truncado" not in ge.texto_legal("Ley 16/1987 Art. 22", corto)


def test_texto_legal_reutiliza_el_parseo_de_normativa_textos():
    # "Art. 7" tiene que resolver contra la clave "7" del caché: eso lo decide
    # objetivos_de_localizador() de normativa_textos, no este módulo.
    assert ge.texto_legal("Reglamento Comunitario (CE) 561/2006 Art. 7", NORMATIVA)
    assert ge.texto_legal("Reglamento Comunitario (CE) 561/2006 Art. 99", NORMATIVA) is None
    assert ge.texto_legal("Ley 16/1987 Art. 22", NORMATIVA) is None  # norma no-resuelta
    assert ge.texto_legal(None, NORMATIVA) is None


def test_texto_legal_cae_al_texto_completo_cuando_no_hay_articulo():
    assert "Texto completo" in ge.texto_legal("OM FOM/1882/2012 Anexo", NORMATIVA)


# --- 3. validador de letras (§5) --------------------------------------------


def test_rechaza_referencias_a_opciones_por_letra():
    for malo in (
        "La opción b es incorrecta porque el tacógrafo registra el tiempo.",
        "La respuesta c confunde pausa con descanso.",
        "Hay que descartar la letra d, que no existe en la práctica.",
        "La opción A) plantea un supuesto imposible.",
        "Las opciones a y c hablan de lo mismo.",
        "Lo dice la letra c) del precepto.",
    ):
        assert ge.cita_letra_de_opcion(malo), malo
        assert "letras" in ge.validar(malo, None)


def test_no_se_persigue_una_letra_suelta_entre_parentesis():
    # El modelo nunca ve las letras de las opciones (van en lista neutra), así
    # que un "c)" suelto sólo puede venir del texto legal: perseguirlo costaría
    # explicaciones buenas sin proteger de nada.
    bueno = "La sanción va de 10.001 a 100.000 euros, según el tramo c) del precepto."
    assert not ge.cita_letra_de_opcion(bueno)


def test_acepta_explicaciones_sin_letras():
    for bueno in (
        "Tras cuatro horas y media de conducción hay que parar 45 minutos.",
        "El error típico es confundir la pausa con el descanso diario.",
        "Conducir seis horas seguidas es sanción segura.",
        # Preposición "a", no letra de opción: no puede rechazarse por esto.
        "La respuesta a esta situación es reducir la velocidad.",
        "La respuesta a la pregunta pasa por revisar la presión de los neumáticos.",
    ):
        assert not ge.cita_letra_de_opcion(bueno), bueno
        assert ge.validar(bueno, None) == []


def test_la_excepcion_de_la_preposicion_no_deja_pasar_letras_reales():
    # "a" seguida de algo que NO es determinante sigue siendo letra de opción.
    assert ge.cita_letra_de_opcion("La opción a es la buena porque frena antes.")
    assert ge.cita_letra_de_opcion("La respuesta a resulta falsa.")
    assert ge.cita_letra_de_opcion("Marca la letra a.")


# --- 4. validador de citas normativas (§5) ----------------------------------


def test_sin_norma_en_contexto_cualquier_cita_legal_se_rechaza():
    for malo in (
        "Lo dice el Reglamento 561/2006 en su artículo 7.",
        "Según la Ley 16/1987 esto es una infracción grave.",
        "El RD 1211/1990 lo regula así.",
        "Está en el artículo 20 del reglamento de circulación.",
        "Lo fija la Directiva 2003/59/CE.",
        "Viene del Convenio CMR 1956 en su art. 23.",
        "Lo recoge el Reglamento (UE) 165/2014.",
    ):
        assert ge.cita_normativa_prohibida(malo, None), malo
        assert "cita-inventada" in ge.validar(malo, None)


def test_sin_norma_en_contexto_una_explicacion_tecnica_pasa():
    for bueno in (
        "Tras cuatro horas y media conduciendo baja la atención y hay que parar.",
        "El freno motor evita el sobrecalentamiento de los frenos de servicio.",
        "Con 44 toneladas y 5 ejes el reparto de masa cambia por completo.",
        "La normativa obliga a hacer una pausa, sin más matices.",
    ):
        assert not ge.cita_normativa_prohibida(bueno, None), bueno
        assert ge.validar(bueno, None) == []


def test_con_norma_en_contexto_se_permite_esa_y_solo_esa():
    norma = "Reglamento Comunitario (CE) 561/2006 Art. 7"
    bueno = "El Reglamento 561/2006 exige una pausa de 45 minutos tras 4h30."
    assert not ge.cita_normativa_prohibida(bueno, norma)
    assert ge.validar(bueno, norma) == []
    # El caso clave: contexto CON norma pero se cita OTRA.
    malo = "El Reglamento 561/2006 lo exige, igual que la Ley 16/1987."
    assert ge.cita_normativa_prohibida(malo, norma)
    assert "cita-otra-norma" in ge.validar(malo, norma)
    otro = "Lo regula el RD 1211/1990 en su artículo 41."
    assert ge.cita_normativa_prohibida(otro, norma)


def test_la_norma_que_da_la_propia_pregunta_se_puede_repetir():
    # "¿Qué norma regula el CAP?" -> "El Real Decreto 284/2021": sin match
    # ministerial, pero repetir el dato de la respuesta no es inventar nada.
    dados = ["284/2021"]
    bueno = "La norma española que regula el CAP es el Real Decreto 284/2021."
    assert not ge.cita_normativa_prohibida(bueno, None, dados)
    assert ge.validar(bueno, None, dados) == []
    # Pero no vale colgarle artículos que nadie ha dado…
    assert ge.cita_normativa_prohibida(
        "Lo dice el artículo 5 del Real Decreto 284/2021.", None, dados
    )
    # …ni traerse otra norma distinta.
    assert ge.cita_normativa_prohibida(
        "El Real Decreto 284/2021 desarrolla la Ley 16/1987.", None, dados
    )
    # Y sin nada dado, la regla estricta sigue en pie.
    assert ge.cita_normativa_prohibida("Lo fija el Real Decreto 284/2021.", None, [])


def test_los_identificadores_dados_salen_del_enunciado_y_las_opciones():
    pregunta = {
        "id": "cap-0003",
        "enunciado": "¿Qué norma regula la cualificación inicial del CAP?",
        "opciones": {
            "a": "El Real Decreto 284/2021, de 20 de abril.",
            "b": "La Ley 16/1987.",
            "c": "Ninguna norma española.",
            "d": "Una orden autonómica.",
        },
        "respuesta_correcta": "a",
        "respuesta_correcta_texto": "El Real Decreto 284/2021, de 20 de abril.",
    }
    ctx = ge.construir_contexto(pregunta, None, None, NORMATIVA)
    assert ctx["identificadores_dados"] == ["16/1987", "284/2021"]
    assert ge.construir_contexto(PREGUNTA, None, None, NORMATIVA)["identificadores_dados"] == []


def test_con_norma_en_contexto_no_hace_falta_citar_nada():
    norma = "Reglamento Comunitario (CE) 561/2006 Art. 7"
    assert ge.validar("Hay que parar 45 minutos tras 4h30 de conducción.", norma) == []


def test_validar_acumula_las_dos_reglas():
    fallos = ge.validar("La opción b contradice la Ley 16/1987.", None)
    assert fallos == ["letras", "cita-inventada"]


# --- 5. longitud (outlier, no rechazo) --------------------------------------


def test_longitud_outlier():
    assert ge.longitud_outlier("corta")
    assert ge.longitud_outlier("x" * 901)
    assert not ge.longitud_outlier("x" * ge.LONGITUD_MIN)
    assert not ge.longitud_outlier("x" * ge.LONGITUD_MAX)
    # Un outlier de longitud NO es un rechazo.
    assert ge.validar("corta", None) == []


# --- 6. muestra de QA: determinista y estratificada -------------------------


def _cache_falsa(n=400):
    origenes = ["norma+texto", "norma", "match", "solo-banco"]
    cache = {}
    for i in range(n):
        origen = origenes[i % 4]
        cache[f"cap-{i:04d}"] = {
            "explicacion": None if i % 40 == 0 else f"explicación {i}",
            "norma": "Ley 16/1987 Art. 22" if origen.startswith("norma") else None,
            "con_texto_legal": origen == "norma+texto",
            "origen_contexto": origen,
        }
    return cache


def test_muestra_qa_es_determinista():
    cache = _cache_falsa()
    assert ge.seleccionar_muestra_qa(cache) == ge.seleccionar_muestra_qa(cache)
    # Y no depende del orden de inserción del diccionario.
    revuelta = dict(reversed(list(cache.items())))
    assert ge.seleccionar_muestra_qa(revuelta) == ge.seleccionar_muestra_qa(cache)


def test_muestra_qa_respeta_la_estratificacion():
    cache = _cache_falsa()
    muestra = ge.seleccionar_muestra_qa(cache)
    assert len(muestra) == 60
    reparto = {}
    for pid in muestra:
        estrato = ge.estrato(cache[pid]["origen_contexto"])
        reparto[estrato] = reparto.get(estrato, 0) + 1
    assert reparto == {"norma+texto": 30, "norma-o-match": 15, "solo-banco": 15}
    assert len(set(muestra)) == 60


def test_muestra_qa_solo_coge_preguntas_con_explicacion():
    cache = _cache_falsa()
    assert all(cache[pid]["explicacion"] for pid in ge.seleccionar_muestra_qa(cache))


def test_muestra_qa_no_falla_si_falta_material():
    escasa = {
        "cap-a": {"explicacion": "x", "origen_contexto": "norma+texto"},
        "cap-b": {"explicacion": "y", "origen_contexto": "solo-banco"},
    }
    assert sorted(ge.seleccionar_muestra_qa(escasa)) == ["cap-a", "cap-b"]


def test_estratos():
    assert ge.estrato("norma+texto") == "norma+texto"
    assert ge.estrato("norma") == "norma-o-match"
    assert ge.estrato("match") == "norma-o-match"
    assert ge.estrato("solo-banco") == "solo-banco"


# --- 7. prompt: las reglas duras viajan siempre -----------------------------


def test_el_prompt_prohibe_citar_si_no_hay_norma():
    prompt = ge.prompt_explicacion(contexto(None, None), [])
    assert "NO puedes hacer NINGUNA cita legal" in prompt
    assert "NUNCA te refieras a una opción por su letra" in prompt


def test_el_prompt_acota_la_cita_a_la_norma_dada():
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL)
    prompt = ge.prompt_explicacion(ctx, [])
    assert "La ÚNICA referencia normativa que puedes mencionar es «Reglamento" in prompt
    assert "Está prohibido citar cualquier otra norma" in prompt


def test_el_prompt_refuerza_la_regla_violada_al_regenerar():
    ctx = contexto(MATCH_CON_NORMA, MINISTERIAL)
    prompt = ge.prompt_explicacion(ctx, ["letras", "cita-otra-norma"])
    assert "se RECHAZÓ por referirse a algo por su letra" in prompt
    assert "se RECHAZÓ por citar una norma distinta" in prompt


# --- 8. Anexo I del RD 284/2021 (§6), troceo sin red ------------------------

ANEXO_MUESTRA = """ANEXO I
Programas de formación
A) Programa de los cursos de cualificación inicial
Sección 1.ª Formación obligatoria para todos los permisos
1. Formación avanzada sobre conducción racional.
a) Objetivo 1.1: Conocer las características de la cadena cinemática.
Duración: Veinte horas, de las que cuatro serán de conducción efectiva.
Cuando se trate de un curso de formación acelerada, la duración será de diez horas.
Contenido: Curvas de par, potencia y consumo específico de un motor.
b) Objetivo 1.2: Conocer los dispositivos de seguridad.
Contenido: Frenos, ABS, ralentizador.
2. Aplicación de la reglamentación.
Objetivo 2.1: Conocer el entorno social del transporte.
Contenido: Tiempos de conducción y descanso, tacógrafo.
Sección 2.ª Formación obligatoria específica para los permisos C
1. Formación avanzada.
Objetivo 1.5: Ser capaz de realizar una operación de carga.
Contenido: Estiba, masas y dimensiones.
B) Programa de los cursos de formación continua
Objetivo 1.1: Esto ya no debe entrar en el troceo.
"""


def test_troceo_del_anexo_i():
    epigrafes = ge.extraer_epigrafes_anexo_i(ANEXO_MUESTRA)
    assert sorted(epigrafes) == ["1.1", "1.2", "1.5", "2.1"]
    assert epigrafes["1.1"].startswith("Objetivo 1.1:")
    assert "Curvas de par" in epigrafes["1.1"]
    # Las líneas administrativas de duración no entran en el contexto.
    assert "Duración:" not in epigrafes["1.1"]
    assert "formación acelerada" not in epigrafes["1.1"]
    # El troceo corta en la siguiente sección y no arrastra contenido ajeno.
    assert "Frenos, ABS" not in epigrafes["1.1"]
    assert "Estiba, masas" in epigrafes["1.5"]
    assert "Estiba" not in epigrafes["2.1"]
    # Sólo el programa de cualificación inicial (apartado A).
    assert "ya no debe entrar" not in epigrafes["1.1"]


def test_el_mapa_de_temas_cubre_los_once_y_solo_objetivos_de_mercancias():
    temas = ge.cargar(ge.TEMAS_JSON, [])
    assert sorted(ge.TEMA_A_OBJETIVOS) == sorted(t["slug"] for t in temas)
    usados = {o for objetivos in ge.TEMA_A_OBJETIVOS.values() for o in objetivos}
    # 1.6, 1.7, 2.3 y 3.8 son de viajeros: no pueden estar mapeados.
    assert usados.isdisjoint({"1.6", "1.7", "2.3", "3.8"})
    assert usados == {"1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.2", "3.1",
                      "3.2", "3.3", "3.4", "3.5", "3.6", "3.7"}


# --- 9. contabilidad de tokens ----------------------------------------------


def test_uso_acumula_y_calcula_coste():
    uso = ge.Uso()
    uso.anotar(
        "explicaciones",
        {
            "promptTokenCount": 1000,
            "candidatesTokenCount": 100,
            "thoughtsTokenCount": 50,
            "totalTokenCount": 1150,
        },
    )
    uso.anotar("qa", {"promptTokenCount": 500, "candidatesTokenCount": 20})
    total = uso.totales()
    assert total["llamadas"] == 2
    assert total["entrada"] == 1500
    assert total["salida"] == 120
    assert total["pensamiento"] == 50
    # Las thoughts se facturan como salida.
    esperado = (1500 * 0.30 + 170 * 2.50) / 1_000_000
    assert abs(ge.Uso.coste(total, 0.30, 2.50) - esperado) < 1e-12
    # Y sobrevive al ida y vuelta a JSON (reanudable).
    revivido = ge.Uso(uso.a_json())
    assert revivido.totales() == total
