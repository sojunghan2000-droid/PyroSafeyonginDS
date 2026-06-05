"""대시보드 페이지 — 3탭 구조 (현황 요약 · 도면 그리드 · 개별 층 상세)."""
from __future__ import annotations

import streamlit as st

from lib import data
from lib.floor_map import make_floor_figure
from lib.ui import badge, fmt_date, page_header, render_kpi_row
from pages_app.floor_map import FLOOR_ORDER, _render_grid


def _sorted_floors(eq_all) -> list[str]:
    return sorted(
        {e.floor for e in eq_all},
        key=lambda f: (FLOOR_ORDER.index(f) if f in FLOOR_ORDER else 999, f),
    )


def _summary_tab() -> None:
    """탭 1 — 기존 대시보드 요약 (KPI + 별지5 + 예정 태스크)."""
    eq_kpi = data.equipment_kpis()
    tk_kpi = data.task_kpis()

    render_kpi_row([
        ("전체 시설", f"{eq_kpi['total']:,}", f"이번 달 +{eq_kpi['new_this_month']}건", "default"),
        ("미조치 항목", f"{eq_kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("지연 태스크", f"{tk_kpi['overdue']}", "즉시 조치 필요", "alert"),
        ("QR 적용률", f"{eq_kpi['qr_coverage']:.1f}%", "QR 부착률", "default"),
    ])

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

    col_l, col_r = st.columns(2)

    def _table_card(title: str, header_html: str, rows_html: str) -> str:
        return (
            "<div class='ps-table'>"
            f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.4rem;'>{title}</div>"
            f"{header_html}{rows_html}</tbody></table>"
            "</div>"
        )

    with col_l:
        defs = data.load_deficiencies()
        header = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.75rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.5rem 0.3rem;'>점검일</th>"
            "<th style='padding:0.5rem 0.3rem;'>장소</th>"
            "<th style='padding:0.5rem 0.3rem;'>지적사항</th>"
            "<th style='padding:0.5rem 0.3rem;'>조치</th>"
            "</tr></thead><tbody>"
        )
        body = "".join(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.6rem 0.3rem; color:#334155;'>{fmt_date(d.inspection_date)}</td>"
            f"<td style='padding:0.6rem 0.3rem; color:#0F172A;'>{d.floor}/{d.zone}</td>"
            f"<td style='padding:0.6rem 0.3rem; color:#0F172A;'>{d.issue}</td>"
            f"<td style='padding:0.6rem 0.3rem;'>{badge(d.resolution)}</td>"
            "</tr>"
            for d in defs[:6]
        )
        st.markdown(_table_card("최근 지적사항 (별지5)", header, body), unsafe_allow_html=True)

    with col_r:
        tasks = data.load_tasks()
        upcoming = sorted(
            [t for t in tasks if t.status in ("Scheduled", "In Progress", "Overdue")],
            key=lambda t: t.due_date,
        )[:6]
        header = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.75rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.5rem 0.3rem;'>Task</th>"
            "<th style='padding:0.5rem 0.3rem;'>Due</th>"
            "<th style='padding:0.5rem 0.3rem;'>Status</th>"
            "</tr></thead><tbody>"
        )
        body = "".join(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.6rem 0.3rem; color:#0F172A; font-weight:600;'>{t.equipment_label}</td>"
            f"<td style='padding:0.6rem 0.3rem; color:#334155;'>{fmt_date(t.due_date)}</td>"
            f"<td style='padding:0.6rem 0.3rem;'>{badge(t.status)}</td>"
            "</tr>"
            for t in upcoming
        )
        st.markdown(_table_card("예정 점검 태스크", header, body), unsafe_allow_html=True)


def _grid_tab() -> None:
    """탭 2 — 도면 그리드 썸네일 (11개 층)."""
    eq_all = data.load_equipment()
    _render_grid(eq_all)


def _detail_tab() -> None:
    """탭 3 — 셀렉트박스 + 개별 층 상세."""
    eq_all = data.load_equipment()
    floors = _sorted_floors(eq_all)
    if not floors:
        st.info("등록된 장비가 없습니다.")
        return

    # 그리드 탭에서 이미 선택된 층 있으면 사전 선택
    default_idx = 0
    pre = st.session_state.get("floor_map_selected")
    if pre and pre in floors:
        default_idx = floors.index(pre)

    sel_col, _, _ = st.columns([1.2, 2, 2])
    with sel_col:
        floor = st.selectbox("층 선택", options=floors, index=default_idx, key="dash_floor_sel")

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

    fig = make_floor_figure(floor_eq, floor, zones or [])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        "<div style='color:#64748B; font-size:0.85rem; margin-top:0.4rem;'>"
        "● 초록=PASS  ● 빨강=FAIL  ● 파랑=DUE · 마커 hover 시 상세 표시</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem;'>{floor}층 장비 리스트</div>",
        unsafe_allow_html=True,
    )

    header = (
        "<table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<th style='padding:0.5rem 0.3rem;'>위치</th>"
        "<th style='padding:0.5rem 0.3rem;'>장비</th>"
        "<th style='padding:0.5rem 0.3rem;'>상태</th>"
        "<th style='padding:0.5rem 0.3rem;'>최근 점검일</th>"
        "</tr></thead><tbody>"
    )
    body = "".join(
        "<tr style='border-bottom:1px solid #F1F5F9;'>"
        f"<td style='padding:0.7rem 0.3rem; font-weight:600; color:#0F172A;'>{e.location_id}</td>"
        f"<td style='padding:0.7rem 0.3rem; color:#0F172A;'>{e.equipment_name}<br>"
        f"<span style='color:#64748B; font-size:0.8rem;'>{e.category}</span></td>"
        f"<td style='padding:0.7rem 0.3rem;'>{badge(e.health_status)}</td>"
        f"<td style='padding:0.7rem 0.3rem; color:#334155;'>{fmt_date(e.last_inspection)}</td>"
        "</tr>"
        for e in floor_eq
    )
    st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)


def render() -> None:
    page_header(
        "대시보드",
        "용인덕성 AI DC 소방안전 점검 통합 현황 · 2026-05-27.",
    )

    tab_summary, tab_grid, tab_detail = st.tabs(
        ["현황 요약", "도면 그리드", "개별 층"]
    )
    with tab_summary:
        _summary_tab()
    with tab_grid:
        _grid_tab()
    with tab_detail:
        _detail_tab()
