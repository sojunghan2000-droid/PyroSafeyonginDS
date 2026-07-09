-- 점검(회차) 취소 (v1.8)
-- inspection_rounds에 취소 플래그/사유 컬럼 추가. Task 제외 패턴의 회차 레벨 확장.
-- 실행: Supabase 대시보드 → SQL Editor → 붙여넣기 → Run (1회).

alter table public.inspection_rounds
  add column if not exists cancelled     boolean     not null default false,
  add column if not exists cancel_reason text,
  add column if not exists cancelled_at  timestamptz,
  add column if not exists cancelled_by  text;
