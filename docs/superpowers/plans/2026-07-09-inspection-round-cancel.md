# 점검(회차) 취소 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 회차(InspectionRound)에 사유가 기록되는 취소 상태를 부여하고, KPI·목록·별지5에서 취소 회차를 적절히 처리한다.

**Architecture:** `inspection_rounds`에 취소 플래그/사유 컬럼 4개를 추가(안전 폴백)하고, `cancel_round()` 데이터 함수 + `compute_round_status` short-circuit로 상태 충돌을 회피한다. 회차 상세 모달에 인라인 사유 입력식 취소 버튼을 붙이고, KPI/목록/필터/별지5 드롭다운에서 취소 회차를 반영한다.

**Tech Stack:** Streamlit 1.57+, Supabase (supabase-py), Python 3.13.

## Global Constraints

- 커밋 메시지 말미: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- push는 `main`에만.
- 이 repo는 pytest 스위트가 없다. 검증은 (a) `python -c "import ast; ast.parse(...)"` 구문 검사, (b) `python -c "import lib.data as data; ..."` 헤드리스 스모크(라이브 Supabase 조회), (c) Streamlit preview.
- Supabase service_role 키는 클라이언트에서 사용 금지 (기존 정책).
- 파일 인코딩 UTF-8. 한글 문자열 유지.

---

### Task 1: 마이그레이션 SQL + 스키마 파일 반영

**Files:**
- Modify: `supabase_schema.sql` (inspection_rounds 정의 근처)
- Create: `docs/superpowers/migrations/2026-07-09-round-cancel.sql`

**Interfaces:**
- Produces: `inspection_rounds`에 컬럼 `cancelled boolean`, `cancel_reason text`, `cancelled_at timestamptz`, `cancelled_by text`.

- [ ] **Step 1: 마이그레이션 SQL 파일 작성**

Create `docs/superpowers/migrations/2026-07-09-round-cancel.sql`:

```sql
-- 점검(회차) 취소: inspection_rounds에 취소 플래그/사유 컬럼 추가
alter table inspection_rounds
  add column if not exists cancelled     boolean     not null default false,
  add column if not exists cancel_reason text,
  add column if not exists cancelled_at  timestamptz,
  add column if not exists cancelled_by  text;
```

- [ ] **Step 2: supabase_schema.sql에도 동일 컬럼 반영**

`supabase_schema.sql`의 `create table ... inspection_rounds (...)` 블록에 4개 컬럼을 추가(기존 컬럼 뒤). 없으면 파일 하단에 위 `alter table` 문을 주석과 함께 append.

- [ ] **Step 3: 사용자에게 마이그레이션 실행 안내**

이 SQL은 Supabase SQL 에디터에서 1회 실행해야 한다. 데이터 계층은 폴백이 있어 실행 전에도 앱은 동작하지만, 실제 취소 저장은 실행 후 가능. **실행은 사용자 몫** — 실행 요청을 명시적으로 전달할 것.

- [ ] **Step 4: Commit**

```bash
git add supabase_schema.sql docs/superpowers/migrations/2026-07-09-round-cancel.sql
git commit -m "chore(db): 회차 취소용 inspection_rounds 컬럼 마이그레이션 SQL"
```

---

### Task 2: 데이터 계층 — 모델 필드 + cancel_round + status short-circuit

**Files:**
- Modify: `lib/data.py` (dataclass `InspectionRound` ~235, `_row_to_round` ~416, `compute_round_status` ~575, `_refresh_round_status` ~747, 쓰기 섹션)

**Interfaces:**
- Consumes: Task 1의 컬럼(없어도 `.get()` 폴백).
- Produces:
  - `InspectionRound.cancelled: bool`, `.cancel_reason: str`, `.cancelled_at: datetime | None`, `.cancelled_by: str`
  - `cancel_round(round_id: str, reason: str, by: str) -> bool` (완료/기취소면 False)
  - `compute_round_status`/`_refresh_round_status`는 취소 회차를 변경하지 않음.

- [ ] **Step 1: dataclass에 필드 추가**

`InspectionRound`에 필드 추가 (note 아래):

```python
    note: str = ""
    cancelled: bool = False
    cancel_reason: str = ""
    cancelled_at: datetime | None = None
    cancelled_by: str = ""
```

