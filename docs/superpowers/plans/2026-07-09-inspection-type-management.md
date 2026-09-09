# 점검 유형 관리 (관리자) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 관리자 메뉴에서 점검 유형을 추가/비활성/삭제하고, 그 목록이 장비 속성·신규 일정 등 선택지에 즉시 반영되게 한다.

**Architecture:** 신규 `inspection_types` 테이블(이름 PK)로 카탈로그를 영구화하되, 테이블이 없으면 하드코딩 `TASK_INSPECTION_TYPES`로 폴백. 데이터 계층에 load/add/toggle/delete 함수를 추가하고, admin_center에 관리 탭, 소비 지점들을 DB 조회로 교체한다.

**Tech Stack:** Streamlit 1.57+, Supabase (supabase-py), Python 3.13.

## Global Constraints

- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- push는 `main`에만.
- pytest 스위트 없음. 검증은 ast 구문 검사 + `python -c "import lib.data ..."` 헤드리스 스모크 + preview.
- 기본 5종(일일·주간·월간·분기·연간)은 삭제 불가(비활성만). 사용 중 유형 삭제 불가.
- rename/reorder 미구현(범위 밖).

---

### Task 1: 마이그레이션 SQL + 스키마 파일 반영

**Files:**
- Modify: `supabase_schema.sql`
- Create: `docs/superpowers/migrations/2026-07-09-inspection-types.sql`

**Interfaces:**
- Produces: 테이블 `inspection_types(name pk, is_active, is_builtin, sort_order, created_at)` + 기본 5종 시드.

- [ ] **Step 1: 마이그레이션 SQL 파일 작성**

Create `docs/superpowers/migrations/2026-07-09-inspection-types.sql`:

```sql
create table if not exists inspection_types (
  name       text primary key,
  is_active  boolean not null default true,
  is_builtin boolean not null default false,
  sort_order int not null default 100,
  created_at timestamptz not null default now()
);
insert into inspection_types (name, is_builtin, sort_order) values
  ('일일 점검', true, 1), ('주간 점검', true, 2), ('월간 점검', true, 3),
  ('분기 점검', true, 4), ('연간 점검', true, 5)
on conflict (name) do nothing;
-- RLS: 기존 테이블(floor_spots 등)과 동일 정책을 적용할 것.
```

- [ ] **Step 2: supabase_schema.sql에 테이블 정의 추가**

기존 테이블 정의 스타일에 맞춰 `inspection_types` create + 시드를 추가.

- [ ] **Step 3: 사용자에게 마이그레이션 실행 안내**

SQL 1회 실행 필요. 실행 전에는 폴백으로 앱 동작하되 "추가"는 불가(관리 탭에서 SQL 안내). 실행은 사용자 몫 — 명시적으로 요청 전달.

- [ ] **Step 4: Commit**

```bash
git add supabase_schema.sql docs/superpowers/migrations/2026-07-09-inspection-types.sql
git commit -m "chore(db): inspection_types 테이블 마이그레이션 SQL"
```

---

### Task 2: 데이터 계층 — 조회/폴백 + add/toggle/delete

**Files:**
- Modify: `lib/data.py` (캐시 조회 섹션 ~473-510, 쓰기 섹션)

**Interfaces:**
- Consumes: Task 1 테이블(없어도 폴백). 기존 상수 `TASK_INSPECTION_TYPES`.
- Produces:
  - `load_inspection_types(active_only: bool = False) -> list[str]`
  - `load_inspection_type_rows() -> list[dict]` (키: name, is_active, is_builtin, sort_order)
  - `add_inspection_type(name: str) -> tuple[bool, str]`
  - `set_inspection_type_active(name: str, active: bool) -> None`
  - `delete_inspection_type(name: str) -> tuple[bool, str]`
  - `inspection_types_table_exists() -> bool`

- [ ] **Step 1: 캐시 조회 + 테이블 존재 판정**

캐시 섹션에 추가:

