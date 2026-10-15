-- Gemini quota (ACCOUNTS_SPEC.md, quota): turns per person per day on the shared key, and a person's own Gemini
-- key as an encrypted connection (provider 'gemini'). Additive and rerunnable; backend-only, RLS on.
-- Run: python -m scripts.migrate_store (from backend/).
begin;

create table if not exists public.koe_usage (
  owner_id text not null, day text not null, turns integer not null default 0,
  primary key (owner_id, day)
);
alter table public.koe_usage enable row level security;
revoke all on public.koe_usage from public;

-- Widen the provider list; the transaction keeps every existing row.
alter table public.koe_connections drop constraint if exists koe_connections_provider_check;
alter table public.koe_connections add constraint koe_connections_provider_check
  check (provider in ('google','github','notion','gemini','spotify'));

commit;
