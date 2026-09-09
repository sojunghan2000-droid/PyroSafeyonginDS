# 점검(회차) 취소 — 설계 문서

- 날짜: 2026-07-09
- 상태: 승인됨 (사용자 3개 결정 확정)
- 대상 파일: `lib/data.py`, `pages_app/inspection_tasks.py`, `supabase_schema.sql`, `PRD.md`

## 배경 / 문제

회차(InspectionRound)는 한 번 생성되면 **취소 수단이 없다**. 잘못 생성/중복/작업 취소된
회차가 `예정`·`지연` 상태로 계속 남아 **활성 점검 일정·지연 KPI를 오염**시키고, 별지5
회차 드롭다운에도 계속 노출된다. Task 레벨에는 이미 `excluded + excluded_reason +
excluded_by`(제외+사유) 패턴이 있으나, 회차 레벨에는 없다.

## 목표

회차에 **사유가 기록되는 종결(취소) 상태**를 부여한다. Task 제외 패턴의 회차 레벨 확장.
근거(사유·시각·작성자)를 보존해 감사 추적 철학과 정합.

## 확정 결정 (사용자)

1. **완료(Completed) 회차는 취소 불가** — 이미 결과·별지5 데이터 존재.
2. **취소 복구(되돌리기) 없음** — 단방향 종결.
3. **목록 표시**: `취소됨` 배지로 **기본 노출**(숨김 아님), 상태 필터에 `취소` 추가.

## 데이터 모델 변경 (마이그레이션)

`inspection_rounds`에 4개 컬럼 추가:

```sql
alter table inspection_rounds
  add column if not exists cancelled     boolean     not null default false,
  add column if not exists cancel_reason text,
  add column if not exists cancelled_at  timestamptz,
  add column if not exists cancelled_by  text;
```

- **안전 폴백**: row 매퍼는 `r.get("cancelled", False)` 등으로 읽어 컬럼이 없어도
  기본값으로 동작(취소 아님으로 간주). 마이그레이션 전에도 앱은 정상.

### `InspectionRound` dataclass
`cancelled: bool = False`, `cancel_reason: str = ""`, `cancelled_at: datetime | None = None`,
`cancelled_by: str = ""` 필드 추가. `_row_to_round`에서 `.get(...)`로 매핑.

## 데이터 계층 (`lib/data.py`)

- `cancel_round(round_id, reason, by) -> None`
  - `_db().table("inspection_rounds").update({cancelled: True, cancel_reason,
    cancelled_at: now, cancelled_by})` → `_round_rows.clear()`
  - 가드: 대상 회차가 `Completed`거나 이미 `cancelled`면 no-op(또는 예외) — UI에서도 차단.
- `compute_round_status` / `_refresh_round_status`: **취소된 회차는 건너뜀**
  (status를 재계산·덮어쓰지 않음). 표시·KPI는 `cancelled`를 우선 반영.

> 상태 충돌 회피: `status`는 Task로부터 자동 재계산되는 필드다. `status="취소"`로 두면
> Task 변경 시 덮어써지므로, **별도 `cancelled` 플래그**로 관리한다.

## UI (`pages_app/inspection_tasks.py`)

### 회차 상세 모달 (`_round_detail_dialog`)
- 헤더 우측(별지5 PDF 버튼 영역 옆/위)에 **`점검 취소`** 버튼 추가.
  - `status == "Completed"` 또는 이미 취소면 **비활성**(사유 표기).
- 클릭 → 인라인 **사유 입력**(textarea) + `[취소 확정]` 버튼. (모달 내 모달 불가 제약 →
  기존 인라인 패턴 재사용.) 확정 시 `cancel_round(round_id, reason, 현재 사용자)` →
  `st.rerun()`.
- 취소된 회차: 헤더에 `취소됨` 배지 + `취소 사유 · 시각 · 작성자` 표기. Task 액션(점검 시작/
  추가/제외) 버튼은 비활성.

### 회차 목록
- `취소됨` 회색 배지 렌더(진행률 바 대신 또는 상태 자리). 행은 회색 톤.
- 상태 필터 옵션에 **`취소`** 추가 → 선택 시 취소 회차만.
- 기본 목록에는 그대로 노출(숨기지 않음).

## 파급 지점

| 위치 | 변경 |
|---|---|
| KPI(활성 점검 일정/지연/진행 중) | 취소 회차 **제외** |
| 회차 목록 status 배지 | 취소 시 `취소됨` 우선 표시 |
| 상태 필터 | `취소` 옵션 추가 |
| 별지5 회차 드롭다운(`report_center.py`) | 취소 회차 **제외** |

## 범위 밖 (YAGNI)

- 취소 복구/되돌리기 (사용자 결정: 불필요)
- 완료 회차 취소
- 취소 회차의 별지 출력 (제외)

## 안전장치

- 완료·기취소 회차 취소 차단(UI + 데이터 함수 가드).
- 사유 필수(공백 불가).
- `compute_round_status`가 취소 상태를 덮어쓰지 않도록 short-circuit.
