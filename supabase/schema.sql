-- مراسلاتي — مخطط Supabase
-- التشغيل: Supabase Dashboard ← SQL Editor ← New query ← الصق هذا الملف ← Run
-- جدول واحد عام يحفظ: المراسلات (letter)، القوالب (tpl)، قوالب التنسيق (fmt)، الإعدادات (prefs).
-- كل مستخدم يرى ويعدّل صفوفه فقط (Row Level Security).

create table if not exists public.awq_store (
  user_id    uuid        not null default auth.uid() references auth.users(id) on delete cascade,
  kind       text        not null check (kind in ('letter', 'tpl', 'fmt', 'prefs')),
  id         text        not null,
  data       jsonb       not null default '{}'::jsonb,
  deleted    boolean     not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, kind, id)
);

create index if not exists awq_store_user_kind_idx on public.awq_store (user_id, kind);

alter table public.awq_store enable row level security;

drop policy if exists "awq_select_own" on public.awq_store;
drop policy if exists "awq_insert_own" on public.awq_store;
drop policy if exists "awq_update_own" on public.awq_store;
drop policy if exists "awq_delete_own" on public.awq_store;

create policy "awq_select_own" on public.awq_store for select to authenticated using (user_id = auth.uid());
create policy "awq_insert_own" on public.awq_store for insert to authenticated with check (user_id = auth.uid());
create policy "awq_update_own" on public.awq_store for update to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "awq_delete_own" on public.awq_store for delete to authenticated using (user_id = auth.uid());

-- بعد إنشاء حسابك: Authentication ← Sign In / Providers ← Email ← عطّل «Allow new users to sign up»
-- حتى لا يقدر أحد غيرك ينشئ حساباً على مشروعك.
