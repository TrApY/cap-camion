"""Tests de la recuperación de textos normativos (BOE / EUR-Lex), sin red.

Todo lo que toca la red vive en ``Descargador``; aquí se ejercitan las funciones
puras: parseo de referencias, clasificación de la norma, CELEX, extracción de
artículos y verificación de identidad. Las fixtures son RECORTES REALES de lo
descargado (``data/normativa/``): tres trozos de XML consolidado del BOE y un
trozo del HTML de EUR-Lex.
"""

from __future__ import annotations

from pathlib import Path

import normativa_textos as nt

FIXTURES = Path(__file__).parent / "fixtures"
BOE_LEY16 = FIXTURES / "normativa_boe_ley16_1987.xml"  # Ley 16/1987, arts. 22 y 23
BOE_LEY50 = FIXTURES / "normativa_boe_ley50_1980.xml"  # artículos en letra
BOE_ANEXO = FIXTURES / "normativa_boe_anexo.xml"  # RD 773/1997, Anexo I
BOE_ANEXO_TROCEADO = FIXTURES / "normativa_boe_anexo_troceado.xml"  # OM FOM/1882/2012
EURLEX = FIXTURES / "normativa_eurlex_165_2014.html"  # Reglamento (UE) 165/2014


# --- 1. parseo de referencias -----------------------------------------------


def test_parseo_de_los_ejemplos_de_la_spec():
    assert nt.parsear_referencia("Ley 16/1987 Art. 22") == ("Ley 16/1987", "Art. 22")
    assert nt.parsear_referencia("RD 773/1997 Anexo I") == ("RD 773/1997", "Anexo I")
    assert nt.parsear_referencia(
        "Reglamento Comunitario (UE) 165/2014 Anexo IB, apartado II, 3 (3821/85)"
    ) == (
        "Reglamento Comunitario (UE) 165/2014",
        "Anexo IB, apartado II, 3 (3821/85)",
    )
    assert nt.parsear_referencia("Convenio CMR") == ("Convenio CMR", None)


def test_parseo_de_casos_propios_del_banco():
    # Varios artículos en una sola cita, y tipos con dos palabras.
    assert nt.parsear_referencia("RD Legislativo 8/2015 Art. 157;Art. 316") == (
        "RD Legislativo 8/2015",
        "Art. 157;Art. 316",
    )
    # Localizador que no es ni artículo ni anexo: la base ha de salir limpia.
    assert nt.parsear_referencia("Ley 16/1987 Título IV") == ("Ley 16/1987", "Título IV")
    # Orden ministerial con siglas y convenio con localizador.
    assert nt.parsear_referencia("OM FOM/1190/2005 Art. 24") == (
        "OM FOM/1190/2005",
        "Art. 24",
    )
    assert nt.parsear_referencia("Convenio CMR Art. 23") == ("Convenio CMR", "Art. 23")
    # Cita combinada de dos reglamentos: NO puede atribuirse al primero.
    base, _ = nt.parsear_referencia(
        "Reglamento Comunitario (UE) 952/2013;(UE) 2015/2446 Art. 92;Art. 83"
    )
    assert base == "Reglamento Comunitario (UE) 952/2013;(UE) 2015/2446"


def test_objetivos_de_localizador():
    assert nt.objetivos_de_localizador("Art. 22") == ["22"]
    assert nt.objetivos_de_localizador("Art. 143.4") == ["143"]  # el apartado sobra
    assert nt.objetivos_de_localizador("Arts. 17 y 18") == ["17", "18"]
    assert nt.objetivos_de_localizador("Art. 157;Art. 316") == ["157", "316"]
    assert nt.objetivos_de_localizador("Art 5, 11, 16 y 21") == ["5", "11", "16", "21"]
    assert nt.objetivos_de_localizador("Art. 10 bis 3") == ["10 bis"]
    assert nt.objetivos_de_localizador("Anexo IB, apartado II, 3 (3821/85)") == ["Anexo IB"]
    assert nt.objetivos_de_localizador("Art. 2 y Anexos I y II") == ["2", "Anexo I", "Anexo II"]
    assert nt.objetivos_de_localizador("Anexo, 3.1") == ["Anexo"]
    # Localizadores no soportados: mejor nada que un texto equivocado.
    assert nt.objetivos_de_localizador("Título IV") == []
    assert nt.objetivos_de_localizador("Considerando") == []
    assert nt.objetivos_de_localizador(None) == []


