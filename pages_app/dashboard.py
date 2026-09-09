"""대시보드 페이지 — 2탭 구조 (현황 요약 · 층별 도면)."""
from __future__ import annotations

import base64
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from lib import data
from lib.ui import TASK_STATUS_KO, badge, fmt_date, page_header, render_kpi_row


# 새 8층 체계 (PDF 도면 기준) — Location 탭에서 사용
LOCATION_FLOORS = ["PIT", "B2", "B1", "1F", "2F", "3F", "4F", "Roof"]
ASSETS_FLOORS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"


def _summary_tab() -> None:
    """탭 1 — 기존 대시보드 요약 (KPI + 별지5 + 예정 태스크)."""
    eq_kpi = data.equipment_kpis()
    tk_kpi = data.task_kpis()
    action_rate = data.notice_action_rate()

    qr_coverage = eq_kpi.get("qr_coverage", 0.0)
    qr_variant = "alert" if qr_coverage < 100 else "default"
    qr_hint = "QR 부착률" if qr_coverage >= 100 else "미부착 장비 있음"
    render_kpi_row([
        ("전체 시설", f"{eq_kpi['total']:,}", f"이번 달 +{eq_kpi['new_this_month']}건", "default"),
        ("미조치 항목", f"{eq_kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("지연 태스크", f"{tk_kpi['overdue']}", "즉시 조치 필요", "alert"),
        ("작업 조치율", f"{action_rate:.1f}%" if action_rate is not None else "—",
         "조치 완료 / 발급 통보서", "default"),
        ("QR 적용률", f"{qr_coverage:.1f}%", qr_hint, qr_variant),
    ], scrollable=True)

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


_HEALTH_COLOR = {"PASS": "#10B981", "FAIL": "#DC2626", "DUE": "#3B82F6"}
_EMPTY_SPOT_COLOR = "#CBD5E1"


def _make_floor_plan_figure(floor: str, items=None, spots=None) -> go.Figure | None:
    """도면 PNG 백그라운드 + spot 마커 + 장비 상태 색.
    items: 이 층의 Equipment 리스트
    spots: 이 층의 Spot 리스트 (None이면 마커 미표시 — 하위 호환)"""
    uri = _floor_image_uri(floor)
    if uri is None:
        return None
    W, H = 2978, 2105
    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=H, sizex=W, sizey=H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    # spot 위에 장비 매핑 — spot_id → list[Equipment]
    if spots:
        by_spot: dict[str, list] = {}
        for e in (items or []):
            if e.spot_id:
                by_spot.setdefault(e.spot_id, []).append(e)

        empty_x, empty_y, empty_text = [], [], []
        marker_x, marker_y, marker_color, marker_text, marker_size = [], [], [], [], []
        for s in spots:
            xpix = s.x_pct / 100 * W
            ypix = H - s.y_pct / 100 * H
            eqs = by_spot.get(s.spot_id, [])
            if not eqs:
                empty_x.append(xpix)
                empty_y.append(ypix)
                empty_text.append(f"{s.room_name}<br>{s.spot_id}<br><i>빈 위치</i>")
            else:
                # 우선순위: FAIL > DUE > PASS
                color = _EMPTY_SPOT_COLOR
                for prio in ("FAIL", "DUE", "PASS"):
                    if any(e.health_status == prio for e in eqs):
                        color = _HEALTH_COLOR[prio]
                        break
                marker_x.append(xpix)
                marker_y.append(ypix)
                marker_color.append(color)
                hover = (
                    f"<b>{s.room_name}</b> ({s.spot_id})<br>"
                    + "<br>".join(
                        f"· {e.equipment_id} · {e.equipment_name} · {e.health_status}"
                        for e in eqs
                    )
                )
                marker_text.append(hover)
                marker_size.append(18 + min(len(eqs) - 1, 4) * 3)  # 장비 많을수록 크게

        if empty_x:
            fig.add_trace(go.Scatter(
                x=empty_x, y=empty_y, mode="markers",
                marker=dict(size=12, color=_EMPTY_SPOT_COLOR,
                            line=dict(color="#FFFFFF", width=2)),
                hovertext=empty_text, hoverinfo="text",
                name="빈 위치", showlegend=False,
            ))
        if marker_x:
            fig.add_trace(go.Scatter(
                x=marker_x, y=marker_y, mode="markers",
                marker=dict(size=marker_size, color=marker_color,
                            line=dict(color="#FFFFFF", width=2)),
                hovertext=marker_text, hoverinfo="text",
                name="장비", showlegend=False,
            ))

    fig.update_xaxes(visible=False, range=[0, W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#F8FAFC",
        height=620,
        dragmode="pan",
        showlegend=False,
        # 잠금 토글 시 줌/팬 상태 유지 (층 변경 시 자동 reset)
        uirevision=f"floor_{floor}",
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

    spots = data.load_spots(floor)
    fig = _make_floor_plan_figure(floor, items=stats["items"], spots=spots)
    if fig is None:
        st.warning(
            f"`{floor}` 도면 이미지가 없습니다. "
            f"`scripts/convert_floor_pdfs.py`를 실행해 도면을 생성해 주세요."
        )
    else:
        from lib.floor_widget import (
            control_toggle, floor_legend_html, lock_overlay_css, plotly_config,
        )
        ctrl_col, leg_col = st.columns([1.2, 5])
        with ctrl_col:
            locked = control_toggle(f"floor_plan_{floor}", default_locked=True)
        with leg_col:
            st.markdown(floor_legend_html(), unsafe_allow_html=True)
        # CSS는 plotly_chart 전에 주입 — timing 안정성
        if locked:
            lock_overlay_css()
        st.plotly_chart(
            fig, use_container_width=True,
            config=plotly_config(),
            key=f"floor_plan_{floor}",
        )
        st.markdown(
            "<div style='color:#64748B; font-size:0.78rem; margin-top:-0.5rem;'>"
            "휠/핀치 줌 · 드래그 팬 · 🏠 아이콘으로 전체 도면 보기 · "
            "잠금 시 인터랙션 비활성"
            "</div>",
            unsafe_allow_html=True,
        )
        if not spots:
            st.info(
                f"`{floor}` 층에 정의된 위치(spot)가 없습니다. 관리자 메뉴 → "
                f"위치 마스터에서 spot을 추가하면 도면 위 마커가 표시됩니다."
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


def render() -> None:
    # 헤더 + 점검 버튼을 한 줄에 (점검은 우측)
    h_col, b_col = st.columns([3, 1])
    with h_col:
        page_header(
            "대시보드",
            f"용인덕성 AI DC 소방안전 점검 통합 현황 · {data.TODAY.isoformat()}.",
        )
    with b_col:
        # 헤더 높이 보정 (page_header의 상단 마진과 맞춤)
        st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
        if st.button("📷 점검 (QR 스캔)", type="primary",
                     use_container_width=True, key="open_inspect_qr"):
            _inspect_qr_dialog()

    # v1.8: st.tabs → st.radio — 층별 도면 탭의 도면 잠금 토글 등 rerun 시 탭 유지
    _dash_section = st.radio(
        "대시보드 탭",
        ["현황 요약", "층별 도면"],
        horizontal=True, label_visibility="collapsed",
        key="dashboard_section",
    )
    if _dash_section == "현황 요약":
        _summary_tab()
    else:
        _grid_tab()


# ---- 점검 QR 스캔 모달 ----

@st.dialog("점검 시작", width="large")
def _inspect_qr_dialog() -> None:
    """3개 작업 카드 라디오 + QR 라이브 스캐너 (후면 카메라).
    QR 디코딩 결과로 equipment_id를 추출해 해당 모달 자동 오픈."""
    notices = data.load_notices()
    pending_notices = sum(1 for n in notices if not n.action_done)

    st.markdown(
        "<div style='color:#64748B; font-size:0.9rem; margin-bottom:0.5rem;'>"
        "작업 유형을 선택한 뒤 장비의 QR 코드를 카메라에 비춰주세요. "
        "인식되면 해당 장비의 점검 화면으로 자동 이동합니다."
        "</div>",
        unsafe_allow_html=True,
    )

    actions = [
        ("지적 입력", "신규 점검 결과 입력 (양호/불량 · 통보서 발급)", True),
        ("조치 입력",
         f"발급된 통보서의 후속 조치 ({pending_notices}건 대기)",
         pending_notices > 0),
        ("오동작 등록", "별지9 소방시설 오동작 관리대장 row 추가", True),
    ]
    # 비활성 옵션은 라디오에서 제외 + 안내
    enabled = [a for a in actions if a[2]]
    disabled = [a for a in actions if not a[2]]

    sel = st.radio(
        "작업 유형",
        options=[a[0] for a in enabled],
        captions=[a[1] for a in enabled],
        key="inspect_qr_action",
    )
    for label, desc, _ in disabled:
        st.caption(f"· {label} — {desc} (현재 조치할 항목이 없어 비활성)")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-weight:600; color:#0F172A; font-size:0.92rem; "
        "margin-bottom:0.3rem;'>QR 스캐너 (후면 카메라)</div>"
        "<div style='color:#94A3B8; font-size:0.78rem; margin-bottom:0.4rem;'>"
        "처음 1회 카메라 권한을 허용해 주세요. 모바일에서는 후면 카메라가 자동 선택됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    # streamlit-qrcode-scanner — 라이브 카메라 + QR 디코드
    try:
        from streamlit_qrcode_scanner import qrcode_scanner
        qr = qrcode_scanner(key="inspect_qr_scanner")
    except Exception as e:
        st.error(
            f"QR 스캐너를 불러올 수 없습니다 ({e}). 아래에 장비 ID를 직접 입력해주세요."
        )
        qr = None

    # 수동 ID 입력 fallback
    manual = st.text_input(
        "수동 입력 (선택) — 장비 ID 또는 QR 페이로드 URL",
        key="inspect_qr_manual",
        placeholder="예: EQ-0006",
    )

    eq_id = _extract_equipment_id(qr) if qr else _extract_equipment_id(manual)
    if eq_id:
        eq = next(
            (x for x in data.load_equipment() if x.equipment_id == eq_id),
            None,
        )
        if eq is None:
            st.error(f"장비를 찾을 수 없습니다: {eq_id}")
            return
        # 라우팅 + 자동 모달 오픈 세션 키 세팅
        st.success(
            f"인식: {eq.equipment_id} · {eq.equipment_name} ({eq.location_id})"
        )
        if st.button("이 장비 점검 시작 →", type="primary",
                     use_container_width=True, key="inspect_qr_route"):
            st.session_state["inspect_target"] = eq.equipment_id
            if sel == "지적 입력":
                st.session_state["page"] = "deficiencies"
                st.session_state["_open_inspect_dialog"] = True
            elif sel == "조치 입력":
                # 점검 작업 페이지 (focus_notice는 페이지가 자동 처리)
                st.session_state["page"] = "inspection"
                st.session_state["focus_equipment"] = eq.equipment_id
            else:  # 오동작 등록
                st.session_state["page"] = "deficiencies"
                st.session_state["_open_malfunction_dialog"] = True
            st.rerun()


def _extract_equipment_id(payload: str | None) -> str | None:
    """QR 페이로드(URL 또는 ID)에서 equipment_id 추출.
    형식 예: 'https://.../inspect?eq=EQ-0006' 또는 'EQ-0006'."""
    if not payload:
        return None
    s = str(payload).strip()
    # URL의 ?eq= 또는 &eq= 부분 추출
    import re
    m = re.search(r"[?&]eq=([A-Za-z0-9\-]+)", s)
    if m:
        return m.group(1).upper()
    # EQ-NNNN 패턴 직접 매칭
    m = re.search(r"\bEQ-\d{4,}\b", s.upper())
    if m:
        return m.group(0)
    return None