`datetime` import 확인 (파일 상단에 `from datetime import date, datetime` 있는지; 없으면 `datetime` 추가).

- [ ] **Step 2: _row_to_round에서 매핑 (폴백 포함)**

```python
def _row_to_round(r: dict) -> InspectionRound:
    return InspectionRound(
        round_id=r["round_id"], task_type=r["task_type"],
        assignee=r.get("assignee") or "",
        due_date=_d(r["due_date"]),
        status=r["status"], note=r.get("note") or "",
        cancelled=bool(r.get("cancelled", False)),
        cancel_reason=r.get("cancel_reason") or "",
        cancelled_at=_dt(r.get("cancelled_at")) if r.get("cancelled_at") else None,
        cancelled_by=r.get("cancelled_by") or "",
    )
```

`_dt` 헬퍼(타임스탬프 파서)가 있는지 확인. 없으면 `cancelled_at=None`로 두고(표시엔 날짜만 필요하면 문자열 그대로 `r.get("cancelled_at")` 사용) 단순화. 실제 파일의 기존 datetime 파싱 헬퍼(`_d`/`_dt`)를 따를 것.

- [ ] **Step 3: compute_round_status short-circuit**

`compute_round_status(round_id)` 함수 맨 앞에 추가:

```python
    r = get_round(round_id)
    if r and r.cancelled:
        return r.status  # 취소 회차는 상태 재계산하지 않음
```

- [ ] **Step 4: _refresh_round_status short-circuit**

`_refresh_round_status(round_id)` 함수 맨 앞에 추가:

```python
    r = get_round(round_id)
    if r and r.cancelled:
        return  # 취소 회차는 자동 status 갱신 대상 아님
```

- [ ] **Step 5: cancel_round 작성 (쓰기 섹션, add_round 근처)**

```python
def cancel_round(round_id: str, reason: str, by: str) -> bool:
    """회차를 취소 처리. 완료/기취소 회차는 거부(False). 성공 시 True."""
    r = get_round(round_id)
    if not r or r.cancelled or r.status == "Completed":
        return False
    _db().table("inspection_rounds").update({
        "cancelled": True,
        "cancel_reason": (reason or "").strip(),
        "cancelled_at": _iso_dt(TODAY),  # 기존 타임스탬프 직렬화 헬퍼 사용
        "cancelled_by": by or "",
    }).eq("round_id", round_id).execute()
    _round_rows.clear()
    return True
```

주의: `cancelled_at` 직렬화는 파일의 기존 패턴을 따를 것 — 날짜만 저장해도 무방하면 `_iso(TODAY)` 사용. 정확한 헬퍼명은 파일에서 확인(`_iso`, `_iso_dt` 등).

- [ ] **Step 6: 헤드리스 스모크 — 모델 로드 회귀 없음 확인**

Run:
```bash
python -c "import lib.data as data; rs=data.load_rounds(); print('rounds', len(rs)); print('cancelled sample', [r.cancelled for r in rs[:3]])"
```
Expected: 에러 없이 `rounds N` 출력, `cancelled` 전부 `False`(마이그레이션 전이면 폴백). 마이그레이션 후에도 동일.

- [ ] **Step 7: 구문 검사 + Commit**

```bash
python -c "import ast; ast.parse(open('lib/data.py',encoding='utf-8').read()); print('OK')"
git add lib/data.py
git commit -m "feat(data): 회차 취소 모델 필드 + cancel_round + status short-circuit"
```

---

### Task 3: 회차 상세 모달 — 점검 취소 버튼 + 사유 입력 + 취소 표시

**Files:**
- Modify: `pages_app/inspection_tasks.py` (`_round_detail_dialog` ~86-155)

**Interfaces:**
- Consumes: `data.cancel_round`, `r.cancelled`, `r.cancel_reason`, `r.cancelled_at`, `r.cancelled_by`.

- [ ] **Step 1: 헤더 우측에 점검 취소 버튼 + 취소 표시 추가**

`_round_detail_dialog`에서 별지5 PDF 컬럼(`pdl, pdr = st.columns([3, 1])`) 영역을 `[별지5 PDF | 점검 취소]` 2버튼으로 확장하거나, 헤더 markdown 아래에 취소 UI 블록을 추가. 취소된 회차면 배지+사유 표시하고 액션 버튼 비활성.

