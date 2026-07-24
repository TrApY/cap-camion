#!/usr/bin/env python3
"""Clasifica el banco de preguntas del CAP en 11 temas con Gemini (reproducible).

- Lotes numerados + responseSchema (enum de slugs, array en orden) -> el modelo
  solo puede devolver slugs validos y el mapeo id<->slug es por posicion.
- Cache incremental en db/out/clasificacion_cache.json: re-ejecutar solo llama a
  Gemini para las preguntas aun sin cachear (idempotente / resumible).
- Al terminar escribe `tema` en banco_preguntas.json, db/temas.json y el informe.

Requiere GEMINI_API_KEY en el entorno. Uso: python db/clasificar_temas.py [--batch N]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import random
import time
import urllib.error
import urllib.request
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parent.parent
BANCO = REPO / "pipeline" / "out" / "banco_preguntas.json"
OUT_DIR = REPO / "db" / "out"
TEMAS_JSON = REPO / "db" / "temas.json"
CACHE_FILE = OUT_DIR / "clasificacion_cache.json"
REPORT_FILE = OUT_DIR / "clasificacion_temas_report.md"
MODEL = "gemini-2.5-flash"
ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
)

# slug -> (etiqueta, seccion, orden)
TEMAS = [
    ("motor-transmision", "El vehículo: motor y transmisión", "Conducción racional y seguridad"),
    ("frenado-seguridad", "Frenado y dispositivos de seguridad", "Conducción racional y seguridad"),
    ("conduccion-eficiente", "Conducción eficiente y consumo", "Conducción racional y seguridad"),
    ("carga-estiba", "Carga, estiba y masas", "Conducción racional y seguridad"),
    ("tiempos-tacografo", "Tiempos de conducción y tacógrafo", "Reglamentación"),
    ("reglamentacion-documentos", "Documentos y reglamentación del transporte", "Reglamentación"),
    ("seguridad-vial-accidentes", "Seguridad vial, accidentes y primeros auxilios", "Salud, seguridad y servicio"),
    ("salud-ergonomia", "Salud, ergonomía y aptitud", "Salud, seguridad y servicio"),
    ("prevencion-riesgos", "Prevención de riesgos (robos, tráfico ilegal)", "Salud, seguridad y servicio"),
    ("calidad-servicio", "Calidad del servicio e imagen de empresa", "Salud, seguridad y servicio"),
    ("entorno-economico", "Entorno económico y organización", "Salud, seguridad y servicio"),
]
SLUGS = [t[0] for t in TEMAS]
SLUG_SET = set(SLUGS)

GUIA = (
    "motor-transmision: cadena cinemática, motor, cilindros, par/potencia, cuentarrevoluciones, caja de cambios, embrague, relación de marchas.\n"
    "frenado-seguridad: frenos, ABS, ralentizador, freno motor, ESP, sistemas de ayuda (TSR, SLI), neumáticos, dirección, energía cinética/frenada.\n"
    "conduccion-eficiente: ahorro de carburante, conducción racional/económica, inercia, resistencias al avance, anticipación.\n"
    "carga-estiba: distribución y sujeción de la carga, estiba, masas y dimensiones, MMA, ejes, centro de gravedad, sobrecarga.\n"
    "tiempos-tacografo: tiempos de conducción/descanso/pausas, tacógrafo digital/analógico, discos/hojas de registro.\n"
    "reglamentacion-documentos: contrato de transporte, carta de porte/CMR, ATP, documentación, autorizaciones, mercancías peligrosas (ADR), tipos de transporte.\n"
    "seguridad-vial-accidentes: prevención de accidentes, comportamiento en accidente, primeros auxilios, señalización, distancias de seguridad.\n"
    "salud-ergonomia: ergonomía, posturas, riesgos físicos, alimentación, fatiga, alcohol/drogas/medicamentos, aptitud física y mental.\n"
    "prevencion-riesgos: prevención de criminalidad, robos de mercancía, tráfico ilegal de personas/inmigrantes clandestinos, seguridad del vehículo/carga.\n"
    "calidad-servicio: atención al cliente, calidad del servicio, imagen de empresa, comportamiento profesional.\n"
    "entorno-economico: organización del mercado del transporte, entorno económico, tipos de empresa (sociedades), competencia, logística, costes, intermediarios."
)


def load(path, default):
    if path.exists():
        return json.load(open(path, encoding="utf-8"))
    return default


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    tmp.replace(path)


def gemini(prompt, key, n_expected, intentos=6):
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {"type": "ARRAY", "items": {"type": "STRING", "enum": SLUGS}},
            "temperature": 0,
        },
    }
    data = json.dumps(payload).encode()
    for intento in range(intentos):
        try:
            req = urllib.request.Request(
                ENDPOINT + "?key=" + key, data=data,
                headers={"Content-Type": "application/json"},
            )
            r = json.load(urllib.request.urlopen(req, timeout=90))
            out = json.loads(r["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(out, list) and len(out) == n_expected and all(s in SLUG_SET for s in out):
                return out
            print(f"    respuesta inválida (len {len(out) if isinstance(out,list) else '?'} vs {n_expected}), reintento")
        except urllib.error.HTTPError as e:
            espera = min(60, 5 * (2 ** intento))
            print(f"    HTTP {e.code}, espera {espera}s")
            time.sleep(espera)
            continue
        except Exception as e:  # noqa: BLE001
            print(f"    error {str(e)[:80]}, reintento")
        time.sleep(3)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=120)
    ap.add_argument("--pausa", type=float, default=1.0)
    args = ap.parse_args()

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    assert key, "falta GEMINI_API_KEY"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    data = load(BANCO, None)
    cache = {k: v for k, v in load(CACHE_FILE, {}).items() if v in SLUG_SET}
    print(f"Banco: {len(data)} preguntas. Caché previa válida: {len(cache)}.")

    pend = [q for q in data if q["id"] not in cache]
    print(f"Pendientes: {len(pend)} (lotes de {args.batch}).", flush=True)

    for i in range(0, len(pend), args.batch):
        lote = pend[i : i + args.batch]
        n = i // args.batch + 1
        listado = "\n".join(f"{j+1}. {q['enunciado']}" for j, q in enumerate(lote))
        prompt = (
            "Eres un clasificador del temario del CAP de mercancías (España). "
            f"Clasifica cada pregunta en UNO de estos {len(SLUGS)} temas. Guía:\n{GUIA}\n\n"
            f"Devuelve un array JSON de EXACTAMENTE {len(lote)} slugs, en el MISMO orden "
            f"que las preguntas.\n\nPreguntas:\n{listado}"
        )
        res = gemini(prompt, key, len(lote))
        if res is None:
            print(f"  lote {n}: FALLÓ tras reintentos, se deja para otra pasada.", flush=True)
            continue
        for q, slug in zip(lote, res):
            cache[q["id"]] = slug
        save(CACHE_FILE, cache)
        print(f"  lote {n}: {len(lote)} ok. Total cacheado: {len(cache)}/{len(data)}", flush=True)
        time.sleep(args.pausa)

    sin = [q["id"] for q in data if q["id"] not in cache]
    if sin:
        print(f"AVISO: {len(sin)} sin clasificar tras esta pasada (re-ejecuta para completarlas).", flush=True)
        return

    # Escribir tema en el banco (in place, conservando orden y demás campos)
    for q in data:
        q["tema"] = cache[q["id"]]
    save(BANCO, data)
    save(TEMAS_JSON, [
        {"slug": s, "label": lbl, "seccion": sec, "orden": i + 1}
        for i, (s, lbl, sec) in enumerate(TEMAS)
    ])

    conteo = Counter(cache[q["id"]] for q in data)
    lineas = ["# Clasificación por temas — informe\n",
              f"Total: {len(data)} preguntas.\n", "| Tema | Nº |", "| --- | ---: |"]
    for s, lbl, _ in TEMAS:
        lineas.append(f"| {lbl} (`{s}`) | {conteo.get(s, 0)} |")
    REPORT_FILE.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    print("\n=== DISTRIBUCIÓN ===")
    for s, lbl, _ in TEMAS:
        print(f"  {conteo.get(s,0):>4}  {lbl}")
    print("\n=== MUESTRA (30 aleatorias) ===")
    rng = random.Random(42)
    for q in rng.sample(data, min(30, len(data))):
        print(f"  [{q['tema']:26s}] {q['enunciado'][:64]}")
    print("\nOK: banco + temas.json + informe escritos.", flush=True)


if __name__ == "__main__":
    main()
