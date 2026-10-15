-- Spotify manual HTTP integration. Replays preserve every provider and journal entry.
begin;
alter table public.koe_connections drop constraint if exists koe_connections_provider_check;
alter table public.koe_connections add constraint koe_connections_provider_check
  check (provider in ('google','github','notion','gemini','spotify'));

create table if not exists public.koe_spotify_flows (
  state_hash text primary key, owner_id text not null, session_hash text not null,
  cookie_hash text not null, redirect_uri text not null, expires text not null, consumed text
);
create index if not exists koe_spotify_flows_expiry on public.koe_spotify_flows (expires);
create table if not exists public.koe_music_mutations (
  owner_id text not null, connection_id text not null, request_id text not null,
  body_hash text not null, operation text not null,
  state text not null check (state in ('prepared','sent','outcome_unknown','confirmed')),
  evidence_enc text not null, result_enc text, created text not null, updated text not null,
  primary key (owner_id, connection_id, request_id)
);
alter table public.koe_spotify_flows enable row level security;
alter table public.koe_music_mutations enable row level security;
revoke all on public.koe_spotify_flows from public;
revoke all on public.koe_music_mutations from public;
commit;
