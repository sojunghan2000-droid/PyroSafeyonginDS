-- 장소 추가 기능 (2026-09-10) — 관리자가 앱에서 직접 등록하는 커스텀 장소.
-- 기존 8개 층(PIT/B2/B1/1F/2F/3F/4F/Roof) + TEMP는 코드 상수로 유지되며
-- 이 테이블에 들어가지 않는다. 여기엔 신규로 추가되는 장소만 저장된다.
create table if not exists public.floors (
  code         text primary key,
  display_name text not null,
  image_path   text not null,
  sort_order   int  not null,
  created_at   timestamptz not null default now()
);
alter table public.floors enable row level security;
