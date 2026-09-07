-- 260907 현장요구사항: 점검유형 카탈로그 5종 → 3종 통합
-- 비가역 — 실행 전 inspection_types / inspection_rounds / inspection_tasks 백업 권장.
-- rename_inspection_type(old, new)는 카탈로그·회차·Task·장비 참조를 한 트랜잭션으로 갱신한다.
select rename_inspection_type('주간 점검', '일일 점검');
select rename_inspection_type('분기 점검', '특별 점검');
select rename_inspection_type('연간 점검', '특별 점검');
