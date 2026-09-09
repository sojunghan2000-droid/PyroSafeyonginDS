-- 점검 유형 관리 (v1.8)
-- 관리자가 점검 유형(주기)을 추가/비활성/삭제할 수 있도록 카탈로그를 테이블화.
-- 실행: Supabase 대시보드 → SQL Editor → 붙여넣기 → Run (1회).
-- 기존 테이블과 동일하게 RLS 활성화 + 정책 없음(앱은 service_role로 서버측 접근).

create table if not exists public.inspection_types (
  name       text primary key,          -- 유형 이름. 장비·회차가 이름으로 참조
  is_active  boolean not null default true,
  is_builtin boolean not null default false,
  sort_order int not null default 100,
  created_at timestamptz not null default now()
);

insert into public.inspection_types (name, is_builtin, sort_order) values
  ('일일 점검', true, 1),
  ('주간 점검', true, 2),
  ('월간 점검', true, 3),
  ('분기 점검', true, 4),
  ('연간 점검', true, 5)
on conflict (name) do nothing;

alter table public.inspection_types enable row level security;