# --- 2. clasificador de tipo de norma ---------------------------------------


def test_clasificador_normas_espanolas():
    assert nt.clasificar_norma("Ley 16/1987") == {
        "clase": "espanola",
        "numero_oficial": "16/1987",
        "rango": "Ley",
    }
    assert nt.clasificar_norma("Ley Orgánica 4/2000")["rango"] == "Ley Orgánica"
    assert nt.clasificar_norma("RD 773/1997")["rango"] == "Real Decreto"
    assert nt.clasificar_norma("RD Legislativo 8/2015")["rango"] == "Real Decreto Legislativo"
    assert nt.clasificar_norma("OM FOM/1190/2005") == {
        "clase": "espanola",
        "numero_oficial": "FOM/1190/2005",
        "rango": "Orden",
    }


def test_clasificador_reglamentos_ue():
    info = nt.clasificar_norma("Reglamento Comunitario (UE) 165/2014")
    assert info["clase"] == "ue" and info["celex"] == "32014R0165"
    assert (info["numero"], info["anio"]) == (165, 2014)
    assert nt.clasificar_norma("Reglamento Comunitario (CE) 561/2006")["celex"] == "32006R0561"


def test_clasificador_deja_fuera_convenios_y_normas_por_fecha():
    for base in (
        "Convenio CMR",
        "Acuerdo ATP",
        "Convenio Aplicación del Acuerdo de Schengen",
        "Directiva 2003/59/CE",
    ):
        assert nt.clasificar_norma(base)["clase"] == "fuera-alcance"
    # Sin número oficial no hay forma de verificar la identidad -> fuera.
    for base in ("Resolución D.G. Tráfico 01/06/2009", "OM 27/07/1999"):
        info = nt.clasificar_norma(base)
        assert info["clase"] == "fuera-alcance"
        assert "número oficial" in info["motivo"]


# --- 3. CELEX ---------------------------------------------------------------


def test_celex_builder():
    assert nt.celex_reglamento("561", "2006") == "32006R0561"
    assert nt.celex_reglamento("165", "2014") == "32014R0165"
    assert nt.celex_reglamento("1", "2005") == "32005R0001"
    # Desde 2015 la UE numera año/número y el Ministerio copia ese formato.
    assert nt.celex_reglamento("2015", "2446") == "32015R2446"


# --- 4. extracción sobre el XML consolidado del BOE -------------------------


def test_extrae_el_articulo_citado_y_solo_ese():
    extraidos = nt.extraer_articulos_boe(BOE_LEY16.read_bytes(), ["22", "999"])
    assert list(extraidos) == ["22"]  # el 23 está en la fixture y NO se extrae
    assert extraidos["22"].startswith("Artículo 22.")
    assert "autorización de operador de transporte de mercancías" in extraidos["22"]


def test_toma_la_version_vigente_del_articulo():
    """El bloque trae tres versiones (1987, 2003 y 2013): vale la de 2013."""
    texto = nt.extraer_articulos_boe(BOE_LEY16.read_bytes(), ["22"])["22"]
    # Redacción original de 1987 y redacción de 2003, ambas ya sustituidas.
    assert "operaciones de carga de las mercancías" not in texto
    assert "se entiende por cargador o remitente" not in texto
    assert "agencias de viajes y otros intermediarios" in texto


