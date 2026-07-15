# 점검 유형 명칭 변경(rename) — 설계 문서

- 날짜: 2026-07-09
- 상태: 승인됨
- 대상 파일: `lib/data.py`, `pages_app/admin_center.py`, `supabase_schema.sql`, `PRD.md`
- 마이그레이션: Postgres 함수 `rename_inspection_type` (MCP로 적용)

## 배경 / 결정

관리자 [점검 유형] 탭에서 유형 이름을 바꿀 수 있어야 한다. 이름은 여러 테이블에
문자열로 저장되므로 rename 시 **연쇄 갱신**이 필요하다. 실제 DB 조사 결과 사이클
유형(일일/주간/월간/분기/연간) 이름이 저장되는 곳은 3곳 + 카탈로그뿐:

- `inspection_types.name` (카탈로그 PK)
- `inspection_rounds.task_type`
- `inspection_tasks.task_type`
- `equipment.inspection_types[]` (jsonb 배열)

`deficiencies`·`notices`(별지5·6)는 다른 어휘(임시소방시설/피난로 등/화기취급감독)라
**무관**. 과거 법정 기록은 보존된다.

**결정: 기본 5종 포함 전부 rename 허용** (사용자 승인). 유일한 코드 결합인
`INSPECTION_TYPE_CATEGORY_DEFAULTS`(새 장비 카테고리 자동추천)는
`default_inspection_types_for()`가 **현재 카탈로그에 있는 이름만 반환**하도록 보강해
깨끗하게 degrade(orphan 없음). 기본 유형 rename 시 그 유형은 자동추천에서만 빠짐(수동 선택 가능).

## 메커니즘 — 원자적 Postgres RPC

```sql
create or replace function public.rename_inspection_type(old_name text, new_name text)
returns void language plpgsql as $$
begin
  new_name := btrim(new_name);
  if new_name = '' then raise exception 'empty name'; end if;
  if not exists (select 1 from public.inspection_types where name = old_name) then
    raise exception 'type not found: %', old_name; end if;
  if exists (select 1 from public.inspection_types where name = new_name) then
    raise exception 'name exists: %', new_name; end if;
  update public.inspection_types  set name = new_name       where name = old_name;
  update public.inspection_rounds set task_type = new_name  where task_type = old_name;
  update public.inspection_tasks  set task_type = new_name  where task_type = old_name;
  update public.equipment set inspection_types = (
      select jsonb_agg(case when t = old_name then new_name else t end)
      from jsonb_array_elements_text(inspection_types) t)
    where inspection_types ? old_name;
end $$;
notify pgrst, 'reload schema';
```

한 트랜잭션에서 전 참조를 갱신 → 부분 실패로 인한 불일치 없음.

## 데이터 계층 (`lib/data.py`)

- `rename_inspection_type(old, new) -> tuple[bool, str]` — 공백/동일/존재/중복 검증 후
  `_db().rpc("rename_inspection_type", {...}).execute()`. 성공 시
  `_inspection_type_rows / _equipment_rows / _round_rows / _task_rows` 캐시 클리어.
- `default_inspection_types_for(category)` — 반환값을 현재 카탈로그(`load_inspection_types()`)로 필터.

## UI (`pages_app/admin_center.py` `_inspection_type_tab`)

- 목록 표에 **[이름 변경]** 컬럼 추가(전 행). 클릭 → 인라인 텍스트 입력(현재 이름 프리필)
  + [저장]/[취소]. 저장 시 `rename_inspection_type` 호출, 성공하면 rerun.
- text_input은 `key`만 사용(사전 session_state 프리필) — value= 경고 회피.

## 범위 밖

- 카테고리 자동추천 매핑을 DB화(현재는 코드 필터로 degrade)
- 이름 변경 이력 로그

## 안전장치

- 공백/중복/미존재 방지(데이터 함수 + RPC 양쪽).
- 원자적 트랜잭션. 캐시 클리어로 즉시 반영.
