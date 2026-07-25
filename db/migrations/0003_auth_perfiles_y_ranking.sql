-- 0003_auth_perfiles_y_ranking.sql
-- CAP-12: cuentas (anónimas + email opcional), nick público y base del ranking.
--
-- Aditiva e idempotente. No toca datos existentes. Las tablas `intentos` y
-- `respuestas_usuario` (con RLS por usuario) existen desde 0001; aquí se añade
-- el detalle de sesión que el cliente sincroniza y la identidad pública (nick).

-- Tabla: perfiles -------------------------------------------------------------
create table if not exists public.perfiles (
    user_id    uuid        primary key references auth.users (id) on delete cascade,
    nick       text        not null,
    created_at timestamptz not null default now(),
    constraint perfiles_nick_formato check (nick ~ '^[A-Za-z0-9_-]{3,20}$')
);

-- Unicidad case-insensitive: "JoTa" y "jota" son el mismo nick.
create unique index if not exists perfiles_nick_unico
    on public.perfiles (lower(nick));

alter table public.perfiles enable row level security;

-- El nick es identidad pública (aparece en el ranking): lectura para todos.
drop policy if exists perfiles_public_read on public.perfiles;
create policy perfiles_public_read on public.perfiles
    for select to anon, authenticated
    using (true);

-- Cada usuario crea y edita solo su propio perfil.
drop policy if exists perfiles_own_insert on public.perfiles;
create policy perfiles_own_insert on public.perfiles
    for insert to authenticated
    with check (auth.uid() = user_id);

drop policy if exists perfiles_own_update on public.perfiles;
create policy perfiles_own_update on public.perfiles
    for update to authenticated
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

-- Intentos: detalle de la sesión sincronizada --------------------------------
-- Nullable a propósito: las filas que pudieran existir de antes no lo tienen.
alter table public.intentos add column if not exists tipo      text;
alter table public.intentos add column if not exists tema      text;
alter table public.intentos add column if not exists total     integer;
alter table public.intentos add column if not exists aciertos  integer;
alter table public.intentos add column if not exists fallos    integer;
alter table public.intentos add column if not exists en_blanco integer;
alter table public.intentos add column if not exists tiempo_ms bigint;

create index if not exists intentos_finished_idx
    on public.intentos (finished_at desc);

-- Ranking de usuarios activos -------------------------------------------------
-- RLS impide leer intentos ajenos, así que el ranking se sirve con una función
-- SECURITY DEFINER que expone SOLO agregados (nick, nº de sesiones, nota media)
-- de usuarios con nick. Ordena por nota media reciente y no por volumen, para
-- premiar ir bien y no hacer más tests (decisión JoTa 2026-07-25).
create or replace function public.ranking_activos(
    dias         integer default 14,
    min_sesiones integer default 3
)
returns table (nick text, sesiones bigint, nota_media numeric)
language sql
security definer
set search_path = public
stable
as $$
    select p.nick,
           count(*)              as sesiones,
           round(avg(i.nota), 1) as nota_media
    from public.intentos i
    join public.perfiles p on p.user_id = i.user_id
    where i.finished_at is not null
      and i.finished_at >= now() - make_interval(days => dias)
      and i.nota is not null
    group by p.nick
    having count(*) >= greatest(min_sesiones, 1)
    order by nota_media desc, sesiones desc
    limit 100;
$$;

revoke all on function public.ranking_activos(integer, integer) from public;
grant execute on function public.ranking_activos(integer, integer) to anon, authenticated;
