"""관리자 메뉴 — 위치 마스터(spot) 정의 + 향후 다른 관리 기능 진입점.

관리자(`auth.is_admin()`)에게만 사이드바에 노출되는 페이지. 첫 탭은 도면 위
spot 객체 정의 UI. 향후 사용자 관리·시스템 설정 등의 탭을 추가할 수 있다.
"""
from __future__ import annotations

import base64
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from lib import auth, data
from lib.data import Spot
from lib.floor_widget import control_toggle, legend_html, plotly_config
from lib.ui import badge, page_header

# 새 8개 층 (대시보드 Location 탭과 동일 순서)
ADMIN_FLOORS = ["PIT", "B2", "B1", "1F", "2F", "3F", "4F", "Roof"]
ASSETS_FLOORS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"

# 도면 PNG 모두 동일 픽셀 크기 (convert_floor_pdfs.py 기준)
FIG_W = 2978
FIG_H = 2105


def _floor_image_uri(floor: str) -> str | None:
    p = ASSETS_FLOORS_DIR / f"{floor}.png"
    if not p.exists():
        return None
    return f"data:image/png;base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"


def _make_floor_fig(floor: str, spots: list[Spot],
                    show_grid: bool = True, height: int = 600) -> go.Figure | None:
    """도면 PNG + 기존 spot 마커.
    show_grid=True 면 좌표 픽업용 격자(파란 점) 표시(신규 위치 추가 모달용).
    show_grid=False 면 읽기 전용 도면(위치 마스터 인라인 미리보기용)."""
    uri = _floor_image_uri(floor)
    if uri is None:
        return None

    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    # 기존 spot — 노란 점 + 라벨
    if spots:
        fig.add_trace(go.Scatter(
            x=[s.x_pct / 100 * FIG_W for s in spots],
            y=[FIG_H - s.y_pct / 100 * FIG_H for s in spots],
            mode="markers+text",
            text=[s.spot_id.split("-")[-1] for s in spots],   # NNN 만 표기
            textposition="top center",
            textfont=dict(size=11, color="#0F172A"),
            marker=dict(size=14, color="#F59E0B",
                        line=dict(color="#FFFFFF", width=2)),
            customdata=[(s.spot_id, s.room_name) for s in spots],
            hovertemplate=("<b>%{customdata[1]}</b><br>%{customdata[0]}<extra></extra>"),
            name="기존 spot",
        ))

    # 좌표 픽업용 격자 (50x50 = 2500개) — 살짝 보이는 점 + 호버 안내
    # 사용자가 클릭 가능 위치를 시각적으로 인지하도록 visible
    if show_grid:
        grid_x, grid_y = [], []
        for i in range(50):
            for j in range(50):
                grid_x.append((i + 0.5) / 50 * FIG_W)
                grid_y.append((j + 0.5) / 50 * FIG_H)
        fig.add_trace(go.Scatter(
            x=grid_x, y=grid_y,
            mode="markers",
            marker=dict(
                size=10,
                color="rgba(59,130,246,0.22)",
                line=dict(width=0),
            ),
            hovertemplate="여기 클릭 → 좌표 픽업<extra></extra>",
            showlegend=False,
            name="grid",
        ))

    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, FIG_H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#F8FAFC",
        height=height,
        dragmode="pan",
        showlegend=False,
        clickmode="event+select",
        # 토글로 staticPlot 전환 시에도 사용자 줌/팬 상태 유지
        uirevision=f"floor_{floor}",
    )
    return fig


