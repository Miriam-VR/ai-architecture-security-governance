-- V04: incident memory. Facts (observations) and inferences (hypotheses) live in SEPARATE tables.
create table if not exists incidents (
  id uuid primary key default gen_random_uuid(),
  incident_id text not null unique,
  plant_id text not null references plants(plant_id),
  equipment_id text not null references equipment(equipment_id),
  status text not null default 'open',
  symptoms text[] not null default '{}',
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists incidents_plant_idx on incidents(plant_id);
create index if not exists incidents_equipment_idx on incidents(equipment_id);

create table if not exists agent_runs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null unique,
  incident_id text not null references incidents(incident_id),
  trace_id text not null,
  status text not null,
  steps int not null default 0,
  node_timings jsonb not null default '{}',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  created_by text not null
);
create index if not exists runs_incident_idx on agent_runs(incident_id);

create table if not exists observations (
  id uuid primary key default gen_random_uuid(),
  incident_id text not null references incidents(incident_id),
  run_id text not null,
  equipment_id text not null,
  name text not null,
  value text not null,
  unit text not null default '',
  source text not null,
  created_at timestamptz not null default now(),
  created_by text not null
);
create index if not exists observations_incident_idx on observations(incident_id);

create table if not exists hypotheses (
  id uuid primary key default gen_random_uuid(),
  incident_id text not null references incidents(incident_id),
  run_id text not null,
  cause text not null,
  confidence numeric not null check (confidence between 0 and 1),
  evidence_ids text[] not null default '{}',
  rationale text not null default '',
  created_at timestamptz not null default now(),
  created_by text not null
);
create index if not exists hypotheses_incident_idx on hypotheses(incident_id);
