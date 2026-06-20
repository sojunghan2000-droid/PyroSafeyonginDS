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
from lib.floor_widget import control_toggle, floor_legend_html, plotly_config
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


def _make_floor_fig(floor: str, spots: list[Spot]) -> go.Figure | None:
    """도면 PNG + 기존 spot 마커. 클릭으로 좌표 픽업할 수 있게 빈 영역 trace 1개."""
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

    # 좌표 픽업용 투명 격자 (50x50 = 2500개) — 클릭 가능 위치
    grid_x, grid_y = [], []
    for i in range(50):
        for j in range(50):
            grid_x.append((i + 0.5) / 50 * FIG_W)
            grid_y.append((j + 0.5) / 50 * FIG_H)
    fig.add_trace(go.Scatter(
        x=grid_x, y=grid_y,
        mode="markers",
        marker=dict(size=18, color="rgba(0,0,0,0)"),  # 완전 투명
        hoverinfo="skip",
        showlegend=False,
        name="grid",
    ))

    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, FIG_H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        plot_bgcolor="#F8FAFC",
        height=600,
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
            control_toggle, floor_legend_html, lock_overlay_css, plotly_config,
        )
        cc, lc = st.columns([1.2, 5])
        with cc:
            locked = control_toggle(f"edit_map_{spot_id}", default_locked=False)
        with lc:
            st.markdown(floor_legend_html(), unsafe_allow_html=True)

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

    changed = (
        new_room.strip() != s.room_name
        or new_notes.strip() != s.notes
        or round(new_x, 2) != round(s.x_pct, 2)
        or round(new_y, 2) != round(s.y_pct, 2)
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
                )
            )
            msg = f"{s.spot_id} 속성 저장 완료."
            if n_synced:
                msg += f" 매핑 장비 {n_synced}건의 위치 정보도 동기화."
            st.session_state["admin_spot_save_msg"] = msg
            # 모달 정리
            for k in (init_x_key, init_y_key,
                      f"edit_room_{spot_id}", f"edit_notes_{spot_id}"):
                st.session_state.pop(k, None)
            st.session_state.pop("admin_spot_edit_id", None)
            st.rerun()
    with bc2:
        if st.button("취소", use_container_width=True,
                     key=f"edit_cancel_{spot_id}"):
            for k in (init_x_key, init_y_key,
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

    # 클릭용 투명 격자
    grid_x, grid_y = [], []
    for i in range(50):
        for j in range(50):
            grid_x.append((i + 0.5) / 50 * FIG_W)
            grid_y.append((j + 0.5) / 50 * FIG_H)
    fig.add_trace(go.Scatter(
        x=grid_x, y=grid_y,
        mode="markers",
        marker=dict(size=18, color="rgba(0,0,0,0)"),
        hoverinfo="skip", showlegend=False,
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


@st.dialog("신규 spot 정의", width="large")
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
        locked = control_toggle(f"admin_dlg_{floor}", default_locked=False)
    with leg_col:
        st.markdown(floor_legend_html(), unsafe_allow_html=True)

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
        st.session_state["admin_spot_x"] = round(pt["x"] / FIG_W * 100, 2)
        st.session_state["admin_spot_y"] = round((FIG_H - pt["y"]) / FIG_H * 100, 2)

    st.markdown(
        "<div style='color:#94A3B8; font-size:0.78rem; margin-top:-0.4rem;'>"
        "휠/핀치 줌 · 드래그 팬 · 잠금 시 인터랙션 비활성 · 도면 클릭 시 좌표 픽업"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        x_pct = st.number_input(
            "x_pct (도면 폭 %)",
            min_value=0.0, max_value=100.0,
            value=float(st.session_state.get("admin_spot_x", 50.0)),
            step=0.5, format="%.2f",
            key="admin_spot_x_input",
        )
    with c2:
        y_pct = st.number_input(
            "y_pct (도면 높이 %)",
            min_value=0.0, max_value=100.0,
            value=float(st.session_state.get("admin_spot_y", 50.0)),
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
                      "admin_spot_x", "admin_spot_y"):
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


def _spot_master_tab() -> None:
    # 상단 헤더 + [+ 신규 spot] 버튼
    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(
            "<div style='color:#64748B; font-size:0.92rem;'>"
            "층별 위치(spot)를 정의·관리합니다. 신규 정의는 우측 버튼에서 모달로 진행."
            "</div>",
            unsafe_allow_html=True,
        )
    with head_r:
        if st.button("+ 신규 spot 정의", type="primary",
                     use_container_width=True, key="admin_spot_open_dlg"):
            for k in ("admin_spot_room", "admin_spot_notes",
                      "admin_spot_x", "admin_spot_y"):
                st.session_state.pop(k, None)
            _spot_define_dialog()

    just_added = st.session_state.pop("admin_spot_just_added", None)
    if just_added:
        st.success(just_added)

    floor = st.selectbox(
        "층 선택",
        options=ADMIN_FLOORS,
        key="admin_spot_floor",
    )
    spots = data.load_spots(floor)

    # --- 이 층의 spot 목록 + 편집/삭제 ---
    st.markdown(
        f"<div style='margin-top:0.6rem; font-weight:700; color:#0F172A; font-size:1.02rem;'>"
        f"이 층의 spot 목록 ({len(spots)}건)</div>",
        unsafe_allow_html=True,
    )
    if not spots:
        st.info("아직 정의된 spot이 없습니다. 도면 위 빈 곳을 클릭하고 폼을 채워 추가하세요.")
        return

    used = {e.spot_id for e in data.load_equipment() if e.spot_id}
    # 컬럼 7개: ID / 방이름 / 비고 / 좌표 / 사용 / [속성변경] / [삭제]
    cols_ratio = [1.3, 1.9, 1.4, 0.9, 0.7, 0.9, 0.7]
    header = st.columns(cols_ratio)
    for col, txt in zip(header,
                        ["spot ID", "방이름", "비고", "좌표(%)", "사용", "", ""]):
        col.markdown(
            f"<div style='color:#64748B; font-size:0.78rem; font-weight:600;'>{txt}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<hr style='margin:0.3rem 0; border-color:#E2E8F0;'>",
                unsafe_allow_html=True)

    for s in spots:
        row = st.columns(cols_ratio, vertical_alignment="center")
        in_use = s.spot_id in used
        row[0].markdown(
            f"<span style='font-weight:600; color:#0F172A;'>{s.spot_id}</span>",
            unsafe_allow_html=True,
        )
        row[1].markdown(s.room_name)
        row[2].markdown(
            f"<span style='color:#475569;'>{s.notes or '-'}</span>",
            unsafe_allow_html=True,
        )
        row[3].markdown(
            f"<span style='color:#334155; font-size:0.85rem;'>"
            f"{s.x_pct:.1f} / {s.y_pct:.1f}</span>",
            unsafe_allow_html=True,
        )
        row[4].markdown(
            "<span style='background:#FEF3C7; color:#92400E; padding:0.1rem 0.4rem; "
            "border-radius:6px; font-size:0.74rem;'>사용 중</span>"
            if in_use else
            "<span style='color:#94A3B8; font-size:0.78rem;'>미사용</span>",
            unsafe_allow_html=True,
        )
        with row[5]:
            if st.button("속성 변경", key=f"admin_spot_edit_{s.spot_id}",
                         use_container_width=True):
                st.session_state["admin_spot_edit_id"] = s.spot_id
                st.rerun()
        with row[6]:
            if st.button("삭제", key=f"admin_spot_del_{s.spot_id}",
                         use_container_width=True, disabled=in_use):
                data.delete_spot(s.spot_id)
                st.rerun()

    # 저장 후 토스트
    msg = st.session_state.pop("admin_spot_save_msg", None)
    if msg:
        st.success(msg)

    # 편집 모달 트리거
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
    tabs = ["위치 마스터", "사용자 관리"]
    section = st.radio(
        "관리자 섹션",
        tabs,
        horizontal=True,
        key="admin_tab",
        label_visibility="collapsed",
    )
    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    if section == "위치 마스터":
        _spot_master_tab()
    else:
        _user_admin_tab()
