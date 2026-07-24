#!/usr/bin/env python3
"""Orquestador del pipeline Fase 0 de CAP Camión.

Lee todos los PDF del corpus (Andalucia + Extremadura), extrae las preguntas,
construye el banco deduplicado y escribe los tres artefactos en ``out/``:

    preguntas_raw.json     todas las apariciones extraidas
    banco_preguntas.json   preguntas canonicas deduplicadas con frecuencia
    informe_frecuencias.md  informe legible para humano

Uso:
    python run.py [--corpus DIR] [--out DIR] [--threshold 90]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cap_pipeline.dedup import build_bank
from cap_pipeline.extract import process_pdf
from cap_pipeline.report import build_report

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = REPO_ROOT / "data" / "corpus_cap_conductor"
DEFAULT_OUT = Path(__file__).resolve().parent / "out"

COMUNIDADES = ("andalucia", "extremadura")


def collect_pdfs(corpus_dir: Path) -> list[tuple[Path, str]]:
    """Devuelve [(path, comunidad)] de todos los PDF del corpus, ordenados."""
    items: list[tuple[Path, str]] = []
    for comunidad in COMUNIDADES:
        folder = corpus_dir / comunidad
        if not folder.is_dir():
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            items.append((pdf, comunidad))
    return items


def run(corpus_dir: Path, out_dir: Path, threshold: float) -> dict:
    pdfs = collect_pdfs(corpus_dir)
    if not pdfs:
        raise SystemExit(f"No se encontraron PDF en {corpus_dir}")

    raw_questions: list[dict] = []
    descartadas_total = 0
    pdfs_con_preguntas: list[str] = []
    pdfs_sin_preguntas: list[str] = []
    pdfs_fallidos: list[str] = []

    for path, comunidad in pdfs:
        result, descartadas = process_pdf(path, comunidad)
        descartadas_total += descartadas
        if result.error is not None:
            pdfs_fallidos.append(result.fuente)
            print(f"  [ERROR] {result.fuente}: {result.error}", file=sys.stderr)
            continue
        if not result.questions:
            pdfs_sin_preguntas.append(result.fuente)
            continue
        pdfs_con_preguntas.append(result.fuente)
        raw_questions.extend(q.to_dict() for q in result.questions)

    print(
        f"Procesados {len(pdfs)} PDF | con preguntas: {len(pdfs_con_preguntas)} "
        f"| sin preguntas: {len(pdfs_sin_preguntas)} | error: {len(pdfs_fallidos)}"
    )
    print(f"Preguntas crudas extraidas: {len(raw_questions)}")

    canonical, conflict_clusters = build_bank(
        raw_questions, enun_threshold=threshold, answer_threshold=threshold
    )
    print(f"Preguntas canonicas: {len(canonical)} | conflictos: {conflict_clusters}")

    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "preguntas_raw.json"
    with raw_path.open("w", encoding="utf-8") as fh:
        json.dump(raw_questions, fh, ensure_ascii=False, indent=2)

    bank_path = out_dir / "banco_preguntas.json"
    with bank_path.open("w", encoding="utf-8") as fh:
        json.dump([c.to_dict() for c in canonical], fh, ensure_ascii=False, indent=2)

    report_md = build_report(
        canonical,
        n_pdfs_total=len(pdfs),
        n_pdfs_con_preguntas=len(pdfs_con_preguntas),
        pdfs_sin_preguntas=pdfs_sin_preguntas,
        pdfs_fallidos=pdfs_fallidos,
        total_raw=len(raw_questions),
        descartadas=descartadas_total,
        conflict_clusters=conflict_clusters,
    )
    report_path = out_dir / "informe_frecuencias.md"
    report_path.write_text(report_md, encoding="utf-8")

    con_resp = sum(1 for c in canonical if c.respuesta_correcta_texto)
    cobertura = (100.0 * con_resp / len(canonical)) if canonical else 0.0

    return {
        "pdfs_total": len(pdfs),
        "pdfs_con_preguntas": len(pdfs_con_preguntas),
        "pdfs_sin_preguntas": pdfs_sin_preguntas,
        "pdfs_fallidos": pdfs_fallidos,
        "preguntas_raw": len(raw_questions),
        "descartadas": descartadas_total,
        "canonicas": len(canonical),
        "cobertura_respuesta_pct": round(cobertura, 1),
        "conflictos": conflict_clusters,
        "artefactos": [str(raw_path), str(bank_path), str(report_path)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Fase 0 CAP Camión")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--threshold", type=float, default=90.0)
    args = parser.parse_args()

    summary = run(args.corpus, args.out, args.threshold)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
