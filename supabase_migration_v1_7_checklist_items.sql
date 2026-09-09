-- PyroSafe v1.7 마이그레이션 — 세부 checklist 항목 (checklist_items jsonb)
-- 실행: Supabase 대시보드 → SQL Editor → 이 파일 붙여넣기 → Run
-- 영향: deficiencies 테이블에 컬럼 1개 추가. 기존 데이터는 빈 dict로 초기화.
--
-- 구조: { "카테고리|세부항목": "OK|NG|NA", ... }
-- 예:   { "방화포·소화기 비치|방화포 즉시 사용 가능 상태 비치": "OK",
--         "방화포·소화기 비치|소화기 인근 충분 비치": "NG",
--         "일일점검체크리스트 작성": "NA" }

alter table public.deficiencies
    add column if not exists checklist_items jsonb not null default '{}'::jsonb;

-- 검증
select column_name, data_type, column_default
from information_schema.columns
where table_schema = 'public'
  and table_name = 'deficiencies'
  and column_name = 'checklist_items';
