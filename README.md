# CAP Camión — App de estudio del CAP de mercancías

App para estudiar y aprobar el **CAP de mercancías** (carnet profesional de camión,
temario estatal en España). El diferencial es el **dato**: un banco de preguntas
construido a partir de exámenes oficiales reales, deduplicado y con la **frecuencia
de repetición** medida por pregunta.

## Estructura
- `data/corpus_cap_conductor/` — 56 exámenes CAP mercancías reales con respuestas
  (Andalucía 2023-2026, Extremadura 2024-2026). **Fuente del banco de preguntas.**
- `data/referencia/` — material de apoyo NO usado para el banco:
  - `competencia_profesional_gva/` — exámenes de *Competencia Profesional del
    transportista* (GVA 2015-2021). Otra titulación distinta; solo referencia.
  - `enlaces_cap_gva_valencia.txt` — enlaces oficiales GVA (carga manual futura).
- `pipeline/` — Fase 0: extracción PDF → banco de preguntas.

## Roadmap
Ver el proyecto en Linear (equipo **CAP**). Fase 0: PoC del banco de preguntas.

## Legal
Exámenes públicos oficiales, reproducidos para estudio sin ánimo de lucro.