```python
@st.cache_data(ttl=_CACHE_TTL)
def _inspection_type_rows() -> list[dict]:
    try:
        return (_db().table("inspection_types").select("*")
                .order("sort_order").order("name").execute().data)
    except Exception:
        return []  # 테이블 미존재 등 → 폴백 신호


def inspection_types_table_exists() -> bool:
    """관리 UI에서 마이그레이션 안내 분기용."""
    try:
        _db().table("inspection_types").select("name").limit(1).execute()
        return True
    except Exception:
        return False
```

- [ ] **Step 2: load 함수 (폴백 포함)**

```python
def load_inspection_types(active_only: bool = False) -> list[str]:
    rows = _inspection_type_rows()
    if not rows:
        return list(TASK_INSPECTION_TYPES)  # 폴백
    if active_only:
        rows = [r for r in rows if r.get("is_active", True)]
    return [r["name"] for r in rows]


def load_inspection_type_rows() -> list[dict]:
    """관리 UI용. 테이블 없으면 하드코딩 5종을 builtin으로 합성."""
    rows = _inspection_type_rows()
    if rows:
        return rows
    return [
        {"name": n, "is_active": True, "is_builtin": True, "sort_order": i + 1}
        for i, n in enumerate(TASK_INSPECTION_TYPES)
    ]
```

- [ ] **Step 3: 쓰기 함수 (add/toggle/delete)**

쓰기 섹션에 추가:

```python
def add_inspection_type(name: str) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name:
        return False, "이름을 입력하세요."
    existing = {r["name"] for r in _inspection_type_rows()}
    if name in existing:
        return False, "이미 존재하는 유형입니다."
    max_order = max([r.get("sort_order", 0) for r in _inspection_type_rows()] or [0])
    _db().table("inspection_types").insert({
        "name": name, "is_active": True, "is_builtin": False,
        "sort_order": max_order + 1,
    }).execute()
    _inspection_type_rows.clear()
    return True, "추가되었습니다."


def set_inspection_type_active(name: str, active: bool) -> None:
    _db().table("inspection_types").update(
        {"is_active": active}
    ).eq("name", name).execute()
    _inspection_type_rows.clear()


def delete_inspection_type(name: str) -> tuple[bool, str]:
    row = next((r for r in _inspection_type_rows() if r["name"] == name), None)
    if row and row.get("is_builtin"):
        return False, "기본 유형은 삭제할 수 없습니다."
    if _inspection_type_usage(name) > 0:
        return False, "사용 중인 유형은 삭제할 수 없습니다(비활성만 가능)."
    _db().table("inspection_types").delete().eq("name", name).execute()
    _inspection_type_rows.clear()
    return True, "삭제되었습니다."


def _inspection_type_usage(name: str) -> int:
    """장비 inspection_types 포함 + 회차 task_type == name 건수."""
    eq_cnt = sum(1 for e in load_equipment() if name in (e.inspection_types or []))
    rnd_cnt = sum(1 for r in load_rounds() if r.task_type == name)
    return eq_cnt + rnd_cnt
```

- [ ] **Step 4: 헤드리스 스모크**

Run:
```bash
python -c "import lib.data as data; print('types', data.load_inspection_types()); print('active', data.load_inspection_types(active_only=True)); print('rows', len(data.load_inspection_type_rows())); print('exists', data.inspection_types_table_exists())"
```
Expected: 마이그레이션 전이면 폴백 5종 출력, `exists=False`. 후이면 DB 5종, `exists=True`. 에러 없음.

- [ ] **Step 5: 구문 검사 + Commit**

```bash
python -c "import ast; ast.parse(open('lib/data.py',encoding='utf-8').read()); print('OK')"
git add lib/data.py
git commit -m "feat(data): inspection_types 조회/폴백 + add/toggle/delete + 사용량 판정"
```

---

### Task 3: 관리자 화면 — 점검 유형 탭

**Files:**
- Modify: `pages_app/admin_center.py` (`render` ~801-813, 새 함수 `_inspection_type_tab`)

**Interfaces:**
- Consumes: `data.load_inspection_type_rows`, `data.add_inspection_type`, `data.set_inspection_type_active`, `data.delete_inspection_type`, `data._inspection_type_usage`, `data.inspection_types_table_exists`.

- [ ] **Step 1: radio 섹션에 '점검 유형' 추가 + 라우팅**

