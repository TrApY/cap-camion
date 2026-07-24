"""Pipeline Fase 0 de CAP Camión.

Convierte los examenes CAP oficiales (PDF) en un banco de preguntas
deduplicado con frecuencia de repeticion. Todo el procesamiento es OFFLINE.
"""

__all__ = ["extract", "normalize", "dedup", "report"]
