"""대시보드 페이지 — 3탭 구조 (현황 요약 · Location · 개별 층 상세)."""
from __future__ import annotations

import base64
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from lib import data
from lib.floor_map import make_floor_figure
from lib.ui import TASK_STATUS_KO, badge, fmt_date, page_header, render_kpi_row
from pages_app.floor_map import FLOOR_ORDER, _render_grid


# 새 8층 체계 (PDF 도면 기준) — Location 탭에서 사용
LOCATION_FLOORS = ["PIT", "B2", "B1", "1F", "2F", "3F", "4F", "Roof"]
ASSETS_FLOORS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"


def _sorted_floors(eq_all) -> list[str]:
    return sorted(
        {e.floor for e in eq_all},
        key=lambda f: (FLOOR_ORDER.index(f) if f in FLOOR_ORDER else 999, f),
    )


def _summary_tab() -> None:
    """탭 1 — 기존 대시보드 요약 (KPI + 별지5 + 예정 태스크)."""
    eq_kpi = data.equipment_kpis()
    tk_kpi = data.task_kpis()
    action_rate = data.notice_action_rate()

    render_kpi_row([
        ("전체 시설", f"{eq_kpi['total']:,}", f"이번 달 +{eq_kpi['new_this_month']}건", "default"),
        ("미조치 항목", f"{eq_kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("지연 태스크", f"{tk_kpi['overdue']}", "즉시 조치 필요", "alert"),
        ("작업 조치율", f"{action_rate:.1f}%" if action_rate is not None else "—",
         "조치 완료 / 발급 통보서", "default"),
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
            f"<td style='padding:0.6rem 0.3rem;'>{badge(TASK_STATUS_KO.get(t.status, t.status))}</td>"
            "</tr>"
            for t in upcoming
        )
        st.markdown(_table_card("예정 점검 태스크", header, body), unsafe_allow_html=True)


def _floor_stats(floor: str, eq_all, notices) -> dict:
    """한 층의 KPI(장비/FAIL/DUE/PASS/미조치 통보서) + 심각도 점수."""
    items = [e for e in eq_all if e.floor == floor]
    fail_n = sum(1 for e in items if e.health_status == "FAIL")
    due_n = sum(1 for e in items if e.health_status == "DUE")
    pass_n = sum(1 for e in items if e.health_status == "PASS")
    pending_notices = sum(
        1 for n in notices if n.floor == floor and not n.action_done
    )
    severity = fail_n * 3 + pending_notices * 2 + due_n
    return {
        "items": items, "fail": fail_n, "due": due_n, "pass": pass_n,
        "pending_notices": pending_notices, "severity": severity,
        "total": len(items),
    }


def _card_color(stats: dict) -> tuple[str, str]:
    """심각도에 따른 좌측 보더 색 + 라벨."""
    if stats["fail"] > 0:
        return "#DC2626", "불량"           # 빨강
    if stats["pending_notices"] > 0:
        return "#F97316", "통보서 대기"     # 주황
    if stats["due"] > 0:
        return "#F59E0B", "점검 도래"       # 노랑
    if stats["total"] == 0:
        return "#94A3B8", "장비 없음"       # 회색
    return "#10B981", "정상"               # 초록


def _floor_image_uri(floor: str) -> str | None:
    """assets/floors/{floor}.png를 data URI로 (plotly 백그라운드용)."""
    p = ASSETS_FLOORS_DIR / f"{floor}.png"
    if not p.exists():
        return None
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _make_floor_plan_figure(floor: str) -> go.Figure | None:
    """도면 PNG를 배경으로 한 plotly 차트 (줌·팬·핀치줌 활성)."""
    uri = _floor_image_uri(floor)
    if uri is None:
        return None
    # PNG는 전부 2978x2105 — 좌표계를 그 픽셀 기준으로 잡는다.
    W, H = 2978, 2105
    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=H, sizex=W, sizey=H,
        sizing="stretch", layer="below", opacity=1.0,
    ))
    fig.update_xaxes(visible=False, range=[0, W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#F8FAFC",
        height=620,
        dragmode="pan",
    )
    return fig


@st.dialog(" ", width="large")
def _floor_detail_dialog(floor: str) -> None:
    """선택된 층의 도면 + 장비 리스트를 큰 모달로 표시."""
    eq_all = data.load_equipment()
    notices = data.load_notices()
    stats = _floor_stats(floor, eq_all, notices)
    border, label = _card_color(stats)

    st.markdown(
        f"<div style='display:flex; align-items:center; gap:0.7rem; margin:-0.5rem 0 0.6rem;'>"
        f"<div style='font-weight:700; font-size:1.4rem; color:#0F172A;'>{floor} 평면도</div>"
        f"<div style='background:{border}1A; color:{border}; "
        f"border:1px solid {border}; padding:0.2rem 0.55rem; border-radius:999px; "
        f"font-size:0.8rem; font-weight:600;'>{label}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 미니 KPI (4개)
    render_kpi_row([
        (f"{floor} 장비", f"{stats['total']}", "총 등록 시설", "default"),
        ("불량(FAIL)", f"{stats['fail']}", "즉시 조치 필요",
         "alert" if stats['fail'] else "default"),
        ("점검 도래(DUE)", f"{stats['due']}", "점검 임박",
         "alert" if stats['due'] else "default"),
        ("미조치 통보서", f"{stats['pending_notices']}", "조치 대기 건",
         "alert" if stats['pending_notices'] else "default"),
    ])

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    fig = _make_floor_plan_figure(floor)
    if fig is None:
        st.warning(
            f"`{floor}` 도면 이미지가 없습니다. "
            f"`scripts/convert_floor_pdfs.py`를 실행해 도면을 생성해 주세요."
        )
    else:
        # scrollZoom=True → 휠/핀치 줌 활성. modeBarButtonsToAdd로 그리기 도구는 숨김.
        st.plotly_chart(
            fig, use_container_width=True,
            config={
                "scrollZoom": True,
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": [
                    "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
                ],
            },
            key=f"floor_plan_{floor}",
        )
        st.markdown(
            "<div style='color:#64748B; font-size:0.78rem; margin-top:-0.5rem;'>"
            "마우스 휠 / 모바일 핀치 확대 · 드래그로 이동 · 홈 아이콘으로 초기화 · "
            "장비 마커 표시는 v1.1에서 도입(위치 spot 객체 도입 후)</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.02rem;'>"
        f"{floor} 장비 리스트 ({stats['total']}건)</div>",
        unsafe_allow_html=True,
    )

    if not stats["items"]:
        st.info("이 층에 등록된 장비가 없습니다.")
        return

    header = (
        "<table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<th style='padding:0.5rem 0.3rem;'>위치 ID</th>"
        "<th style='padding:0.5rem 0.3rem;'>장비</th>"
        "<th style='padding:0.5rem 0.3rem;'>카테고리</th>"
        "<th style='padding:0.5rem 0.3rem;'>상태</th>"
        "<th style='padding:0.5rem 0.3rem;'>최근 점검일</th>"
        "</tr></thead><tbody>"
    )
    body = "".join(
        "<tr style='border-bottom:1px solid #F1F5F9;'>"
        f"<td style='padding:0.65rem 0.3rem; font-weight:600; color:#0F172A;'>{e.location_id}</td>"
        f"<td style='padding:0.65rem 0.3rem; color:#0F172A;'>{e.equipment_name}</td>"
        f"<td style='padding:0.65rem 0.3rem; color:#475569;'>{e.category}</td>"
        f"<td style='padding:0.65rem 0.3rem;'>{badge(e.health_status)}</td>"
        f"<td style='padding:0.65rem 0.3rem; color:#334155;'>{fmt_date(e.last_inspection)}</td>"
        "</tr>"
        for e in stats["items"]
    )
    st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)


