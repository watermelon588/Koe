-- Connections (ACCOUNTS_SPEC.md, connections): one row per person per service. The token JSON is encrypted by the
-- backend (Fernet, KOE_SECRET_KEY) before it gets here, so a copy of this table alone can't be used.
-- Additive and rerunnable; backend-only, RLS on, no PUBLIC privileges. Run: python -m scripts.migrate_store
begin;

create table if not exists public.koe_connections (
  owner_id text not null, provider text not null check (provider in ('google','github','notion')),
  account text not null default '', scopes text not null default '', token_enc text not null,
  created text not null, updated text not null,
  primary key (owner_id, provider)
);

alter table public.koe_connections enable row level security;
revoke all on public.koe_connections from public;

commit;
