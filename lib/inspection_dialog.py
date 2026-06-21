"""신규 점검 모달 — 지적·오동작 관리에서 호출.

`@st.dialog`로 점검 폼을 띄운다.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from lib import data
from lib.data import (
    Deficiency, Equipment, InspectionRound, InspectionTask, Malfunction, Notice,
    TASK_INSPECTION_TYPES,
    add_deficiency, add_equipment, add_malfunction, add_notice,
    add_round, add_task,
    default_inspection_types_for,
    location_id_from_spot,
    next_equipment_id, next_notice_no, next_round_id, next_serial,
    next_task_id,
)
from lib.qr import make_qr, payload_for
from lib.ui import badge, fmt_date, photo_input


# 시설 카테고리 (소화기·소화전·감지기 등) — Equipment.category 에서 사용
EQ_CATEGORIES = [
    "소화기", "간이소화장치", "비상경보장치", "가스누설경보기",
    "간이피난유도선", "방화포", "감지기", "발신기", "수신기",
    "확산소화기", "유도등", "스프링클러", "소화전", "기타",
]

# 등록 가능한 층
EQ_FLOORS = ["B3", "B2", "B1", "P4", "L1", "L2", "2F", "4F", "5F", "6F", "SRV"]


INSPECTION_TYPES = ["임시소방시설", "피난로 등", "화기취급감독"]

# 별지9 카테고리 (임시소방시설 6종 + 그 외 6종)
MAL_CATEGORIES_TEMP = ["소화기", "간이소화장치", "비상경보장치",
                       "가스누설경보기", "간이피난유도선", "방화포"]
MAL_CATEGORIES_OTHER = ["감지기", "발신기", "수신기",
                        "확산소화기", "유도등", "기타"]
MAL_ALL_CATEGORIES = MAL_CATEGORIES_TEMP + MAL_CATEGORIES_OTHER


@st.dialog("신규 점검 입력", width="large")
def new_inspection_dialog() -> None:
    """신규 점검 폼 모달. `st.session_state["inspect_target"]`가 있으면 사전 선택."""
    eq_all = data.load_equipment()

    options = [f"{e.equipment_id} · {e.location_id} · {e.equipment_name}" for e in eq_all]
    id_to_idx = {e.equipment_id: i for i, e in enumerate(eq_all)}
    default_idx = id_to_idx.get(st.session_state.get("inspect_target"), 0)
    sel_label = st.selectbox("점검 대상 장비", options=options, index=default_idx,
                             key="dlg_inspect_sel")
    sel_id = sel_label.split(" · ")[0]
    eq = next(e for e in eq_all if e.equipment_id == sel_id)

    # 장비 정보 + QR
    info_col, qr_col = st.columns([2.4, 1])
    with info_col:
        st.markdown(
            "<div style='background:#F8FAFC; border:1px solid #E2E8F0; "
            "border-radius:10px; padding:0.85rem 1rem;'>"
            f"<div style='font-weight:700; color:#0F172A; font-size:1.0rem; margin-bottom:0.3rem;'>"
            f"{eq.equipment_name}</div>"
            f"<div style='color:#475569; font-size:0.9rem; line-height:1.7;'>"
            f"<b>장비 ID</b> · {eq.equipment_id} &nbsp;|&nbsp; "
            f"<b>위치</b> · {eq.location_id} ({eq.floor}/{eq.zone})<br>"
            f"<b>카테고리</b> · {eq.category}<br>"
            f"<b>현재 상태</b> · {badge(eq.health_status)} {badge(eq.qr_status)}"
            "</div></div>",
            unsafe_allow_html=True,
        )
    with qr_col:
        st.image(make_qr(eq, box_size=5), width=130)

    st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        inspector = st.text_input("점검자", value="박소방", key="dlg_inspector")
    with c2:
        inspect_date = st.date_input("점검일", value=date.today(), key="dlg_inspect_date")

    types_selected = st.multiselect(
        "점검 종류 (별지5)",
        options=list(INSPECTION_TYPES),
        key="dlg_chk_types",
        placeholder="해당 점검종류를 선택하세요 (복수 가능)",
    )

    st.markdown("<b style='color:#334155; font-size:0.92rem; margin-top:0.5rem;'>점검 결과</b>",
                unsafe_allow_html=True)
    result = st.radio("결과", ["양호", "불량"], horizontal=True,
                      label_visibility="collapsed", key="dlg_result")

    issue = ""
    action_immediate = False
    action_note_now = ""
    action_photo_now = None
    confirmer = inspector

    if result == "불량":
        issue = st.text_area("지적사항",
                             placeholder="예: 1-A계단 피난구 유도등 점등 불량",
                             key="dlg_issue")
        st.info(f"통보서 자동 발급 (다음 번호: **{next_notice_no(inspect_date)}**)")
        action_immediate = st.checkbox(
            "현장에서 즉시 조치 완료",
            value=False,
            key="dlg_action_imm",
            help="체크 시 통보서가 즉시 완료 처리되어 별지6 PDF 즉시 출력 가능.",
        )
        if action_immediate:
            confirmer = st.text_input("확인자 (선택)", value=inspector, key="dlg_confirmer")
            action_note_now = st.text_area(
                "조치 내용 (선택)",
                placeholder="예: 적재물 이동, 흡연자에게 중단 요청 등",
                key="dlg_action_note",
            )
            action_photo_now = photo_input(
                "조치 사진 (선택)",
                key="dlg_action_photo",
                help_text="휴대폰·태블릿에서는 카메라 촬영 탭으로 즉시 촬영 가능합니다.",
            )
        else:
            st.markdown(
                "<div style='color:#64748B; font-size:0.82rem;'>"
                "→ 통보서는 미완료 상태로 발급되며, 조치 담당자가 별도 시점에 조치 입력합니다."
                "</div>",
                unsafe_allow_html=True,
            )

    if st.button("점검 결과 제출", type="primary", use_container_width=True,
                 key="dlg_submit"):
        if not types_selected:
            st.error("점검 종류를 최소 1개 선택해야 합니다.")
            return
        if result == "불량" and not issue.strip():
            st.error("불량인 경우 지적사항을 입력해 주세요.")
            return

        # 이 장비의 활성 회차에서 미완료 Task 자동 매핑 (있으면)
        matched_task_id: str | None = None
        for t in data.load_tasks():
            if (t.round_id and not t.excluded
                    and t.equipment_label
                    and eq.location_id in t.equipment_label
                    and t.status not in ("Completed",)):
                matched_task_id = t.task_id
                break

        new_no = None
        if result == "불량":
            new_no = next_notice_no(inspect_date)
            photo_bytes = action_photo_now.getvalue() if action_photo_now else None
            add_notice(Notice(
                notice_no=new_no,
                inspection_date=inspect_date,
                floor=eq.floor, zone=eq.zone,
                inspection_type=types_selected[0],  # type: ignore[arg-type]
                issue=issue.strip(), photo_path=None,
                submitter=inspector,
                confirmer=confirmer if action_immediate else "김소장",
                action_done=action_immediate,
                action_at=inspect_date if action_immediate else None,
                action_note=action_note_now.strip() if action_immediate else "",
                action_photo=photo_bytes,
                task_id=matched_task_id,
            ))

        new_def_id = data.next_deficiency_id()
        add_deficiency(Deficiency(
            deficiency_id=new_def_id,
            inspection_date=inspect_date, inspector=inspector,
            floor=eq.floor, zone=eq.zone,
            inspection_types=types_selected,  # type: ignore[arg-type]
            issue=issue.strip() or "양호",
            resolution=("완료" if (result == "양호" or action_immediate) else "불가"),  # type: ignore[arg-type]
            confirmer=confirmer if (result == "양호" or action_immediate) else None,
            notice_no=new_no,
            task_id=matched_task_id,
        ))

        # 장비의 최근 점검일·건강 상태 갱신 (KPI 카드 즉시 반영)
        data.record_equipment_inspection(
            eq.equipment_id, inspect_date,
            "PASS" if result == "양호" else "FAIL",
        )

        # 모달 닫기 (rerun으로 페이지 갱신)
        st.session_state.pop("inspect_target", None)
        st.session_state["just_submitted_inspection"] = True
        st.rerun()


def _add_task_map_picker(round_id: str, candidates, all_eq, already_locs):
    """[+ Task 추가] 모달의 도면 선택 탭. 회차 매칭 장비 + 빈 spot 마커 + 단일 클릭 선택.
    candidates: 회차 매칭 후보 장비 (미포함만). all_eq: 전체 장비.
    already_locs: 이미 회차에 포함된 location_id 집합.
    반환: 선택된 항목 dict ({'type': 'equipment'|'empty_spot', 'data': ...}) 또는 None.
    """
    import base64
    from pathlib import Path
    import plotly.graph_objects as go
    from lib.floor_widget import (
        control_toggle, floor_legend_html, plotly_config,
    )

    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"
    FIG_W, FIG_H = 2978, 2105

    # 후보 장비 또는 spot 정의된 층 모음 (빈 spot도 추가 대상이므로 spot 층 포함)
    all_spots = data.load_spots()
    spot_floors = {s.floor for s in all_spots}
    cand_floors = sorted(
        {c.floor for c in candidates if c.floor} | spot_floors
    )
    if not cand_floors:
        st.info("도면을 표시할 수 있는 층이 없습니다.")
        return None

    floor = st.selectbox(
        "층", options=cand_floors,
        key=f"add_tsk_map_floor_{round_id}",
    )

    # 컨트롤 토글 + 임시 위치 추가 토글 + 범례
    cc, ac, lc = st.columns([1.2, 1.6, 4])
    with cc:
        locked = control_toggle(f"add_tsk_map_{round_id}", default_locked=False)
    with ac:
        add_spot_mode_key = f"add_tsk_add_spot_mode_{round_id}"
        if add_spot_mode_key not in st.session_state:
            st.session_state[add_spot_mode_key] = False
        add_spot_mode = st.toggle(
            "🆕 임시 위치 추가",
            value=st.session_state[add_spot_mode_key],
            key=add_spot_mode_key,
            help="ON 시 도면 빈 곳 클릭으로 임시 spot 좌표 픽업 (기본 OFF)",
        )
    with lc:
        st.markdown(floor_legend_html(), unsafe_allow_html=True)

    img_path = ASSETS_DIR / f"{floor}.png"
    if not img_path.exists():
        st.warning(f"{floor} 도면 이미지가 없습니다.")
        return None
    uri = "data:image/png;base64," + base64.b64encode(img_path.read_bytes()).decode()

    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    # 후보 장비 (도면 매칭 가능 = floor 일치 + 좌표 있음)
    # 매칭(점검 주기 일치) = 파란 / 비매칭 = 옅은 회색 (자유 추가)
    floor_cands = [c for c in candidates if c.floor == floor]
    _round_obj = data.get_round(round_id)
    _round_task_type = _round_obj.task_type if _round_obj else ""
    matched_set = {e.equipment_id for e in candidates
                   if _round_task_type in (e.inspection_types or [])}
    if floor_cands:
        spots = {s.spot_id: s for s in data.load_spots(floor)}
        match_xs, match_ys, match_txt, match_cd = [], [], [], []
        nomat_xs, nomat_ys, nomat_txt, nomat_cd = [], [], [], []
        for c in floor_cands:
            sp = spots.get(c.spot_id) if c.spot_id else None
            if not sp:
                continue
            x = sp.x_pct / 100 * FIG_W
            y = FIG_H - sp.y_pct / 100 * FIG_H
            txt = c.equipment_id.split("-")[-1]
            cd = (c.equipment_id, c.equipment_name, c.location_id)
            if c.equipment_id in matched_set:
                match_xs.append(x); match_ys.append(y)
                match_txt.append(txt); match_cd.append(cd)
            else:
                nomat_xs.append(x); nomat_ys.append(y)
                nomat_txt.append(txt); nomat_cd.append(cd)
        if nomat_xs:
            fig.add_trace(go.Scatter(
                x=nomat_xs, y=nomat_ys, mode="markers+text",
                text=nomat_txt, textposition="top center",
                textfont=dict(size=10, color="#475569"),
                marker=dict(size=16, color="#CBD5E1",
                            line=dict(color="#94A3B8", width=1.5)),
                customdata=nomat_cd,
                hovertemplate=(
                    "<b>%{customdata[1]}</b> (매핑 외 · 자유 추가)<br>"
                    "%{customdata[2]} · %{customdata[0]}<extra></extra>"
                ),
                name="매핑 외", showlegend=False,
            ))
        if match_xs:
            fig.add_trace(go.Scatter(
                x=match_xs, y=match_ys, mode="markers+text",
                text=match_txt, textposition="top center",
                textfont=dict(size=10, color="#0F172A"),
                marker=dict(size=18, color="#2563EB",
                            line=dict(color="#FFFFFF", width=2)),
                customdata=match_cd,
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "%{customdata[2]} · %{customdata[0]}<extra></extra>"
                ),
                name="후보 장비", showlegend=False,
            ))

    # 이미 포함된 장비 (회색 비활성 마커)
    floor_already = [
        e for e in all_eq
        if e.floor == floor and e.location_id in already_locs
    ]
    floor_spots = data.load_spots(floor)
    if floor_already:
        spot_map = {s.spot_id: s for s in floor_spots}
        xs, ys, custom = [], [], []
        for e in floor_already:
            sp = spot_map.get(e.spot_id) if e.spot_id else None
            if not sp:
                continue
            xs.append(sp.x_pct / 100 * FIG_W)
            ys.append(FIG_H - sp.y_pct / 100 * FIG_H)
            custom.append((e.equipment_id, e.equipment_name, e.location_id))
        if xs:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers",
                marker=dict(size=14, color="#64748B",
                            line=dict(color="#FFFFFF", width=1.5)),
                customdata=custom,
                hovertemplate=(
                    "<b>%{customdata[1]}</b> (이미 포함)<br>"
                    "%{customdata[2]} · %{customdata[0]}<extra></extra>"
                ),
                name="이미 포함", showlegend=False,
                hoverinfo="text",
            ))

    # 빈 spot / 임시 spot — 다이아 마커
    used_spot_ids = {e.spot_id for e in all_eq if e.spot_id and e.floor == floor}
    already_empty_spot_ids = {
        t.equipment_label.split(" - ")[0]
        for t in data.tasks_of_round(round_id, include_excluded=True)
        if "(빈 spot)" in t.equipment_label or "(임시 spot)" in t.equipment_label
    }
    empty_spots = [
        s for s in floor_spots
        if s.spot_id not in used_spot_ids and not s.is_temporary
    ]
    temp_spots = [s for s in floor_spots if s.is_temporary]

    if empty_spots:
        xs, ys, txts, custom = [], [], [], []
        for sp in empty_spots:
            xs.append(sp.x_pct / 100 * FIG_W)
            ys.append(FIG_H - sp.y_pct / 100 * FIG_H)
            in_round = sp.spot_id in already_empty_spot_ids
            txts.append("빈·포함" if in_round else "빈")
            custom.append(("spot", sp.spot_id, sp.room_name, in_round))
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            text=txts, textposition="bottom center",
            textfont=dict(size=9, color="#94A3B8"),
            marker=dict(size=14, color="#94A3B8",
                        line=dict(color="#FFFFFF", width=1.5),
                        symbol="diamond"),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[2]}</b> (빈 spot)<br>"
                "%{customdata[1]}<extra></extra>"
            ),
            name="빈 spot", showlegend=False,
        ))

    if temp_spots:
        xs, ys, txts, custom = [], [], [], []
        for sp in temp_spots:
            xs.append(sp.x_pct / 100 * FIG_W)
            ys.append(FIG_H - sp.y_pct / 100 * FIG_H)
            in_round = sp.spot_id in already_empty_spot_ids
            txts.append("임시·포함" if in_round else "임시")
            custom.append(("spot", sp.spot_id, sp.room_name, in_round))
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            text=txts, textposition="bottom center",
            textfont=dict(size=9, color="#1D4ED8"),
            marker=dict(size=14, color="#3B82F6",
                        line=dict(color="#1E40AF", width=2),
                        symbol="diamond-open"),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[2]}</b> (임시 spot)<br>"
                "%{customdata[1]} · 관리자 검증 대기<extra></extra>"
            ),
            name="임시 spot", showlegend=False,
        ))

    # 임시 위치 추가 모드 ON일 때만 클릭 가능 격자 추가
    if add_spot_mode:
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
            customdata=[("grid",)] * len(grid_x),
            hovertemplate="여기 클릭 → 임시 spot 좌표 픽업<extra></extra>",
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
        # 잠금 토글 시 줌/팬 상태 유지
        uirevision=f"floor_addtsk_{floor}",
    )

    if locked:
        from lib.floor_widget import lock_overlay_css
        lock_overlay_css()
    event = st.plotly_chart(
        fig, use_container_width=True,
        config=plotly_config(),
        on_select="rerun",
        selection_mode=["points"],
        key=f"add_tsk_map_chart_{round_id}_{floor}",
    )

    # 클릭 → 후보 장비 / 빈 spot / 임시 spot / 격자(빈 곳) 분기
    pending_grid_key = f"add_tsk_pending_grid_{round_id}_{floor}"
    if (not locked and event and getattr(event, "selection", None)
            and getattr(event.selection, "points", None)):
        pt = event.selection.points[-1]
        cd = pt.get("customdata")
        if cd:
            kind = cd[0]
            if kind == "spot":
                _, spot_id, room_name, in_round = cd
                if in_round:
                    st.warning(
                        f"{spot_id} ({room_name})는 이미 회차에 포함되어 있습니다."
                    )
                else:
                    sel_spot = next(
                        (s for s in floor_spots if s.spot_id == spot_id), None
                    )
                    if sel_spot:
                        label = "임시 spot" if sel_spot.is_temporary else "빈 spot"
                        st.success(
                            f"선택: **{sel_spot.spot_id}** · {sel_spot.room_name} "
                            f"({label})"
                        )
                        st.session_state.pop(pending_grid_key, None)
                        return {"type": "empty_spot", "data": sel_spot}
            elif kind == "grid":
                # 빈 곳 클릭 — 임시 spot 좌표 픽업
                x_pct = round(pt["x"] / FIG_W * 100, 2)
                y_pct = round((FIG_H - pt["y"]) / FIG_H * 100, 2)
                st.session_state[pending_grid_key] = (x_pct, y_pct)
            else:
                # 장비 마커 (기존 customdata 포맷: (eq_id, name, location_id))
                eq_id = cd[0]
                picked = next(
                    (c for c in candidates if c.equipment_id == eq_id), None
                )
                if picked:
                    st.success(
                        f"선택: **{picked.equipment_id}** · "
                        f"{picked.equipment_name} ({picked.location_id})"
                    )
                    st.session_state.pop(pending_grid_key, None)
                    return {"type": "equipment", "data": picked}
                st.warning(f"{eq_id}는 이미 회차에 포함된 장비입니다.")

    # 임시 spot 추가 폼 — 빈 곳 클릭으로 좌표 픽업된 상태일 때 노출
    pending = st.session_state.get(pending_grid_key)
    if pending:
        x_pct, y_pct = pending
        st.markdown(
            f"<div style='background:#EFF6FF; border:1px solid #BFDBFE; "
            f"border-radius:8px; padding:0.6rem 0.8rem; margin-top:0.3rem;'>"
            f"<b style='color:#1E3A8A;'>🆕 임시 spot 위치 픽업됨</b> · "
            f"좌표 ({x_pct}, {y_pct}) · 다음 spot ID: "
            f"<code>{data.next_spot_id(floor)}</code><br>"
            f"<span style='color:#475569; font-size:0.84rem;'>"
            f"위치 설명을 입력하고 [임시 spot + Task 추가]를 누르면 "
            f"임시 spot이 생성되고 Task도 함께 등록됩니다. "
            f"관리자가 위치 마스터에서 검증 후 정식 전환합니다.</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
        desc = st.text_input(
            "위치 설명 (room_name) *",
            key=f"add_tsk_temp_desc_{round_id}",
            placeholder="예: 4F 동측 출입구 옆",
        )
        bcols = st.columns([1, 1])
        with bcols[0]:
            if st.button(
                "임시 spot + Task 추가",
                type="primary", use_container_width=True,
                key=f"add_tsk_temp_submit_{round_id}",
                disabled=not desc.strip(),
            ):
                new_id = data.next_spot_id(floor)
                from lib.data import Spot
                new_spot = Spot(
                    spot_id=new_id, floor=floor,
                    room_name=desc.strip(), notes="임시 등록 (검증 대기)",
                    x_pct=float(x_pct), y_pct=float(y_pct),
                    is_temporary=True,
                )
                data.add_spot(new_spot)
                st.session_state.pop(pending_grid_key, None)
                st.session_state.pop(f"add_tsk_temp_desc_{round_id}", None)
                return {"type": "empty_spot", "data": new_spot}
        with bcols[1]:
            if st.button(
                "좌표 취소",
                use_container_width=True,
                key=f"add_tsk_temp_cancel_{round_id}",
            ):
                st.session_state.pop(pending_grid_key, None)
                st.session_state.pop(f"add_tsk_temp_desc_{round_id}", None)

    if add_spot_mode:
        st.caption(
            "🆕 임시 위치 추가 모드 — 도면 빈 곳 클릭으로 좌표 픽업. "
            "마커 클릭은 기존 장비/spot 선택."
        )
    else:
        st.caption(
            "🔵 파란 원 = 매칭 장비 · ⚪ 옅은 회색 원 = 매핑 외(자유 추가) · "
            "⚫ 진회색 = 이미 포함 · ◇ 회색 다이아 = 빈 spot · 🔷 파란 다이아 = 임시 spot · "
            "임시 위치를 새로 만들려면 상단 토글 활성화"
        )
    return None


@st.dialog("회차에 Task 추가", width="large")
def add_task_to_round_dialog(round_id: str) -> None:
    """v1.5 자유 점검 회차에 Task 1건 동적 추가.
    진입 방식 — 직접 선택 / QR 스캔 / 📍 도면 선택 3가지."""
    r = data.get_round(round_id)
    if not r:
        st.error("회차를 찾을 수 없습니다.")
        return

    st.markdown(
        f"<div style='color:#64748B; font-size:0.86rem; margin-bottom:0.5rem;'>"
        f"<b>{r.round_id}</b> · {r.task_type}<br>"
        f"담당 {r.assignee or '미지정'} · 마감 {fmt_date(r.due_date)}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 후보 = 회차 미포함 장비 전체 (점검 주기 매칭 무관, v1.5+ 자유화)
    # 매칭 장비는 우선 정렬, 비매칭은 별도 표기로 인지 가능
    all_eq = data.load_equipment()

    # 이미 회차에 포함된 장비는 후보에서 제외 (location_id 기준)
    already_locs = {
        t.equipment_label.split(" - ")[0].strip()
        for t in data.tasks_of_round(round_id, include_excluded=True)
    }

    def _is_match(e):
        return (r.task_type in TASK_INSPECTION_TYPES
                and r.task_type in (e.inspection_types or []))

    matched = [e for e in all_eq
               if e.location_id not in already_locs and _is_match(e)]
    unmatched = [e for e in all_eq
                 if e.location_id not in already_locs and not _is_match(e)]
    candidates = matched + unmatched  # 매칭 우선 정렬

    # 진입 방식 — 직접 선택 / QR 스캔 / 📍 도면 선택 (모바일 친화)
    tab_pick, tab_qr, tab_map = st.tabs(["직접 선택", "QR 스캔", "📍 도면 선택"])
    sel_eq = None        # Equipment (장비 기반 추가)
    sel_empty_spot = None  # Spot (빈 spot 기반 추가)
    with tab_pick:
        eq_idx = st.selectbox(
            "추가할 장비 (매칭 우선 · 매핑 외 장비도 자유 추가 가능)",
            options=range(len(candidates)),
            format_func=lambda i: (
                f"{'✓' if _is_match(candidates[i]) else '·'} "
                f"{candidates[i].location_id} · {candidates[i].equipment_name} "
                f"({candidates[i].category})"
            ),
            key=f"add_tsk_eq_{round_id}",
        )
        sel_eq = candidates[eq_idx]
    with tab_qr:
        st.caption("장비에 부착된 QR을 카메라로 비추면 해당 장비가 자동 선택됩니다.")
        try:
            from streamlit_qrcode_scanner import qrcode_scanner
            qr_val = qrcode_scanner(key=f"add_tsk_qr_{round_id}")
        except Exception as e:
            st.error(f"QR 스캐너를 불러올 수 없습니다 ({e}). 직접 선택 탭을 이용해 주세요.")
            qr_val = None
        manual = st.text_input(
            "수동 입력 (EQ-NNNN 또는 QR 페이로드 URL)",
            key=f"add_tsk_manual_{round_id}",
            placeholder="예: EQ-0006",
        )
        # 페이로드 → equipment_id 추출 (대시보드 점검 모달과 동일 로직)
        import re

        def _extract(payload):
            if not payload:
                return None
            s = str(payload).strip()
            m = re.search(r"[?&]eq=([A-Za-z0-9\-]+)", s)
            if m:
                return m.group(1).upper()
            m = re.search(r"\bEQ-\d{4,}\b", s.upper())
            return m.group(0) if m else None

        eq_id = _extract(qr_val) or _extract(manual)
        if eq_id:
            matched = next((c for c in candidates if c.equipment_id == eq_id), None)
            if matched:
                sel_eq = matched
                st.success(
                    f"인식: {matched.equipment_id} · {matched.equipment_name} "
                    f"({matched.location_id})"
                )
            else:
                # 회차 후보에는 없지만 전체 장비에 있는 경우
                other = next((e for e in all_eq if e.equipment_id == eq_id), None)
                if other and other.location_id in already_locs:
                    st.warning(
                        f"{eq_id}는 이미 이 회차에 포함된 장비입니다."
                    )
                elif other:
                    st.warning(
                        f"{eq_id}는 이 회차 점검 유형({r.task_type})에 매핑되어 있지 않습니다. "
                        f"장비 마스터의 inspection_types에 추가 후 다시 시도하세요."
                    )
                else:
                    st.error(f"장비를 찾을 수 없습니다: {eq_id}")

    with tab_map:
        picked = _add_task_map_picker(
            round_id, candidates, all_eq, already_locs,
        )
        if picked is not None:
            if picked.get("type") == "empty_spot":
                sel_empty_spot = picked["data"]
                sel_eq = None  # 빈 spot은 장비 없음
            else:
                sel_eq = picked["data"]

    note = st.text_input(
        "메모(선택)",
        key=f"add_tsk_note_{round_id}",
        placeholder=r.note,
    )

    has_selection = sel_eq is not None or sel_empty_spot is not None
    if st.button(
        "추가", type="primary", use_container_width=True,
        key=f"add_tsk_submit_{round_id}",
        disabled=not has_selection,
    ):
        if not has_selection:
            st.error("장비를 선택하거나 QR을 인식하거나 빈 spot을 골라 주세요.")
            return
        from lib.data import next_task_id, add_task, _refresh_round_status
        new_tsk = next_task_id()
        if sel_empty_spot is not None:
            # spot 기반 — 장비 없이 spot 정보만 사용 (임시/정식 구분)
            spot_tag = (
                "(임시 spot)" if sel_empty_spot.is_temporary else "(빈 spot)"
            )
            equipment_label = (
                f"{sel_empty_spot.spot_id} - {sel_empty_spot.room_name} {spot_tag}"
            )
            floor = sel_empty_spot.floor
            zone = sel_empty_spot.room_name
        else:
            equipment_label = f"{sel_eq.location_id} - {sel_eq.equipment_name}"
            floor = sel_eq.floor
            zone = sel_eq.zone
        add_task(InspectionTask(
            task_id=new_tsk,
            equipment_label=equipment_label,
            task_type=r.task_type,
            assignee=r.assignee or "Unassigned",
            due_date=r.due_date,
            status="Scheduled",
            floor=floor,
            zone=zone,
            note=note.strip() or r.note,
            round_id=round_id,
        ))
        _refresh_round_status(round_id)
        st.session_state["just_added_task"] = new_tsk
        st.rerun()


@st.dialog("조치 입력", width="large")
def action_input_dialog(deficiency_id: str) -> None:
    """v1.5 Deficiency 후속 조치 입력 모달. 작업 조치 관리에서 호출."""
    d = next(
        (x for x in data.load_deficiencies() if x.deficiency_id == deficiency_id),
        None,
    )
    if not d:
        st.error("지적사항을 찾을 수 없습니다.")
        return

    st.markdown(
        f"<div style='color:#475569; font-size:0.88rem; margin-bottom:0.5rem;'>"
        f"<b>{d.deficiency_id}</b>"
        f"{' · 통보서 ' + d.notice_no if d.notice_no else ''}"
        f"<br><b>위치</b> · {d.floor}/{d.zone} · <b>점검일</b> · "
        f"{fmt_date(d.inspection_date)} · 점검자 <b>{d.inspector}</b>"
        f"<br><b>지적사항</b> · {d.issue}"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        confirmer = st.text_input(
            "확인자", value=d.confirmer or "김소장",
            key=f"act_dlg_conf_{deficiency_id}",
        )
    with c2:
        action_at = st.date_input(
            "조치일", value=date.today(),
            key=f"act_dlg_date_{deficiency_id}",
        )
    action_note = st.text_area(
        "조치 내용",
        placeholder="예: 적재물 이동 완료, 전구 교체, 안전핀 재장착 등",
        key=f"act_dlg_note_{deficiency_id}",
    )
    photo = photo_input(
        "조치 결과 사진",
        key=f"act_dlg_photo_{deficiency_id}",
        help_text="휴대폰·태블릿에서는 카메라 촬영 탭으로 즉시 촬영 가능합니다.",
    )

    if st.button(
        "조치 결과 저장", type="primary", use_container_width=True,
        key=f"act_dlg_submit_{deficiency_id}",
    ):
        if not action_note.strip():
            st.error("조치 내용을 입력해 주세요.")
            return
        photo_bytes = photo.getvalue() if photo else None
        data.record_deficiency_action(
            deficiency_id=deficiency_id,
            action_at=action_at,
            action_note=action_note.strip(),
            confirmer=confirmer.strip() or "김소장",
            photo=photo_bytes,
        )
        st.session_state["just_recorded_action"] = deficiency_id
        st.rerun()


@st.dialog("점검 시작", width="large")
def task_inspect_dialog(task_id: str) -> None:
    """task_inspect_inline을 단독 모달로 띄우는 wrapper.
    회차 상세 모달 외부(예: 시설 관리 QR 모달)에서 진입할 때 사용."""
    task_inspect_inline(task_id)


def task_inspect_inline(task_id: str) -> None:
    """Task 단위 점검 입력 본문 — 회차 상세 모달 행 아래 인라인으로도, 단독 모달로도 호출 가능.
    위치 정정 expander 안 도면 spot 선택은 인라인 유지 (모달 분리는 후속).

    이 함수는 데코레이터 없이 호출 가능. 단독 모달로 띄우려면 task_inspect_dialog 사용."""
    t = next((x for x in data.load_tasks() if x.task_id == task_id), None)
    if not t:
        st.error("점검 작업을 찾을 수 없습니다.")
        return

    # 장비 매칭 (location_id 기반 추정)
    eq = None
    if t.equipment_label:
        loc = t.equipment_label.split(" - ")[0].strip()
        eq = next(
            (e for e in data.load_equipment() if e.location_id == loc),
            None,
        )

    st.markdown(
        f"<div style='color:#64748B; font-size:0.85rem; margin-bottom:0.5rem;'>"
        f"<b>{t.task_id}</b> · {t.task_type}<br>"
        f"<b>대상</b> · {t.equipment_label}<br>"
        f"<b>마감</b> · {fmt_date(t.due_date)} · <b>회차</b> · "
        f"{t.round_id or '—'}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 장비 정보 박스 (있으면)
    if eq:
        st.markdown(
            "<div style='background:#F8FAFC; border:1px solid #E2E8F0; "
            "border-radius:10px; padding:0.7rem 0.9rem;'>"
            f"<div style='font-weight:700; color:#0F172A;'>"
            f"{eq.equipment_name}</div>"
            f"<div style='color:#475569; font-size:0.86rem;'>"
            f"위치 {eq.location_id} ({eq.floor}/{eq.zone}) · "
            f"카테고리 {eq.category} · 시리얼 {eq.serial}</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    # 위치 정정 (선택) — Deficiency 저장 시 우선 적용
    override_floor = eq.floor if eq else t.floor
    override_zone = eq.zone if eq else t.zone
    override_label = None  # 사용자 표시용

    with st.expander("장소·구역 정정 (선택)"):
        st.caption(
            "장비 정보의 층/구역이 맞지 않으면 QR 스캔으로 다른 장비를 인식하거나 "
            "도면의 위치(spot)를 직접 골라 정정합니다. 정정된 값은 별지5 row에 반영됩니다."
        )
        tab_qr, tab_spot = st.tabs(["QR 스캔", "도면 spot 선택"])

        # 1) QR 스캔 정정
        with tab_qr:
            try:
                from streamlit_qrcode_scanner import qrcode_scanner
                qr_val = qrcode_scanner(key=f"tsk_loc_qr_{task_id}")
            except Exception as e:
                st.error(f"QR 스캐너를 불러올 수 없습니다 ({e}).")
                qr_val = None
            qr_manual = st.text_input(
                "수동 입력 (EQ-NNNN 또는 QR 페이로드 URL)",
                key=f"tsk_loc_qr_manual_{task_id}",
                placeholder="예: EQ-0006",
            )
            import re

            def _extract(payload):
                if not payload:
                    return None
                s = str(payload).strip()
                m = re.search(r"[?&]eq=([A-Za-z0-9\-]+)", s)
                if m:
                    return m.group(1).upper()
                m = re.search(r"\bEQ-\d{4,}\b", s.upper())
                return m.group(0) if m else None

            picked = _extract(qr_val) or _extract(qr_manual)
            if picked:
                p_eq = next(
                    (e for e in data.load_equipment() if e.equipment_id == picked),
                    None,
                )
                if p_eq:
                    override_floor = p_eq.floor
                    override_zone = p_eq.zone
                    override_label = (
                        f"QR 스캔 정정 → {p_eq.location_id} "
                        f"({p_eq.floor}/{p_eq.zone}) · {p_eq.equipment_name}"
                    )
                else:
                    st.warning(f"장비를 찾을 수 없습니다: {picked}")

        # 2) 도면 spot 선택 정정 — 실제 도면에서 마커 클릭
        with tab_spot:
            import base64
            from pathlib import Path
            import plotly.graph_objects as go
            from lib.floor_widget import (
                control_toggle, floor_legend_html, lock_overlay_css, plotly_config,
            )

            all_spots = data.load_spots()
            spot_floors = sorted({s.floor for s in all_spots})
            if not spot_floors:
                st.info(
                    "정의된 spot이 없습니다. 관리자 메뉴 → 위치 마스터에서 등록."
                )
            else:
                cur_floor = override_floor if override_floor in spot_floors else spot_floors[0]
                floor_pick = st.selectbox(
                    "층",
                    options=spot_floors,
                    index=spot_floors.index(cur_floor),
                    key=f"tsk_loc_spot_floor_{task_id}",
                )

                ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"
                FIG_W, FIG_H = 2978, 2105
                img_path = ASSETS_DIR / f"{floor_pick}.png"
                if not img_path.exists():
                    st.warning(f"{floor_pick} 도면 이미지가 없습니다.")
                else:
                    cc, lc = st.columns([1.2, 5])
                    with cc:
                        locked = control_toggle(
                            f"tsk_loc_map_{task_id}", default_locked=False,
                        )
                    with lc:
                        st.markdown(floor_legend_html(), unsafe_allow_html=True)

                    uri = "data:image/png;base64," + base64.b64encode(
                        img_path.read_bytes()).decode()
                    fig = go.Figure()
                    fig.add_layout_image(dict(
                        source=uri, xref="x", yref="y",
                        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
                        sizing="stretch", layer="below", opacity=1.0,
                    ))

                    floor_spots = [s for s in all_spots if s.floor == floor_pick]
                    # 현재 적용된 spot 식별 — override_zone 또는 t.zone 기준
                    cur_spot_id = None
                    if override_label and "spot 정정 →" in override_label:
                        # 이미 클릭으로 선택된 spot — label에 spot_id 들어있음
                        parts = override_label.split("→")[1].strip().split(" ")
                        if parts:
                            cur_spot_id = parts[0]

                    other_xs, other_ys, other_txt, other_cd = [], [], [], []
                    cur_xs, cur_ys, cur_txt = [], [], []
                    for sp in floor_spots:
                        x = sp.x_pct / 100 * FIG_W
                        y = FIG_H - sp.y_pct / 100 * FIG_H
                        if sp.spot_id == cur_spot_id:
                            cur_xs.append(x); cur_ys.append(y)
                            cur_txt.append(sp.spot_id.split("-")[-1])
                        else:
                            other_xs.append(x); other_ys.append(y)
                            other_txt.append(sp.spot_id.split("-")[-1])
                            other_cd.append((sp.spot_id, sp.room_name, sp.floor))

                    if other_xs:
                        fig.add_trace(go.Scatter(
                            x=other_xs, y=other_ys, mode="markers+text",
                            text=other_txt, textposition="top center",
                            textfont=dict(size=10, color="#92400E"),
                            marker=dict(size=16, color="#FDE68A",
                                        line=dict(color="#F59E0B", width=1.5)),
                            customdata=other_cd,
                            hovertemplate=(
                                "<b>%{customdata[1]}</b><br>"
                                "%{customdata[0]} · %{customdata[2]}<extra></extra>"
                            ),
                            name="spot", showlegend=False,
                        ))
                    if cur_xs:
                        fig.add_trace(go.Scatter(
                            x=cur_xs, y=cur_ys, mode="markers+text",
                            text=cur_txt, textposition="top center",
                            textfont=dict(size=12, color="#1D4ED8"),
                            marker=dict(size=22, color="#2563EB",
                                        line=dict(color="#FFFFFF", width=2.5)),
                            hovertemplate="<b>선택됨</b><extra></extra>",
                            name="current", showlegend=False,
                        ))

                    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
                    fig.update_yaxes(visible=False, range=[0, FIG_H],
                                     scaleanchor="x", scaleratio=1)
                    fig.update_layout(
                        margin=dict(l=0, r=0, t=0, b=0),
                        plot_bgcolor="#F8FAFC", height=420,
                        dragmode="pan", showlegend=False,
                        clickmode="event+select",
                        uirevision=f"floor_tskloc_{floor_pick}",
                    )

                    if locked:
                        lock_overlay_css()
                    event = st.plotly_chart(
                        fig, use_container_width=True,
                        config=plotly_config(),
                        on_select="rerun",
                        selection_mode=["points"],
                        key=f"tsk_loc_map_chart_{task_id}_{floor_pick}",
                    )
                    if (not locked and event
                            and getattr(event, "selection", None)
                            and getattr(event.selection, "points", None)):
                        pt = event.selection.points[-1]
                        cd = pt.get("customdata")
                        if cd:
                            sel = next(
                                (s for s in floor_spots if s.spot_id == cd[0]),
                                None,
                            )
                            if sel:
                                override_floor = sel.floor
                                override_zone = sel.room_name
                                override_label = (
                                    f"spot 정정 → {sel.spot_id} "
                                    f"({sel.floor}/{sel.room_name})"
                                )
                    st.caption(
                        "도면 위 spot 마커를 탭하면 그 위치로 정정됩니다. "
                        "파란 마커 = 현재 선택, 옅은 주황 = 다른 spot."
                    )

    if override_label:
        st.markdown(
            f"<div style='background:#FEF9C3; border:1px solid #FACC15; "
            f"border-radius:8px; padding:0.5rem 0.75rem; color:#854D0E; "
            f"font-size:0.85rem; margin:0.3rem 0;'>"
            f"<b>위치 정정 적용 예정</b> · {override_label}"
            f"</div>",
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1, 1])
    with c1:
        inspector = st.text_input(
            "점검자",
            value=t.assignee if t.assignee not in ("", "Unassigned") else "박소방",
            key=f"tsk_insp_{task_id}",
        )
    with c2:
        inspect_date = st.date_input(
            "점검일", value=date.today(), key=f"tsk_date_{task_id}",
        )

    types_selected = st.multiselect(
        "점검 종류 (별지5)",
        options=list(INSPECTION_TYPES),
        key=f"tsk_chk_types_{task_id}",
        placeholder="해당 점검종류를 선택하세요 (복수 가능)",
    )

    st.markdown(
        "<b style='color:#334155; font-size:0.92rem; margin-top:0.5rem;'>"
        "점검 결과</b>",
        unsafe_allow_html=True,
    )
    result = st.radio(
        "결과", ["양호", "불량"], horizontal=True,
        label_visibility="collapsed", key=f"tsk_res_{task_id}",
    )

    issue = ""
    action_immediate = False
    action_note_now = ""
    action_photo_now = None
    confirmer_value = inspector

    if result == "불량":
        issue = st.text_area(
            "지적사항",
            placeholder="예: 1-A계단 피난구 유도등 점등 불량",
            key=f"tsk_issue_{task_id}",
        )
        action_immediate = st.checkbox(
            "현장에서 즉시 조치 완료 (선택)",
            value=False,
            key=f"tsk_act_imm_{task_id}",
            help="체크 시 지적사항의 조치 단계가 즉시 완료로 기록됩니다.",
        )
        if action_immediate:
            confirmer_value = st.text_input(
                "확인자",
                value=inspector,
                key=f"tsk_conf_{task_id}",
            )
            action_note_now = st.text_area(
                "조치 내용",
                placeholder="예: 적재물 이동 완료, 전구 교체 등",
                key=f"tsk_act_note_{task_id}",
            )
            action_photo_now = photo_input(
                "조치 사진 (선택)",
                key=f"tsk_act_photo_{task_id}",
                help_text="모바일은 카메라 촬영 탭으로 즉시 촬영.",
            )
        else:
            st.caption(
                "→ 지적사항만 등록되며, 작업 조치 관리에서 별도 시점에 조치 입력합니다."
            )

    if st.button(
        "점검 결과 제출",
        type="primary",
        use_container_width=True,
        key=f"tsk_submit_{task_id}",
    ):
        if not types_selected:
            st.error("점검 종류를 1개 이상 선택해 주세요.")
            return
        if result == "불량" and not issue.strip():
            st.error("불량이면 지적사항을 입력해 주세요.")
            return

        # 통보서 번호 (불량일 때만 발급)
        new_no = None
        if result == "불량":
            new_no = next_notice_no(inspect_date)

        # Deficiency row 생성 (v1.5: 조치 단계 포함)
        photo_bytes = (
            action_photo_now.getvalue()
            if (action_photo_now and action_immediate)
            else None
        )
        new_def_id = data.next_deficiency_id()
        photo_path = None
        if photo_bytes:
            photo_path = data._upload_action_photo(new_def_id, photo_bytes)

        # 사용 영역: 정정값이 있으면 그것을 우선, 아니면 장비/Task 정보 사용
        floor = override_floor
        zone = override_zone
        data.add_deficiency(data.Deficiency(
            deficiency_id=new_def_id,
            inspection_date=inspect_date,
            inspector=inspector,
            floor=floor, zone=zone,
            inspection_types=types_selected,  # type: ignore[arg-type]
            issue=issue.strip() or "양호",
            resolution=(
                "완료" if (result == "양호" or action_immediate) else "불가"
            ),  # type: ignore[arg-type]
            confirmer=confirmer_value if (result == "양호" or action_immediate) else None,
            notice_no=new_no,
            task_id=t.task_id,
            action_done=action_immediate or result == "양호",
            action_at=inspect_date if (action_immediate or result == "양호") else None,
            action_note=action_note_now.strip() if action_immediate else "",
            action_photo_path=photo_path,
            submitter=inspector,
        ))

        # 장비 health_status 갱신 (있으면)
        if eq:
            data.record_equipment_inspection(
                eq.equipment_id, inspect_date,
                "PASS" if result == "양호" else "FAIL",
            )

        # Task → Completed + 회차 status 자동 재계산
        from lib.data import _db, _task_rows, _refresh_round_status
        _db().table("inspection_tasks").update(
            {"status": "Completed"}
        ).eq("task_id", t.task_id).execute()
        _task_rows.clear()
        if t.round_id:
            _refresh_round_status(t.round_id)

        st.session_state.pop("round_inline_start_for", None)
        st.session_state["just_completed_task"] = t.task_id
        st.rerun()


@st.dialog("오동작 등록 (별지9)", width="large")
def malfunction_dialog() -> None:
    """별지9 소방시설 오동작 관리대장 row 추가 모달."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.5rem;'>"
        "운영 중 발생한 소방시설 오동작을 별지9에 기록합니다. 점검 결과와는 별개 사건입니다.<br>"
        "<b>등록만</b> 하고 조치는 별도 시점에 [작업 조치 관리]에서 입력합니다."
        "</div>",
        unsafe_allow_html=True,
    )

    cat_section = st.radio(
        "분류",
        ["임시소방시설 6종 (법적기준)", "그 외 소방시설"],
        horizontal=True,
        key="mal_dlg_section",
    )
    cat_options = (
        MAL_CATEGORIES_TEMP if cat_section.startswith("임시") else MAL_CATEGORIES_OTHER
    )
    category = st.selectbox("소방시설 구분", options=cat_options, key="mal_dlg_cat")

    c1, c2 = st.columns([1, 1])
    with c1:
        occurred = st.date_input("발생일자", value=date.today(), key="mal_dlg_date")
    with c2:
        reporter = st.text_input("최초 발견자", value="박소방", key="mal_dlg_reporter")

    detail = st.text_area(
        "오동작 내용",
        placeholder="예: 점등 불량, 충수 상태 불량, 오작동 등",
        key="mal_dlg_detail",
    )

    if st.button("등록", type="primary", use_container_width=True, key="mal_dlg_submit"):
        if not detail.strip():
            st.error("오동작 내용을 입력해 주세요.")
            return

        new_id = data.next_malfunction_id()
        add_malfunction(Malfunction(
            malfunction_id=new_id,
            category=category,  # type: ignore[arg-type]
            occurred_on=occurred,
            detail=detail.strip(),
            action="",  # 조치는 후속 시점에 작업 조치 관리에서 입력
            confirmer=reporter,  # 최초 발견자
            action_done=False,
        ))
        st.session_state["just_submitted_malfunction"] = True
        st.rerun()


