create extension if not exists pgcrypto;

create table if not exists vehicles (
  id uuid primary key default gen_random_uuid(), vin text unique not null, serial_no text,
  model text, customer text, salesperson text, in_service_date date, source text,
  extra_fields jsonb not null default '{}'::jsonb, created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create index if not exists vehicles_serial_idx on vehicles(serial_no);
create index if not exists vehicles_customer_idx on vehicles(customer);

create table if not exists dtna_orders (
  id uuid primary key default gen_random_uuid(), serial_no text unique not null, vin text,
  sales_order text, lead_serial_no text, model text, customer text, salesperson text, status text,
  status_date text, projected_delivery text, original_projected_delivery text, destination_received text,
  chassis_start text, dispatch_date text, delivered_date text, build_location text,
  raw_data jsonb not null default '{}'::jsonb, updated_at timestamptz not null default now()
);
create index if not exists dtna_orders_vin_idx on dtna_orders(vin);

create table if not exists vehicle_changes (
  id bigint generated always as identity primary key, vin text, serial_no text, field_name text not null,
  old_value text, new_value text, source text default 'DTNA', changed_at timestamptz not null default now(), sync_run_id uuid
);
create index if not exists vehicle_changes_vin_idx on vehicle_changes(vin,changed_at desc);

create table if not exists sync_runs (
  id uuid primary key default gen_random_uuid(), source text not null, status text not null default 'running',
  order_count int default 0, vin_count int default 0, in_service_count int default 0, change_count int default 0,
  metadata jsonb not null default '{}'::jsonb, started_at timestamptz not null default now(), completed_at timestamptz
);

create table if not exists vehicle_identifiers (
  id bigint generated always as identity primary key, vin text not null, identifier_type text not null,
  identifier_value text not null, unique(identifier_type,identifier_value)
);
