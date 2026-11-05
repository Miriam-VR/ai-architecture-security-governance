-- V02/V03: base master data. Convention: uuid internal PK + readable business code (UNIQUE).
create extension if not exists vector;
create extension if not exists pgcrypto;

create table if not exists plants (
  id uuid primary key default gen_random_uuid(),
  plant_id text not null unique,
  name text not null,
  created_at timestamptz not null default now(),
  created_by text not null default 'seed'
);

create table if not exists equipment (
  id uuid primary key default gen_random_uuid(),
  equipment_id text not null unique,
  plant_id text not null references plants(plant_id),
  type text not null,
  model text not null,
  criticality text not null,
  location text not null,
  next_maintenance date,
  created_at timestamptz not null default now(),
  created_by text not null default 'seed'
);
create index if not exists equipment_plant_idx on equipment(plant_id);

create table if not exists sensor_readings (
  id uuid primary key default gen_random_uuid(),
  reading_id text not null unique,
  equipment_id text not null references equipment(equipment_id),
  sensor text not null,
  value double precision not null,
  unit text not null,
  quality text not null default 'good',
  read_at timestamptz not null,
  created_at timestamptz not null default now(),
  created_by text not null default 'seed'
);
create index if not exists sensor_equipment_idx on sensor_readings(equipment_id, read_at desc);
