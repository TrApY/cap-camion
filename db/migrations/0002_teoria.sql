-- 0002_teoria.sql
-- Teoría del CAP: explicaciones por pregunta y resúmenes por tema.
--
-- Qué añade:
--   * preguntas.explicacion -> por qué la respuesta correcta lo es (texto
--     didáctico redactado a partir del banco oficial y de la normativa citada).
--   * preguntas.norma       -> referencia normativa TAL CUAL la publica el
--     Ministerio en su banco oficial (nunca se reescribe ni se interpreta).
--   * public.temas_teoria   -> resumen de teoría (markdown) por cada uno de los
--     11 temas del catálogo (ver db/temas.json / web/src/lib/temas.ts).
--
-- Origen y licencia de los datos: banco oficial de preguntas del Ministerio de
-- Transportes y Movilidad Sostenible y Anexo I del RD 284/2021 (contenidos
-- mínimos del CAP) publicado en el BOE. Ambos son información del sector
-- público reutilizable con la obligación de citar la fuente y la fecha de la
-- última actualización, sin desnaturalizar su sentido; la app cumple esa
-- atribución en el pie de la portada y junto a cada explicación.

-- Columnas nuevas en preguntas -------------------------------------------------
alter table public.preguntas add column if not exists explicacion text;
alter table public.preguntas add column if not exists norma text;

comment on column public.preguntas.explicacion is
    'Explicación didáctica de la respuesta correcta. Se resiembra entera desde db/seed_teoria.py.';
comment on column public.preguntas.norma is
    'Referencia normativa oficial del Ministerio, literal (no se transforma).';

-- Tabla: temas_teoria ---------------------------------------------------------
create table if not exists public.temas_teoria (
    slug        text        primary key,
    titulo      text        not null,
    resumen_md  text        not null,
    updated_at  timestamptz not null default now()
);

comment on table public.temas_teoria is
    'Resumen de teoría por tema (markdown sencillo) derivado del banco oficial del Ministerio y del Anexo I del RD 284/2021.';

-- Row Level Security ----------------------------------------------------------
alter table public.temas_teoria enable row level security;

-- Contenido de estudio: lectura pública (anon + authenticated), igual que el
-- resto del banco.
create policy temas_teoria_public_read on public.temas_teoria
    for select to anon, authenticated
    using (true);
