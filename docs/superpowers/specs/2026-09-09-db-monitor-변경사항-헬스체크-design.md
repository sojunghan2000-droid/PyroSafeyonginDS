# DB 모니터 — 변경사항(감사로그) 탭 + 헬스체크 버튼 · 설계

- 날짜: 2026-09-09
- 대상: `db_monitor.py` (별도 Streamlit 앱, 신규 Supabase 프로젝트 `ivpzfrvboazpbcejpqwc`를 읽기전용으로 조회)
- 상태: 설계 확정 (브레인스토밍 완료)

## 배경 / 문제

`db_monitor.py`는 이미 개요/추이/브라우저/운영 4개 탭으로 테이블 현황·행수·최근 생성·raw 조회를 제공한다. 그러나:

1. **변경 이력이 없다** — 모든 PyroSafe 테이블에 `created_at`은 있지만 `updated_at`이나 변경 이력 컬럼이 전혀 없고 트리거도 없다. UPDATE/DELETE는 DB 레벨에서 완전히 비가시적이다.
2. **시스템 상태를 한눈에 확인할 수단이 없다** — DB/Storage/Auth 연결이 살아있는지, 감사로그 트리거가 죽지 않았는지 등을 확인하려면 탭을 일일이 열어봐야 한다.

## 목표

- DB에 감사로그(audit_log) 인프라를 추가해 PyroSafe 8개 테이블의 INSERT/UPDATE/DELETE를 기록하고, 모니터에 **"변경사항" 탭**으로 열람한다.
- 모니터에 **헬스체크 버튼**을 추가해 DB/테이블/Storage/Auth/감사로그 상태를 한 번에 점검한다.

## 결정 사항 (브레인스토밍)

1. **행위자(누가 변경했는지) 추적은 보류** — PyroSafe 본앱(쓰기 코드)이 로그인 사용자를 DB 세션에 세팅하지 않으므로, 트리거는 "누가"를 알 수 없다. 대신 new_data(없으면 old_data)에서 `inspector`/`submitter`/`confirmer`/`assignee`/`excluded_by`/`cancelled_by` 중 존재하는 첫 값을 "입력자(추정)"로 표시한다. 일반 UPDATE(예: 지적사항 본문만 수정)는 이 값이 비거나 부정확할 수 있음을 UI에 명시한다. 본앱을 건드려 정확한 행위자를 세팅하는 것은 별도 후속 과제로 미룬다.
2. **범용 audit_log 테이블 + 공용 트리거 함수 1개** — 테이블마다 audit 쌍둥이 테이블을 만드는 방식은 보일러플레이트가 크고 테이블을 가로지르는 통합 활동 피드를 만들기 어려워 기각. 대신 `audit_log` 단일 테이블에 `old_data`/`new_data`를 JSONB로 담고, PyroSafe 8개 테이블(equipment, inspection_tasks, inspection_rounds, deficiencies, notices, malfunctions, floor_spots, inspection_types) 전체에 동일한 트리거 함수를 연결한다(테이블마다 PK 컬럼명만 인자로 다름).
3. **UI 우선순위** — deficiencies/malfunctions/inspection_tasks/inspection_rounds를 기본 필터로 우선 노출하되, 체크박스로 8개 전체를 토글할 수 있게 한다.
4. **마이그레이션은 사용자가 직접 실행** — 운영 DB(FIRE-PASS와 공유)에 스키마 변경이 들어가므로, 마이그레이션 SQL 파일만 준비하고 Supabase 대시보드에서 실행할지는 사용자가 판단한다.
5. **헬스체크는 기존 커넥션 재사용** — 새 커넥션을 만들지 않고 `get_conn()` 캐시 커넥션으로 순차 점검한다.

## 설계

### 1) 마이그레이션 — `docs/superpowers/migrations/2026-09-09-audit-log.sql`

```sql
create table if not exists public.audit_log (
  id           bigserial primary key,
  table_name   text not null,
  op           text not null,        -- INSERT | UPDATE | DELETE
  row_pk       text not null,
  old_data     jsonb,
  new_data     jsonb,
  changed_at   timestamptz not null default now()
);
create index if not exists audit_log_table_changed_idx
  on public.audit_log (table_name, changed_at desc);

create or replace function public.fn_audit_log() returns trigger as $$
begin
  insert into public.audit_log(table_name, op, row_pk, old_data, new_data)
  values (
    TG_TABLE_NAME, TG_OP,
    coalesce((to_jsonb(NEW)->>TG_ARGV[0]), (to_jsonb(OLD)->>TG_ARGV[0])),
    case when TG_OP <> 'INSERT' then to_jsonb(OLD) end,
    case when TG_OP <> 'DELETE' then to_jsonb(NEW) end
  );
  return coalesce(NEW, OLD);
end;
$$ language plpgsql security definer;

-- 8개 테이블 x 1트리거, PK 컬럼명만 다름
create trigger audit_equipment after insert or update or delete on public.equipment
  for each row execute function public.fn_audit_log('equipment_id');
create trigger audit_inspection_tasks after insert or update or delete on public.inspection_tasks
  for each row execute function public.fn_audit_log('task_id');
create trigger audit_inspection_rounds after insert or update or delete on public.inspection_rounds
  for each row execute function public.fn_audit_log('round_id');
create trigger audit_deficiencies after insert or update or delete on public.deficiencies
  for each row execute function public.fn_audit_log('deficiency_id');
create trigger audit_notices after insert or update or delete on public.notices
  for each row execute function public.fn_audit_log('notice_no');
create trigger audit_malfunctions after insert or update or delete on public.malfunctions
  for each row execute function public.fn_audit_log('malfunction_id');
create trigger audit_floor_spots after insert or update or delete on public.floor_spots
  for each row execute function public.fn_audit_log('spot_id');
create trigger audit_inspection_types after insert or update or delete on public.inspection_types
  for each row execute function public.fn_audit_log('name');

-- 검증
select count(*) from information_schema.triggers where trigger_name like 'audit_%';
```