def _location_card_html(floor: str, stats: dict) -> str:
    """카드 본문 HTML (KPI 행 + 미니 상태 칩)."""
    border, label = _card_color(stats)
    return (
        f"<div style='background:#FFFFFF; border:1px solid #E2E8F0; "
        f"border-left:6px solid {border}; border-radius:10px; "
        f"padding:0.85rem 1rem 0.7rem; min-height:130px;'>"
        f"<div style='display:flex; justify-content:space-between; "
        f"align-items:baseline; margin-bottom:0.45rem;'>"
        f"<div style='font-size:1.3rem; font-weight:700; color:#0F172A;'>{floor}</div>"
        f"<div style='background:{border}15; color:{border}; "
        f"padding:0.15rem 0.5rem; border-radius:999px; "
        f"font-size:0.72rem; font-weight:600;'>{label}</div>"
        f"</div>"
        f"<div style='display:flex; gap:0.6rem; flex-wrap:wrap; "
        f"color:#475569; font-size:0.83rem; margin-bottom:0.5rem;'>"
        f"<span><b style='color:#0F172A;'>{stats['total']}</b> 장비</span>"
        f"<span style='color:#DC2626;'>FAIL <b>{stats['fail']}</b></span>"
        f"<span style='color:#F59E0B;'>DUE <b>{stats['due']}</b></span>"
        f"<span style='color:#F97316;'>통보 <b>{stats['pending_notices']}</b></span>"
        f"</div>"
        f"</div>"
    )


