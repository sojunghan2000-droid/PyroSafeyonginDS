"""Floor Map — 그리드 ↔ 개별 층 상세 (단일 상태 기반 네비게이션)."""
from __future__ import annotations

import streamlit as st

from lib import data
from lib.floor_map import make_floor_figure
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 그리드 출력 시 층 순서 (지하 → 지상 → 특수)
FLOOR_ORDER = ["B3", "B2", "B1", "P4", "L1", "L2", "2F", "4F", "5F", "6F", "SRV"]
GRID_COLS = 4


def _sorted_floors(eq_all) -> list[str]:
    return sorted(
        {e.floor for e in eq_all},
        key=lambda f: (FLOOR_ORDER.index(f) if f in FLOOR_ORDER else 999, f),
    )


def _render_grid(eq_all) -> None:
    floors = _sorted_floors(eq_all)
    total = len(eq_all)
    fail_n = sum(1 for e in eq_all if e.health_status == "FAIL")
    due_n = sum(1 for e in eq_all if e.health_status == "DUE")
    pass_n = total - fail_n - due_n

    render_kpi_row([
        ("전체 장비", f"{total}", f"{len(floors)}개 층", "default"),
        ("정상", f"{pass_n}", "PASS 상태", "default"),
        ("불량", f"{fail_n}", "즉시 조치 필요", "alert" if fail_n else "default"),
        ("점검 필요", f"{due_n}", "DUE 임박", "default"),
    ])

    st.markdown(
        "<div style='color:#64748B; font-size:0.85rem; margin:0.8rem 0 0.4rem;'>"
        "썸네일 아래 버튼을 눌러 해당 층 상세로 이동. ● 초록=PASS  ● 빨강=FAIL  ● 파랑=DUE</div>",
        unsafe_allow_html=True,
    )

    for row_start in range(0, len(floors), GRID_COLS):
        row_floors = floors[row_start:row_start + GRID_COLS]
        cols = st.columns(GRID_COLS)
        for col, fl in zip(cols, row_floors):
            with col:
                items = [e for e in eq_all if e.floor == fl]
                zones = data.floor_layout(fl)
                fig = make_floor_figure(items, fl, zones, compact=True)
                st.plotly_chart(
                    fig, use_container_width=True,
                    config={"displayModeBar": False},
                    key=f"thumb_{fl}",
                )
                if st.button(
                    f"{fl} 상세 보기",
                    key=f"goto_{fl}",
                    use_container_width=True,
                ):
                    st.session_state["floor_map_selected"] = fl
                    st.rerun()


def _render_detail(eq_all, floor: str) -> None:
    # 뒤로가기 버튼 + 페이지 타이틀
    back_col, title_col = st.columns([0.15, 4])
    with back_col:
        if st.button("←", key="floor_map_back", help="전체 보기로 돌아가기",
                     use_container_width=True):
            st.session_state["floor_map_selected"] = None
            st.rerun()
    with title_col:
        st.markdown(
            f"<div style='font-weight:700; font-size:1.25rem; color:#0F172A;'>"
            f"{floor}층 상세</div>"
            "<div style='color:#64748B; font-size:0.85rem;'>← 버튼으로 전체 보기로 돌아갑니다.</div>",
            unsafe_allow_html=True,
        )

    floor_eq = [e for e in eq_all if e.floor == floor]
    zones = data.floor_layout(floor)
    pass_n = sum(1 for e in floor_eq if e.health_status == "PASS")
    fail_n = sum(1 for e in floor_eq if e.health_status == "FAIL")
    due_n = sum(1 for e in floor_eq if e.health_status == "DUE")
    render_kpi_row([
        (f"{floor}층 장비", f"{len(floor_eq)}", "총 등록 시설", "default"),
        ("정상", f"{pass_n}", "PASS 상태", "default"),
        ("불량", f"{fail_n}", "즉시 조치 필요", "alert" if fail_n else "default"),
        ("점검 필요", f"{due_n}", "DUE 임박", "default"),
    ])

    if not floor_eq:
        st.info(f"{floor} 층에 등록된 장비가 없습니다.")
        return
    if not zones:
        st.warning(f"{floor} 층의 도면 정의가 없어 마커만 표시됩니다.")

    fig = make_floor_figure(floor_eq, floor, zones or [])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        "<div style='color:#64748B; font-size:0.85rem; margin-top:0.4rem;'>"
        "● 초록=PASS  ● 빨강=FAIL  ● 파랑=DUE  · 마커 hover 시 상세 표시</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem;'>"
        f"{floor}층 장비 리스트</div>",
        unsafe_allow_html=True,
    )

    header = (
        "<table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<th style='padding:0.5rem 0.3rem;'>LOCATION</th>"
        "<th style='padding:0.5rem 0.3rem;'>EQUIPMENT</th>"
        "<th style='padding:0.5rem 0.3rem;'>HEALTH</th>"
        "<th style='padding:0.5rem 0.3rem;'>LAST INSPECTION</th>"
        "<th style='padding:0.5rem 0.3rem;'>좌표 (x, y)</th>"
        "</tr></thead><tbody>"
    )
    body = "".join(
        "<tr style='border-bottom:1px solid #F1F5F9;'>"
        f"<td style='padding:0.7rem 0.3rem; font-weight:600; color:#0F172A;'>{e.location_id}</td>"
        f"<td style='padding:0.7rem 0.3rem; color:#0F172A;'>{e.equipment_name}<br>"
        f"<span style='color:#64748B; font-size:0.8rem;'>{e.category}</span></td>"
        f"<td style='padding:0.7rem 0.3rem;'>{badge(e.health_status)}</td>"
        f"<td style='padding:0.7rem 0.3rem; color:#334155;'>{fmt_date(e.last_inspection)}</td>"
        f"<td style='padding:0.7rem 0.3rem; color:#64748B; font-size:0.85rem;'>"
        f"({e.pixel_x:.0f}, {e.pixel_y:.0f})</td>"
        "</tr>"
        for e in floor_eq
    )
    st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)


def render() -> None:
    page_header(
        "도면",
        "도면 위에서 QR 장비 위치와 점검 상태를 한눈에 확인.",
    )

    eq_all = data.load_equipment()
    selected = st.session_state.get("floor_map_selected")

    if selected and any(e.floor == selected for e in eq_all):
        _render_detail(eq_all, selected)
    else:
        _render_grid(eq_all)