def test_extrae_articulos_numerados_con_letra():
    """Las normas antiguas titulan "Artículo dieciséis", el banco cita "Art. 16"."""
    extraidos = nt.extraer_articulos_boe(BOE_LEY50.read_bytes(), ["16", "3", "6 bis"])
    assert set(extraidos) == {"16", "3", "6 bis"}
    assert extraidos["3"].startswith("Artículo tercero")
    assert extraidos["16"].startswith("Artículo dieciséis")
    assert extraidos["6 bis"].startswith("Artículo sexto bis")


def test_extrae_un_anexo_del_boe():
    extraidos = nt.extraer_articulos_boe(BOE_ANEXO.read_bytes(), ["Anexo I", "Anexo II"])
    assert list(extraidos) == ["Anexo I"]
    assert "ANEXO I" in extraidos["Anexo I"][:40]


def test_extrae_un_anexo_troceado_en_varios_bloques():
    """En el BOE el anexo es un "encabezado" y su contenido va en los bloques
    siguientes: extraer solo el rótulo dejaría al RAG sin nada."""
    extraidos = nt.extraer_articulos_boe(BOE_ANEXO_TROCEADO.read_bytes(), ["Anexo", "7"])
    anexo = extraidos["Anexo"]
    assert anexo.startswith("ANEXO")
    assert "Condiciones generales de contratación" in anexo
    assert "1. Definiciones" in anexo and "2. Carta de porte" in anexo
    assert len(anexo) > 10_000
    # El artículo previo al anexo no se contamina con el contenido de este.
    assert extraidos["7"].startswith("Artículo 7.")
    assert "Carta de porte" not in extraidos["7"]


def test_casa_titulo_exige_frontera():
    assert nt._casa_titulo("Artículo 22", "22")
    assert not nt._casa_titulo("Artículo 220", "22")
    assert not nt._casa_titulo("Artículo 22 bis", "22")
    assert nt._casa_titulo("Artículo 22 bis", "22 bis")
    assert nt._casa_titulo("ANEXO I", "Anexo I")
    assert not nt._casa_titulo("ANEXO II", "Anexo I")
    # Algunas normas titulan los anexos en cifras y el banco los cita en romanos.
    assert nt._casa_titulo("ANEXO 1", "Anexo I")
    assert nt._casa_titulo("ANEXO 1 (codificación)", "Anexo I")


# --- 5. extracción sobre el HTML de EUR-Lex ---------------------------------


def test_extrae_articulos_y_anexo_de_eurlex():
    html = EURLEX.read_text(encoding="utf-8")
    extraidos = nt.extraer_articulos_eurlex(html, ["33", "35", "Anexo I", "Anexo IB"])
    assert set(extraidos) == {"33", "35", "Anexo I"}
    assert extraidos["33"].startswith("Artículo 33")
    assert "Responsabilidad de las empresas de transporte" in extraidos["33"]
    assert extraidos["35"].startswith("Artículo 35")
    # No se cuela el artículo siguiente dentro del anterior.
    assert "Artículo 35" not in extraidos["33"]
    assert extraidos["Anexo I"].startswith("ANEXO I")
    # El Anexo IB es del derogado 3821/85: no está en este documento y no se inventa.
    assert "Anexo IB" not in extraidos


def test_extraccion_eurlex_por_texto_plano_sin_anclas():
    """Plan B para documentos sin marcado ELI: regex sobre el texto limpio."""
    html = (
        "<html><body><p>REGLAMENTO (UE) 1/2000 DEL CONSEJO</p>"
        "<p>Artículo 1</p><p>Ámbito de aplicación del reglamento.</p>"
        "<p>Artículo 2</p><p>Definiciones aplicables.</p>"
        "<p>ANEXO I</p><p>Tabla de equivalencias.</p></body></html>"
    )
    extraidos = nt.extraer_articulos_eurlex(html, ["1", "Anexo I"])
    assert "Ámbito de aplicación" in extraidos["1"]
    assert "Definiciones" not in extraidos["1"]
    assert "Tabla de equivalencias" in extraidos["Anexo I"]