```python
    tabs = ["위치 마스터", "점검 유형", "사용자 관리"]
    section = st.radio(... 기존 그대로 ...)
    ...
    if section == "위치 마스터":
        _spot_master_tab()
    elif section == "점검 유형":
        _inspection_type_tab()
    else:
        _user_admin_tab()
```

- [ ] **Step 2: _inspection_type_tab 작성**

```python
def _inspection_type_tab() -> None:
    st.markdown(
        "<div style='color:#64748B; font-size:0.92rem;'>"
        "점검 유형(주기) 카탈로그를 관리합니다 — 추가 / 비활성 / 삭제. "
        "비활성 유형은 새 선택 목록에서 숨겨지지만, 이미 지정된 장비·회차엔 그대로 남습니다."
        "</div>",
        unsafe_allow_html=True,
    )
    if not data.inspection_types_table_exists():
        st.warning("점검 유형 테이블이 없습니다. 아래 SQL을 Supabase에서 1회 실행하세요.")
        st.code(
            "create table if not exists inspection_types (\n"
            "  name text primary key, is_active boolean not null default true,\n"
            "  is_builtin boolean not null default false,\n"
            "  sort_order int not null default 100,\n"
            "  created_at timestamptz not null default now());\n"
            "insert into inspection_types (name, is_builtin, sort_order) values\n"
            "  ('일일 점검',true,1),('주간 점검',true,2),('월간 점검',true,3),\n"
            "  ('분기 점검',true,4),('연간 점검',true,5) on conflict (name) do nothing;",
            language="sql",
        )
        return

    # 추가
    ac1, ac2 = st.columns([3, 1])
    with ac1:
        new_name = st.text_input("새 유형", key="new_insp_type",
                                 label_visibility="collapsed",
                                 placeholder="새 점검 유형 (예: 반기 점검)")
    with ac2:
        if st.button("추가", use_container_width=True, type="primary",
                     key="add_insp_type_btn"):
            ok, msg = data.add_inspection_type(new_name)
            (st.success if ok else st.error)(msg)
            if ok:
                st.session_state.pop("new_insp_type", None)
                st.rerun()

    st.markdown("<hr style='margin:0.5rem 0;'>", unsafe_allow_html=True)

    # 목록
    rows = data.load_inspection_type_rows()
    hc = st.columns([2, 1, 1, 1.2])
    for c, t in zip(hc, ["유형", "사용중", "기본", "활성/조치"]):
        c.markdown(f"<div style='color:#64748B; font-weight:600; font-size:0.8rem; "
                   f"text-align:center;'>{t}</div>", unsafe_allow_html=True)
    for row in rows:
        name = row["name"]
        usage = data._inspection_type_usage(name)
        builtin = bool(row.get("is_builtin"))
        cols = st.columns([2, 1, 1, 1.2])
        cols[0].markdown(f"<div style='text-align:center; font-weight:600;'>{name}</div>",
                         unsafe_allow_html=True)
        cols[1].markdown(f"<div style='text-align:center; color:#475569;'>{usage}건</div>",
                         unsafe_allow_html=True)
        cols[2].markdown(
            "<div style='text-align:center;'>"
            + ("<span style='color:#2563EB; font-size:0.8rem;'>기본</span>" if builtin else "—")
            + "</div>", unsafe_allow_html=True)
        with cols[3]:
            active = st.toggle("활성", value=bool(row.get("is_active", True)),
                               key=f"insp_active_{name}", label_visibility="collapsed")
            if active != bool(row.get("is_active", True)):
                data.set_inspection_type_active(name, active)
                st.rerun()
            deletable = (not builtin) and usage == 0
            if st.button("삭제", key=f"insp_del_{name}", use_container_width=True,
                         disabled=not deletable):
                ok, msg = data.delete_inspection_type(name)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
```

주의: st.toggle에 `value=` + 즉시 비교 후 write하는 패턴은 경고 없이 동작(별도 `key`만 있고 사전 session_state 설정은 안 함). 만약 경고가 뜨면 `control_toggle`처럼 key 전용 + 콜백으로 전환.

- [ ] **Step 3: 구문 검사 + preview + Commit**