```python
    # 취소 상태 표시
    if r.cancelled:
        st.markdown(
            f"<div style='background:#FEF2F2; border:1px solid #FECACA; "
            f"border-radius:8px; padding:0.5rem 0.8rem; margin:0.3rem 0 0.6rem;'>"
            f"<b style='color:#B91C1C;'>취소됨</b> "
            f"<span style='color:#7F1D1D; font-size:0.85rem;'>· 사유: "
            f"{r.cancel_reason or '-'} · {fmt_date(r.cancelled_at) if r.cancelled_at else ''} "
            f"· {r.cancelled_by or ''}</span></div>",
            unsafe_allow_html=True,
        )
```

- [ ] **Step 2: 취소 버튼 + 인라인 사유 입력 (완료/취소 회차는 비활성)**

별지5 PDF 버튼 옆에 취소 버튼. 모달 안 모달 불가 → session_state 토글로 인라인 사유 폼 노출:

```python
    can_cancel = (not r.cancelled) and r.status != "Completed"
    cancel_key = f"round_cancel_open_{round_id}"
    with pdr:  # 또는 별도 컬럼
        if can_cancel:
            if st.button("점검 취소", key=f"round_cancel_btn_{round_id}",
                         use_container_width=True):
                st.session_state[cancel_key] = True
        else:
            st.button("점검 취소", key=f"round_cancel_dis_{round_id}",
                      use_container_width=True, disabled=True,
                      help="완료·기취소 회차는 취소할 수 없습니다.")

    if st.session_state.get(cancel_key):
        reason = st.text_area("취소 사유", key=f"round_cancel_reason_{round_id}",
                              placeholder="예: 일정 중복 생성 / 작업 취소로 점검 불필요")
        cc1, cc2 = st.columns(2)
        with cc1:
            if st.button("취소 확정", type="primary", use_container_width=True,
                         key=f"round_cancel_confirm_{round_id}",
                         disabled=not reason.strip()):
                by = (auth.current_user() or {}).get("name") or "관리자"
                if data.cancel_round(round_id, reason, by):
                    st.session_state.pop(cancel_key, None)
                    st.rerun()
                else:
                    st.error("취소할 수 없는 회차입니다(완료/기취소).")
        with cc2:
            if st.button("닫기", use_container_width=True,
                         key=f"round_cancel_close_{round_id}"):
                st.session_state.pop(cancel_key, None)
                st.rerun()
```

`auth` import 확인(`from lib import auth` 또는 기존 방식). 취소된 회차면 Task 액션 버튼(점검 시작/추가/제외)도 `disabled` 처리 — 최소한 [+ Task 추가]와 각 행 버튼에 `disabled=r.cancelled` 반영.

- [ ] **Step 3: 구문 검사 + Commit**

```bash
python -c "import ast; ast.parse(open('pages_app/inspection_tasks.py',encoding='utf-8').read()); print('OK')"
git add pages_app/inspection_tasks.py
git commit -m "feat(tasks): 회차 상세에 점검 취소(사유 입력) + 취소 상태 표시"
```

---

### Task 4: 파급 — KPI 제외 · 목록 배지 · 상태 필터 · 별지5 드롭다운

**Files:**
- Modify: `pages_app/inspection_tasks.py` (KPI 계산 ~463-465, 목록 렌더 ~500-567, 필터 ~484-498)
- Modify: `lib/data.py` (`compute_kpis` 회차 관련 카운트가 있으면; 없으면 inspection_tasks 내 카운트만)
- Modify: `pages_app/report_center.py` (별지5 회차 옵션 ~514-516)

**Interfaces:**
- Consumes: `r.cancelled`.

- [ ] **Step 1: KPI에서 취소 회차 제외**

inspection_tasks.py의 회차 KPI 계산부(예: `overdue_rounds = sum(... r.status == "Overdue")` ~463-465)를 취소 제외로 수정:

```python
    active_rounds = [r for r in rounds if not r.cancelled]
    overdue_rounds = sum(1 for r in active_rounds if r.status == "Overdue")
    in_prog_rounds = sum(1 for r in active_rounds if r.status == "In Progress")
    completed_rounds = sum(1 for r in active_rounds if r.status == "Completed")
```

"전체 회차/활성 점검 일정" KPI도 `active_rounds` 기준으로. (취소 건수는 필요 시 별도 표기.)

