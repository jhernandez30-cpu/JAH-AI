create extension if not exists pgcrypto;

-- ============================================================
-- JAH AI Supabase schema
-- Auth: Supabase Auth (auth.users)
-- Database: PostgreSQL with Row Level Security
-- ============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- =========================
-- Profiles
-- =========================
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  role text not null default 'user',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_role_check check (role in ('user', 'admin'))
);

alter table public.profiles enable row level security;

drop policy if exists "Users can read own profile" on public.profiles;
create policy "Users can read own profile" on public.profiles
for select to authenticated using (auth.uid() = id);

drop policy if exists "Users can insert own profile" on public.profiles;
create policy "Users can insert own profile" on public.profiles
for insert to authenticated with check (auth.uid() = id);

drop policy if exists "Users can update own profile" on public.profiles;
create policy "Users can update own profile" on public.profiles
for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'display_name', new.raw_user_meta_data->>'name'),
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_user();

-- =========================
-- Spaces
-- =========================
create table if not exists public.spaces (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.spaces enable row level security;

drop policy if exists "Users can read own spaces" on public.spaces;
create policy "Users can read own spaces" on public.spaces
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own spaces" on public.spaces;
create policy "Users can insert own spaces" on public.spaces
for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "Users can update own spaces" on public.spaces;
create policy "Users can update own spaces" on public.spaces
for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "Users can delete own spaces" on public.spaces;
create policy "Users can delete own spaces" on public.spaces
for delete to authenticated using (auth.uid() = user_id);

drop trigger if exists trg_spaces_updated_at on public.spaces;
create trigger trg_spaces_updated_at
before update on public.spaces
for each row execute function public.set_updated_at();

-- =========================
-- Projects
-- =========================
create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  space_id uuid references public.spaces(id) on delete set null,
  name text not null,
  description text,
  status text not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint projects_status_check check (status in ('active', 'archived', 'paused'))
);

alter table public.projects enable row level security;