```bash
python -c "import ast; ast.parse(open('pages_app/admin_center.py',encoding='utf-8').read()); print('OK')"
git add pages_app/admin_center.py
git commit -m "feat(admin): 점검 유형 관리 탭 (추가/비활성/삭제)"
```

---

### Task 4: 소비 지점 교체 (TASK_INSPECTION_TYPES → DB)

**Files:**
- Modify: `pages_app/equipment_inventory.py:367` (import ~8)
- Modify: `lib/inspection_dialog.py:628, 1787, 1890` (import ~14)

**Interfaces:**
- Consumes: `data.load_inspection_types`.

- [ ] **Step 1: 장비 속성 멀티셀렉트 (equipment_inventory.py)**

`_qr_dialog` 내 옵션(~367)을 활성 유형 ∪ 그 장비 기존 유형으로:

```python
    _active = data.load_inspection_types(active_only=True)
    _opts = _active + [t for t in (eq.inspection_types or []) if t not in _active]
    edited_types = st.multiselect(
        ...,
        options=_opts,
        ...
    )
```

상단 `from lib.data import TASK_INSPECTION_TYPES` 는 유지 가능하나 이 지점은 `data.load_inspection_types` 사용. `import lib.data as data` 또는 기존 import 방식 확인.

- [ ] **Step 2: inspection_dialog 신규 일정 유형(1787) + 유형 옵션(1890)**

```python
# ~1787
        options=data.load_inspection_types(active_only=True),
# ~1890
    type_options = data.load_inspection_types(active_only=True) + ["기타"]
```

- [ ] **Step 3: inspection_dialog 매칭 검증(628) — 전체(활성+비활성)**

```python
    def _is_match(e):
        return (r.task_type in data.load_inspection_types()
                and r.task_type in (e.inspection_types or []))
```

`data`가 이미 import되어 있는지 확인(inspection_dialog는 `from lib.data import ...`로 개별 import 중 → `from lib import data` 추가하거나 `load_inspection_types`를 개별 import에 추가).

- [ ] **Step 4: 구문 검사 + 헤드리스 스모크 + Commit**

```bash
python -c "import ast; ast.parse(open('pages_app/equipment_inventory.py',encoding='utf-8').read()); ast.parse(open('lib/inspection_dialog.py',encoding='utf-8').read()); print('OK')"
python -c "import lib.data as data; print(data.load_inspection_types(active_only=True))"
git add pages_app/equipment_inventory.py lib/inspection_dialog.py
git commit -m "refactor: 점검 유형 선택지를 DB(load_inspection_types)로 교체"
```

---

### Task 5: preview 검증 + PRD 동기화

**Files:**
- Modify: `PRD.md` (6.6 관리자 메뉴 / 점검 주기 카탈로그 서술)

- [ ] **Step 1: preview 검증 (마이그레이션 실행 후)**

관리자 메뉴 → 점검 유형 탭 → 새 유형 추가 → 목록 반영 확인 → 장비 속성 멀티셀렉트/신규 일정에서 새 유형 노출 확인 → 비활성 시 새 목록에서 숨김 확인. preview 불안정 시 헤드리스+구문으로 대체.

- [ ] **Step 2: PRD 갱신**

점검 주기 카탈로그(~191) + 관리자 메뉴(6.6) 서술에 "관리자 점검 유형 관리(추가/비활성/삭제, DB `inspection_types`, 폴백)" 추가.

- [ ] **Step 3: Commit + push**

```bash
git add PRD.md
git commit -m "docs(prd): 관리자 점검 유형 관리 반영 (v1.8)"
git push origin main
```

## Self-Review 결과

- 스펙 커버리지: 테이블/시드(T1)·데이터함수+폴백(T2)·관리탭(T3)·소비지점 4곳(T4)·PRD(T5) 매핑됨. 안전점검 필터(inspection_tasks:486)는 변경 없음(스펙과 일치).
- Placeholder: import 방식은 파일 확인 지시로 명시. toggle 경고 대비책 포함.
- 타입 일관성: `load_inspection_types(active_only)`·`add_inspection_type -> (bool,str)`·`delete_inspection_type -> (bool,str)` 정의(T2) ↔ 사용(T3,T4) 일치.
