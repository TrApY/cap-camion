# db/ — Esquema y siembra de la base de datos CAP

Base de datos: **Supabase** (proyecto `qcotnigcbvgmspdvhasm`, schema `public`).

## Contenido

| Ruta | Qué es |
|------|--------|
| `migrations/0001_cap_schema_inicial.sql` | Esquema inicial (extensión `vector` + tablas `preguntas`, `opciones`, `intentos`, `respuestas_usuario`, índices y RLS). Reconstruido con fidelidad del esquema aplicado. |
| `seed_supabase.py` | Genera el SQL de carga del banco de preguntas a partir de `pipeline/out/banco_preguntas.json`. Escapado de SQL correcto y salida por lotes. |
| `seed_out/` | Ficheros SQL por lotes generados por el script (regenerables; no editar a mano). |
| `clasificar_temas.py` | Clasifica el banco en los 11 temas de `temas.json` con Gemini (caché en `out/`). |
| `ministerio_descarga.py` | Descarga el banco oficial del Ministerio y lo parsea a `out/ministerio_preguntas.json`. |
| `ministerio_match.py` | Cruza nuestro banco con el del Ministerio para asignar NORMA → `out/ministerio_match.json`. |
| `normativa_textos.py` | Recupera de BOE/EUR-Lex el texto de los artículos citados por esas normas → `out/normativa_cache.json`. |
| `generar_explicaciones.py` | Genera con Gemini la explicación de cada pregunta y los 11 resúmenes de teoría → `out/explicaciones.json`, `out/resumenes_temas.json`. |
| `tests/` | Tests sin red del parseo y del matching del banco ministerial, de la recuperación de textos normativos y de la generación de explicaciones. |

## Banco oficial del Ministerio (norma por pregunta)

`ministerio_descarga.py` baja de la landing CAP de transportes.gob.es los ZIP
`CAPMercancias.zip` y `CAPComunes.zip` (viajeros queda fuera: nuestro banco es
de mercancías) y los parsea. Dentro hay un `.txt` en cp1252 por objetivo con
bloques `COD/enunciado/A-B-C-D/RESPUESTA/NORMA`.

**Cortesía obligatoria con el sitio** (es un servicio público): user-agent de
navegador, espera aleatoria de 12-20 s entre peticiones, backoff de 120 s y un
único reintento ante 403, y parada si el WAF insiste. Todo lo descargado se
guarda tal cual en `data/ministerio/` con `manifest.json` (url, fecha, sha256,
bytes): **si una URL ya está en el manifest no se vuelve a pedir**, así que
re-ejecutar el script no genera tráfico nuevo.

```bash
# Los scripts necesitan rapidfuzz/pypdf: usar el intérprete del pipeline.
pipeline/.venv/bin/python db/ministerio_descarga.py               # descarga + parseo
pipeline/.venv/bin/python db/ministerio_descarga.py --solo-parsear  # sin red
pipeline/.venv/bin/python db/ministerio_match.py                  # cruce con nuestro banco
pipeline/.venv/bin/python -m pytest db/tests/ -q
```

Artefactos en `out/`: `ministerio_preguntas.json` (banco oficial parseado),
`ministerio_match.json` (id nuestro → origen/num/norma/score/método),
`ministerio_report.md` y `ministerio_match_report.md`.

## Textos normativos para el RAG (`normativa_textos.py`)

Del campo `norma` de `out/ministerio_match.json` (709 referencias) se agrupan las
**normas base** y, para las que tienen **>= 4 referencias**, se recupera el texto
real de los artículos/anexos citados. Ese texto es el ancla anti-alucinación de
las explicaciones; la cita que ve el usuario sigue siendo la del Ministerio tal
cual. Una norma que no se resuelva limpiamente se marca `no-resuelta` y no pasa
nada: sólo se pierde contexto.

Dos fuentes, ambas verificadas contra su documentación oficial:

- **BOE, API de legislación consolidada** (`www.boe.es/datosabiertos`) para las
  normas españolas con número oficial: búsqueda por `numero_oficial` y descarga
  del XML de `/id/{id}/texto`. **Nunca se acepta un identificador sin verificar**:
  se exige ámbito estatal, el rango esperado y que el título empiece por
  `<rango> <numero/año>`; si sobreviven cero o más de un candidato → `no-resuelta`.
- **EUR-Lex** para los reglamentos comunitarios, con CELEX determinista
  `3{AAAA}R{NNNN}`, verificando el número y el año en el título del acto.

Convenios (CMR, TIR, CIDE, ATP, Schengen), directivas, acuerdos y normas
identificadas sólo por fecha quedan **fuera de alcance v1** y no gastan ni una
petición.

Cortesía: espera aleatoria de 3-6 s entre peticiones, backoff de 60 s y un único
reintento ante 403/429. El raw se guarda en `data/normativa/` con `manifest.json`
(url, fecha, sha256, bytes), así que **re-ejecutar cuesta 0 peticiones**.

```bash
pipeline/.venv/bin/python db/normativa_textos.py                 # descarga + extracción
pipeline/.venv/bin/python db/normativa_textos.py --solo-extraer  # sin red
```

Artefactos en `out/`: `normativa_cache.json` (por norma base: estado, fuente, id,
url, título, nº de referencias y el texto limpio de cada artículo/anexo citado,
recortado a 20 KB) y `normativa_report.md` (estado norma a norma y cuántas de las
709 referencias acaban con texto disponible).

## Explicaciones y resúmenes (`generar_explicaciones.py`)

Una explicación breve por pregunta y 11 resúmenes de teoría, generados con
`gemini-2.5-flash`. Tres principios mandan sobre todo lo demás:

- **La cita normativa que ve el usuario es la del Ministerio, tal cual.** Sale
  del campo `norma` de `out/ministerio_match.json` y se copia literalmente al
  campo `norma` de la salida: el modelo nunca la redacta ni la reformula.
- **El modelo no puede citar normativa que no esté en su contexto.** Si no se le
  da norma, cero citas legales; si se le da una, no puede mencionar otra.
- **Ninguna explicación puede referirse a las opciones por su letra**, porque la
  app las baraja al presentarlas: sólo vale hablar del CONTENIDO.

Los tres se validan **automáticamente** después de generar (`validar()`): una
explicación que los incumpla se rechaza y se regenera hasta dos veces con la
regla violada reforzada en el prompt; si persiste, la pregunta se queda sin
explicación y se cuenta en el informe. La longitud fuera de 120–900 caracteres
sólo se lista como outlier, no rechaza.

El contexto de cada pregunta se monta con lo que haya, y el campo
`origen_contexto` de la salida dice con qué se generó: `norma+texto` (norma
oficial + el artículo real recuperado del BOE/EUR-Lex, recortado a 8.000
caracteres) > `norma` > `match` (sólo la respuesta oficial) > `solo-banco`.

Los resúmenes por tema se anclan en dos fuentes: el epígrafe correspondiente del
**Anexo I del RD 284/2021** (`BOE-A-2021-6624`, descargado con el mecanismo de
`normativa_textos.py`, con verificación de título; el mapa de los 11 slugs a sus
objetivos 1.x/2.x/3.x es la constante `TEMA_A_OBJETIVOS`) y las 20 preguntas más
frecuentes del tema con su respuesta correcta.

`--qa` hace un segundo pase con Gemini de crítico independiente sobre una
muestra determinista y estratificada de 60 explicaciones; si más del 5 % sale
`mala`, se reporta como bloqueo y no se regenera en bucle.

```bash
export GEMINI_API_KEY=...
pipeline/.venv/bin/python db/generar_explicaciones.py                      # todo
pipeline/.venv/bin/python db/generar_explicaciones.py --explicaciones      # sólo etapa 1
pipeline/.venv/bin/python db/generar_explicaciones.py --resumenes --qa
pipeline/.venv/bin/python db/generar_explicaciones.py --informe            # sin red
```