@st.dialog("오동작 조치 입력", width="large")
def malfunction_action_dialog(malfunction_id: str) -> None:
    """별지9 오동작의 후속 조치 입력 모달. 작업 조치 관리 [조치 입력 →]에서 호출."""
    m = next(
        (x for x in data.load_malfunctions() if x.malfunction_id == malfunction_id),
        None,
    )
    if not m:
        st.error("오동작 정보를 찾을 수 없습니다.")
        return

    st.markdown(
        f"<div style='background:#F8FAFC; border:1px solid #E2E8F0; "
        f"border-radius:8px; padding:0.6rem 0.8rem; margin-bottom:0.5rem;'>"
        f"<b style='color:#0F172A;'>{m.malfunction_id}</b> · {m.category}<br>"
        f"<span style='color:#475569; font-size:0.86rem;'>"
        f"발생 {fmt_date(m.occurred_on)} · 최초 발견자 {m.confirmer or '-'}</span><br>"
        f"<div style='color:#92400E; font-size:0.86rem; margin-top:0.3rem;'>"
        f"⚠️ {m.detail}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1])
    with c1:
        act_at = st.date_input(
            "조치 일자", value=date.today(),
            key=f"mal_act_date_{malfunction_id}",
        )
    with c2:
        confirmer = st.text_input(
            "확인자", value=m.confirmer or "김소장",
            key=f"mal_act_conf_{malfunction_id}",
        )
    act_note = st.text_area(
        "조치 내용",
        placeholder="예: 부품 교체, 회로 점검 완료, 외부 수리 의뢰 등",
        key=f"mal_act_note_{malfunction_id}",
    )

    if st.button(
        "조치 완료 저장", type="primary", use_container_width=True,
        key=f"mal_act_submit_{malfunction_id}",
    ):
        if not act_note.strip():
            st.error("조치 내용을 입력해 주세요.")
            return
        data.record_malfunction_action(
            malfunction_id, act_at, act_note.strip(), confirmer.strip(),
        )
        st.session_state["just_recorded_malfunction_action"] = malfunction_id
        st.rerun()


@st.dialog("신규 장비 등록", width="large")
def equipment_dialog() -> None:
    """시설 마스터에 신규 장비를 등록. 위치는 spot 객체에서 선택 (관리자가
    위치 마스터에서 정의). 등록 후 QR 모달은 자동 노출하지 않는다."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.5rem;'>"
        "새 소방시설을 시설 마스터에 등록합니다. 위치는 관리자가 정의한 "
        "spot 목록에서 선택하며, 등록 즉시 QR이 발급됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    # 자동 생성 ID/시리얼
    auto_eid = next_equipment_id()
    auto_serial = next_serial()

    c1, c2 = st.columns([1, 1])
    with c1:
        category = st.selectbox("카테고리", options=EQ_CATEGORIES, key="eq_dlg_cat")
    with c2:
        equipment_name = st.text_input(
            "장비명",
            placeholder="예: ABC Extinguisher (5kg)",
            key="eq_dlg_name",
        )

    # ── 위치 spot 선택 (층 → spot 2단계) ──
    all_spots = data.load_spots()
    floors_with_spots = sorted({s.floor for s in all_spots},
                               key=lambda f: EQ_FLOORS.index(f) if f in EQ_FLOORS else 999)

    c3, c4 = st.columns([1, 2])
    with c3:
        if floors_with_spots:
            floor = st.selectbox(
                "층", options=floors_with_spots, key="eq_dlg_floor",
            )
        else:
            floor = None
            st.markdown(
                "<div style='padding-top:1.7rem; color:#DC2626; font-size:0.85rem;'>"
                "정의된 위치가 없습니다.</div>",
                unsafe_allow_html=True,
            )
    with c4:
        floor_spots = [s for s in all_spots if s.floor == floor] if floor else []
        if floor_spots:
            spot_idx = st.selectbox(
                "위치 (spot)",
                options=range(len(floor_spots)),
                format_func=lambda i: (
                    f"{floor_spots[i].room_name} "
                    f"({floor_spots[i].spot_id})"
                ),
                key="eq_dlg_spot_idx",
            )
            sel_spot = floor_spots[spot_idx]
        else:
            sel_spot = None
            st.markdown(
                "<div style='padding-top:1.7rem; color:#94A3B8; font-size:0.85rem;'>"
                "이 층에 정의된 위치가 없습니다. 관리자에게 위치 마스터에서 spot을 "
                "추가해달라고 요청하세요.</div>",
                unsafe_allow_html=True,
            )

    serial = st.text_input(
        "시리얼 번호 (자동 + 수정 가능)",
        value=auto_serial,
        key="eq_dlg_serial",
    )

    # 카테고리 변경 시 점검 유형 기본값을 새로 채움
    cat_default_types = default_inspection_types_for(category)
    last_cat = st.session_state.get("eq_dlg_last_cat")
    if last_cat != category:
        st.session_state["eq_dlg_types"] = cat_default_types
        st.session_state["eq_dlg_last_cat"] = category

    insp_types = st.multiselect(
        "적용 점검 유형 (카테고리 기본값 자동 채움, 수정 가능)",
        options=TASK_INSPECTION_TYPES,
        key="eq_dlg_types",
        placeholder="이 장비에 적용 가능한 점검 유형을 선택",
    )

    # 자동 생성 영역 (정보 표시용)
    if sel_spot:
        loc_preview = location_id_from_spot(sel_spot.spot_id)
        loc_html = (
            f"<b>위치 ID</b> · {loc_preview} &nbsp;|&nbsp; "
            f"<b>spot</b> · {sel_spot.room_name} ({sel_spot.spot_id})<br>"
            f"<b>도면 좌표</b> · ({sel_spot.x_pct:.1f}%, {sel_spot.y_pct:.1f}%)"
        )
    else:
        loc_html = "<b>위치</b> · 위치 spot 미선택 (등록 불가)"

    st.markdown(
        "<div style='background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; "
        "padding:0.7rem 0.95rem; color:#475569; font-size:0.88rem; line-height:1.6;'>"
        f"<b>장비 ID</b> · {auto_eid}<br>"
        f"{loc_html}<br>"
        f"<b>초기 상태</b> · {badge('DUE')} {badge('ASSIGNED')} (미점검 · QR 발급됨)"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.button(
        "등록 + QR 발급", type="primary", use_container_width=True,
        key="eq_dlg_submit", disabled=(sel_spot is None),
    ):
        if not equipment_name.strip():
            st.error("장비명을 입력해 주세요.")
            return
        if not serial.strip():
            st.error("시리얼 번호를 입력해 주세요.")
            return

        existing_serials = {e.serial for e in data.load_equipment()}
        if serial.strip() in existing_serials:
            st.error(
                f"시리얼 번호 '{serial.strip()}' 가 이미 사용 중입니다. "
                "다른 번호를 입력하거나 자동 발급된 번호를 그대로 사용하세요."
            )
            return

        # spot 정보로 zone/location_id/pixel 좌표 자동 채움
        location_id = location_id_from_spot(sel_spot.spot_id)  # 예: 1F-03
        zone_value = sel_spot.room_name                        # 방이름

        new_eq = Equipment(
            equipment_id=auto_eid,
            location_id=location_id,
            category=category,  # type: ignore[arg-type]
            equipment_name=equipment_name.strip(),
            serial=serial.strip(),
            qr_status="ASSIGNED",
            last_inspection=None,
            health_status="DUE",
            floor=sel_spot.floor,
            zone=zone_value,
            pixel_x=sel_spot.x_pct,
            pixel_y=sel_spot.y_pct,
            inspection_types=list(insp_types),
            spot_id=sel_spot.spot_id,
        )
        add_equipment(new_eq)
        st.session_state["just_submitted_equipment"] = True
        # 다음 모달 진입 시 기본값 재초기화 (다른 카테고리 선택 시 다시 반영되도록)
        st.session_state.pop("eq_dlg_last_cat", None)
        st.rerun()


@st.dialog("신규 점검 일정 등록", width="large")
def task_dialog() -> None:
    """점검 유형을 선택하면 해당 유형에 적용 가능한 장비들이 후보로 필터링되고,
    선택한 장비 N개에 대해 동일 담당자·마감일·메모로 Task N개를 일괄 생성."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.5rem;'>"
        "점검 유형 선택 → 해당 유형 적용 장비가 후보로 자동 필터됩니다. "
        "선택한 장비마다 별도의 점검 일정(TSK)이 생성됩니다."
        "</div>",
        unsafe_allow_html=True,
    )

    type_options = TASK_INSPECTION_TYPES + ["기타"]
    c1, c2 = st.columns([1, 1])
    with c1:
        type_choice = st.selectbox(
            "점검 유형",
            options=type_options,
            key="task_dlg_type",
        )
    with c2:
        custom_type = ""
        if type_choice == "기타":
            custom_type = st.text_input(
                "점검 유형 직접 입력",
                key="task_dlg_type_custom",
                placeholder="예: 화기취급감독",
            )
        else:
            st.markdown(
                "<div style='color:#94A3B8; font-size:0.83rem; padding-top:1.7rem;'>"
                "장비 마스터의 inspection_types에서 매칭</div>",
                unsafe_allow_html=True,
            )

    resolved_type = (custom_type.strip() if type_choice == "기타" else type_choice)

    # v1.5: 자유 점검 옵션 — 대상을 미리 선택하지 않고 점검 시작 시 정하는 방식
    free_mode = st.checkbox(
        "대상 미선택 (자유 점검) — 회차만 만들고 점검 시작 시 장비를 선택",
        key="task_dlg_free_mode",
        help=(
            "체크 시 회차 1건만 만들고 Task는 0개입니다. "
            "점검자가 안전점검 → [신규 Task 추가] 로 그때그때 등록 가능."
        ),
    )

    if free_mode:
        candidates = []
        selected_eqs = []
        st.markdown(
            "<div style='color:#94A3B8; font-size:0.82rem;'>"
            "회차만 등록되고 대상 장비는 빈 상태로 시작합니다.</div>",
            unsafe_allow_html=True,
        )
    else:
        # 점검 유형 → 적용 가능 장비 후보 필터
        all_eq = data.load_equipment()
        if type_choice == "기타":
            candidates = all_eq  # 기타는 전체에서 자유 선택
        else:
            candidates = [
                e for e in all_eq if resolved_type in (e.inspection_types or [])
            ]

        eq_indices = list(range(len(candidates)))

        # 점검 유형이 바뀌면 multiselect 선택 초기화
        last_type = st.session_state.get("task_dlg_last_type")
        if last_type != type_choice:
            st.session_state["task_dlg_eq_idxs"] = []
            st.session_state["task_dlg_last_type"] = type_choice

        # dialog 안에서는 st.rerun()이 모달을 닫아버리므로 session_state만 세팅
        sel_col, clr_col = st.columns(2)
        with sel_col:
            if st.button("모두 선택", key="task_dlg_select_all",
                         use_container_width=True,
                         disabled=not eq_indices):
                st.session_state["task_dlg_eq_idxs"] = list(eq_indices)
        with clr_col:
            if st.button("일괄 해제", key="task_dlg_clear_all",
                         use_container_width=True):
                st.session_state["task_dlg_eq_idxs"] = []

        sel_idxs = st.multiselect(
            f"대상 장비 (이 유형 해당 {len(candidates)}건 후보)",
            options=eq_indices,
            format_func=lambda i: (
                f"{candidates[i].location_id} · {candidates[i].equipment_name}"
            ),
            key="task_dlg_eq_idxs",
            placeholder="장비를 선택하세요 (여러 건 선택 가능)",
        )
        selected_eqs = [candidates[i] for i in sel_idxs]

    # 공유 입력 (담당자·마감일·메모)
    c_a, c_b = st.columns([1, 1])
    with c_a:
        assignee = st.text_input(
            "담당자",
            key="task_dlg_assignee",
            placeholder="예: 박소방 (빈 값이면 '미지정')",
        )
    with c_b:
        default_due = data.TODAY + timedelta(days=14)
        due_date = st.date_input(
            "마감일",
            value=default_due,
            key="task_dlg_due",
        )

    note = st.text_area(
        "메모(선택)",
        key="task_dlg_note",
        placeholder="다중 등록 시 모든 일정에 동일 메모로 적용됩니다.",
        height=80,
    )

    if due_date < data.TODAY:
        st.warning("마감일이 오늘 이전입니다. 과거 일정 보정용이면 그대로 등록 가능합니다.")

    n_sel = len(selected_eqs)
    if free_mode:
        submit_label = "회차만 등록 (자유 점검)"
        submit_disabled = False
    else:
        submit_label = f"등록 ({n_sel}건)" if n_sel else "장비를 1건 이상 선택하세요"
        submit_disabled = (n_sel == 0)
    if st.button(submit_label, type="primary",
                 use_container_width=True,
                 key="task_dlg_submit",
                 disabled=submit_disabled):
        if not resolved_type:
            st.error("점검 유형을 선택(또는 입력)해 주세요.")
            return

        assignee_value = assignee.strip() or "Unassigned"
        # 회차(Round) 1건 + 그 안에 Task N건 — 모두 같은 round_id 공유
        round_id = next_round_id()
        add_round(InspectionRound(
            round_id=round_id,
            task_type=resolved_type,
            assignee=assignee_value,
            due_date=due_date,
            status="Scheduled",
            note=note.strip(),
        ))
        created_ids: list[str] = []
        for eq in selected_eqs:
            tsk_id = next_task_id()  # 매 호출마다 +1 (세션 누적 반영)
            add_task(InspectionTask(
                task_id=tsk_id,
                equipment_label=f"{eq.location_id} - {eq.equipment_name}",
                task_type=resolved_type,
                assignee=assignee_value,
                due_date=due_date,
                status="Scheduled",
                floor=eq.floor,
                zone=eq.zone,
                note=note.strip(),
                round_id=round_id,
            ))
            created_ids.append(tsk_id)

        st.session_state["just_submitted_tasks"] = created_ids
        st.session_state["just_submitted_round"] = round_id
        # 다음 모달 진입 시 입력 초기화 위해 키 제거
        for k in ("task_dlg_last_type", "task_dlg_eq_idxs"):
            st.session_state.pop(k, None)
        st.rerun()
