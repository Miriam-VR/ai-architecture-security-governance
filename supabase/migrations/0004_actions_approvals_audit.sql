-- V09/V11/V13: governed actions, approvals, append-only audit, versioned policies.
create table if not exists policy_versions (
  id uuid primary key default gen_random_uuid(),
  version text not null unique,
  rules jsonb not null,
  rules_hash text not null,
  active boolean not null default false,
  created_at timestamptz not null default now(),
  created_by text not null
);

create table if not exists action_requests (
  id uuid primary key default gen_random_uuid(),
  action_id text not null unique,
  incident_id text not null references incidents(incident_id),
  plant_id text not null,
  run_id text,
  action_type text not null,
  params jsonb not null default '{}',
  risk text not null,
  status text not null,   -- pending_approval | approved | queued | executing | executed | rejected | denied
  idempotency_key text not null unique,
  policy_version text not null,
  result jsonb,
  created_at timestamptz not null default now(),
  created_by text not null,
  updated_at timestamptz not null default now(),
  executed_at timestamptz
);
create index if not exists actions_incident_idx on action_requests(incident_id);

create table if not exists approvals (
  id uuid primary key default gen_random_uuid(),
  approval_id text not null unique,
  action_id text not null references action_requests(action_id),
  status text not null,   -- pending | approved | rejected | consumed | expired
  action_hash text not null,
  expires_at timestamptz not null,
  decided_by text,
  decided_at timestamptz,
  created_at timestamptz not null default now(),
  created_by text not null
);
create index if not exists approvals_action_idx on approvals(action_id);

create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  event_id text not null unique,
  ts timestamptz not null default now(),
  event_type text not null,
  incident_id text,
  run_id text,
  trace_id text,
  actor text not null,
  decision text,
  details jsonb not null default '{}'
);
create index if not exists audit_incident_idx on audit_events(incident_id, ts);

-- Append-only: block UPDATE/DELETE even for privileged roles (superusers may still disable triggers).
create or replace function audit_events_immutable() returns trigger language plpgsql as $$
begin raise exception 'audit_events is append-only'; end $$;
drop trigger if exists audit_events_no_update on audit_events;
create trigger audit_events_no_update before update or delete on audit_events
  for each row execute function audit_events_immutable();
