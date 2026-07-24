-- 0001_cap_schema_inicial.sql
-- Esquema inicial del proyecto CAP-Camión (Supabase, schema public).
--
-- Reconstruido con fidelidad a partir del esquema realmente aplicado en el
-- proyecto Supabase qcotnigcbvgmspdvhasm (columnas, tipos, defaults, NOT NULL,
-- claves, índices, FKs y políticas RLS verificados contra el catálogo pg_*).
--
-- Contiene: extensión vector + tablas preguntas / opciones / intentos /
-- respuestas_usuario, con RLS (lectura pública en preguntas y opciones,
-- políticas por usuario en intentos y respuestas_usuario).

-- Extensiones -----------------------------------------------------------------
-- pgvector en el schema `extensions` (recomendación de seguridad de Supabase:
-- no instalar extensiones en `public`). Uso previsto: similitud de preguntas (Fase 2).
create extension if not exists vector with schema extensions;

-- Tabla: preguntas ------------------------------------------------------------
create table if not exists public.preguntas (
    id                        text        primary key,
    enunciado                 text        not null,
    respuesta_correcta        char(1),
    respuesta_correcta_texto  text,
    frecuencia                integer     not null default 1,
    comunidades               text[]      not null default '{}',
    fuentes                   text[]      not null default '{}',
    conflicto_respuesta       boolean     not null default false,
    tema                      text,
    created_at                timestamptz not null default now()
);

create index if not exists preguntas_frecuencia_idx
    on public.preguntas (frecuencia desc);

-- Tabla: opciones -------------------------------------------------------------
create table if not exists public.opciones (
    id           bigint  generated always as identity primary key,
    pregunta_id  text    not null references public.preguntas (id) on delete cascade,
    letra        char(1) not null,
    texto        text,
    es_correcta  boolean not null default false,
    unique (pregunta_id, letra)
);

create index if not exists opciones_pregunta_idx
    on public.opciones (pregunta_id);

-- Tabla: intentos -------------------------------------------------------------
create table if not exists public.intentos (
    id          bigint      generated always as identity primary key,
    user_id     uuid        not null references auth.users (id) on delete cascade,
    modo        text        not null,
    started_at  timestamptz not null default now(),
    finished_at timestamptz,
    nota        numeric
);

create index if not exists intentos_user_idx
    on public.intentos (user_id);

-- Tabla: respuestas_usuario ---------------------------------------------------
create table if not exists public.respuestas_usuario (
    id            bigint      generated always as identity primary key,
    intento_id    bigint      references public.intentos (id) on delete cascade,
    user_id       uuid        not null references auth.users (id) on delete cascade,
    pregunta_id   text        not null references public.preguntas (id),
    letra_elegida char(1),
    correcta      boolean,
    answered_at   timestamptz not null default now()
);

create index if not exists respuestas_user_pregunta_idx
    on public.respuestas_usuario (user_id, pregunta_id);

-- Row Level Security ----------------------------------------------------------
alter table public.preguntas          enable row level security;
alter table public.opciones           enable row level security;
alter table public.intentos           enable row level security;
alter table public.respuestas_usuario enable row level security;

-- Contenido del banco: lectura pública (anon + authenticated).
create policy preguntas_public_read on public.preguntas
    for select to anon, authenticated
    using (true);

create policy opciones_public_read on public.opciones
    for select to anon, authenticated
    using (true);

-- Datos del usuario: cada usuario sólo ve/gestiona lo suyo.
create policy intentos_own on public.intentos
    for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

create policy respuestas_own on public.respuestas_usuario
    for all to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);
