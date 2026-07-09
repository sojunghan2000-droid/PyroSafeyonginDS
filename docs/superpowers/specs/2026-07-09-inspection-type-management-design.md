# 점검 유형 관리 (관리자) — 설계 문서

- 날짜: 2026-07-09
- 상태: 승인됨
- 대상 파일: `lib/data.py`, `pages_app/admin_center.py`, `pages_app/equipment_inventory.py`,
  `lib/inspection_dialog.py`, `supabase_schema.sql`, `PRD.md`

## 배경 / 문제

점검 유형(주기) 카탈로그는 `lib/data.py`의 하드코딩 리스트 `TASK_INSPECTION_TYPES`
(일일·주간·월간·분기·연간 5종)이다. 관리자가 새 유형(예: 반기 점검)을 추가하려면 코드
수정·배포가 필요하다. 앱의 다른 마스터 데이터(spot, 사용자, 장비)는 모두 Supabase 테이블
기반인데, 유형 카탈로그만 코드에 박혀 있다.

## 목표

관리자 메뉴에서 점검 유형을 **추가/비활성/삭제**할 수 있는 화면 제공. 추가한 유형이
**영구 저장**되고 장비 속성·신규 일정 등 선택 목록에 즉시 반영.

## 확정 결정 (사용자)

- **범위: 추가 + 삭제/숨김**
  - 새 유형 추가
  - 안 쓰는 유형 **비활성화/삭제**
  - 기본 5종은 **보호**(삭제 불가, 비활성만 가능)
  - **사용 중(장비·회차 참조) 유형은 삭제 불가 → 비활성만**
- 범위 밖: 이름 변경(rename), 순서 변경(reorder)

## 데이터 모델 (신규 테이블)

```sql
create table if not exists inspection_types (
  name       text primary key,          -- 유형 이름. 장비·회차가 이름으로 참조
  is_active  boolean not null default true,
  is_builtin boolean not null default false,
  sort_order int not null default 100,
  created_at timestamptz not null default now()
);
insert into inspection_types (name, is_builtin, sort_order) values
  ('일일 점검', true, 1), ('주간 점검', true, 2), ('월간 점검', true, 3),
  ('분기 점검', true, 4), ('연간 점검', true, 5)
on conflict (name) do nothing;
-- RLS: 기존 테이블과 동일 정책 적용
```

- **이름을 PK로** — 장비 `inspection_types`(jsonb)·회차 `task_type`이 이름 문자열로 참조하므로.
- **안전 폴백**: 테이블이 없거나 비면 `load_inspection_types()`가 하드코딩
  `TASK_INSPECTION_TYPES`로 폴백 → 마이그레이션 전에도 앱 정상. 관리 탭에서만 "먼저 이 SQL
  실행" 안내(SQL 표시).

## 데이터 계층 (`lib/data.py`)

- `@st.cache_data _inspection_type_rows() -> list[dict]` — 테이블 조회. 실패/미존재 시 `[]`.
- `load_inspection_types(active_only: bool = False) -> list[str]`
  - rows 있으면 이름 목록(active_only면 `is_active` 필터, `sort_order` 순).
  - rows 없으면 `TASK_INSPECTION_TYPES` 폴백.
- `load_inspection_type_rows() -> list[dict]` — 관리 UI용(name/is_active/is_builtin/sort_order).
  rows 없으면 하드코딩 5종을 builtin으로 합성 반환.
- `add_inspection_type(name)` — strip·중복·공백 검증 후 insert(sort_order=max+1) → `.clear()`.
- `set_inspection_type_active(name, active)` — update → `.clear()`.
- `delete_inspection_type(name)` — **가드**: `is_builtin` 또는 사용 중이면 거부. 아니면 delete → `.clear()`.
- 사용 중 판정/카운트는 관리 탭에서 계산: `equipment.inspection_types` 포함 수 +
  `rounds.task_type == name` 수.

## 관리자 화면 (`pages_app/admin_center.py`)

- `render()`의 `tabs = ["위치 마스터", "사용자 관리"]` → **`["위치 마스터", "점검 유형", "사용자 관리"]`**.
  라우팅에 `elif section == "점검 유형": _inspection_type_tab()` 추가.
- `_inspection_type_tab()`:
  - 상단 안내 + (테이블 미존재 시) 마이그레이션 SQL 안내 박스.
  - **＋ 새 유형 추가**: `st.text_input` + `[추가]` → `add_inspection_type`.
  - 목록 테이블(기존 스타일, 가운데 정렬): `유형 이름 / 사용중 N건 / 기본 배지 / 활성 토글 / 조치`.
    - 사용중(≥1) 또는 기본 → `[삭제]` 비활성, `활성 토글`만.
    - 미사용 + 비기본 → `[삭제]` 가능.
  - 안내: "비활성 유형은 새 선택 목록에서 숨겨지지만, 이미 지정된 장비·회차엔 그대로 남습니다."

## 소비 지점 교체 (`TASK_INSPECTION_TYPES` → DB)

| 위치 | 변경 |
|---|---|
| 장비 속성 멀티셀렉트 (`equipment_inventory.py:367`) | `load_inspection_types(active_only=True)` **∪ 그 장비 기존 유형** (비활성이어도 기존 선택 표시) |
| 신규 일정 유형 목록 (`inspection_dialog.py:1787`) | `load_inspection_types(active_only=True)` |
| 유형 옵션 (`inspection_dialog.py:1890`) | `load_inspection_types(active_only=True) + ["기타"]` |
| 매칭 검증 (`inspection_dialog.py:628`) | `load_inspection_types()` **전체(활성+비활성)** — 과거 회차 매칭 유지 |
| 안전점검 관리 필터 (`inspection_tasks.py:486`) | **변경 없음** — 이미 회차 `task_type`에서 파생 |

## 기존 하드코딩 처리

`TASK_INSPECTION_TYPES` / `INSPECTION_TYPE_CATEGORY_DEFAULTS`는 **폴백·카테고리 기본값용으로 유지**
(삭제하지 않음). 카테고리별 기본 유형 자동 채움 로직은 그대로.

## 범위 밖 (YAGNI)

- 이름 변경(rename), 순서 변경(reorder)
- 카테고리 기본값 편집 UI (별도 기능)

## 안전장치

- 이름 공백/중복 방지, 기본 5종 삭제 방지, 사용 중 유형 삭제 방지(비활성만).
- rename 미도입으로 참조 불일치 원천 차단.
- 테이블 미존재 시 폴백 + 관리 탭 마이그레이션 안내.
