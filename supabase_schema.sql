create table if not exists opc_demand_history (
  record_id text primary key,
  scan_id text,
  idea_id text,
  signal_key text,
  category text,
  scanned_at text,
  payload jsonb
);

create table if not exists opc_demand_labels (
  idea_id text primary key,
  label text,
  note text,
  updated_at text
);
