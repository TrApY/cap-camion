"""Generacion del informe de frecuencias en Markdown."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from .dedup import CanonicalQuestion


def build_report(
    canonical: list[CanonicalQuestion],
    *,
    n_pdfs_total: int,
    n_pdfs_con_preguntas: int,
    pdfs_sin_preguntas: list[str],
    pdfs_fallidos: list[str],
    total_raw: int,
    descartadas: int,
    conflict_clusters: int,
) -> str:
    """Devuelve el informe de frecuencias como texto Markdown."""
    n_unique = len(canonical)
    con_resp = sum(1 for c in canonical if c.respuesta_correcta_texto)
    cobertura = (100.0 * con_resp / n_unique) if n_unique else 0.0

    freq_dist = Counter(c.frecuencia for c in canonical)
    top = sorted(canonical, key=lambda c: (-c.frecuencia, c.enunciado))[:50]

    # Estadisticas de conflicto derivadas de los datos reales (no de un contador
    # externo), para que el resumen cuadre con el detalle listado mas abajo.
    conflicts = [c for c in canonical if c.conflicto_respuesta]
    n_conflict_entries = len(conflicts)
    n_conflict_enunciados = len({c.enunciado for c in conflicts})

    lines: list[str] = []
    lines.append("# Informe de frecuencias — Banco de preguntas CAP (Fase 0)")
    lines.append("")
    lines.append(f"_Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    lines.append("")

    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- PDF en el corpus: **{n_pdfs_total}**")
    lines.append(f"- PDF con preguntas extraidas: **{n_pdfs_con_preguntas}**")
    lines.append(
        f"- PDF sin preguntas (hojas de respuesta OMR en blanco): "
        f"**{len(pdfs_sin_preguntas)}**"
    )
    lines.append(f"- PDF con error de lectura: **{len(pdfs_fallidos)}**")
    lines.append(f"- Preguntas crudas extraidas (todas las apariciones): **{total_raw}**")
    lines.append(f"- Bloques descartados por parseo incompleto: **{descartadas}**")
    lines.append(f"- Preguntas unicas (canonicas): **{n_unique}**")
    lines.append(
        f"- Cobertura de respuesta correcta: **{cobertura:.1f}%** "
        f"({con_resp}/{n_unique} canonicas con respuesta)"
    )
    lines.append(
        f"- Clusters con conflicto de respuesta: **{conflict_clusters}** "
        f"(→ {n_conflict_enunciados} enunciados distintos, "
        f"{n_conflict_entries} entradas canonicas flageadas)"
    )
    lines.append("")

    lines.append("## Distribucion de frecuencias")
    lines.append("")
    lines.append("Numero de exámenes distintos en los que aparece cada pregunta canonica.")
    lines.append("")
    lines.append("| Frecuencia | Nº de preguntas |")
    lines.append("| ---: | ---: |")
    for freq in sorted(freq_dist, reverse=True):
        lines.append(f"| {freq} | {freq_dist[freq]} |")
    lines.append("")

    if pdfs_sin_preguntas:
        lines.append("## PDF sin preguntas (OMR / hoja de respuestas)")
        lines.append("")
        for name in sorted(pdfs_sin_preguntas):
            lines.append(f"- {name}")
        lines.append("")

    if pdfs_fallidos:
        lines.append("## PDF con error de lectura")
        lines.append("")
        for name in sorted(pdfs_fallidos):
            lines.append(f"- {name}")
        lines.append("")

    if conflicts:
        lines.append("## Clusters con conflicto de respuesta")
        lines.append("")
        lines.append(
            f"{n_conflict_enunciados} enunciados distintos ({n_conflict_entries} "
            "entradas canonicas) con respuestas correctas distintas entre "
            "exámenes. No se elige ninguna automaticamente: requieren revision "
            "humana."
        )
        lines.append("")
        seen: set[str] = set()
        for c in conflicts:
            key = c.enunciado
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- **{c.enunciado}**")
            for ans in c.respuestas_en_conflicto:
                lines.append(f"  - respuesta candidata: {ans}")
        lines.append("")

    lines.append("## TOP-50 preguntas mas repetidas")
    lines.append("")
    lines.append("| # | Frec. | Resp. | Enunciado |")
    lines.append("| ---: | ---: | :---: | :--- |")
    for i, c in enumerate(top, start=1):
        letra = c.respuesta_correcta or "—"
        enun = c.enunciado.replace("|", "\\|")
        if len(enun) > 140:
            enun = enun[:137] + "..."
        lines.append(f"| {i} | {c.frecuencia} | {letra} | {enun} |")
    lines.append("")

    return "\n".join(lines)
