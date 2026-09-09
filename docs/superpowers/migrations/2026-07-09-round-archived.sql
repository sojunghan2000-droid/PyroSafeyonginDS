-- 취소 회차 숨김(아카이브) (v1.8)
-- 취소된 회차를 목록에서 숨김(기록 보존·복구 가능). 실행: Supabase SQL Editor → Run (1회).

alter table public.inspection_rounds
  add column if not exists archived boolean not null default false;
