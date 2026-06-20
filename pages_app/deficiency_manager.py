"""지적·오동작 관리 — 별지5/6/9를 단일 통합 리스트로 표시 + 조치 입력 진입."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_t

import streamlit as st

from lib import data
from lib.inspection_dialog import malfunction_dialog, new_inspection_dialog
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 통합 row 컬럼 비율 — 작업 ID 컬럼 추가
COL_RATIOS = [0.9, 1.0, 1.0, 1.3, 2.2, 1.0, 1.1, 1.0, 1.1]


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


def _build_unified_rows() -> list[UnifiedRow]:
    """별지5/9 데이터를 통합 row 리스트로 변환. 별지6 통보서 정보는 별지5 row에 inline."""
    rows: list[UnifiedRow] = []
    notice_map = {n.notice_no: n for n in data.load_notices()}

    # 별지5 지적사항 — 통보서가 있으면 후속조치 상태 inline 표시
    for d in data.load_deficiencies():
        notice = notice_map.get(d.notice_no) if d.notice_no else None
        if d.resolution == "완료":
            # 양호 또는 현장 즉시 조치 완료
            status = "완료"
        elif notice and notice.action_done:
            status = "조치 완료"
        elif notice:
            status = "조치 대기"
        else:
            status = "불가"  # 통보서 매칭 안 됨 (legacy)

        rows.append(UnifiedRow(
            type="지적사항",
            date=d.inspection_date,
            location=f"{d.floor} / {d.zone}",
            category=", ".join(d.inspection_types),
            content=d.issue,
            status=status,
            notice_no=d.notice_no or "-",
            raw_id=d.deficiency_id,
            action_done=notice.action_done if notice else False,
            task_id=d.task_id or "-",
        ))

    # 별지9 오동작 (별도 row 유지)
    for m in data.load_malfunctions():
        rows.append(UnifiedRow(
            type="오동작",
            date=m.occurred_on,
            location=m.category,
            category="—",
            content=m.detail,
            status=m.action or "-",
            notice_no="-",
            raw_id=m.malfunction_id,
            action_done=False,
            task_id=m.task_id or "-",
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
        "<div>구분</div>"
        "<div>일자</div>"
        "<div>장소·시설</div>"
        "<div>점검종류</div>"
        "<div>내용</div>"
        "<div>상태</div>"
        "<div>통보서 번호</div>"
        "<div>작업 ID</div>"
        "<div>작업</div>"
        "</div>"
    )


def render() -> None:
    notices = data.load_notices()
    notice_map = {n.notice_no: n for n in notices}

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "지적·오동작 관리",
            "별지5 지적사항 + 별지6 통보서 + 별지9 오동작을 한 페이지에서 통합 관리합니다.",
        )
    # 외부에서 설정된 트리거 (QR deeplink / 시설 관리에서 진입)
    auto_open = st.session_state.get("_open_inspect_dialog", False)
    auto_open_mal = st.session_state.get("_open_malfunction_dialog", False)
    insp_clicked = False
    mal_clicked = False

    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("신규 점검 추가", type="primary",
                         use_container_width=True, key="open_new_inspection"):
                insp_clicked = True
        with b2:
            if st.button("오동작 등록", use_container_width=True,
                         key="open_new_malfunction"):
                mal_clicked = True

    if st.session_state.pop("just_submitted_inspection", False):
        st.success("점검 결과가 저장되었습니다.")
    if st.session_state.pop("just_submitted_malfunction", False):
        st.success("오동작이 별지9에 등록되었습니다.")

    if auto_open or insp_clicked:
        st.session_state["_open_inspect_dialog"] = False
        new_inspection_dialog()
    elif auto_open_mal or mal_clicked:
        st.session_state["_open_malfunction_dialog"] = False
        malfunction_dialog()

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
            st.markdown(_type_badge(r.type), unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"<span style='color:#334155;'>{fmt_date(r.date)}</span>",
                        unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f"<b style='color:#0F172A;'>{r.location}</b>",
                        unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f"<span style='color:#334155;'>{r.category}</span>",
                        unsafe_allow_html=True)
        with cols[4]:
            st.markdown(f"<span style='color:#0F172A;'>{r.content}</span>",
                        unsafe_allow_html=True)
        with cols[5]:
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
        with cols[6]:
            no_color = "#1D4ED8" if r.notice_no != "-" else "#94A3B8"
            st.markdown(
                f"<span style='color:{no_color}; font-weight:600;'>{r.notice_no}</span>",
                unsafe_allow_html=True,
            )
        with cols[7]:
            tid_color = "#334155" if r.task_id != "-" else "#94A3B8"
            st.markdown(
                f"<span style='color:{tid_color}; font-size:0.85rem;'>{r.task_id}</span>",
                unsafe_allow_html=True,
            )
        with cols[8]:
            # 조치 대기 row에만 "조치 입력 →" 버튼
            if r.status == "조치 대기" and r.notice_no != "-":
                if st.button("조치 입력 →", key=f"act_{r.type}_{r.raw_id}",
                             type="primary", use_container_width=True):
                    st.session_state["focus_notice"] = r.notice_no
                    st.session_state["page"] = "inspection"
                    st.rerun()
            else:
                st.markdown("<span style='color:#94A3B8;'>-</span>",
                            unsafe_allow_html=True)
