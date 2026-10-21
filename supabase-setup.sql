-- Achievement Winter: Supabase setup
-- 1) Create your owner account first in Supabase Dashboard > Authentication > Users.
-- 2) Copy that user's UUID and replace OWNER_AUTH_USER_UUID below.
-- 3) Run this entire script in SQL Editor.
create table if not exists public.owner_data (
  id integer primary key check (id = 1),
  owner_id uuid not null references auth.users(id),
  data jsonb not null default '{"version":1,"games":{}}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.owner_data enable row level security;

drop policy if exists "Public can read owner data" on public.owner_data;
create policy "Public can read owner data"
  on public.owner_data for select
  to anon, authenticated
  using (true);

drop policy if exists "Only owner can update owner data" on public.owner_data;
create policy "Only owner can update owner data"
  on public.owner_data for update
  to authenticated
  using (auth.uid() = owner_id)
  with check (auth.uid() = owner_id);

-- No browser insert/delete policies are intentionally created.
insert into public.owner_data (id, owner_id, data)
values (
  1,
  'OWNER_AUTH_USER_UUID'::uuid,
  '{"version":1,"updated_at":null,"games":{}}'::jsonb
)
on conflict (id) do update set owner_id = excluded.owner_id;
