-- A.I.D.A. V7 Supabase setup
--
-- Run in Supabase -> SQL Editor.
-- Do NOT expose the service-role key in browser JavaScript.

create table if not exists public.aida_live_sessions (
    session_id text primary key,
    status text not null default 'queued',
    created_at timestamptz not null default now(),
    accepted_at timestamptz,
    ended_at timestamptz,
    end_reason text not null default '',
    contact_name text not null default '',
    contact_email text not null default '',
    issue text not null default '',
    language text not null default 'en',
    summary text not null default '',
    messages jsonb not null default '[]'::jsonb,
    updated_at timestamptz not null default now()
);

create table if not exists public.aida_managed_files (
    path text primary key,
    category text not null default 'content',
    content_type text not null default 'application/octet-stream',
    size_bytes bigint not null default 0,
    updated_at timestamptz not null default now()
);

alter table public.aida_live_sessions enable row level security;
alter table public.aida_managed_files enable row level security;

-- No public browser policies are deliberately created.
-- Flask uses the private service-role key server-side.

create index if not exists
aida_live_sessions_status_idx
on public.aida_live_sessions(status);

create index if not exists
aida_live_sessions_ended_at_idx
on public.aida_live_sessions(ended_at desc);
