-- Row Level Security. The BACKEND connects with a privileged DB role that BYPASSES RLS, so it must
-- also filter by plant on every operation (see app/security + app/store). RLS protects every other
-- path: Supabase Data API (PostgREST), dashboards, and any direct use of user JWTs.
create or replace function public.jwt_plants() returns text[] language sql stable as $$
  select coalesce(
    array(select jsonb_array_elements_text(
      coalesce(auth.jwt() -> 'app_metadata' -> 'plants', '[]'::jsonb))), '{}')
$$;

create or replace function public.jwt_is_admin() returns boolean language sql stable as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'app_role', '') = 'administrator'
$$;

do $$
declare t text;
begin
  foreach t in array array['plants','equipment','sensor_readings','failure_history','failure_history_chunks',
    'incidents','agent_runs','observations','hypotheses','policy_versions','action_requests','approvals','audit_events']
  loop execute format('alter table %I enable row level security', t); end loop;
end $$;

-- Tables with plant_id: read only own plants (or admin / global rows where plant_id is null)
do $$
declare t text;
begin
  foreach t in array array['equipment','failure_history','incidents','action_requests']
  loop
    execute format('drop policy if exists %I on %I', t||'_read_plant', t);
    execute format('create policy %I on %I for select to authenticated using (plant_id = any(public.jwt_plants()) or public.jwt_is_admin())', t||'_read_plant', t);
  end loop;
end $$;

drop policy if exists plants_read on plants;
create policy plants_read on plants for select to authenticated using (plant_id = any(public.jwt_plants()) or public.jwt_is_admin());

drop policy if exists chunks_read on failure_history_chunks;
create policy chunks_read on failure_history_chunks for select to authenticated
  using (plant_id is null or plant_id = any(public.jwt_plants()) or public.jwt_is_admin());

drop policy if exists sensors_read on sensor_readings;
create policy sensors_read on sensor_readings for select to authenticated using (
  exists (select 1 from equipment e where e.equipment_id = sensor_readings.equipment_id
          and (e.plant_id = any(public.jwt_plants()) or public.jwt_is_admin())));

-- Child tables: visible through the parent incident
do $$
declare t text;
begin
  foreach t in array array['agent_runs','observations','hypotheses']
  loop
    execute format('drop policy if exists %I on %I', t||'_read', t);
    execute format('create policy %I on %I for select to authenticated using (exists (select 1 from incidents i where i.incident_id = %I.incident_id and (i.plant_id = any(public.jwt_plants()) or public.jwt_is_admin())))', t||'_read', t, t);
  end loop;
end $$;

-- approvals / audit_events / policy_versions: no policy for 'authenticated' => denied via Data API.
-- Only the backend (privileged role) touches them. Writes by end users via Data API are never allowed.
