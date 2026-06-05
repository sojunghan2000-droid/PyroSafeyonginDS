"""시설 관리 페이지 — 테이블 각 행에 QR 모달 진입 버튼."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import data
from lib.qr import make_qr, payload_for, qr_png_bytes, sticker_sheet_pdf
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 테이블 컬럼 비율 (총합 = 1)
COL_RATIOS = [1.1, 2.0, 1.0, 1.1, 0.9, 1.0]


def _table_header_html() -> str:
    return (
        "<div style='display:grid; "
        f"grid-template-columns: {' '.join(f'{r}fr' for r in COL_RATIOS)}; "
        "gap: 0.4rem; padding: 0.6rem 0.4rem; "
        "color:#64748B; font-size:0.78rem; font-weight:600; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<div>위치 ID</div>"
        "<div>시설 종류</div>"
        "<div>QR 상태</div>"
        "<div>최근 점검일</div>"
        "<div>Inspection Status</div>"
        "<div>작업</div>"
        "</div>"
    )


@st.dialog("QR 코드 미리보기", width="large")
def _qr_dialog(equipment_id: str) -> None:
    """선택된 장비의 QR 모달."""
    eq = next((x for x in data.load_equipment() if x.equipment_id == equipment_id), None)
    if not eq:
        st.error("장비를 찾을 수 없습니다.")
        return

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.image(make_qr(eq, box_size=10), width=240)
    with col_b:
        st.markdown(
            f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.5rem;'>"
            f"{eq.equipment_name}</div>"
            f"<div style='color:#475569; font-size:0.93rem; line-height:1.7;'>"
            f"<b>장비 ID</b> · {eq.equipment_id}<br>"
            f"<b>위치(구역)</b> · {eq.location_id} ({eq.floor} / {eq.zone})<br>"
            f"<b>카테고리</b> · {eq.category}<br>"
            f"<b>시리얼</b> · {eq.serial}<br>"
            f"<b>현재 상태</b> · {badge(eq.health_status)} {badge(eq.qr_status)}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='color:#64748B; font-size:0.85rem; margin-top:0.75rem;'>"
            "QR 페이로드 (스캔 시 열리는 URL)</div>",
            unsafe_allow_html=True,
        )
        st.code(payload_for(eq), language="text")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    dl_col, go_col = st.columns(2)
    with dl_col:
        st.download_button(
            "PNG 다운로드",
            data=qr_png_bytes(eq, box_size=12),
            file_name=f"QR_{eq.equipment_id}_{eq.location_id}.png",
            mime="image/png",
            use_container_width=True,
            key=f"qr_dlg_dl_{eq.equipment_id}",
        )
    with go_col:
        if st.button(
            "이 장비 점검 입력 →",
            key=f"qr_dlg_goto_{eq.equipment_id}",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["inspect_target"] = eq.equipment_id
            st.session_state["page"] = "deficiencies"
            st.session_state["_open_inspect_dialog"] = True
            st.rerun()


def render() -> None:
    eq = data.load_equipment()
    kpi = data.equipment_kpis()

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "시설 관리",
            "전 층 소방안전 시설 자산의 실시간 현황과 QR 부착 상태를 관리합니다.",
        )
    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            st.download_button(
                "QR 스티커 일괄 출력",
                data=sticker_sheet_pdf(eq),
                file_name="QR 스티커 시트 (4x6).pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with b2:
            st.button("신규 장비 등록", type="primary", use_container_width=True)

    render_kpi_row([
        ("전체 시설", f"{kpi['total']:,}", f"이번 달 +{kpi['new_this_month']}건", "default"),
        ("최근 점검", f"{kpi['recently_inspected']:,}", "지난 48시간", "default"),
        ("미조치 항목", f"{kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("QR 적용률", f"{kpi['qr_coverage']:.1f}%", "QR 부착률", "default"),
    ])

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    f1, f2, _, tab_col = st.columns([0.8, 0.8, 0.4, 3.5])
    with f1:
        floor_filter = st.selectbox(
            "Filter",
            ["전체 층"] + sorted({e.floor for e in eq}),
            label_visibility="collapsed",
        )
    with f2:
        sort_by = st.selectbox(
            "Sort",
            ["최근 점검순", "위치 순", "상태 순"],
            label_visibility="collapsed",
        )
    with tab_col:
        view = st.radio(
            "view",
            ["전체", "소화기·소화장치", "경보·감지", "소화전"],
            horizontal=True,
            label_visibility="collapsed",
        )

    cat_filter_map = {
        "소화기·소화장치": {"소화기", "확산소화기", "간이소화장치"},
        "경보·감지": {"비상경보장치", "가스누설경보기", "감지기", "발신기", "수신기"},
        "소화전": {"소화전"},
    }

    rows = eq
    if floor_filter != "전체 층":
        rows = [e for e in rows if e.floor == floor_filter]
    if view != "전체":
        rows = [e for e in rows if e.category in cat_filter_map.get(view, set())]

    if sort_by == "최근 점검순":
        rows = sorted(rows, key=lambda e: e.last_inspection or pd.Timestamp.min.date(), reverse=True)
    elif sort_by == "위치 순":
        rows = sorted(rows, key=lambda e: e.location_id)
    else:
        order = {"FAIL": 0, "DUE": 1, "PASS": 2}
        rows = sorted(rows, key=lambda e: order.get(e.health_status, 9))

    # ---------- 테이블 (st.columns 기반) ----------
    st.markdown(_table_header_html(), unsafe_allow_html=True)

    for e in rows:
        cols = st.columns(COL_RATIOS, vertical_alignment="center")
        with cols[0]:
            st.markdown(
                f"<span style='font-weight:600; color:#0F172A;'>{e.location_id}</span>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"<div style='font-weight:600; color:#0F172A;'>{e.equipment_name}</div>"
                f"<div style='color:#64748B; font-size:0.8rem;'>SN: {e.serial}</div>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(badge(e.qr_status), unsafe_allow_html=True)
        with cols[3]:
            st.markdown(
                f"<span style='color:#334155;'>{fmt_date(e.last_inspection)}</span>",
                unsafe_allow_html=True,
            )
        with cols[4]:
            st.markdown(badge(e.health_status), unsafe_allow_html=True)
        with cols[5]:
            if st.button("QR", key=f"qr_btn_{e.equipment_id}", use_container_width=True):
                _qr_dialog(e.equipment_id)

    foot_l, _, foot_r = st.columns([3, 4, 1])
    with foot_l:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.85rem; padding-top:0.6rem;'>"
            f"{kpi['total']:,}개 중 {len(rows)}개 표시</div>",
            unsafe_allow_html=True,
        )
    with foot_r:
        c1, c2 = st.columns(2)
        c1.button("‹", key="eq_prev", use_container_width=True)
        c2.button("›", key="eq_next", use_container_width=True)
