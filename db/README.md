# db/ — Esquema y siembra de la base de datos CAP

Base de datos: **Supabase** (proyecto `qcotnigcbvgmspdvhasm`, schema `public`).

## Contenido

| Ruta | Qué es |
|------|--------|
| `migrations/0001_cap_schema_inicial.sql` | Esquema inicial (extensión `vector` + tablas `preguntas`, `opciones`, `intentos`, `respuestas_usuario`, índices y RLS). Reconstruido con fidelidad del esquema aplicado. |
| `seed_supabase.py` | Genera el SQL de carga del banco de preguntas a partir de `pipeline/out/banco_preguntas.json`. Escapado de SQL correcto y salida por lotes. |
| `seed_out/` | Ficheros SQL por lotes generados por el script (regenerables; no editar a mano). |

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
