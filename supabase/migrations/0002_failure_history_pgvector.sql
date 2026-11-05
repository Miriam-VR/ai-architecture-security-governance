-- V02: failure history + RAG chunks (pgvector). dim 1536 = text-embedding-3-small (mock embedder uses the same dim).
create table if not exists failure_history (
  id uuid primary key default gen_random_uuid(),
  failure_id text not null unique,
  plant_id text not null references plants(plant_id),
  equipment_id text not null references equipment(equipment_id),
  equipment_type text not null,
  occurred_on date not null,
  symptoms text[] not null,
  root_cause text not null,
  confirmed_cause text not null,
  actions_taken text[] not null default '{}',
  downtime_hours numeric,
  repair_cost_usd numeric,
  refs text[] not null default '{}',
  created_at timestamptz not null default now(),
  created_by text not null default 'seed'
);
create index if not exists failure_plant_idx on failure_history(plant_id);
create index if not exists failure_equipment_idx on failure_history(equipment_id);

-- Also holds manual/procedure fragments (source_type). plant_id NULL = global, non-sensitive document.
create table if not exists failure_history_chunks (
  id uuid primary key default gen_random_uuid(),
  chunk_id text not null unique,
  source_id text not null,
  source_type text not null check (source_type in ('failure','manual','procedure')),
  plant_id text references plants(plant_id),
  equipment_id text references equipment(equipment_id),
  equipment_type text not null default 'all',
  root_cause text,
  symptoms text[] not null default '{}',
  text text not null,
  embedding vector(1536) not null,
  created_at timestamptz not null default now(),
  created_by text not null default 'ingest'
);
create index if not exists chunks_plant_idx on failure_history_chunks(plant_id);
create index if not exists chunks_equipment_idx on failure_history_chunks(equipment_id);
create index if not exists chunks_embedding_idx on failure_history_chunks
  using hnsw (embedding vector_cosine_ops);