@st.dialog("spot 속성 변경", width="large")
def _spot_edit_dialog(spot_id: str) -> None:
    """기존 spot 속성 변경 모달. 도면 클릭으로 새 좌표 픽업, number_input 미세조정."""
    spots = data.load_spots()
    s = next((x for x in spots if x.spot_id == spot_id), None)
    if not s:
        st.error(f"spot을 찾을 수 없습니다: {spot_id}")
        return

    used = {e.spot_id for e in data.load_equipment() if e.spot_id}
    in_use = s.spot_id in used
    mapped_cnt = sum(1 for e in data.load_equipment() if e.spot_id == s.spot_id)

    st.markdown(
        f"<div style='color:#475569; font-size:0.9rem; margin-bottom:0.4rem;'>"
        f"<b style='color:#0F172A;'>{s.spot_id}</b> · 층 <b>{s.floor}</b>"
        f"<span style='color:#94A3B8;'> (spot_id/층은 변경 불가)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if in_use:
        st.caption(
            f"이 spot은 장비 {mapped_cnt}건에 매핑되어 있습니다. "
            "방이름·좌표 변경 시 해당 장비의 위치 정보도 함께 갱신됩니다."
        )

    # 좌표 픽업 초기값 — 첫 진입 시 현재 spot 좌표 사용
    init_x_key = f"edit_x_pct_{spot_id}"
    init_y_key = f"edit_y_pct_{spot_id}"
    if init_x_key not in st.session_state:
        st.session_state[init_x_key] = float(s.x_pct)
        st.session_state[init_y_key] = float(s.y_pct)

    # 도면 — 현재 spot은 파란색, 다른 spot은 옅은 주황
    other_spots = [x for x in spots if x.floor == s.floor and x.spot_id != s.spot_id]
    fig = _make_floor_fig_edit(s, other_spots,
                               st.session_state[init_x_key],
                               st.session_state[init_y_key])
    if fig is None:
        st.warning(f"{s.floor} 도면 이미지가 없습니다.")
    else:
        from lib.floor_widget import (
            control_toggle, legend_html, lock_overlay_css, plotly_config,
        )
        cc, lc = st.columns([1.2, 5])
        with cc:
            locked = control_toggle(f"edit_map_{spot_id}", default_locked=True)
        with lc:
            st.markdown(legend_html([
                ("#2563EB", "현재 spot"),
                ("#FDE68A", "다른 spot"),
            ]), unsafe_allow_html=True)

        # CSS는 plotly_chart 전에 주입 — timing 안정성
        if locked:
            lock_overlay_css()
        # plotly_chart props는 잠금 상태와 무관하게 항상 동일 — Plotly 재마운트 회피
        event = st.plotly_chart(
            fig, use_container_width=True,
            config=plotly_config(),
            on_select="rerun",
            selection_mode=["points"],
            key=f"edit_map_chart_{spot_id}",
        )
        if (not locked and event and getattr(event, "selection", None)
                and getattr(event.selection, "points", None)):
            pt = event.selection.points[-1]
            st.session_state[init_x_key] = round(pt["x"] / FIG_W * 100, 2)
            st.session_state[init_y_key] = round((FIG_H - pt["y"]) / FIG_H * 100, 2)
            st.rerun()

        st.markdown(
            "<div style='color:#94A3B8; font-size:0.78rem; margin-top:-0.4rem;'>"
            "파란 마커 = 현재 spot · 옅은 주황 = 다른 spot · "
            "도면 클릭 시 좌표 픽업 (그리드 단위 스냅)"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:0.4rem;'></div>", unsafe_allow_html=True)

    ec1, ec2 = st.columns([1, 2])
    with ec1:
        new_room = st.text_input(
            "방이름 *",
            value=s.room_name,
            key=f"edit_room_{spot_id}",
        )
    with ec2:
        new_notes = st.text_input(
            "비고",
            value=s.notes,
            key=f"edit_notes_{spot_id}",
        )

    ec3, ec4, _ = st.columns([1, 1, 2])
    with ec3:
        new_x = st.number_input(
            "x_pct (도면 폭 %)",
            min_value=0.0, max_value=100.0,
            step=0.5, format="%.2f",
            key=init_x_key,
        )
    with ec4:
        new_y = st.number_input(
            "y_pct (도면 높이 %)",
            min_value=0.0, max_value=100.0,
            step=0.5, format="%.2f",
            key=init_y_key,
        )

    # 신규 위치(임시 등록)인 경우 정식 전환 토글
    promote_to_regular = False
    if s.is_temporary:
        st.markdown(
            "<div style='background:#EFF6FF; border:1px solid #BFDBFE; "
            "border-radius:8px; padding:0.5rem 0.7rem; margin:0.3rem 0; "
            "color:#1E3A8A; font-size:0.86rem;'>"
            "🆕 이 spot은 점검자가 현장에서 신규 등록(검증 대기)했습니다. "
            "방이름·좌표를 확인하고 정식 전환하세요."
            "</div>",
            unsafe_allow_html=True,
        )
        promote_to_regular = st.checkbox(
            "정식 spot으로 전환 (체크 + 저장)",
            key=f"edit_promote_{spot_id}",
        )

    new_is_temp = (s.is_temporary and not promote_to_regular)
    changed = (
        new_room.strip() != s.room_name
        or new_notes.strip() != s.notes
        or round(new_x, 2) != round(s.x_pct, 2)
        or round(new_y, 2) != round(s.y_pct, 2)
        or new_is_temp != s.is_temporary
    )

    bc1, bc2 = st.columns([1, 1])
    with bc1:
        if st.button("저장", type="primary", use_container_width=True,
                     key=f"edit_save_{spot_id}",
                     disabled=not changed or not new_room.strip()):
            n_synced = data.update_spot_with_equipment_sync(
                data.Spot(
                    spot_id=s.spot_id, floor=s.floor,
                    room_name=new_room.strip(),
                    notes=new_notes.strip(),
                    x_pct=float(new_x), y_pct=float(new_y),
                    is_temporary=new_is_temp,
                )
            )
            msg = f"{s.spot_id} 속성 저장 완료."
            if s.is_temporary and not new_is_temp:
                msg += " (신규 → 정식 전환됨)"
            if n_synced:
                msg += f" 매핑 장비 {n_synced}건의 위치 정보도 동기화."
            st.session_state["admin_spot_save_msg"] = msg
            # 모달 정리
            for k in (init_x_key, init_y_key, f"edit_promote_{spot_id}",
                      f"edit_room_{spot_id}", f"edit_notes_{spot_id}"):
                st.session_state.pop(k, None)
            st.session_state.pop("admin_spot_edit_id", None)
            st.rerun()
    with bc2:
        if st.button("취소", use_container_width=True,
                     key=f"edit_cancel_{spot_id}"):
            for k in (init_x_key, init_y_key, f"edit_promote_{spot_id}",
                      f"edit_room_{spot_id}", f"edit_notes_{spot_id}"):
                st.session_state.pop(k, None)
            st.session_state.pop("admin_spot_edit_id", None)
            st.rerun()


def _make_floor_fig_edit(cur_spot, other_spots, x_pct, y_pct) -> go.Figure | None:
    """spot 편집 모달용 도면 — 현재 spot은 파란색(현재 좌표 또는 클릭 좌표),
    다른 spot은 옅은 주황. 좌표 픽업 그리드 + 클릭 가능 빈 영역."""
    uri = _floor_image_uri(cur_spot.floor)
    if uri is None:
        return None

    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    if other_spots:
        fig.add_trace(go.Scatter(
            x=[s.x_pct / 100 * FIG_W for s in other_spots],
            y=[FIG_H - s.y_pct / 100 * FIG_H for s in other_spots],
            mode="markers+text",
            text=[s.spot_id.split("-")[-1] for s in other_spots],
            textposition="top center",
            textfont=dict(size=10, color="#94A3B8"),
            marker=dict(size=12, color="#FDE68A",
                        line=dict(color="#F59E0B", width=1.5)),
            hovertemplate="<b>%{text}</b><extra></extra>",
            name="다른 spot", showlegend=False,
        ))

    # 현재 spot — 파란 강조 (클릭으로 변경되면 새 좌표)
    fig.add_trace(go.Scatter(
        x=[x_pct / 100 * FIG_W],
        y=[FIG_H - y_pct / 100 * FIG_H],
        mode="markers+text",
        text=[f"<b>{cur_spot.spot_id.split('-')[-1]}</b>"],
        textposition="top center",
        textfont=dict(size=12, color="#1D4ED8"),
        marker=dict(size=20, color="#2563EB",
                    line=dict(color="#FFFFFF", width=2.5),
                    symbol="circle"),
        hovertemplate=f"<b>{cur_spot.room_name}</b><br>{cur_spot.spot_id}<extra></extra>",
        name="현재 spot", showlegend=False,
    ))

    # 클릭용 격자 — 살짝 보이는 점 + 호버 안내 (속성 변경 모달도 동일 UX)
    grid_x, grid_y = [], []
    for i in range(50):
        for j in range(50):
            grid_x.append((i + 0.5) / 50 * FIG_W)
            grid_y.append((j + 0.5) / 50 * FIG_H)
    fig.add_trace(go.Scatter(
        x=grid_x, y=grid_y,
        mode="markers",
        marker=dict(
            size=10,
            color="rgba(59,130,246,0.22)",
            line=dict(width=0),
        ),
        hovertemplate="여기 클릭 → 새 좌표 픽업<extra></extra>",
        showlegend=False,
        name="grid",
    ))

    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, FIG_H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#F8FAFC", height=520,
        dragmode="pan", showlegend=False,
        clickmode="event+select",
        uirevision=f"floor_edit_{cur_spot.floor}",
    )
    return fig


@st.dialog("신규 위치 추가", width="large")
def _spot_define_dialog() -> None:
    """도면 클릭으로 좌표 픽업 + 속성 입력 + 저장. 위치 마스터 페이지에서 진입."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.9rem; margin-bottom:0.5rem;'>"
        "층 선택 → 도면 위 빈 곳을 클릭하면 좌표가 자동 입력됩니다. "
        "기존 spot(주황색 점)과의 위치 관계를 보고 결정하세요."
        "</div>",
        unsafe_allow_html=True,
    )

    floor = st.selectbox(
        "층 선택",
        options=ADMIN_FLOORS,
        key="admin_spot_dlg_floor",
    )
    spots = data.load_spots(floor)

    fig = _make_floor_fig(floor, spots)
    if fig is None:
        st.error(
            f"`{floor}` 도면 이미지가 없습니다. "
            f"`scripts/convert_floor_pdfs.py` 실행 후 다시 시도하세요."
        )
        return

    # 도면 상단 컨트롤 토글 + 범례
    ctrl_col, leg_col = st.columns([1.2, 5])
    with ctrl_col:
        locked = control_toggle(f"admin_dlg_{floor}", default_locked=True)
    with leg_col:
        st.markdown(legend_html([
            ("#F59E0B", "기존 위치"),
            ("#3B82F6", "클릭 가능 영역(좌표 픽업)"),
        ]), unsafe_allow_html=True)

    if locked:
        from lib.floor_widget import lock_overlay_css
        lock_overlay_css()
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        config=plotly_config(),
        on_select="rerun",
        selection_mode=["points"],
        key=f"admin_dlg_chart_{floor}",
    )

    if (not locked and event and getattr(event, "selection", None)
            and getattr(event.selection, "points", None)):
        pt = event.selection.points[-1]
        # number_input widget key와 동일하게 직접 set — 다음 number_input 그려질 때 그 값 사용
        st.session_state["admin_spot_x_input"] = round(pt["x"] / FIG_W * 100, 2)
        st.session_state["admin_spot_y_input"] = round((FIG_H - pt["y"]) / FIG_H * 100, 2)

    st.markdown(
        "<div style='color:#94A3B8; font-size:0.78rem; margin-top:-0.4rem;'>"
        "휠/핀치 줌 · 드래그 팬 · 잠금 시 인터랙션 비활성 · 도면 클릭 시 좌표 픽업"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # widget key가 있으면 session_state[key]가 우선 — value는 첫 진입 디폴트
    if "admin_spot_x_input" not in st.session_state:
        st.session_state["admin_spot_x_input"] = 50.0
    if "admin_spot_y_input" not in st.session_state:
        st.session_state["admin_spot_y_input"] = 50.0

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        x_pct = st.number_input(
            "x_pct (도면 폭 %)",
            min_value=0.0, max_value=100.0,
            step=0.5, format="%.2f",
            key="admin_spot_x_input",
        )
    with c2:
        y_pct = st.number_input(
            "y_pct (도면 높이 %)",
            min_value=0.0, max_value=100.0,
            step=0.5, format="%.2f",
            key="admin_spot_y_input",
        )
    with c3:
        st.markdown(
            "<div style='padding-top:1.7rem; color:#64748B; font-size:0.85rem;'>"
            f"다음 spot ID: <b>{data.next_spot_id(floor)}</b>"
            "</div>",
            unsafe_allow_html=True,
        )

    room_name = st.text_input(
        "방이름 *",
        key="admin_spot_room",
        placeholder="예: 로비 동쪽 출입구 좌측",
    )
    notes = st.text_input(
        "비고",
        key="admin_spot_notes",
        placeholder="예: 소화기 권장 / 감지기 함께 설치 등",
    )

    bcol1, bcol2 = st.columns([1, 1])
    with bcol1:
        if st.button("취소", use_container_width=True, key="admin_spot_dlg_cancel"):
            for k in ("admin_spot_room", "admin_spot_notes",
                      "admin_spot_x_input", "admin_spot_y_input"):
                st.session_state.pop(k, None)
            st.rerun()
    with bcol2:
        if st.button("spot 추가", type="primary", use_container_width=True,
                     key="admin_spot_dlg_submit"):
            if not room_name.strip():
                st.error("방이름을 입력해 주세요.")
            else:
                new_id = data.next_spot_id(floor)
                data.add_spot(Spot(
                    spot_id=new_id, floor=floor,
                    room_name=room_name.strip(), notes=notes.strip(),
                    x_pct=x_pct, y_pct=y_pct,
                ))
                for k in ("admin_spot_room", "admin_spot_notes",
                          "admin_spot_x", "admin_spot_y"):
                    st.session_state.pop(k, None)
                st.session_state["admin_spot_just_added"] = (
                    f"{new_id} 등록 완료 ({room_name.strip()})."
                )
                st.rerun()


def _select_admin_floor(target: str) -> None:
    """미니맵 [이 층 보기] 클릭 콜백 — 층 선택 selectbox를 target 층으로 전환."""
    st.session_state["admin_spot_floor"] = target


def _spot_master_floor_preview(floor: str, spots: list[Spot]) -> None:
    """위치 마스터 층 선택 아래 도면 미리보기 (읽기 전용).
    - 특정 층: 그 층 도면 + spot 마커
    - 전체: 전 층 미니맵 그리드 + [이 층 보기] 드릴인 버튼
    """
    if floor != "전체":
        fig = _make_floor_fig(floor, spots, show_grid=False, height=460)
        if fig is None:
            st.caption(f"({floor} 도면 이미지가 없습니다)")
            return
        st.markdown(
            f"<div style='margin-top:0.4rem; color:#475569; font-size:0.85rem;'>"
            f"🗺️ <b>{floor}</b> 도면 · 등록된 위치 {len(spots)}개</div>",
            unsafe_allow_html=True,
        )
        st.markdown(legend_html([
            ("#F59E0B", "등록된 위치(spot)"),
        ]), unsafe_allow_html=True)
        st.plotly_chart(
            fig, use_container_width=True,
            config={"displayModeBar": False, "staticPlot": True},
            key=f"admin_spot_fig_{floor}",
        )
        return

    # 전체 — 전 층 미니맵 그리드 (4열) + 드릴인 버튼
    st.markdown(
        "<div style='margin-top:0.4rem; color:#475569; font-size:0.85rem;'>"
        "🗺️ 전 층 미니맵 — <b>[이 층 보기]</b>로 해당 층 상세로 이동</div>",
        unsafe_allow_html=True,
    )
    st.markdown(legend_html([
        ("#F59E0B", "등록된 위치(spot)"),
    ]), unsafe_allow_html=True)
    all_spots = spots  # 이미 전체 로드됨
    by_floor: dict[str, list[Spot]] = {f: [] for f in ADMIN_FLOORS}
    for s in all_spots:
        by_floor.setdefault(s.floor, []).append(s)

    n_cols = 4
    for row_start in range(0, len(ADMIN_FLOORS), n_cols):
        row_floors = ADMIN_FLOORS[row_start:row_start + n_cols]
        cols = st.columns(n_cols)
        for col, fl in zip(cols, row_floors):
            with col:
                fspots = by_floor.get(fl, [])
                mini = _make_floor_fig(fl, fspots, show_grid=False, height=150)
                st.markdown(
                    f"<div style='font-weight:600; color:#0F172A; font-size:0.82rem; "
                    f"margin-bottom:0.1rem;'>{fl} "
                    f"<span style='color:#94A3B8; font-weight:500;'>({len(fspots)})</span></div>",
                    unsafe_allow_html=True,
                )
                if mini is not None:
                    st.plotly_chart(
                        mini, use_container_width=True,
                        config={"displayModeBar": False, "staticPlot": True},
                        key=f"admin_mini_{fl}",
                    )
                else:
                    st.caption("(도면 없음)")
                st.button(
                    "이 층 보기", key=f"admin_drill_{fl}",
                    use_container_width=True,
                    on_click=_select_admin_floor, args=(fl,),
                )


def _spot_master_tab() -> None:
    # 상단 헤더 + [+ 신규 위치 추가] 버튼
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(
            "<div style='color:#64748B; font-size:0.92rem;'>"
            "등록된 위치(spot)를 <b>관리·검증</b>합니다 — 사용 여부 확인, 신규(임시) 위치 "
            "정식 전환, 속성·좌표 조정.<br>"
            "<span style='color:#94A3B8; font-size:0.85rem;'>"
            "일상 신규 위치는 <b>시설 관리(장비 등록)</b>·<b>안전점검(신규 위치 점검)</b>에서 "
            "생성됩니다. 아래 버튼은 초기 세팅·예외용.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    with head_r:
        if st.button("+ 신규 위치 등록", type="secondary",
                     use_container_width=True, key="admin_spot_open_dlg"):
            for k in ("admin_spot_room", "admin_spot_notes",
                      "admin_spot_x_input", "admin_spot_y_input"):
                st.session_state.pop(k, None)
            _spot_define_dialog()

    just_added = st.session_state.pop("admin_spot_just_added", None)
    if just_added:
        st.success(just_added)

    floor = st.selectbox(
        "층 선택",
        options=["전체"] + list(ADMIN_FLOORS),
        key="admin_spot_floor",
    )
    spots = data.load_spots() if floor == "전체" else data.load_spots(floor)

    # --- 도면 미리보기 (읽기 전용, v1.7) ---
    _spot_master_floor_preview(floor, spots)

    # --- spot 목록 + 편집/삭제 ---
    list_title = (
        f"전체 spot 목록 ({len(spots)}건)" if floor == "전체"
        else f"{floor}층 spot 목록 ({len(spots)}건)"
    )
    st.markdown(
        f"<div style='margin-top:0.6rem; font-weight:700; color:#0F172A; font-size:1.02rem;'>"
        f"{list_title}</div>",
        unsafe_allow_html=True,
    )
    if not spots:
        st.info("아직 정의된 spot이 없습니다. 도면 위 빈 곳을 클릭하고 폼을 채워 추가하세요.")
        return

    # spot_id → 그 자리에 배치된 장비 ID (없으면 미포함). 첫 컬럼 장비 ID/- 표시용
    eq_by_spot = {e.spot_id: e.equipment_id
                  for e in data.load_equipment() if e.spot_id}
    used = set(eq_by_spot)
    # 컬럼 9개: 장비 ID / spot ID / 방이름 / 비고 / 좌표 / 사용 / [승인] / [속성변경] / [삭제]
    cols_ratio = [0.85, 1.15, 1.5, 1.1, 0.8, 0.65, 0.85, 0.9, 0.65]
    header = st.columns(cols_ratio)
    for col, txt in zip(header,
                        ["장비 ID", "spot ID", "방이름", "비고", "좌표(%)", "사용", "승인", "", ""]):
        col.markdown(
            f"<div style='color:#64748B; font-size:0.78rem; font-weight:600;'>{txt}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin:0.3rem 0; border-color:#E2E8F0;'>",
                unsafe_allow_html=True)

    for s in spots:
        row = st.columns(cols_ratio, vertical_alignment="center")
        in_use = s.spot_id in used
        # 이 spot에 배치된 장비 ID (없으면 "-"). 층은 spot ID, 신규는 [승인] 버튼으로 식별
        eq_id = eq_by_spot.get(s.spot_id)
        eq_disp = (
            f"<span style='font-weight:600; color:#0F172A;'>{eq_id}</span>"
            if eq_id else "<span style='color:#94A3B8;'>-</span>"
        )
        row[0].markdown(eq_disp, unsafe_allow_html=True)
        row[1].markdown(
            f"<span style='color:#64748B; font-size:0.82rem;'>{s.spot_id}</span>",
            unsafe_allow_html=True,
        )
        row[2].markdown(s.room_name)
        row[3].markdown(
            f"<span style='color:#475569;'>{s.notes or '-'}</span>",
            unsafe_allow_html=True,
        )
        row[4].markdown(
            f"<span style='color:#334155; font-size:0.85rem;'>"
            f"{s.x_pct:.1f} / {s.y_pct:.1f}</span>",
            unsafe_allow_html=True,
        )
        row[5].markdown(
            "<span style='background:#FEF3C7; color:#92400E; padding:0.1rem 0.4rem; "
            "border-radius:6px; font-size:0.74rem;'>사용 중</span>"
            if in_use else
            "<span style='color:#94A3B8; font-size:0.78rem;'>미사용</span>",
            unsafe_allow_html=True,
        )
        with row[6]:
            # 검증 대기(임시) spot에만 [승인] 노출 → 기존 '속성 변경' 모달을
            # '정식 전환' 기본 체크 상태로 열어 방이름·좌표 수정 후 저장 시 전환
            if s.is_temporary:
                if st.button("승인", key=f"admin_spot_approve_{s.spot_id}",
                             type="primary", use_container_width=True):
                    st.session_state[f"edit_promote_{s.spot_id}"] = True
                    st.session_state["admin_spot_edit_id"] = s.spot_id
                    st.rerun()
        with row[7]:
            if st.button("속성 변경", key=f"admin_spot_edit_{s.spot_id}",
                         use_container_width=True):
                st.session_state["admin_spot_edit_id"] = s.spot_id
                st.rerun()
        with row[8]:
            if st.button("삭제", key=f"admin_spot_del_{s.spot_id}",
                         use_container_width=True, disabled=in_use):
                data.delete_spot(s.spot_id)
                st.rerun()

    # 저장 후 토스트
    msg = st.session_state.pop("admin_spot_save_msg", None)
    if msg:
        st.success(msg)

    # 편집/승인 공통 모달 트리거 (승인도 이 모달을 정식 전환 체크 상태로 사용)
    edit_id = st.session_state.get("admin_spot_edit_id")
    if edit_id:
        _spot_edit_dialog(edit_id)


def _user_admin_tab() -> None:
    """사용자 관리 — Supabase Auth 사용자 리스트 + 권한·이름·비밀번호 관리."""
    me = auth.current_user()
    if not me:
        st.error("로그인이 필요합니다.")
        return
    admin = auth.admin_client()
    try:
        users = admin.auth.admin.list_users()
    except Exception as e:
        st.error(f"사용자 목록 조회 실패: {e}")
        return

    admin_count = sum(
        1 for u in users if (u.app_metadata or {}).get("role") == "admin"
    )
    st.markdown(
        f"<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.6rem;'>"
        f"전체 사용자 {len(users)}명 · 관리자 {admin_count}명</div>",
        unsafe_allow_html=True,
    )

    for u in users:
        meta = u.user_metadata or {}
        username = meta.get("username") or (u.email or "").split("@")[0]
        name = meta.get("name") or username
        role = (u.app_metadata or {}).get("role", "user")
        is_me = u.id == me["user_id"]
        role_label = "관리자" if role == "admin" else "일반"
        title = f"{name} ({username}) · {role_label}" + (" · 본인" if is_me else "")

        with st.expander(title):
            c1, c2, c3 = st.columns(3)

            # 권한 변경 (본인 제외, 마지막 관리자 강등 방지)
            with c1:
                st.markdown("<b style='font-size:0.88rem;'>권한 변경</b>",
                            unsafe_allow_html=True)
                if is_me:
                    st.caption("본인 권한은 변경할 수 없습니다.")
                else:
                    new_role = st.selectbox(
                        "역할", ["user", "admin"],
                        index=0 if role == "user" else 1,
                        format_func=lambda r: "일반" if r == "user" else "관리자",
                        key=f"role_{u.id}",
                    )
                    if st.button("권한 적용", key=f"role_btn_{u.id}",
                                 use_container_width=True):
                        if role == "admin" and new_role == "user" and admin_count <= 1:
                            st.error("마지막 관리자는 강등할 수 없습니다.")
                        else:
                            try:
                                admin.auth.admin.update_user_by_id(
                                    u.id, {"app_metadata": {"role": new_role}}
                                )
                                st.success("권한이 변경되었습니다.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"실패: {e}")

            # 이름 수정
            with c2:
                st.markdown("<b style='font-size:0.88rem;'>이름 수정</b>",
                            unsafe_allow_html=True)
                edit_name = st.text_input("이름", value=name,
                                          key=f"name_{u.id}",
                                          label_visibility="collapsed")
                if st.button("이름 저장", key=f"name_btn_{u.id}",
                             use_container_width=True):
                    if not edit_name.strip():
                        st.error("이름을 입력해 주세요.")
                    else:
                        try:
                            admin.auth.admin.update_user_by_id(
                                u.id,
                                {"user_metadata": {**meta, "name": edit_name.strip()}},
                            )
                            st.success("이름이 변경되었습니다.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"실패: {e}")

            # 비밀번호 초기화
            with c3:
                st.markdown("<b style='font-size:0.88rem;'>비밀번호 초기화</b>",
                            unsafe_allow_html=True)
                temp_pw = st.text_input("새 임시 비밀번호", type="password",
                                        key=f"pw_{u.id}",
                                        label_visibility="collapsed",
                                        placeholder="새 임시 비밀번호 (6자+)")
                if st.button("초기화 적용", key=f"pw_btn_{u.id}",
                             use_container_width=True):
                    if len(temp_pw) < 6:
                        st.error("6자 이상 입력해 주세요.")
                    else:
                        try:
                            admin.auth.admin.update_user_by_id(
                                u.id, {"password": temp_pw}
                            )
                            st.success("비밀번호가 초기화되었습니다. "
                                       "해당 사용자에게 전달 후 직접 변경하도록 안내하세요.")
                        except Exception as e:
                            st.error(f"실패: {e}")


_MIGRATION_SQL_INSP_TYPES = (
    "create table if not exists public.inspection_types (\n"
    "  name text primary key, is_active boolean not null default true,\n"
    "  is_builtin boolean not null default false,\n"
    "  sort_order int not null default 100,\n"
    "  created_at timestamptz not null default now());\n"
    "insert into public.inspection_types (name, is_builtin, sort_order) values\n"
    "  ('일일 점검',true,1),('주간 점검',true,2),('월간 점검',true,3),\n"
    "  ('분기 점검',true,4),('연간 점검',true,5) on conflict (name) do nothing;\n"
    "alter table public.inspection_types enable row level security;"
)


def _inspection_type_tab() -> None:
    """점검 유형(주기) 카탈로그 관리 — 추가/비활성/삭제."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.92rem;'>"
        "점검 유형(주기) 카탈로그를 관리합니다 — <b>추가 / 비활성 / 삭제</b>. "
        "비활성 유형은 새 선택 목록에서 숨겨지지만, 이미 지정된 장비·회차엔 그대로 남습니다."
        "</div>",
        unsafe_allow_html=True,
    )

    if not data.inspection_types_table_exists():
        st.warning(
            "점검 유형 테이블(`inspection_types`)이 없습니다. 아래 SQL을 "
            "Supabase SQL 에디터에서 1회 실행한 뒤 새로고침하세요."
        )
        st.code(_MIGRATION_SQL_INSP_TYPES, language="sql")
        return

    # 새 유형 추가
    ac1, ac2 = st.columns([3, 1])
    with ac1:
        new_name = st.text_input(
            "새 유형", key="new_insp_type", label_visibility="collapsed",
            placeholder="새 점검 유형 (예: 반기 점검)",
        )
    with ac2:
        if st.button("추가", use_container_width=True, type="primary",
                     key="add_insp_type_btn"):
            ok, msg = data.add_inspection_type(new_name)
            if ok:
                st.session_state.pop("new_insp_type", None)
                st.rerun()
            else:
                st.error(msg)

    st.markdown("<hr style='margin:0.5rem 0 0.3rem; border:none; "
                "border-top:1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 목록 헤더
    ratios = [2.0, 0.8, 0.7, 0.95, 0.95, 0.85]
    hcols = st.columns(ratios, vertical_alignment="center")
    for c, t in zip(hcols, ["유형", "사용중", "기본", "활성", "이름 변경", "삭제"]):
        c.markdown(
            f"<div style='color:#64748B; font-weight:600; font-size:0.78rem; "
            f"text-align:center;'>{t}</div>", unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin:0.15rem 0 0.1rem; border:none; "
                "border-top:1px solid #E2E8F0;'>", unsafe_allow_html=True)

    for row in data.load_inspection_type_rows():
        name = row["name"]
        usage = data._inspection_type_usage(name)
        builtin = bool(row.get("is_builtin"))
        is_active = bool(row.get("is_active", True))
        cols = st.columns(ratios, vertical_alignment="center")
        cols[0].markdown(
            f"<div style='text-align:center; font-weight:600; color:#0F172A;'>{name}</div>",
            unsafe_allow_html=True,
        )
        cols[1].markdown(
            f"<div style='text-align:center; color:#475569;'>{usage}건</div>",
            unsafe_allow_html=True,
        )
        cols[2].markdown(
            "<div style='text-align:center;'>"
            + ("<span style='color:#2563EB; font-size:0.78rem; font-weight:600;'>기본</span>"
               if builtin else "<span style='color:#CBD5E1;'>—</span>")
            + "</div>", unsafe_allow_html=True,
        )
        # 활성/비활성 — 버튼 토글 (value= 경고 회피)
        with cols[3]:
            if st.button("🟢 활성" if is_active else "⚪ 비활성",
                         key=f"insp_active_{name}", use_container_width=True):
                data.set_inspection_type_active(name, not is_active)
                st.rerun()
        # 이름 변경 — 전 유형 가능 (기본 포함, 참조 연쇄 갱신)
        with cols[4]:
            if st.button("이름 변경", key=f"insp_rename_btn_{name}",
                         use_container_width=True):
                st.session_state[f"insp_rename_open_{name}"] = True
        # 삭제 — 기본·사용중은 불가
        with cols[5]:
            deletable = (not builtin) and usage == 0
            if st.button("삭제", key=f"insp_del_{name}", use_container_width=True,
                         disabled=not deletable,
                         help=None if deletable else "기본·사용중 유형은 삭제 불가(비활성만)"):
                ok, msg = data.delete_inspection_type(name)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        # 인라인 이름 변경 폼
        if st.session_state.get(f"insp_rename_open_{name}"):
            _rk = f"insp_rename_input_{name}"
            if _rk not in st.session_state:
                st.session_state[_rk] = name  # 현재 이름 프리필 (value= 경고 회피)
            rc1, rc2, rc3 = st.columns([2.0, 0.7, 0.7], vertical_alignment="center")
            with rc1:
                st.text_input("새 이름", key=_rk, label_visibility="collapsed",
                              placeholder="새 이름 입력")
            with rc2:
                if st.button("저장", key=f"insp_rename_save_{name}",
                             use_container_width=True, type="primary"):
                    ok, msg = data.rename_inspection_type(name, st.session_state[_rk])
                    if ok:
                        st.session_state.pop(f"insp_rename_open_{name}", None)
                        st.session_state.pop(_rk, None)
                        st.rerun()
                    else:
                        st.error(msg)
            with rc3:
                if st.button("취소", key=f"insp_rename_cancel_{name}",
                             use_container_width=True):
                    st.session_state.pop(f"insp_rename_open_{name}", None)
                    st.session_state.pop(_rk, None)
                    st.rerun()


def render() -> None:
    if not auth.is_admin():
        st.error("관리자 권한이 필요합니다. 사이드바의 일반 메뉴를 이용해 주세요.")
        return

    page_header(
        "관리자 메뉴",
        "관리자 전용 설정 — 위치 마스터(spot) 정의 · 사용자 권한·계정 관리.",
    )

    # 사이드바 하위 메뉴에서 어떤 탭을 활성화할지 결정 (admin_tab 세션 키)
    # st.tabs는 외부 활성화가 어려우므로 st.radio 패턴으로 구현
    tabs = ["위치 마스터 관리", "점검 유형 관리", "사용자 관리"]
    # 라벨 변경(v1.8) 이전 세션에 캐시된 옛 라벨이 남아 있으면 라디오 오류 → 정리
    if st.session_state.get("admin_tab") not in tabs:
        st.session_state.pop("admin_tab", None)
    section = st.radio(
        "관리자 섹션",
        tabs,
        horizontal=True,
        key="admin_tab",
        label_visibility="collapsed",
    )
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    if section == "위치 마스터 관리":
        _spot_master_tab()
    elif section == "점검 유형 관리":
        _inspection_type_tab()
    else:
        _user_admin_tab()