drop policy if exists "Users can read own projects" on public.projects;
create policy "Users can read own projects" on public.projects
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own projects" on public.projects;
create policy "Users can insert own projects" on public.projects
for insert to authenticated
with check (
  auth.uid() = user_id
  and (
    space_id is null
    or exists (
      select 1 from public.spaces s
      where s.id = space_id and s.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can update own projects" on public.projects;
create policy "Users can update own projects" on public.projects
for update to authenticated
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and (
    space_id is null
    or exists (
      select 1 from public.spaces s
      where s.id = space_id and s.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can delete own projects" on public.projects;
create policy "Users can delete own projects" on public.projects
for delete to authenticated using (auth.uid() = user_id);

drop trigger if exists trg_projects_updated_at on public.projects;
create trigger trg_projects_updated_at
before update on public.projects
for each row execute function public.set_updated_at();

-- =========================
-- Chats
-- =========================
create table if not exists public.chats (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  space_id uuid references public.spaces(id) on delete set null,
  title text not null default 'Nuevo chat',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.chats enable row level security;

drop policy if exists "Users can read own chats" on public.chats;
create policy "Users can read own chats" on public.chats
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own chats" on public.chats;
create policy "Users can insert own chats" on public.chats
for insert to authenticated
with check (
  auth.uid() = user_id
  and (
    project_id is null
    or exists (
      select 1 from public.projects p
      where p.id = project_id and p.user_id = auth.uid()
    )
  )
  and (
    space_id is null
    or exists (
      select 1 from public.spaces s
      where s.id = space_id and s.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can update own chats" on public.chats;
create policy "Users can update own chats" on public.chats
for update to authenticated
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and (
    project_id is null
    or exists (
      select 1 from public.projects p
      where p.id = project_id and p.user_id = auth.uid()
    )
  )
  and (
    space_id is null
    or exists (
      select 1 from public.spaces s
      where s.id = space_id and s.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can delete own chats" on public.chats;
create policy "Users can delete own chats" on public.chats
for delete to authenticated using (auth.uid() = user_id);

drop trigger if exists trg_chats_updated_at on public.chats;
create trigger trg_chats_updated_at
before update on public.chats
for each row execute function public.set_updated_at();

-- =========================
-- Messages
-- =========================
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references public.chats(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('user', 'assistant', 'system', 'tool')),
  content text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

alter table public.messages enable row level security;

drop policy if exists "Users can read own messages" on public.messages;
create policy "Users can read own messages" on public.messages
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own messages" on public.messages;
create policy "Users can insert own messages" on public.messages
for insert to authenticated
with check (
  auth.uid() = user_id
  and exists (
    select 1 from public.chats c
    where c.id = chat_id and c.user_id = auth.uid()
  )
);

drop policy if exists "Users can update own messages" on public.messages;
create policy "Users can update own messages" on public.messages
for update to authenticated
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and exists (
    select 1 from public.chats c
    where c.id = chat_id and c.user_id = auth.uid()
  )
);

drop policy if exists "Users can delete own messages" on public.messages;
create policy "Users can delete own messages" on public.messages
for delete to authenticated using (auth.uid() = user_id);

-- =========================
-- Uploaded files metadata
-- =========================
create table if not exists public.uploaded_files (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  chat_id uuid references public.chats(id) on delete set null,
  original_name text not null,
  stored_name text not null,
  storage_bucket text,
  storage_path text,
  mime_type text,
  size_bytes bigint,
  file_kind text default 'file',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uploaded_files_size_check check (size_bytes is null or size_bytes >= 0)
);

alter table public.uploaded_files enable row level security;

drop policy if exists "Users can read own uploaded files" on public.uploaded_files;
create policy "Users can read own uploaded files" on public.uploaded_files
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own uploaded files" on public.uploaded_files;
create policy "Users can insert own uploaded files" on public.uploaded_files
for insert to authenticated
with check (
  auth.uid() = user_id
  and (
    project_id is null
    or exists (
      select 1 from public.projects p
      where p.id = project_id and p.user_id = auth.uid()
    )
  )
  and (
    chat_id is null
    or exists (
      select 1 from public.chats c
      where c.id = chat_id and c.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can update own uploaded files" on public.uploaded_files;
create policy "Users can update own uploaded files" on public.uploaded_files
for update to authenticated
using (auth.uid() = user_id)
with check (
  auth.uid() = user_id
  and (
    project_id is null
    or exists (
      select 1 from public.projects p
      where p.id = project_id and p.user_id = auth.uid()
    )
  )
  and (
    chat_id is null
    or exists (
      select 1 from public.chats c
      where c.id = chat_id and c.user_id = auth.uid()
    )
  )
);

drop policy if exists "Users can delete own uploaded files" on public.uploaded_files;
create policy "Users can delete own uploaded files" on public.uploaded_files
for delete to authenticated using (auth.uid() = user_id);

drop trigger if exists trg_uploaded_files_updated_at on public.uploaded_files;
create trigger trg_uploaded_files_updated_at
before update on public.uploaded_files
for each row execute function public.set_updated_at();

-- =========================
-- User settings
-- =========================
create table if not exists public.user_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  settings jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.user_settings enable row level security;

drop policy if exists "Users can read own settings" on public.user_settings;
create policy "Users can read own settings" on public.user_settings
for select to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert own settings" on public.user_settings;
create policy "Users can insert own settings" on public.user_settings
for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists "Users can update own settings" on public.user_settings;
create policy "Users can update own settings" on public.user_settings
for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop trigger if exists trg_user_settings_updated_at on public.user_settings;
create trigger trg_user_settings_updated_at
before update on public.user_settings
for each row execute function public.set_updated_at();

-- =========================
-- Helpful indexes
-- =========================
create index if not exists idx_profiles_email on public.profiles(email);
create index if not exists idx_spaces_user_id on public.spaces(user_id);
create index if not exists idx_projects_user_id on public.projects(user_id);
create index if not exists idx_projects_space_id on public.projects(space_id);
create index if not exists idx_chats_user_id on public.chats(user_id);
create index if not exists idx_chats_project_id on public.chats(project_id);
create index if not exists idx_chats_space_id on public.chats(space_id);
create index if not exists idx_messages_chat_id on public.messages(chat_id);
create index if not exists idx_messages_user_id on public.messages(user_id);
create index if not exists idx_messages_created_at on public.messages(created_at);
create index if not exists idx_uploaded_files_user_id on public.uploaded_files(user_id);
create index if not exists idx_uploaded_files_project_id on public.uploaded_files(project_id);
create index if not exists idx_uploaded_files_chat_id on public.uploaded_files(chat_id);
create index if not exists idx_uploaded_files_created_at on public.uploaded_files(created_at);
