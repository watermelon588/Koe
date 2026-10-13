-- Per-person settings (ACCOUNTS_SPEC.md): small named values such as the timesheet Koe created for you
-- (`google_sheets_id`). Additive and rerunnable; backend-only, RLS on, no PUBLIC privileges.
-- Run: python -m scripts.migrate_store (from backend/).
begin;

create table if not exists public.koe_prefs (
  owner_id text not null, name text not null, value text not null, updated text not null,
  primary key (owner_id, name)
);

alter table public.koe_prefs enable row level security;
revoke all on public.koe_prefs from public;

commit;