**롤백**: `drop trigger audit_<table> on public.<table>;` (8회) → `drop function public.fn_audit_log();` → `drop table public.audit_log;`. 기존 테이블/데이터는 전혀 건드리지 않으므로 완전 원복 가능.

### 2) `db_monitor.py` — 변경사항 탭

- `ACTOR_COLUMNS = ["inspector", "submitter", "confirmer", "assignee", "excluded_by", "cancelled_by"]`
- `fetch_audit_log(conn, tables: list[str], ops: list[str], days: int | None, limit: int) -> pd.DataFrame` — `audit_log`을 `table_name in %s and op in %s`, 기간 필터, `changed_at desc limit %s`로 조회. 화이트리스트는 `PYROSAFE_TABLES`와 `{"INSERT","UPDATE","DELETE"}`로 검증.
- `infer_actor(row: dict) -> str | None` — `new_data`(없으면 `old_data`)에서 `ACTOR_COLUMNS` 순회, 처음 non-empty 값 반환.
- `diff_columns(old: dict | None, new: dict | None) -> dict[str, tuple]` — INSERT/DELETE는 전체 컬럼을, UPDATE는 `old[k] != new[k]`인 컬럼만 `{col: (old_val, new_val)}`로 반환.
- `render_changes(conn) -> None`:
  - 필터 위젯: 테이블 다중선택(기본값 = deficiencies/malfunctions/inspection_tasks/inspection_rounds, "전체 8개" 체크박스로 확장), Op 다중선택(기본 전체), 기간 selectbox(최근 1일/7일/30일/전체)
  - `fetch_audit_log` 결과를 최신순으로 순회하며 각 행을 `st.expander(f"{table_name} · {op} · {row_pk} · {changed_at}")`로: 상단에 "입력자(추정): {actor}" 캡션(없으면 "— 기록 없음, 이 변경은 담당자 컬럼이 없을 수 있음"), 본문에 `diff_columns` 결과를 2열 표(컬럼명 | 변경 전 → 변경 후)로 렌더.
  - 결과 없으면 `st.info("해당 조건의 변경 이력이 없습니다.")`.
- `main()`의 탭을 5개로: `t1..t5 = st.tabs(["개요","추이","브라우저","변경사항","운영"])`, `with t4: render_changes(conn)`.

### 3) `db_monitor.py` — 헬스체크 버튼

- `run_health_checks(conn) -> list[dict]` — 아래 5개를 순서대로 실행, 각각 `{"name": str, "ok": bool, "ms": int, "detail": str}` 반환(개별 실패가 나머지를 막지 않도록 각 체크를 `try/except`로 격리하고 실패 시 `conn.rollback()`):
  1. `SELECT 1` 왕복 시간
  2. `PYROSAFE_TABLES` 각각 `SELECT 1 FROM public."{t}" LIMIT 1`
  3. `SELECT 1 FROM storage.buckets LIMIT 1`
  4. `SELECT count(*) FROM auth.users`
  5. `SELECT max(changed_at) FROM public.audit_log` — 결과가 24시간 이상 전이거나 테이블이 없으면 `ok=False`, detail에 사유 명시(트리거 미설치 vs 24시간 무변경 구분)
- `render_health_check(conn) -> None` — 사이드바에 "헬스체크 실행" 버튼. 클릭 시 `run_health_checks` 호출, 요약 배지(`f"{정상 개수}/{len(results)} 정상"`, 전부 정상이면 `st.success`, 아니면 `st.warning`) + 실패 항목만 `st.error(f"{name}: {detail}")`로 펼쳐 보여줌. 사이드바의 기존 새로고침/로그아웃 버튼 사이에 배치.

### 4) 테스트 — `tests/test_db_monitor.py`

기존 테스트 패턴(mock 커넥션/커서)을 따라 순수 함수 위주로 추가:
- `infer_actor`: 여러 액터 컬럼 중 우선순위, 전부 없을 때 `None`
- `diff_columns`: INSERT(전체), DELETE(전체), UPDATE(변경분만, 동일값 컬럼 제외)
- `fetch_audit_log`: 테이블/Op 화이트리스트 밖 입력 시 `ValueError`
- `run_health_checks`: 커서 mock으로 성공/예외 케이스 각각, 개별 실패가 나머지 체크를 막지 않는지

### 변경 없음

- `개요`/`추이`/`브라우저`/`운영` 탭 로직 — 그대로.
- PyroSafe 본앱(`pages_app/`, `lib/`) — 전혀 건드리지 않음. 행위자 정밀 추적(세션 사용자를 DB에 전달)은 후속 과제로 별도 브레인스토밍 필요.
- 기존 테이블 스키마·데이터 — 컬럼 추가/변경 없음. `audit_log`는 순수 추가 테이블.
