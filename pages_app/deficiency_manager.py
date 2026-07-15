"""지적·오동작 관리 — 별지5/6/9를 단일 통합 리스트로 표시 + 조치 입력 진입."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_t

import streamlit as st

from lib import data
from lib.inspection_dialog import (
    action_input_dialog, malfunction_dialog, new_inspection_dialog,
)
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 통합 row 컬럼 비율 (v1.8: 내용 컬럼은 행 펼침으로 이동, 끝에 펼침 토글)
# [점검ID, 작업ID, 구분, 일자, 장소·시설, 점검종류, 상태, 통보서번호, 작업, 내용토글]
COL_RATIOS = [1.1, 1.0, 0.9, 1.0, 1.3, 1.4, 1.0, 1.1, 1.1, 0.6]


@dataclass
class UnifiedRow:
    """통합 리스트의 단일 row."""
    type: str           # "지적사항" / "통보서" / "오동작"
    date: date_t
    location: str
    category: str       # 점검종류 / 시설구분
    content: str        # 지적사항 / 통보서 issue / 오동작 내용
    status: str         # 현장조치 또는 조치 결과
    notice_no: str      # 별지6 통보서 번호 (없으면 "-")
    raw_id: str         # 원본 식별자 (조치 버튼 key용)
    action_done: bool   # 조치 완료 여부 (별지6만 의미 있음)
    task_id: str        # v1.4: 회차 Task 매핑 (없으면 "-")
    round_id: str       # v1.5+: 점검 ID (task → round_id, 없으면 "-")


def _build_unified_rows() -> list[UnifiedRow]:
    """별지5 지적사항(조치 단계 흡수) + 별지9 오동작을 통합 row로 변환.
    v1.5: 별지6 Notice 의존 제거 — Deficiency 자체 action_* 필드만 사용.
    v1.5+: task_id → round_id 매핑으로 '점검 ID' 컬럼도 채움."""
    rows: list[UnifiedRow] = []

    # task_id → round_id (점검 ID) lookup 한 번만 로드
    task_round_map = {t.task_id: (t.round_id or "") for t in data.load_tasks()}

    # 별지5 지적사항 — 조치 단계는 Deficiency 자체에서 (구 별지6 흡수)
    for d in data.load_deficiencies():
        if d.resolution == "완료" and not d.notice_no:
            # 양호 결과만 등록된 행 (불량 아님)
            status = "완료"
        elif d.action_done:
            # 현장 즉시 조치 또는 후속 조치 완료
            status = "조치 완료" if d.notice_no else "완료"
        elif d.notice_no:
            # 통보서 발급됐고 미조치
            status = "조치 대기"
        else:
            status = d.resolution

        rows.append(UnifiedRow(
            type="지적사항",
            date=d.inspection_date,
            location=f"{d.floor} / {d.zone}",
            category=", ".join(d.inspection_types),
            content=d.issue,
            status=status,
            notice_no=d.notice_no or "-",
            raw_id=d.deficiency_id,
            action_done=d.action_done,
            task_id=d.task_id or "-",
            round_id=(task_round_map.get(d.task_id, "") or "-") if d.task_id else "-",
        ))

    # 별지9 오동작 (v1.5+: 등록/조치 분리)
    for m in data.load_malfunctions():
        status = "조치 완료" if m.action_done else "조치 대기"
        rows.append(UnifiedRow(
            type="오동작",
            date=m.occurred_on,
            location=m.category,
            category="—",
            content=m.detail,
            status=status,
            notice_no="-",
            raw_id=m.malfunction_id,
            action_done=m.action_done,
            task_id=m.task_id or "-",
            round_id=(task_round_map.get(m.task_id, "") or "-") if m.task_id else "-",
        ))

    rows.sort(key=lambda r: r.date, reverse=True)
    return rows


def _type_badge(t: str) -> str:
    color = {
        "지적사항": "#1D4ED8",
        "통보서":   "#B45309",
        "오동작":   "#DC2626",
    }.get(t, "#475569")
    bg = {
        "지적사항": "#DBEAFE",
        "통보서":   "#FEF3C7",
        "오동작":   "#FEE2E2",
    }.get(t, "#F1F5F9")
    return (
        f"<span style='background:{bg}; color:{color}; "
        f"padding:0.18rem 0.55rem; border-radius:999px; "
        f"font-size:0.75rem; font-weight:700;'>{t}</span>"
    )


def _table_header() -> str:
    return (
        "<div style='display:grid; "
        f"grid-template-columns: {' '.join(f'{r}fr' for r in COL_RATIOS)}; "
        "gap: 0.4rem; padding: 0.6rem 0.4rem; "
        "color:#64748B; font-size:0.78rem; font-weight:600; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<div>점검 ID</div>"
        "<div>작업 ID</div>"
        "<div>구분</div>"
        "<div>일자</div>"
        "<div>장소·시설</div>"
        "<div>점검종류</div>"
        "<div>상태</div>"
        "<div>통보서 번호</div>"
        "<div>작업</div>"
        "<div>내용</div>"
        "</div>"
    )


def render() -> None:
    # v1.5+ QR 첫 스캔으로 PENDING → ASSIGNED 자동 전환된 경우 안내 (app.py에서 set)
    just_assigned = st.session_state.pop("_qr_just_assigned", None)
    if just_assigned:
        st.toast(
            f"QR 첫 스캔 인식 — {just_assigned} 가 ASSIGNED(부착 완료)로 전환되었습니다.",
            icon="✅",
        )

    notices = data.load_notices()
    notice_map = {n.notice_no: n for n in notices}

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "작업 조치 관리",
            "별지5 지적사항의 조치 단계를 처리하고 별지9 오동작을 관리합니다.",
        )
    # 외부에서 설정된 트리거 (QR deeplink / 시설 관리에서 진입)
    auto_open = st.session_state.get("_open_inspect_dialog", False)
    insp_clicked = False

    with action_col:
        if st.button("신규 점검 추가", type="primary",
                     use_container_width=True, key="open_new_inspection"):
            insp_clicked = True

    if st.session_state.pop("just_submitted_inspection", False):
        st.success("점검 결과가 저장되었습니다.")

    if auto_open or insp_clicked:
        st.session_state["_open_inspect_dialog"] = False
        new_inspection_dialog()

    # [조치 입력] 버튼 트리거 — Deficiency 직접 모달
    open_action = st.session_state.pop("_open_action_input", None)
    if open_action:
        action_input_dialog(open_action)

    just_acted = st.session_state.pop("just_recorded_action", None)
    if just_acted:
        st.success(f"{just_acted} 조치 결과가 저장되었습니다.")

    # 오동작 조치 입력 모달 트리거 (v1.5+)
    open_mal_action = st.session_state.pop("_open_malfunction_action", None)
    if open_mal_action:
        from lib.inspection_dialog import malfunction_action_dialog
        malfunction_action_dialog(open_mal_action)

    just_mal_acted = st.session_state.pop("just_recorded_malfunction_action", None)
    if just_mal_acted:
        st.success(f"{just_mal_acted} 오동작 조치가 저장되었습니다.")

    # KPI
    all_rows = _build_unified_rows()
    cnt_def = sum(1 for r in all_rows if r.type == "지적사항")
    cnt_mal = sum(1 for r in all_rows if r.type == "오동작")
    cnt_notice = len(notices)
    cnt_pending = sum(1 for r in all_rows if r.status == "조치 대기")

    action_rate = data.notice_action_rate()
    render_kpi_row([
        ("전체 항목", f"{len(all_rows)}", f"지적 {cnt_def} · 오동작 {cnt_mal}", "default"),
        ("지적사항", f"{cnt_def}", "별지5", "default"),
        ("통보서 발급", f"{cnt_notice}", f"조치 대기 {cnt_pending}",
         "alert" if cnt_pending else "default"),
        ("오동작", f"{cnt_mal}", "별지9", "default"),
        ("작업 조치율",
         f"{action_rate:.1f}%" if action_rate is not None else "—",
         "조치 완료 / 발급 통보서", "default"),
    ], scrollable=True)

    # 필터
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    fcol1, fcol2, _ = st.columns([1, 1, 3])
    with fcol1:
        type_filter = st.selectbox(
            "구분",
            ["전체", "지적사항", "오동작", "조치 대기만"],
            label_visibility="collapsed",
            key="unified_type",
        )
    with fcol2:
        sort_opt = st.selectbox(
            "정렬",
            ["최신순", "오래된순"],
            label_visibility="collapsed",
            key="unified_sort",
        )

    rows = all_rows
    if type_filter == "조치 대기만":
        rows = [r for r in rows if r.status == "조치 대기"]
    elif type_filter != "전체":
        rows = [r for r in rows if r.type == type_filter]
    if sort_opt == "오래된순":
        rows = list(reversed(rows))

    # 테이블
    st.markdown(_table_header(), unsafe_allow_html=True)

    for r in rows:
        cols = st.columns(COL_RATIOS, vertical_alignment="center")
        with cols[0]:
            rid_color = "#1D4ED8" if r.round_id != "-" else "#94A3B8"
            st.markdown(
                f"<span style='color:{rid_color}; font-size:0.82rem; "
                f"font-weight:600;'>{r.round_id}</span>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            tid_color = "#334155" if r.task_id != "-" else "#94A3B8"
            st.markdown(
                f"<span style='color:{tid_color}; font-size:0.85rem;'>{r.task_id}</span>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(_type_badge(r.type), unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f"<span style='color:#334155;'>{fmt_date(r.date)}</span>",
                        unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f"<b style='color:#0F172A;'>{r.location}</b>",
                        unsafe_allow_html=True)
        with cols[5]:
            st.markdown(f"<span style='color:#334155;'>{r.category}</span>",
                        unsafe_allow_html=True)
        with cols[6]:
            if r.status == "완료":
                st.markdown("<span style='color:#16A34A; font-weight:600;'>✓ 완료</span>",
                            unsafe_allow_html=True)
            elif r.status == "조치 완료":
                st.markdown("<span style='color:#16A34A; font-weight:600;'>✓ 조치 완료</span>",
                            unsafe_allow_html=True)
            elif r.status == "조치 대기":
                st.markdown("<span style='color:#DC2626; font-weight:600;'>● 조치 대기</span>",
                            unsafe_allow_html=True)
            elif r.status == "불가":
                st.markdown(badge("불가"), unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:#334155;'>{r.status}</span>",
                            unsafe_allow_html=True)
        with cols[7]:
            no_color = "#1D4ED8" if r.notice_no != "-" else "#94A3B8"
            st.markdown(
                f"<span style='color:{no_color}; font-weight:600;'>{r.notice_no}</span>",
                unsafe_allow_html=True,
            )
        with cols[8]:
            # 조치 대기 row에 "조치 입력 →" — 지적사항 / 오동작 분기
            if r.status == "조치 대기" and r.type == "지적사항":
                if st.button("조치 입력 →", key=f"act_{r.type}_{r.raw_id}",
                             type="primary", use_container_width=True):
                    st.session_state["_open_action_input"] = r.raw_id
                    st.rerun()
            elif r.status == "조치 대기" and r.type == "오동작":
                if st.button("조치 입력 →", key=f"act_{r.type}_{r.raw_id}",
                             type="primary", use_container_width=True):
                    st.session_state["_open_malfunction_action"] = r.raw_id
                    st.rerun()
            else:
                st.markdown("<span style='color:#94A3B8;'>-</span>",
                            unsafe_allow_html=True)
        with cols[9]:
            # 내용 펼침 토글 (기본 접힘)
            _exp_key = f"def_expand_{r.type}_{r.raw_id}"
            _expanded = st.session_state.get(_exp_key, False)
            if st.button("▾" if _expanded else "▸",
                         key=f"exp_{r.type}_{r.raw_id}", use_container_width=True,
                         help="내용 접기" if _expanded else "내용 펼치기"):
                st.session_state[_exp_key] = not _expanded
                st.rerun()

        # 펼침 시 — 내용 전체 폭으로 (줄바꿈)
        if st.session_state.get(f"def_expand_{r.type}_{r.raw_id}", False):
            st.markdown(
                "<div style='background:#F8FAFC; border:1px solid #E2E8F0; "
                "border-radius:8px; padding:0.6rem 0.9rem; margin:0.1rem 0 0.5rem; "
                "color:#0F172A; font-size:0.9rem; line-height:1.7; "
                "white-space:pre-wrap; word-break:break-word;'>"
                "<span style='color:#64748B; font-size:0.78rem; font-weight:600;'>"
                f"내용</span><br>{r.content}</div>",
                unsafe_allow_html=True,
            )