Todo es **reanudable**: `out/explicaciones_cache.json`, `out/resumenes_temas.json`
y `out/qa_explicaciones_cache.json` se escriben cada pocas llamadas, así que
re-ejecutar no repite nada de lo ya hecho. Antes de la pasada completa el script
proyecta el coste con las 10 primeras llamadas y **para si supera 15 $**.

Artefactos en `out/`: `explicaciones.json` (por pregunta: explicación, norma
oficial, si hubo texto legal y el origen del contexto), `resumenes_temas.json`,
`explicaciones_uso.json` (tokens y coste acumulados) y `explicaciones_report.md`.

## Modelo de datos (resumen)

- `preguntas(id text PK, enunciado, respuesta_correcta char(1) null, respuesta_correcta_texto null, frecuencia int, comunidades text[], fuentes text[], conflicto_respuesta bool, tema text null, created_at)`
- `opciones(id bigint identity PK, pregunta_id text FK→preguntas ON DELETE CASCADE, letra char(1), texto null, es_correcta bool, UNIQUE(pregunta_id, letra))`
  - Se inserta **una fila por letra a/b/c/d con `texto` NO nulo**; `es_correcta = (letra == respuesta_correcta)`.
- `intentos`, `respuestas_usuario`: datos por usuario (RLS `auth.uid() = user_id`).

RLS: lectura pública (`anon` + `authenticated`) en `preguntas` y `opciones`; acceso restringido al propio usuario en `intentos` y `respuestas_usuario`.

## Re-sembrar el banco de preguntas

La siembra es **idempotente**: siempre empieza por
`truncate table public.opciones, public.preguntas restart identity cascade;`,
así que puede repetirse sin duplicar. Sólo afecta a `preguntas` y `opciones`
(no toca `intentos` ni `respuestas_usuario`).

### 1. Generar el SQL por lotes

```bash
python3 db/seed_supabase.py
# -> db/seed_out/00_truncate.sql
#    db/seed_out/10_preguntas_XXX.sql   (400 preguntas por lote)
#    db/seed_out/20_opciones_XXX.sql    (1500 filas por lote)
```

Opciones útiles:

```bash
python3 db/seed_supabase.py --stdout                       # todo el SQL a stdout
python3 db/seed_supabase.py --preguntas-batch 200 --opciones-batch 1000
python3 db/seed_supabase.py --input otro_banco.json
```

### 2. Aplicar el SQL

Aplicar **en orden**: primero `00_truncate.sql`, luego los `10_preguntas_*`
(por la FK, antes que las opciones) y por último los `20_opciones_*`.

- **Con `psql` / cadena de conexión de Supabase:**

  ```bash
  for f in db/seed_out/00_truncate.sql db/seed_out/10_preguntas_*.sql db/seed_out/20_opciones_*.sql; do
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f"
  done
  ```

- **Con la consola SQL de Supabase o el MCP `execute_sql`:** pegar/ejecutar el
  contenido de cada fichero en el mismo orden.

> Nota histórica: en la carga inicial no había `psql` ni driver de Postgres
> local ni credenciales de conexión directa. Se cargó server-side usando la
> extensión `http` de Postgres para descargar el JSON y parsearlo con funciones
> `jsonb_*` (verificado byte a byte con hashes MD5 de contenido). La extensión
> `http` se instaló sólo como mecanismo de carga y **se desinstaló al terminar**;
> no forma parte del esquema. Los `seed_out/*.sql` son la vía de carga estándar
> y reproducible a partir de ahora.

### 3. Verificar

```sql
select count(*) from public.preguntas;   -- 2636
select count(*) from public.opciones;    -- 10543
select count(*) from public.preguntas where respuesta_correcta is not null;  -- 2568
-- Cada pregunta con respuesta debe tener exactamente una opción correcta:
select count(*) from (
  select p.id from public.preguntas p
  join public.opciones o on o.pregunta_id = p.id
  where p.respuesta_correcta is not null
  group by p.id having count(*) filter (where o.es_correcta) <> 1
) t;  -- 0
```
