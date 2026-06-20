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
    )
    return fig


def _spot_master_tab() -> None:
    st.markdown(
        "<div style='color:#64748B; font-size:0.92rem; margin-bottom:0.4rem;'>"
        "도면 위 빈 곳을 클릭해 신규 위치(spot)를 정의합니다. "
        "기존 spot은 주황색 점으로 표시됩니다. 클릭한 좌표가 폼에 자동 입력됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    floor = st.selectbox(
        "층 선택",
        options=ADMIN_FLOORS,
        key="admin_spot_floor",
    )
    spots = data.load_spots(floor)

    fig = _make_floor_fig(floor, spots)
    if fig is None:
        st.error(
            f"`{floor}` 도면 이미지가 없습니다. "
            f"`scripts/convert_floor_pdfs.py` 실행 후 다시 시도하세요."
        )
        return

    event = st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": [
                "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
            ],
        },
        on_select="rerun",
        selection_mode=["points"],
        key=f"admin_floor_chart_{floor}",
    )

    picked_x = picked_y = None
    if (event and getattr(event, "selection", None)
            and getattr(event.selection, "points", None)):
        # 마지막 클릭 좌표 — 도면 픽셀 → % 환산
        pt = event.selection.points[-1]
        px, py = pt["x"], pt["y"]
        picked_x = round(px / FIG_W * 100, 2)
        picked_y = round((FIG_H - py) / FIG_H * 100, 2)
        # 폼 키에 반영
        st.session_state["admin_spot_x"] = picked_x
        st.session_state["admin_spot_y"] = picked_y

    st.markdown(
        "<div style='color:#94A3B8; font-size:0.8rem; margin-top:-0.5rem;'>"
        "휠/핀치 줌 · 드래그 팬 · 도면 어디든 클릭하면 좌표 픽업 (그리드 단위로 스냅)"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

    # --- 신규 spot 폼 ---
    with st.expander("신규 spot 정의", expanded=True):
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

        if st.button("spot 추가", type="primary", use_container_width=True,
                     key="admin_spot_submit"):
            if not room_name.strip():
                st.error("방이름을 입력해 주세요.")
            else:
                new_id = data.next_spot_id(floor)
                data.add_spot(Spot(
                    spot_id=new_id, floor=floor,
                    room_name=room_name.strip(), notes=notes.strip(),
                    x_pct=x_pct, y_pct=y_pct,
                ))
                # 폼 초기화
                for k in ("admin_spot_room", "admin_spot_notes",
                          "admin_spot_x", "admin_spot_y"):
                    st.session_state.pop(k, None)
                st.success(f"{new_id} 등록 완료 ({room_name.strip()}).")
                st.rerun()

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

    # 인라인 편집으로 열린 spot 1개 추적 (한 번에 한 행만 펼침)
    open_spot_key = "admin_spot_edit_open"
    open_spot_id = st.session_state.get(open_spot_key)

    for s in spots:
        row = st.columns(cols_ratio, vertical_alignment="center")
        in_use = s.spot_id in used
        is_open = open_spot_id == s.spot_id
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
            btn_label = "닫기" if is_open else "속성 변경"
            if st.button(btn_label, key=f"admin_spot_edit_{s.spot_id}",
                         use_container_width=True,
                         type="primary" if is_open else "secondary"):
                # 다른 행이 열려 있으면 닫고, 같은 행 클릭이면 토글
                st.session_state[open_spot_key] = (
                    None if is_open else s.spot_id
                )
                # 폼 키 초기화 (이전 spot의 값이 남아있지 않도록)
                for k in ("edit_room_name", "edit_notes",
                          "edit_x_pct", "edit_y_pct"):
                    st.session_state.pop(k, None)
                st.rerun()
        with row[6]:
            if st.button("삭제", key=f"admin_spot_del_{s.spot_id}",
                         use_container_width=True, disabled=in_use):
                data.delete_spot(s.spot_id)
                st.rerun()

        # 인라인 편집 영역 — 펼침
        if is_open:
            with st.container(border=True):
                st.markdown(
                    f"<div style='color:#475569; font-size:0.85rem; "
                    f"margin-bottom:0.4rem;'>"
                    f"<b style='color:#0F172A;'>{s.spot_id}</b> 속성 변경 "
                    f"<span style='color:#94A3B8;'>· 층 <b>{s.floor}</b> "
                    f"(spot_id/층은 변경 불가)</span></div>",
                    unsafe_allow_html=True,
                )
                if in_use:
                    st.caption(
                        "이 spot은 장비에 매핑되어 있습니다. "
                        "방이름·좌표 변경 시 해당 장비의 위치 정보도 함께 갱신됩니다."
                    )
                ec1, ec2 = st.columns([1, 2])
                with ec1:
                    new_room = st.text_input(
                        "방이름",
                        value=s.room_name,
                        key="edit_room_name",
                    )
                with ec2:
                    new_notes = st.text_input(
                        "비고",
                        value=s.notes,
                        key="edit_notes",
                    )
                ec3, ec4, _ = st.columns([1, 1, 2])
                with ec3:
                    new_x = st.number_input(
                        "x_pct (도면 폭 %)",
                        min_value=0.0, max_value=100.0,
                        value=float(s.x_pct), step=0.5, format="%.2f",
                        key="edit_x_pct",
                    )
                with ec4:
                    new_y = st.number_input(
                        "y_pct (도면 높이 %)",
                        min_value=0.0, max_value=100.0,
                        value=float(s.y_pct), step=0.5, format="%.2f",
                        key="edit_y_pct",
                    )

                # 변경 여부 표시
                changed = (
                    new_room.strip() != s.room_name
                    or new_notes.strip() != s.notes
                    or round(new_x, 2) != round(s.x_pct, 2)
                    or round(new_y, 2) != round(s.y_pct, 2)
                )

                bc1, bc2 = st.columns([1, 1])
                with bc1:
                    if st.button(
                        "저장",
                        type="primary",
                        use_container_width=True,
                        key=f"admin_spot_save_{s.spot_id}",
                        disabled=not changed or not new_room.strip(),
                    ):
                        n_synced = data.update_spot_with_equipment_sync(
                            data.Spot(
                                spot_id=s.spot_id, floor=s.floor,
                                room_name=new_room.strip(),
                                notes=new_notes.strip(),
                                x_pct=float(new_x), y_pct=float(new_y),
                            )
                        )
                        st.session_state[open_spot_key] = None
                        msg = f"{s.spot_id} 속성 저장 완료."
                        if n_synced:
                            msg += f" 매핑 장비 {n_synced}건의 위치 정보도 동기화."
                        st.session_state["admin_spot_save_msg"] = msg
                        st.rerun()
                with bc2:
                    if st.button(
                        "취소",
                        use_container_width=True,
                        key=f"admin_spot_cancel_{s.spot_id}",
                    ):
                        st.session_state[open_spot_key] = None
                        st.rerun()

    # 저장 후 토스트
    msg = st.session_state.pop("admin_spot_save_msg", None)
    if msg:
        st.success(msg)


def render() -> None:
    if not auth.is_admin():
        st.error("관리자 권한이 필요합니다. 사이드바의 일반 메뉴를 이용해 주세요.")
        return

    page_header(
        "관리자 메뉴",
        "관리자 전용 설정 — 위치 마스터(spot) 정의, 사용자 관리(v2 예정) 등.",
    )

    tab_spots, = st.tabs(["위치 마스터 (spot)"])
    with tab_spots:
        _spot_master_tab()
