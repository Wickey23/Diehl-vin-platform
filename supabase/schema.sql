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

create table if not exists lookup_batches (
  id uuid primary key default gen_random_uuid(), lookup_mode text not null default 'in_service_customer', status text not null default 'queued',
  total_vins int not null default 0, options jsonb not null default '{}'::jsonb, worker_id text,
  created_at timestamptz not null default now(), started_at timestamptz, completed_at timestamptz
);
create index if not exists lookup_batches_status_idx on lookup_batches(status,created_at);

create table if not exists lookup_batch_items (
  id uuid primary key default gen_random_uuid(), batch_id uuid not null references lookup_batches(id) on delete cascade,
  vin text not null, queue_position int not null default 0, status text not null default 'queued', attempts int not null default 0,
  result jsonb not null default '{}'::jsonb, error_message text, started_at timestamptz, completed_at timestamptz,
  unique(batch_id,vin)
);
create index if not exists lookup_items_queue_idx on lookup_batch_items(batch_id,status,queue_position);

create table if not exists worker_status (
  worker_id text primary key, hostname text, dtna_status text, outlook_status text, onedrive_status text,
  master_workbook text, details jsonb not null default '{}'::jsonb, last_seen timestamptz not null default now()
);