def test_verificar_eurlex_no_acepta_un_documento_que_no_es():
    """El título de 165/2014 menciona al 561/2006: no puede acreditarlo."""
    html = EURLEX.read_text(encoding="utf-8")
    assert nt.verificar_eurlex(html, 165, 2014)
    assert not nt.verificar_eurlex(html, 561, 2006)
    assert not nt.verificar_eurlex(html, 3821, 85)
    assert not nt.verificar_eurlex("<html><body>página de error</body></html>", 165, 2014)


# --- 6. verificación del candidato del BOE ----------------------------------


def _item(identificador, titulo, rango, numero, ambito="1"):
    return {
        "identificador": identificador,
        "titulo": titulo,
        "rango": {"codigo": "1300", "texto": rango},
        "ambito": {"codigo": ambito, "texto": "Estatal"},
        "numero_oficial": numero,
    }


def test_candidato_verificado_exige_rango_ambito_y_titulo():
    bueno = _item(
        "BOE-A-2015-11724",
        "Real Decreto Legislativo 8/2015, de 30 de octubre, por el que se aprueba…",
        "Real Decreto Legislativo",
        "8/2015",
    )
    ruido = [
        _item("BOE-A-2015-4621", "Ley 8/2015, de 1 de abril, de Cabildos Insulares.", "Ley", "8/2015"),
        _item(
            "BOE-A-2015-8222",
            "Ley Orgánica 8/2015, de 22 de julio, de modificación…",
            "Ley Orgánica",
            "8/2015",
        ),
    ]
    elegido = nt.candidato_verificado(
        ruido + [bueno], "8/2015", "Real Decreto Legislativo"
    )
    assert elegido is not None and elegido["identificador"] == "BOE-A-2015-11724"

    # Sin candidato del rango pedido: nunca se acepta uno "parecido".
    assert nt.candidato_verificado(ruido, "8/2015", "Real Decreto Legislativo") is None
    # Norma autonómica con el mismo número: descartada por ámbito.
    autonomica = _item(
        "BOE-A-2016-6722", "Ley 8/2015, de 2 de diciembre, de medidas…", "Ley", "8/2015", ambito="2"
    )
    assert nt.candidato_verificado([autonomica], "8/2015", "Ley") is None
    # Ambigüedad (dos candidatos válidos) -> no-resuelta, no se elige a dedo.
    assert nt.candidato_verificado([ruido[0], ruido[0]], "8/2015", "Ley") is None


def test_url_busqueda_boe_usa_el_contrato_de_la_api():
    url = nt.url_busqueda_boe("16/1987")
    assert url.startswith(nt.BOE_API + "?")
    assert "numero_oficial" in url and "limit=50" in url


# --- 7. límites de texto ----------------------------------------------------


def test_recortar_marca_el_truncado():
    texto = "á" * 30_000  # 60 000 bytes utf-8
    recortado = nt.recortar(texto, nt.LIMITE_BLOQUE)
    assert len(recortado.encode("utf-8")) <= nt.LIMITE_BLOQUE + 40
    assert recortado.endswith("[…truncado a 20 KB]")
    assert nt.recortar("corto", nt.LIMITE_BLOQUE) == "corto"


def test_limpiar_colapsa_espacios_y_quita_lineas_vacias():
    assert nt.limpiar("  hola\xa0 mundo \n\n\n  y  adiós ") == "hola mundo\ny adiós"


# --- 8. universo de normas --------------------------------------------------


def test_universo_agrupa_por_norma_base_y_aplica_el_minimo():
    match = {
        f"q{i}": {"norma": "Ley 16/1987 Art. 22"} for i in range(4)
    } | {
        "q4": {"norma": "Convenio CMR Art. 6"},
        "q5": {"norma": None},
        "q6": {"norma": "Ley 16/1987 Anexo I"},
    }
    dentro, fuera = nt.universo(match, min_refs=4)
    assert list(dentro) == ["Ley 16/1987"]
    assert len(dentro["Ley 16/1987"]) == 5
    assert list(fuera) == ["Convenio CMR"]
