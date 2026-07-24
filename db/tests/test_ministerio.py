"""Tests del banco oficial del Ministerio: parseo y matching (sin red).

El parseo se fija sobre una muestra REAL (3 preguntas del cuadernillo de
mercancías objetivo 1, en su codificación cp1252 original) guardada en
``fixtures/``; el matching sobre preguntas sintéticas que ejercitan cada rama
del algoritmo cerrado (umbral alto, zona gris, veto por respuesta, variantes).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import ministerio_descarga as md
import ministerio_match as mm

FIXTURES = Path(__file__).parent / "fixtures"
MUESTRA = FIXTURES / "ministerio_muestra_objetivo1.txt"


# --- parseo -----------------------------------------------------------------


def _parsear_muestra(origen: str = "especificas-mercancias-objetivo-1") -> list[dict]:
    return md.parsear_texto(md.decodificar(MUESTRA.read_bytes()), origen)


def test_parser_produce_el_contrato_completo():
    preguntas = _parsear_muestra()
    assert len(preguntas) == 3

    primera = preguntas[0]
    assert set(primera) == {"origen", "num", "enunciado", "opciones", "respuesta", "norma"}
    assert primera["origen"] == "especificas-mercancias-objetivo-1"
    assert primera["num"] == 10
    assert primera["enunciado"] == "¿A qué se debe la resistencia a la aceleración?"
    assert primera["opciones"] == {
        "a": "A la máxima velocidad del camión.",
        "b": "A la inercia de la masa del camión.",
        "c": "Al estado de la superficie de la calzada.",
        "d": "A la fuerza aerodinámica.",
    }
    assert primera["respuesta"] == "b"


def test_parser_sin_referencia_es_null_y_norma_multilinea_se_colapsa():
    preguntas = {p["num"]: p for p in _parsear_muestra()}
    # "NORMA: Sin referencia" -> null
    assert preguntas[10]["norma"] is None
    # Norma repartida en tres líneas -> una sola cadena con espacios colapsados
    assert preguntas[48]["norma"] == "Acuerdo ADR 2015 7.3.2.4"


def test_parser_admite_enunciado_que_empieza_por_letra_de_opcion():
    # "A mayor altura del centro de gravedad…" NO es la opción A.
    pregunta = {p["num"]: p for p in _parsear_muestra()}[500]
    assert pregunta["enunciado"] == (
        "A mayor altura del centro de gravedad, la estabilidad del camión:"
    )
    assert pregunta["opciones"]["a"] == "disminuye."
    assert pregunta["respuesta"] == "a"


def test_normalizar_norma():
    assert md.normalizar_norma("  RD  97/2014   Art. 42 ") == "RD 97/2014 Art. 42"
    assert md.normalizar_norma("Sin referencia") is None
    assert md.normalizar_norma("SIN REFERENCIA") is None
    assert md.normalizar_norma("   ") is None
    assert md.normalizar_norma(None) is None


def test_parser_descarta_bloques_incompletos_y_los_reporta():
    texto = (
        "COD: 1\n¿Enunciado completo?\nA uno.\nB dos.\nC tres.\nD cuatro.\n"
        "RESPUESTA: C\nNORMA: RD 284/2021 Anexo I\n"
        "COD: 2\n¿Enunciado sin opciones?\nRESPUESTA: A\nNORMA: Sin referencia\n"
    )
    incidencias: list[str] = []
    preguntas = md.parsear_texto(texto, "comunes-objetivo-3", incidencias)
    assert [p["num"] for p in preguntas] == [1]
    assert preguntas[0]["norma"] == "RD 284/2021 Anexo I"
    assert len(incidencias) == 1 and "COD 2" in incidencias[0]


def test_parsear_fichero_zip_deduce_el_objetivo_del_nombre(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("CAPMercancias2.txt", MUESTRA.read_bytes())
    ruta = tmp_path / "especificas-mercancias__CAPMercancias.zip"
    ruta.write_bytes(buffer.getvalue())

    preguntas, incidencias = md.parsear_fichero(ruta, "especificas-mercancias")
    assert incidencias == []
    assert len(preguntas) == 3
    assert {p["origen"] for p in preguntas} == {"especificas-mercancias-objetivo-2"}


def test_clasificar_familia_no_confunde_comunes_con_viajeros():
    # El enlace de comunes se titula "Preguntas comunes a mercancías y viajeros".
    assert (
        md.clasificar_familia(
            "https://cdn.mitma.gob.es/portal-web-drupal/cap/CAPComunes.zip",
            "Preguntas comunes a mercancías y viajeros (ZIP)",
        )
        == "comunes"
    )
    assert (
        md.clasificar_familia(
            "https://cdn.mitma.gob.es/portal-web-drupal/cap/CAPMercancias.zip",
            "Preguntas mercancías (ZIP)",
        )
        == "especificas-mercancias"
    )
    assert (
        md.clasificar_familia(
            "https://cdn.mitma.gob.es/portal-web-drupal/cap/CAPViajeros.zip",
            "Preguntas viajeros (ZIP)",
        )
        is None
    )


# --- matching ---------------------------------------------------------------

UMBRALES = (mm.UMBRAL_ALTO, mm.UMBRAL_GRIS, mm.UMBRAL_RESPUESTA)


def _nuestra(enunciado, correcta_texto, variantes=None, qid="cap-test"):
    return {
        "id": qid,
        "enunciado": enunciado,
        "variantes_enunciado": variantes or [enunciado],
        "opciones": {"a": correcta_texto, "b": "otra", "c": "otra", "d": "otra"},
        "respuesta_correcta": "a" if correcta_texto else None,
        "respuesta_correcta_texto": correcta_texto,
        "tema": "carga-estiba",
    }


def _ministerial(enunciado, correcta_texto, num=1, norma="RD 97/2014 Art. 42"):
    return {
        "origen": "especificas-mercancias-objetivo-1",
        "num": num,
        "enunciado": enunciado,
        "opciones": {"a": correcta_texto, "b": "otra", "c": "otra", "d": "otra"},
        "respuesta": "a",
        "norma": norma,
    }


def _cruzar(nuestra, ministerio):
    """Ejecuta el algoritmo completo (candidatos + decisión) sobre 1 pregunta."""
    candidatos = mm.candidatos_por_pregunta([nuestra], ministerio)[0]
    score, empatados = mm.maximo_y_empates(candidatos)
    return mm.decidir(nuestra, ministerio, score, empatados, *UMBRALES)


def test_match_claro_por_enunciado():
    nuestra = _nuestra(
        "¿Cuál es la masa máxima autorizada de un camión rígido de tres ejes?",
        "26.000 kg.",
    )
    ministerio = [
        _ministerial(
            "¿Cuál es la masa máxima autorizada de un camión rígido de tres ejes?",
            "26.000 kg.",
            num=37,
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert motivo is None
    assert entrada["metodo"] == "enunciado"
    assert entrada["score"] >= mm.UMBRAL_ALTO
    assert entrada["num"] == 37
    assert entrada["norma"] == "RD 97/2014 Art. 42"
    assert entrada["origen"] == "especificas-mercancias-objetivo-1"


def test_zona_gris_con_respuesta_que_casa_se_acepta():
    nuestra = _nuestra(
        "La carga debe sujetarse con cinchas homologadas y calzos de madera "
        "en la caja",
        "Con cinchas homologadas y barras de bloqueo en la caja.",
    )
    ministerio = [
        _ministerial(
            "La carga debe sujetarse con cinchas homologadas y barras de "
            "bloqueo en la caja",
            "Con cinchas homologadas y barras de bloqueo.",
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert motivo is None, f"esperado match en zona gris, no {motivo}"
    assert mm.UMBRAL_GRIS <= entrada["score"] < mm.UMBRAL_ALTO
    assert entrada["metodo"] == "enunciado+respuesta"


def test_zona_gris_con_respuesta_que_no_casa_se_rechaza():
    nuestra = _nuestra(
        "La carga debe sujetarse con cinchas homologadas y calzos de madera "
        "en la caja",
        "Basta con apoyar la carga contra el testero delantero.",
    )
    ministerio = [
        _ministerial(
            "La carga debe sujetarse con cinchas homologadas y barras de "
            "bloqueo en la caja",
            "Con cinchas homologadas y barras de bloqueo.",
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert entrada is None
    assert motivo == "respuesta incompatible"


def test_score_bajo_no_hay_match():
    nuestra = _nuestra(
        "¿Cada cuánto tiempo debe descargarse la tarjeta de conductor?",
        "Cada 28 días.",
    )
    ministerio = [
        _ministerial(
            "¿Qué elemento del motor transforma el movimiento alternativo en "
            "rotativo dentro del bloque?",
            "El cigüeñal.",
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert entrada is None
    assert motivo == "score < umbral"


def test_veto_por_respuesta_aunque_el_enunciado_sea_identico():
    """La respuesta forma parte de la identidad de la pregunta (Fase 0)."""
    nuestra = _nuestra(
        "¿Qué código ATP corresponde a un vehículo isotermo reforzado con "
        "equipo frigorífico de clase C?",
        "FRC.",
    )
    ministerio = [
        _ministerial(
            "¿Qué código ATP corresponde a un vehículo isotermo reforzado con "
            "equipo frigorífico de clase C?",
            "FRF.",
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert entrada is None
    assert motivo == "respuesta incompatible"


def test_usa_las_variantes_de_enunciado():
    """El enunciado principal no casa, pero una variante sí."""
    nuestra = _nuestra(
        "Senale la afirmacion correcta sobre el tacografo",  # variante OCR pobre
        "Cada 28 días.",
        variantes=[
            "Senale la afirmacion correcta sobre el tacografo",
            "¿Cada cuánto tiempo debe descargarse la tarjeta de conductor?",
        ],
    )
    ministerio = [
        _ministerial(
            "¿Cada cuánto tiempo debe descargarse la tarjeta de conductor?",
            "Cada 28 días.",
            num=812,
            norma="RD 1211/1990 Art. 5",
        )
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert motivo is None
    assert entrada["num"] == 812
    assert entrada["metodo"] == "enunciado"
    assert entrada["score"] >= mm.UMBRAL_ALTO


def test_desempate_prefiere_el_candidato_cuya_respuesta_casa():
    """Con varios candidatos al mismo score máximo gana el que confirma la respuesta."""
    enunciado = "¿Cuál es la masa máxima autorizada de un camión rígido de tres ejes?"
    nuestra = _nuestra(enunciado, "26.000 kg.")
    ministerio = [
        _ministerial(enunciado, "40.000 kg.", num=1, norma="NORMA MALA"),
        _ministerial(enunciado, "26.000 kg.", num=2, norma="RD 2822/1998 Anexo IX"),
    ]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert motivo is None
    assert entrada["num"] == 2
    assert entrada["norma"] == "RD 2822/1998 Anexo IX"


def test_sin_respuesta_nuestra_el_veto_no_aplica_pero_la_zona_gris_no_pasa():
    enunciado = "¿Cuál es la masa máxima autorizada de un camión rígido de tres ejes?"
    nuestra = _nuestra(enunciado, None)
    nuestra["respuesta_correcta"] = None
    ministerio = [_ministerial(enunciado, "26.000 kg.")]
    entrada, motivo = _cruzar(nuestra, ministerio)
    assert motivo is None and entrada["metodo"] == "enunciado"

    # En zona gris, sin respuesta que confirmar, no hay match.
    gris = _nuestra(
        "La carga debe sujetarse con cinchas homologadas y calzos de madera "
        "en la caja",
        None,
    )
    ministerio_gris = [
        _ministerial(
            "La carga debe sujetarse con cinchas homologadas y barras de "
            "bloqueo en la caja",
            "Con cinchas homologadas y barras de bloqueo.",
        )
    ]
    entrada, motivo = _cruzar(gris, ministerio_gris)
    assert entrada is None
    assert motivo == "zona gris sin confirmación de respuesta"