- [ ] **Step 2: 상태 필터에 '취소' 추가 + 취소 필터링**

`type_filter`가 아닌 status 필터부(`target_status` 매핑/`visible` 필터 ~496). 상태 옵션 목록에 `취소` 추가하고:

```python
    if status_filter == "취소":
        visible = [r for r in visible if r.cancelled]
    else:
        visible = [r for r in visible if not r.cancelled or status_filter == "전체"]
        # 기존 status 매칭 로직 유지 (취소 회차는 취소 필터에서만)
```

정확한 기존 필터 변수명(`target_status`)에 맞춰 조정. 기본(전체/특정 상태)에서는 취소 회차를 `취소됨` 배지로 노출하되 status 매칭에서는 제외.

- [ ] **Step 3: 목록 행에 취소됨 배지**

행 렌더에서 상태 배지 자리(예: ~567 `r.status` 배지)를 취소 우선으로:

```python
    if r.cancelled:
        status_html = "<span style='color:#B91C1C; font-weight:600;'>취소됨</span>"
    else:
        # 기존 status 배지 로직
```

행 전체를 옅은 회색 톤으로(선택). 진행률 바는 취소 시 숨김.

- [ ] **Step 4: 별지5 회차 드롭다운에서 취소 회차 제외**

`report_center.py`의 별지5 옵션 루프(~515):

```python
    for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
        if _r.cancelled:
            continue
        _opts[f"{_r.round_id} · {_r.task_type} · {_cnt.get(_r.round_id, 0)}건"] = _r.round_id
```

(별지6 드롭다운도 동일하게 `_r.cancelled` 제외 — `report_center.py`의 `_opts6` 루프.)

- [ ] **Step 5: 구문 검사 + 헤드리스 스모크 + Commit**

```bash
python -c "import ast; ast.parse(open('pages_app/inspection_tasks.py',encoding='utf-8').read()); ast.parse(open('pages_app/report_center.py',encoding='utf-8').read()); print('OK')"
python -c "import lib.data as data; rs=data.load_rounds(); print('active', sum(1 for r in rs if not r.cancelled), '/ total', len(rs))"
git add pages_app/inspection_tasks.py pages_app/report_center.py lib/data.py
git commit -m "feat(tasks): 취소 회차 — KPI 제외/목록 배지/상태 필터/별지5·6 드롭다운 반영"
```

---

### Task 5: preview 검증 + PRD 동기화

**Files:**
- Modify: `PRD.md` (6.3 안전점검 관리)

- [ ] **Step 1: preview 검증 (가능 시)**

서버 재시작(포트 8511 프로세스 kill 후 preview_start) → 로그인 → 안전점검 관리 → 회차 상세 → 점검 취소 → 사유 입력 → 확정 → `취소됨` 배지 + KPI/목록 반영 확인. preview 불안정 시 헤드리스+구문으로 대체하고 사용자에게 Ctrl+F5 확인 요청.

- [ ] **Step 2: PRD 6.3에 점검 취소 항목 추가**

회차 상세 모달 설명(~205-223) 부근에 추가:

```markdown
  - **점검 취소 (v1.8)**: 회차 상세 우측 [점검 취소] → 사유 입력 후 확정. 완료·기취소 회차는 불가.
    취소 회차는 `취소됨` 배지 + 사유·시각·작성자 표기, 활성/지연/진행중 KPI·별지5·6 드롭다운에서 제외,
    상태 필터 '취소'로 조회. (복구 없음 — 단방향 종결. Task 제외 패턴의 회차 레벨 확장.)
```

- [ ] **Step 3: Commit + push**

```bash
git add PRD.md
git commit -m "docs(prd): 점검(회차) 취소 반영 (v1.8)"
git push origin main
```

## Self-Review 결과

- 스펙 커버리지: 4컬럼 마이그레이션(T1)·모델/cancel_round/short-circuit(T2)·버튼+사유(T3)·KPI/목록/필터/별지드롭다운(T4)·PRD(T5) 모두 매핑됨.
- Placeholder: `_iso`/`_dt` 등 헬퍼명은 파일 확인 지시(실제 존재 함수로 대체) — 구현 시 확정.
- 타입 일관성: `cancel_round(round_id, reason, by) -> bool` T2 정의 ↔ T3 호출 일치.