def _grid_tab() -> None:
    """탭 2 — Location: 8개 층 카드 그리드 + 도면 모달."""
    eq_all = data.load_equipment()
    notices = data.load_notices()

    all_stats = {fl: _floor_stats(fl, eq_all, notices) for fl in LOCATION_FLOORS}
    total = sum(s["total"] for s in all_stats.values())
    fail_total = sum(s["fail"] for s in all_stats.values())
    due_total = sum(s["due"] for s in all_stats.values())
    pending_total = sum(s["pending_notices"] for s in all_stats.values())

    render_kpi_row([
        ("총 장비", f"{total}", f"{len(LOCATION_FLOORS)}개 층", "default"),
        ("불량", f"{fail_total}", "즉시 조치 필요",
         "alert" if fail_total else "default"),
        ("점검 도래", f"{due_total}", "DUE 임박",
         "alert" if due_total else "default"),
        ("통보서 대기", f"{pending_total}", "조치 대기 건",
         "alert" if pending_total else "default"),
    ])

    st.markdown(
        "<div style='color:#64748B; font-size:0.85rem; margin:0.8rem 0 0.4rem;'>"
        "층 카드 → [상세 보기] 클릭 시 도면 + 장비 리스트 팝업. "
        "좌측 컬러 보더: 빨강 FAIL · 주황 통보서 대기 · 노랑 DUE · 초록 정상.</div>",
        unsafe_allow_html=True,
    )

    # 4열 × 2행 카드 그리드
    GRID_COLS = 4
    pending_open: str | None = None
    for row_start in range(0, len(LOCATION_FLOORS), GRID_COLS):
        row = LOCATION_FLOORS[row_start:row_start + GRID_COLS]
        cols = st.columns(GRID_COLS)
        for col, fl in zip(cols, row):
            with col:
                st.markdown(_location_card_html(fl, all_stats[fl]),
                            unsafe_allow_html=True)
                if st.button(f"{fl} 상세 보기 →", key=f"loc_card_{fl}",
                             use_container_width=True):
                    pending_open = fl

    if pending_open:
        _floor_detail_dialog(pending_open)


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
        f"용인덕성 AI DC 소방안전 점검 통합 현황 · {data.TODAY.isoformat()}.",
    )

    tab_summary, tab_grid, tab_detail = st.tabs(
        ["현황 요약", "Location", "개별 층"]
    )
    with tab_summary:
        _summary_tab()
    with tab_grid:
        _grid_tab()
    with tab_detail:
        _detail_tab()
