-- Run in your Supabase project's SQL Editor. This migration is additive and rerunnable.
-- Backend-only tables: RLS + no anon/authenticated table or function privileges.
-- https://supabase.com/docs/guides/database/functions#function-privileges
begin;

create table if not exists public.koe_activity (
  id uuid primary key default gen_random_uuid(), owner_id text not null,
  ts timestamptz not null default now(), session_id uuid not null,
  channel text not null check (channel in ('web','cli','whatsapp','github')),
  kind text not null, summary text not null, payload_json jsonb not null default '{}',
  latency_json jsonb not null default '{}'
);
alter table public.koe_activity add column if not exists latency_json jsonb not null default '{}';
create index if not exists koe_activity_owner_ts on public.koe_activity(owner_id, ts desc);

create table if not exists public.koe_pending_actions (
  id uuid primary key default gen_random_uuid(), owner_id text not null,
  session_id uuid not null, channel text not null,
  created_ts timestamptz not null default now(), expires_ts timestamptz not null default now() + interval '10 minutes',
  tool text not null, args_json jsonb not null, summary text not null,
  status text not null default 'pending' check (status in ('pending','executing','rejected','expired','executed','failed')),
  result_json jsonb
);
create unique index if not exists koe_one_pending_per_session
  on public.koe_pending_actions(owner_id, session_id) where status = 'pending';

create table if not exists public.koe_daily_notes (
  owner_id text not null, date date not null, summary text not null,
  primary key(owner_id, date)
);
create table if not exists public.koe_github_deliveries (
  owner_id text not null, delivery_id text not null, ts timestamptz not null default now(),
  primary key(owner_id, delivery_id)
);

alter table public.koe_activity enable row level security;
alter table public.koe_pending_actions enable row level security;
alter table public.koe_daily_notes enable row level security;
alter table public.koe_github_deliveries enable row level security;
revoke all on public.koe_activity, public.koe_pending_actions, public.koe_daily_notes,
  public.koe_github_deliveries from public, anon, authenticated;
grant all on public.koe_activity, public.koe_pending_actions, public.koe_daily_notes,
  public.koe_github_deliveries to service_role;

create or replace function public.koe_record_activity(
  p_owner text, p_session uuid, p_channel text, p_kind text, p_summary text, p_payload jsonb
) returns uuid language sql security invoker set search_path = '' as $$
  insert into public.koe_activity(owner_id,session_id,channel,kind,summary,payload_json,latency_json)
  values(p_owner,p_session,p_channel,p_kind,p_summary,p_payload,coalesce(p_payload->'latency','{}'::jsonb)) returning id;
$$;

create or replace function public.koe_propose_action(
  p_owner text, p_session uuid, p_channel text, p_tool text, p_args jsonb, p_summary text
) returns jsonb language plpgsql security invoker set search_path = '' as $$
declare a public.koe_pending_actions;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_owner || p_session::text, 0));
  with expired as (
    update public.koe_pending_actions set status='expired'
    where owner_id=p_owner and session_id=p_session and status='pending' and expires_ts <= now()
    returning *
  ) insert into public.koe_activity(owner_id,session_id,channel,kind,summary,payload_json)
    select owner_id,session_id,channel,'approval','expired',jsonb_build_object('action_id',id) from expired;
  select * into a from public.koe_pending_actions
    where owner_id=p_owner and session_id=p_session and status='pending';
  if found then
    if a.tool=p_tool and a.args_json=p_args then return to_jsonb(a); end if;
    return jsonb_build_object('error',jsonb_build_object('code','pending_action_exists',
      'message','Resolve the existing proposal first.', 'hint',a.summary));
  end if;
  insert into public.koe_pending_actions(owner_id,session_id,channel,tool,args_json,summary)
    values(p_owner,p_session,p_channel,p_tool,p_args,p_summary) returning * into a;
  perform public.koe_record_activity(p_owner,p_session,p_channel,'approval','proposed',
    jsonb_build_object('action_id',a.id,'tool',p_tool,'args',p_args,'summary',p_summary));
  return to_jsonb(a);
end;
$$;

create or replace function public.koe_claim_action(p_owner text,p_session uuid,p_id uuid,p_approve boolean)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare a public.koe_pending_actions;
begin
  update public.koe_pending_actions set status=case
    when expires_ts <= now() then 'expired' when p_approve then 'executing' else 'rejected' end
    where id=p_id and owner_id=p_owner and session_id=p_session and status='pending'
    returning * into a;
  if not found then return null; end if;
  perform public.koe_record_activity(p_owner,p_session,a.channel,'approval',
    case when a.status='executing' then 'approved' else a.status end,jsonb_build_object('action_id',a.id));
  return to_jsonb(a);
end;
$$;

create or replace function public.koe_finish_action(p_owner text,p_session uuid,p_id uuid,p_ok boolean,p_result jsonb)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare a public.koe_pending_actions;
begin
  update public.koe_pending_actions set status=case when p_ok then 'executed' else 'failed' end,result_json=p_result
    where id=p_id and owner_id=p_owner and session_id=p_session and status='executing'
    returning * into a;
  if not found then raise exception 'Action not executing'; end if;
  perform public.koe_record_activity(p_owner,p_session,a.channel,'approval',a.status,
    jsonb_build_object('action_id',a.id,'result',p_result));
  return to_jsonb(a);
end;
$$;

revoke execute on function public.koe_record_activity(text,uuid,text,text,text,jsonb),
  public.koe_propose_action(text,uuid,text,text,jsonb,text),
  public.koe_claim_action(text,uuid,uuid,boolean), public.koe_finish_action(text,uuid,uuid,boolean,jsonb)
  from public, anon, authenticated;
grant execute on function public.koe_record_activity(text,uuid,text,text,text,jsonb),
  public.koe_propose_action(text,uuid,text,text,jsonb,text),
  public.koe_claim_action(text,uuid,uuid,boolean), public.koe_finish_action(text,uuid,uuid,boolean,jsonb)
  to service_role;
commit;
