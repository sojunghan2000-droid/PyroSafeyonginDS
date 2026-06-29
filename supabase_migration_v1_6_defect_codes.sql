-- PyroSafe v1.6 마이그레이션 — 불량 사유 카탈로그 (defect_codes/defect_other)
-- 실행: Supabase 대시보드 → SQL Editor → 이 파일 붙여넣기 → Run
-- 영향: deficiencies 테이블에 컬럼 2개 추가. 기존 데이터는 빈 배열/빈 문자열로 초기화.

alter table public.deficiencies
    add column if not exists defect_codes text[] not null default '{}',
    add column if not exists defect_other text not null default '';

-- 검증
select column_name, data_type, column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'deficiencies'
  and column_name in ('defect_codes', 'defect_other');
