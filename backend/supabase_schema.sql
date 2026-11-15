-- MistakeCoach 云端库表（Supabase SQL Editor 一次性执行；脚本可重复运行）
-- 结构：profiles（业务用户资料，注册触发器自动建档）+ cards（错题卡，复合主键支持 PostgREST upsert）
-- 安全：全部启用 RLS——即使后端漏鉴权，数据库层也只允许用户访问自己的行（auth.uid()）

-- ============ profiles：业务用户资料 ============
create table if not exists public.profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  nickname   text not null default '',
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;
drop policy if exists "profiles: owner read" on public.profiles;
drop policy if exists "profiles: owner update" on public.profiles;
create policy "profiles: owner read" on public.profiles
  for select using (auth.uid() = id);
create policy "profiles: owner update" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- 注册瞬间自动创建对应 profile 行（security definer 以表所有者身份写入 auth 事件）
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, nickname)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'nickname', ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============ cards：错题卡 ============
-- 复合主键 (user_id, card_id)：card_id 是前端错题卡自己的 id（mc_cards 里的 c.id），
-- 后端同步接口靠它做 PostgREST merge-duplicates（幂等 upsert，重复同步不产生重复行）
create table if not exists public.cards (
  user_id    uuid not null references auth.users(id) on delete cascade,
  card_id    text not null,
  card       jsonb not null,               -- 整张错题卡（FR-7 Schema 原样）
  subject    text not null default '',     -- 冗余索引字段：学科（云端筛选/统计预留）
  category   text not null default '',     -- 冗余索引字段：错因类型
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, card_id)
);

create index if not exists cards_user_updated_idx
  on public.cards (user_id, updated_at desc);

alter table public.cards enable row level security;
drop policy if exists "cards: owner all" on public.cards;
create policy "cards: owner all" on public.cards
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- 每次更新自动刷新 updated_at（为将来按时间排序/冲突检测预留）
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists cards_touch on public.cards;
create trigger cards_touch
  before update on public.cards
  for each row execute function public.touch_updated_at();
