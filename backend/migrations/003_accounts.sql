-- Accounts (ACCOUNTS_SPEC.md, identity): Google sign-in, invite list, sessions. Additive and rerunnable; same rules
-- as 001/002: backend-only tables, RLS on, no PUBLIC privileges. Times are ISO-8601 UTC text, as in koe/db.py.
-- Run: python -m scripts.migrate_store (from backend/).
begin;

create table if not exists public.koe_users (
  id text primary key,                      -- the owner's id is KOE_OWNER_ID, so existing rows stay theirs
  google_sub text unique not null,          -- Google's stable account id (the ID token's `sub`)
  email text not null, name text not null default '', created text not null
);

create table if not exists public.koe_invites (
  email text primary key, invited_by text not null, created text not null
);

-- Only the SHA-256 of a session token is stored: a database leak can't be replayed as a login.
create table if not exists public.koe_sessions (
  token_hash text primary key, user_id text not null references public.koe_users(id) on delete cascade,
  created text not null, expires text not null, revoked text
);
create index if not exists koe_sessions_user on public.koe_sessions(user_id);

alter table public.koe_users enable row level security;
alter table public.koe_invites enable row level security;
alter table public.koe_sessions enable row level security;
revoke all on public.koe_users, public.koe_invites, public.koe_sessions from public;

commit;
