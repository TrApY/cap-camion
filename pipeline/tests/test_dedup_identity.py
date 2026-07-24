"""Tests de la identidad de pregunta en la deduplicacion.

La identidad de una pregunta es (enunciado, opciones). Estos tests fijan el
comportamiento tras corregir:
  - el colapso de enunciados genericos ("Señale la afirmación correcta:"), y
  - el over-merge difuso de preguntas distintas con estructura parecida.
"""

from __future__ import annotations

from cap_pipeline.dedup import build_bank


def _q(enunciado, opciones, correcta, fuente, fecha="2025-01-01"):
    return {
        "enunciado": enunciado,
        "opciones": opciones,
        "respuesta_correcta": correcta,
        "fuente": fuente,
        "comunidad": "andalucia",
        "fecha": fecha,
        "modelo": "A",
    }


def test_generic_stem_with_different_options_stays_separate():
    """Mismo enunciado generico + opciones distintas => preguntas distintas."""
    raw = [
        _q(
            "Señale la afirmación correcta:",
            {"a": "El cielo es azul.", "b": "El sol es frio.",
             "c": "El agua moja.", "d": "El fuego enfria."},
            "a",
            "EX_A.pdf",
        ),
        _q(
            "Señale la afirmación correcta:",
            {"a": "Un camion tiene ruedas.", "b": "Los peces vuelan.",
             "c": "Las piedras nadan.", "d": "El hielo arde."},
            "a",
            "EX_B.pdf",
        ),
    ]
    bank, conflicts = build_bank(raw)
    assert len(bank) == 2, "los dos enunciados genericos NO deben fusionarse"
    assert conflicts == 0, "no hay conflicto de respuesta real: son preguntas distintas"


def test_same_question_shuffled_options_merges():
    """La misma pregunta en modelos A/B (opciones barajadas) => una sola entrada."""
    opts_a = {"a": "Rozamiento.", "b": "Frenada.", "c": "Deceleración.", "d": "Inercia."}
    opts_b = {"a": "Inercia.", "b": "Deceleración.", "c": "Frenada.", "d": "Rozamiento."}
    raw = [
        _q("¿Cómo se denomina la fuerza de contacto?", opts_a, "a", "EX_A.pdf"),
        _q("¿Cómo se denomina la fuerza de contacto?", opts_b, "d", "EX_B.pdf"),
    ]
    bank, conflicts = build_bank(raw)
    assert len(bank) == 1, "misma pregunta con opciones barajadas debe ser 1 entrada"
    assert bank[0].frecuencia == 2
    assert conflicts == 0, "misma respuesta (Rozamiento) => sin conflicto"


def test_similar_stem_different_options_not_overmerged():
    """Enunciados casi identicos pero preguntas distintas (TSR vs SLI) no se fusionan."""
    raw = [
        _q(
            "¿Qué función tiene el sistema de ayuda a la conducción denominado TSR?",
            {"a": "Reconocer señales de tráfico.", "b": "Frenar de emergencia.",
             "c": "Mantener el carril.", "d": "Aparcar solo."},
            "a",
            "EX_A.pdf",
        ),
        _q(
            "¿Qué función tiene el sistema de ayuda a la conducción denominado SLI?",
            {"a": "Limitar la velocidad según la señal.", "b": "Encender las luces.",
             "c": "Regular la presión.", "d": "Medir el consumo."},
            "a",
            "EX_B.pdf",
        ),
    ]
    bank, _ = build_bank(raw)
    assert len(bank) == 2, "TSR y SLI son preguntas distintas y no deben fusionarse"


def test_ids_unique_when_answer_text_shared_options_differ():
    """Regresion: mismo enunciado generico + misma respuesta-TEXTO pero distractores
    distintos => preguntas DISTINTAS => ids distintos (unicidad de clave primaria)."""
    correcta = "Reducir el consumo de carburante."
    raw = [
        _q(
            "Señale la afirmación correcta:",
            {"a": correcta, "b": "Aumentar la velocidad siempre.",
             "c": "Frenar en curva.", "d": "Circular sin cinturón."},
            "a",
            "EX_A.pdf",
        ),
        _q(
            "Señale la afirmación correcta:",
            {"a": correcta, "b": "Ignorar las señales.",
             "c": "Adelantar en línea continua.", "d": "Conducir cansado."},
            "a",
            "EX_B.pdf",
        ),
    ]
    bank, _ = build_bank(raw)
    assert len(bank) == 2, "distractores distintos => preguntas distintas"
    assert bank[0].id != bank[1].id, "entradas distintas NO deben compartir id"
    assert len({c.id for c in bank}) == len(bank), "todos los ids deben ser unicos"


def test_genuine_answer_conflict_is_flagged():
    """Misma pregunta (mismo enunciado+opciones) con respuesta distinta => conflicto."""
    opts = {"a": "Verdadero.", "b": "Falso.", "c": "A veces.", "d": "Nunca."}
    raw = [
        _q("¿Es correcta la afirmación X?", opts, "a", "EX_A.pdf"),
        _q("¿Es correcta la afirmación X?", opts, "b", "EX_B.pdf"),
    ]
    bank, conflicts = build_bank(raw)
    assert conflicts == 1, "debe detectarse el conflicto de respuesta"
    assert all(c.conflicto_respuesta for c in bank)
    assert len(bank) == 2, "una entrada canonica por cada respuesta en conflicto"
