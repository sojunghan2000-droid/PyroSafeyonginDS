"""신규 점검 모달 — 지적·오동작 관리에서 호출.

`@st.dialog`로 점검 폼을 띄운다.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from lib import data
from lib.data import (
    Deficiency, Equipment, InspectionRound, InspectionTask, Malfunction, Notice,
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

# 등록 가능한 층 (구 명칭 — 일부 로직 호환용)
EQ_FLOORS = ["B3", "B2", "B1", "P4", "L1", "L2", "2F", "4F", "5F", "6F", "SRV"]
# 실제 도면 PNG(assets/floors)가 있는 8개 층 — 신규 위치 생성 좌표 픽업용
SPOT_FLOORS = ["PIT", "B2", "B1", "1F", "2F", "3F", "4F", "Roof"]


INSPECTION_TYPES = [
    "임시소방시설", "피난로 등", "화기취급감독",
    # v1.6: 신규 점검 종류 (불량 사유 카탈로그 보유)
    "화기작업구간 점검", "가설컨테이너 사무실 점검",
]

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

    # === 점검 회차 연결 (v1.7) — 진행 중 점검이 여러 개면 어느 회차인지 선택 ===
    _open_tasks = [
        t for t in data.load_tasks()
        if t.round_id and not t.excluded and t.equipment_label
        and eq.location_id in t.equipment_label
        and t.status not in ("Completed",)
    ]
    selected_task_id: str | None = None
    if len(_open_tasks) == 1:
        _ot = _open_tasks[0]
        selected_task_id = _ot.task_id
        st.caption(f"🔗 이 점검은 **{_ot.round_id}** ({_ot.task_type}) 회차에 연결됩니다.")
    elif len(_open_tasks) >= 2:
        from lib.ui import TASK_STATUS_KO
        _NONE_ROUND = "__none__"
        st.markdown(
            "<b style='color:#334155; font-size:0.92rem; margin-top:0.5rem;'>"
            "어느 회차 점검인가요?</b>", unsafe_allow_html=True,
        )
        st.caption(
            f"이 장비에 진행 중인 점검이 {len(_open_tasks)}건입니다. "
            "결과를 연결할 회차를 선택하세요."
        )

        def _fmt_round(tid: str) -> str:
            if tid == _NONE_ROUND:
                return "— 회차 미연결 (단독 기록) —"
            t = next(x for x in _open_tasks if x.task_id == tid)
            return (f"{t.round_id} · {t.task_type} · 마감 {fmt_date(t.due_date)} "
                    f"({TASK_STATUS_KO.get(t.status, t.status)})")

        _pick = st.radio(
            "회차 선택",
            options=[t.task_id for t in _open_tasks] + [_NONE_ROUND],
            format_func=_fmt_round, key="dlg_round_pick",
            label_visibility="collapsed",
        )
        selected_task_id = None if _pick == _NONE_ROUND else _pick

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

        # 회차 연결 — 렌더 시 결정된 선택값 사용
        # (진행 중 점검 1건=자동 / 2건 이상=사용자가 위에서 선택 / 0건=None)
        matched_task_id: str | None = selected_task_id

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
    """[+ Task 추가] 모달의 신규 위치 점검 탭(도면). 회차 매칭 장비 + 빈 spot 마커 + 단일 클릭 선택.
    candidates: 회차 매칭 후보 장비 (미포함만). all_eq: 전체 장비.
    already_locs: 이미 회차에 포함된 location_id 집합.
    반환: 선택된 항목 dict ({'type': 'equipment'|'empty_spot', 'data': ...}) 또는 None.
    """
    import base64
    from pathlib import Path
    import plotly.graph_objects as go
    from lib.floor_widget import (
        control_toggle, legend_html, plotly_config,
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

    # 컨트롤 토글 + 신규 위치 추가 토글 + 범례
    cc, ac, lc = st.columns([1.2, 1.6, 4])
    with cc:
        locked = control_toggle(f"add_tsk_map_{round_id}", default_locked=True)
    with ac:
        add_spot_mode_key = f"add_tsk_add_spot_mode_{round_id}"
        if add_spot_mode_key not in st.session_state:
            st.session_state[add_spot_mode_key] = False
        add_spot_mode = st.toggle(
            "🆕 신규 위치 추가",
            value=st.session_state[add_spot_mode_key],
            key=add_spot_mode_key,
            help="ON 시 도면 빈 곳 클릭으로 신규 위치 좌표 픽업 (기본 OFF)",
        )
    with lc:
        st.markdown(legend_html([
            ("#2563EB", "점검 대상 (회차 매칭)"),
            ("#94A3B8", "그 외 선택 가능 (● 장비 · ◇ 빈/신규 위치)"),
            ("#64748B", "이미 포함 (선택 불가)"),
        ]), unsafe_allow_html=True)

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
                marker=dict(size=16, color="#94A3B8",
                            line=dict(color="#FFFFFF", width=1.5)),
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

    # 빈 spot / 신규 위치(임시 등록) — 다이아 마커
    used_spot_ids = {e.spot_id for e in all_eq if e.spot_id and e.floor == floor}
    already_empty_spot_ids = {
        t.equipment_label.split(" - ")[0]
        for t in data.tasks_of_round(round_id, include_excluded=True)
        if "(빈 spot)" in t.equipment_label or "(신규 위치)" in t.equipment_label
           or "(임시 spot)" in t.equipment_label  # 구 데이터 호환
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
            txts.append("신규·포함" if in_round else "신규")
            custom.append(("spot", sp.spot_id, sp.room_name, in_round))
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            text=txts, textposition="bottom center",
            textfont=dict(size=9, color="#64748B"),
            marker=dict(size=14, color="#94A3B8",
                        line=dict(color="#64748B", width=2),
                        symbol="diamond-open"),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[2]}</b> (신규 위치)<br>"
                "%{customdata[1]} · 관리자 검증 대기<extra></extra>"
            ),
            name="신규 위치", showlegend=False,
        ))

    # 신규 위치 추가 모드 ON일 때만 클릭 가능 격자 추가
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
            hovertemplate="여기 클릭 → 신규 위치 좌표 픽업<extra></extra>",
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

    # 클릭 → 후보 장비 / 빈 spot / 신규 위치 / 격자(빈 곳) 분기
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
                        label = "신규 위치" if sel_spot.is_temporary else "빈 spot"
                        st.success(
                            f"선택: **{sel_spot.spot_id}** · {sel_spot.room_name} "
                            f"({label})"
                        )
                        st.session_state.pop(pending_grid_key, None)
                        return {"type": "empty_spot", "data": sel_spot}
            elif kind == "grid":
                # 빈 곳 클릭 — 신규 위치 좌표 픽업
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

    # 신규 위치 추가 폼 — 빈 곳 클릭으로 좌표 픽업된 상태일 때 노출
    pending = st.session_state.get(pending_grid_key)
    if pending:
        x_pct, y_pct = pending
        st.markdown(
            f"<div style='background:#EFF6FF; border:1px solid #BFDBFE; "
            f"border-radius:8px; padding:0.6rem 0.8rem; margin-top:0.3rem;'>"
            f"<b style='color:#1E3A8A;'>🆕 신규 위치 픽업됨</b> · "
            f"좌표 ({x_pct}, {y_pct}) · 다음 spot ID: "
            f"<code>{data.next_spot_id(floor)}</code><br>"
            f"<span style='color:#475569; font-size:0.84rem;'>"
            f"위치 설명을 입력하고 [신규 위치 + Task 추가]를 누르면 "
            f"신규 위치가 생성되고 Task도 함께 등록됩니다. "
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
                "신규 위치 + Task 추가",
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
            "🆕 신규 위치 추가 모드 — 도면 빈 곳 클릭으로 좌표 픽업. "
            "마커 클릭은 기존 장비/spot 선택."
        )
    else:
        st.caption(
            "🆕 신규 위치를 새로 만들려면 상단 **신규 위치 추가** 토글을 켜세요. "
            "(마커 색 설명은 위 범례 참고)"
        )
    return None


@st.dialog("회차에 Task 추가", width="large")
def add_task_to_round_dialog(round_id: str) -> None:
    """v1.5 자유 점검 회차에 Task 1건 동적 추가.
    진입 방식 — 장비 선택(QR+목록 통합) / 📍 신규 위치 점검(도면) 2가지 (v1.7)."""
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
        # 전체 유형(활성+비활성)으로 검증 — 과거/비활성 유형 회차 매칭 유지
        return (r.task_type in data.load_inspection_types()
                and r.task_type in (e.inspection_types or []))

    matched = [e for e in all_eq
               if e.location_id not in already_locs and _is_match(e)]
    unmatched = [e for e in all_eq
                 if e.location_id not in already_locs and not _is_match(e)]
    candidates = matched + unmatched  # 매칭 우선 정렬

    # 진입 방식 — 장비 선택(사전 위치 설정됨) / 📍 신규 위치 점검(도면)
    # v1.7: '직접 선택'과 'QR 스캔'은 둘 다 등록 장비를 고르는 동일 흐름이라 한 탭으로 통합.
    #        화기작업 구간은 별도 탭 없이 '신규 위치 점검 → 신규 위치'로 통합 (탭 중복 제거)
    tab_eq, tab_map = st.tabs(["장비 선택 (사전 위치 설정됨)", "신규 위치 점검"])
    sel_eq = None        # Equipment (장비 기반 추가)
    sel_empty_spot = None  # Spot (빈 spot 기반 추가)
    with tab_eq:
        st.caption(
            "등록된 장비를 **목록** 또는 **QR 스캔**으로 선택합니다. "
            "장비의 층·구역은 이미 설정되어 있어 자동 반영됩니다."
        )
        st.caption(
            "💡 도면에 정의되지 않은 작업 구간(화기작업 등)은 "
            "**신규 위치 점검 탭 → 🆕 신규 위치 추가**로 등록할 수 있습니다."
        )

        # 1) 목록에서 직접 선택 (기본 경로)
        st.markdown("**① 목록에서 선택**")
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
        sel_eq = candidates[eq_idx] if candidates else None

        st.divider()

        # 2) QR 스캔 (모바일 · 인식 시 목록 선택보다 우선 적용)
        st.markdown("**② QR 스캔** (선택)")
        try:
            from streamlit_qrcode_scanner import qrcode_scanner
            qr_val = qrcode_scanner(key=f"add_tsk_qr_{round_id}")
        except Exception as e:
            st.caption(f"QR 스캐너를 불러올 수 없습니다 ({e}). 위 목록에서 선택하세요.")
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

        # QR/수동 인식 시 목록 선택보다 우선 적용
        if eq_id:
            matched = next((c for c in candidates if c.equipment_id == eq_id), None)
            if matched:
                sel_eq = matched
                st.success(
                    f"QR 인식: {matched.equipment_id} · {matched.equipment_name} "
                    f"({matched.location_id}) — 이 장비로 추가됩니다."
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

    has_selection = (
        sel_eq is not None
        or sel_empty_spot is not None
    )
    if st.button(
        "추가", type="primary", use_container_width=True,
        key=f"add_tsk_submit_{round_id}",
        disabled=not has_selection,
    ):
        if not has_selection:
            st.error("장비/QR/spot 중 하나를 선택해 주세요.")
            return
        from lib.data import next_task_id, add_task, _refresh_round_status
        new_tsk = next_task_id()
        if sel_empty_spot is not None:
            # spot 기반 — 장비 없이 spot 정보만 사용 (임시/정식 구분)
            spot_tag = (
                "(신규 위치)" if sel_empty_spot.is_temporary else "(빈 spot)"
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
                control_toggle, legend_html, lock_overlay_css, plotly_config,
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
                            f"tsk_loc_map_{task_id}", default_locked=True,
                        )
                    with lc:
                        st.markdown(legend_html([
                            ("#2563EB", "현재 선택 위치"),
                            ("#FDE68A", "다른 spot (클릭해 정정)"),
                        ]), unsafe_allow_html=True)

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

    # v1.7: 세부 checklist — 점검 종류가 카탈로그 보유 종류면 렌더링
    # 첫 카탈로그 매칭 종류 기준. 각 항목 OK/NG/NA 라디오.
    checklist_kind = next(
        (k for k in types_selected if data.checklist_for(k) is not None),
        None,
    )
    checklist_items: dict[str, str] = {}
    checklist_has_ng = False
    if checklist_kind:
        catalog = data.checklist_for(checklist_kind)
        st.markdown(
            f"<div style='background:#EFF6FF; border:1px solid #BFDBFE; "
            f"border-radius:8px; padding:0.5rem 0.75rem; margin:0.4rem 0; "
            f"color:#1E40AF; font-size:0.85rem;'>"
            f"📋 <b>{checklist_kind}</b> — 세부 항목별 점검 (OK / NG / N/A)"
            f"</div>",
            unsafe_allow_html=True,
        )

        def _chk_radio(key_id: str, label: str) -> str:
            # NG 자주 씀 → 명확성 위해 라디오. 기본 OK
            return st.radio(
                label,
                options=["OK", "NG", "N/A"],
                horizontal=True,
                key=f"tsk_chk_{task_id}_{key_id}",
                label_visibility="visible",
            )

        if isinstance(catalog, dict):
            # 화기작업 — 카테고리별
            for cat, items in catalog.items():
                st.markdown(
                    f"<div style='font-weight:600; color:#0F172A; "
                    f"font-size:0.86rem; margin-top:0.4rem;'>· {cat}</div>",
                    unsafe_allow_html=True,
                )
                for it in items:
                    key = f"{cat}|{it}"
                    val = _chk_radio(key, it)
                    checklist_items[key] = val
                    if val == "NG":
                        checklist_has_ng = True
        else:
            # 가설컨테이너 — 단일 리스트
            for it in catalog:
                val = _chk_radio(it, it)
                checklist_items[it] = val
                if val == "NG":
                    checklist_has_ng = True

        if checklist_has_ng:
            st.warning(
                "⚠ NG 항목이 있습니다. 아래 결과를 **불량**으로 선택하고 "
                "사유 카탈로그·조치 사진을 첨부해 주세요."
            )

    st.markdown(
        "<b style='color:#334155; font-size:0.92rem; margin-top:0.5rem;'>"
        "점검 결과</b>",
        unsafe_allow_html=True,
    )
    result = st.radio(
        "결과", ["양호", "불량", "오동작"], horizontal=True,
        label_visibility="collapsed", key=f"tsk_res_{task_id}",
    )

    issue = ""
    action_immediate = False
    action_note_now = ""
    action_photo_now = None
    confirmer_value = inspector

    # 오동작 입력 영역 (v1.5+)
    mal_category = (eq.category if eq else "기타")
    mal_detail = ""
    mal_occurred = inspect_date
    if result == "오동작":
        st.caption(
            "⚠ 시설 자체의 오작동을 별지9에 기록합니다. "
            "조치는 [작업 조치 관리]에서 별도 시점에 입력하세요."
        )
        all_mal_cats = list(MAL_CATEGORIES_TEMP) + list(MAL_CATEGORIES_OTHER)
        auto_mapped = (mal_category in all_mal_cats)

        mc1, mc2 = st.columns([1, 1])
        with mc1:
            if auto_mapped:
                # 장비 카테고리가 별지9 카테고리에 직접 매핑 — 텍스트만 표시
                st.markdown(
                    f"<div style='color:#475569; font-size:0.86rem;'>"
                    f"<b style='color:#334155;'>시설구분 (별지9)</b><br>"
                    f"<span style='font-size:0.95rem; color:#0F172A;'>"
                    f"{mal_category}</span>"
                    f"<span style='color:#94A3B8; font-size:0.78rem; "
                    f"margin-left:0.3rem;'>(Task 장비 기준 자동)</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                # 별지9에 직접 매핑 없음 — 사용자 선택 필요
                st.caption(
                    f"장비({mal_category})가 별지9 카테고리에 직접 매핑되지 않습니다. "
                    "분류를 선택해 주세요."
                )
                mal_category = st.selectbox(
                    "시설구분 (별지9)",
                    options=all_mal_cats,
                    index=0,
                    key=f"tsk_mal_cat_{task_id}",
                )
        with mc2:
            mal_occurred = st.date_input(
                "발생일자", value=inspect_date,
                key=f"tsk_mal_date_{task_id}",
            )
        mal_detail = st.text_area(
            "오동작 내용",
            placeholder="예: 점등 불량, 충수 상태 불량, 오작동 등",
            key=f"tsk_mal_detail_{task_id}",
        )

    # v1.6: 점검 종류 매칭되는 불량 사유 카탈로그 (화기작업/가설컨테이너)
    # types_selected에서 카탈로그 보유 종류가 하나라도 있으면 그것의 사유 카탈로그를 사용
    defect_codes_selected: list[str] = []
    defect_other_text = ""
    matching_kind_for_codes = next(
        (k for k in types_selected if k in data.DEFECT_CODE_CATALOG),
        None,
    )

    if result == "불량":
        issue = st.text_area(
            "지적사항 (선택)",
            placeholder="예: 1-A계단 피난구 유도등 점등 불량",
            key=f"tsk_issue_{task_id}",
        )

        # v1.6: 점검 종류가 카탈로그 보유 종류면 사유 multiselect 노출
        if matching_kind_for_codes:
            st.caption(
                f"📋 **{matching_kind_for_codes}** — 불량 사유 카탈로그가 적용됩니다 (복수 선택 가능)"
            )
            defect_codes_selected = st.multiselect(
                "불량 사유 *",
                options=data.defect_codes_for(matching_kind_for_codes),
                key=f"tsk_dcodes_{task_id}",
                placeholder="해당 사유를 모두 선택해주세요",
            )
            if "기타" in defect_codes_selected:
                defect_other_text = st.text_input(
                    "기타 — 상세 내용 *",
                    key=f"tsk_dother_{task_id}",
                    placeholder="기타 선택 시 구체 내용 필수",
                )

        # 불량 조치 사진 — 의무화 (v1.6)
        st.markdown(
            "<div style='color:#DC2626; font-size:0.82rem; font-weight:600; margin-top:0.4rem;'>"
            "📷 조치 사진 — 필수 첨부</div>",
            unsafe_allow_html=True,
        )
        action_photo_now = photo_input(
            "조치 사진 *",
            key=f"tsk_act_photo_{task_id}",
            help_text="불량 시 사진 첨부 필수. 모바일은 카메라 촬영 탭으로 즉시 촬영.",
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
        if result == "오동작":
            if not mal_detail.strip():
                st.error("오동작 내용을 입력해 주세요.")
                return
            # 오동작은 별지9에 등록, Deficiency 생성 X
            from lib.data import next_malfunction_id, Malfunction, _db, _task_rows, _refresh_round_status
            new_mid = next_malfunction_id()
            data.add_malfunction(Malfunction(
                malfunction_id=new_mid,
                category=mal_category,  # type: ignore[arg-type]
                occurred_on=mal_occurred,
                detail=mal_detail.strip(),
                action="",
                confirmer=inspector,
                task_id=t.task_id,
                action_done=False,
            ))
            # Task → Completed + 회차 status 자동 재계산
            _db().table("inspection_tasks").update(
                {"status": "Completed"}
            ).eq("task_id", t.task_id).execute()
            _task_rows.clear()
            if t.round_id:
                _refresh_round_status(t.round_id)
            st.session_state.pop("round_inline_start_for", None)
            st.session_state["just_completed_task"] = t.task_id
            st.session_state["just_submitted_malfunction"] = True
            st.rerun()
            return

        if not types_selected:
            st.error("점검 종류를 1개 이상 선택해 주세요.")
            return

        # v1.7: NG 항목이 있는데 결과가 "양호"면 저장 차단
        if checklist_kind and checklist_has_ng and result == "양호":
            st.error(
                "세부 checklist에 NG 항목이 있습니다. 결과를 '불량'으로 선택하고 "
                "사유 카탈로그·조치 사진을 첨부해 주세요."
            )
            return

        # v1.6: 불량 시 검증 강화
        if result == "불량":
            # 사유 카탈로그 적용 종류면 최소 1개 선택 필수
            if matching_kind_for_codes and not defect_codes_selected:
                st.error(f"{matching_kind_for_codes} — 불량 사유를 1개 이상 선택해 주세요.")
                return
            # 기타 선택 시 상세 텍스트 필수
            if "기타" in defect_codes_selected and not defect_other_text.strip():
                st.error("기타를 선택했으면 상세 내용을 입력해 주세요.")
                return
            # 조치 사진 필수 (v1.6)
            if not action_photo_now:
                st.error("불량 시 조치 사진은 필수입니다. 첨부 후 다시 제출해 주세요.")
                return
            # 사유 카탈로그가 없는 종류일 때만 지적사항 텍스트 필수
            if not matching_kind_for_codes and not issue.strip():
                st.error("불량이면 지적사항을 입력해 주세요.")
                return

        # 통보서 번호 (불량일 때만 발급)
        new_no = None
        if result == "불량":
            new_no = next_notice_no(inspect_date)

        # 사진 업로드 — v1.6: 불량 시 항상, 양호 시 없음
        photo_bytes = (
            action_photo_now.getvalue()
            if (action_photo_now and result == "불량")
            else None
        )
        new_def_id = data.next_deficiency_id()
        photo_path = None
        if photo_bytes:
            photo_path = data._upload_action_photo(new_def_id, photo_bytes)

        # issue 텍스트 — 사유 카탈로그가 있으면 사유 요약, 없으면 자유 입력
        if result == "불량" and matching_kind_for_codes:
            codes_display = list(defect_codes_selected)
            if "기타" in codes_display and defect_other_text.strip():
                codes_display = [
                    c if c != "기타" else f"기타: {defect_other_text.strip()}"
                    for c in codes_display
                ]
            issue_final = " · ".join(codes_display)
            if issue.strip():
                issue_final = f"{issue_final} — {issue.strip()}"
        else:
            issue_final = issue.strip() or "양호"

        # 사용 영역: 정정값이 있으면 그것을 우선, 아니면 장비/Task 정보 사용
        floor = override_floor
        zone = override_zone
        data.add_deficiency(data.Deficiency(
            deficiency_id=new_def_id,
            inspection_date=inspect_date,
            inspector=inspector,
            floor=floor, zone=zone,
            inspection_types=types_selected,  # type: ignore[arg-type]
            issue=issue_final,
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
            defect_codes=defect_codes_selected,  # v1.6
            defect_other=defect_other_text.strip(),  # v1.6
            checklist_items=checklist_items,  # v1.7
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


def _eq_new_spot_map(floor: str):
    """신규 장비 등록 '신규 위치 만들기' — 도면 클릭 좌표 픽업.
    빈 곳(격자) 클릭 시 (x_pct, y_pct) 반환, 아니면 None.
    기존 spot은 노란 점(참고), 현재 선택 좌표는 파란 별로 표시."""
    import base64
    from pathlib import Path
    import plotly.graph_objects as go
    from lib.floor_widget import (
        control_toggle, plotly_config, lock_overlay_css, legend_html,
    )

    ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"
    FIG_W, FIG_H = 2978, 2105
    img_path = ASSETS_DIR / f"{floor}.png"
    if not img_path.exists():
        st.caption(f"({floor} 도면 이미지가 없어 아래 좌표를 직접 입력하세요)")
        return None
    uri = "data:image/png;base64," + base64.b64encode(img_path.read_bytes()).decode()

    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    # 기존 spot (참고용, 노란 점)
    fspots = data.load_spots(floor)
    if fspots:
        fig.add_trace(go.Scatter(
            x=[s.x_pct / 100 * FIG_W for s in fspots],
            y=[FIG_H - s.y_pct / 100 * FIG_H for s in fspots],
            mode="markers",
            marker=dict(size=12, color="#F59E0B", line=dict(color="#FFFFFF", width=1.5)),
            customdata=[("spot",)] * len(fspots),
            hovertemplate="기존 위치<extra></extra>", showlegend=False, name="기존",
        ))

    # 현재 선택 좌표 (파란 별)
    cx = float(st.session_state.get("eq_dlg_new_x", 50.0))
    cy = float(st.session_state.get("eq_dlg_new_y", 50.0))
    fig.add_trace(go.Scatter(
        x=[cx / 100 * FIG_W], y=[FIG_H - cy / 100 * FIG_H],
        mode="markers",
        marker=dict(size=20, color="#2563EB", symbol="star",
                    line=dict(color="#FFFFFF", width=2)),
        customdata=[("cur",)],
        hovertemplate="현재 선택 위치<extra></extra>", showlegend=False, name="현재",
    ))

    # 클릭 격자
    gx, gy = [], []
    for i in range(50):
        for j in range(50):
            gx.append((i + 0.5) / 50 * FIG_W)
            gy.append((j + 0.5) / 50 * FIG_H)
    fig.add_trace(go.Scatter(
        x=gx, y=gy, mode="markers",
        marker=dict(size=10, color="rgba(59,130,246,0.22)", line=dict(width=0)),
        customdata=[("grid",)] * len(gx),
        hovertemplate="여기 클릭 → 좌표 픽업<extra></extra>",
        showlegend=False, name="grid",
    ))

    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, FIG_H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor="#F8FAFC", height=420,
        dragmode="pan", showlegend=False, clickmode="event+select",
        uirevision=f"eq_new_{floor}",
    )

    st.markdown(legend_html([
        ("#2563EB", "현재 선택 위치(★)"),
        ("#F59E0B", "기존 위치"),
        ("#93C5FD", "클릭 가능 영역(좌표 픽업)"),
    ]), unsafe_allow_html=True)

    # 좌표 픽업이 주목적이라 기본 잠금 해제 (바로 클릭 가능)
    locked = control_toggle("eq_new_spot_map", default_locked=False)
    if locked:
        lock_overlay_css()
    event = st.plotly_chart(
        fig, use_container_width=True, config=plotly_config(),
        on_select="rerun", selection_mode=["points"],
        key=f"eq_new_map_{floor}",
    )
    if (not locked and event and getattr(event, "selection", None)
            and getattr(event.selection, "points", None)):
        pt = event.selection.points[-1]
        cd = pt.get("customdata")
        if cd and cd[0] == "grid":
            x_pct = round(pt["x"] / FIG_W * 100, 2)
            y_pct = round((FIG_H - pt["y"]) / FIG_H * 100, 2)
            return (x_pct, y_pct)
    return None


@st.dialog("신규 장비 등록", width="large")
def equipment_dialog() -> None:
    """시설 마스터에 신규 장비를 등록. 위치는 spot 객체에서 선택 (관리자가
    위치 마스터에서 정의). 등록 후 QR 모달은 자동 노출하지 않는다."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.5rem;'>"
        "새 소방시설을 시설 마스터에 등록합니다. 위치는 기존 spot에서 선택하거나 "
        "**신규 위치를 즉석 생성**할 수 있으며, 등록 즉시 QR이 발급됩니다."
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

    # ── 위치 지정: 기존 spot 선택 OR 신규 위치 즉석 생성 (v1.7 전체 이관) ──
    all_spots = data.load_spots()
    floors_with_spots = sorted({s.floor for s in all_spots},
                               key=lambda f: EQ_FLOORS.index(f) if f in EQ_FLOORS else 999)

    loc_mode = st.radio(
        "위치 지정",
        ["기존 위치 선택", "신규 위치 만들기"],
        horizontal=True,
        key="eq_dlg_loc_mode",
    )

    sel_spot = None          # 기존 선택 결과
    new_spot_meta = None     # 신규 생성 결과 (floor, room_name, x, y)

    if loc_mode == "기존 위치 선택":
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
                    "정의된 위치가 없습니다. '신규 위치 만들기'를 사용하세요.</div>",
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
                st.markdown(
                    "<div style='padding-top:1.7rem; color:#94A3B8; font-size:0.85rem;'>"
                    "이 층에 정의된 위치가 없습니다. '신규 위치 만들기'로 등록하세요.</div>",
                    unsafe_allow_html=True,
                )
    else:
        # 신규 위치 즉석 생성 — 도면 클릭으로 좌표 픽업 + 등록과 동시에 spot 정식 생성
        nc1, nc2 = st.columns([1, 2])
        with nc1:
            new_floor = st.selectbox("층", options=SPOT_FLOORS, key="eq_dlg_new_floor")
        with nc2:
            new_room = st.text_input(
                "위치 설명(방이름)",
                key="eq_dlg_new_room",
                placeholder="예: B2 기계실 입구",
            )

        # 좌표 세션 기본값 (widget 생성 전 초기화 — 도면 클릭 결과가 여기 반영됨)
        if "eq_dlg_new_x" not in st.session_state:
            st.session_state["eq_dlg_new_x"] = 50.0
        if "eq_dlg_new_y" not in st.session_state:
            st.session_state["eq_dlg_new_y"] = 50.0

        # 도면 클릭 좌표 픽업 — number_input 생성 전에 처리해야 세션값 반영됨
        picked = _eq_new_spot_map(new_floor)
        if picked is not None:
            st.session_state["eq_dlg_new_x"] = picked[0]
            st.session_state["eq_dlg_new_y"] = picked[1]

        xc, yc = st.columns(2)
        with xc:
            new_x = st.number_input(
                "x_pct (도면 폭 %)", min_value=0.0, max_value=100.0,
                step=0.5, format="%.1f", key="eq_dlg_new_x",
            )
        with yc:
            new_y = st.number_input(
                "y_pct (도면 높이 %)", min_value=0.0, max_value=100.0,
                step=0.5, format="%.1f", key="eq_dlg_new_y",
            )
        st.caption(
            "💡 도면 잠금을 풀고 빈 곳을 클릭하면 좌표가 자동 픽업됩니다 "
            "(파란 별 = 현재 선택). 미세조정은 위 숫자입력."
        )
        if new_room.strip():
            new_spot_meta = (new_floor, new_room.strip(), new_x, new_y)

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

    # 활성 유형 ∪ 사전 설정된 값(카테고리 기본값·현재 선택) — 옵션 누락 방지
    _active_types = data.load_inspection_types(active_only=True)
    _seen: set[str] = set()
    _extra_types = [
        t for t in (list(cat_default_types)
                    + list(st.session_state.get("eq_dlg_types", []) or []))
        if t and t not in _active_types and not (t in _seen or _seen.add(t))
    ]
    insp_types = st.multiselect(
        "적용 점검 유형 (카테고리 기본값 자동 채움, 수정 가능)",
        options=_active_types + _extra_types,
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
    elif new_spot_meta:
        nf, nr, nx, ny = new_spot_meta
        loc_html = (
            f"<b>신규 위치</b> · {nf} / {nr} (등록 시 spot 생성)<br>"
            f"<b>도면 좌표</b> · ({nx:.1f}%, {ny:.1f}%)"
        )
    else:
        loc_html = "<b>위치</b> · 위치 미지정 (기존 선택 또는 신규 만들기 필요)"

    has_location = (sel_spot is not None) or (new_spot_meta is not None)

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
        key="eq_dlg_submit", disabled=(not has_location),
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

        # 신규 위치 만들기 모드면 spot을 먼저 정식 생성 (is_temporary=False)
        if sel_spot is None and new_spot_meta is not None:
            nf, nr, nx, ny = new_spot_meta
            new_spot = data.Spot(
                spot_id=data.next_spot_id(nf),
                floor=nf, room_name=nr, notes="",
                x_pct=nx, y_pct=ny, is_temporary=False,
            )
            data.add_spot(new_spot)
            sel_spot = new_spot

        # spot 정보로 zone/location_id/pixel 좌표 자동 채움
        location_id = location_id_from_spot(sel_spot.spot_id)  # 예: 1F-03
        zone_value = sel_spot.room_name                        # 방이름

        new_eq = Equipment(
            equipment_id=auto_eid,
            location_id=location_id,
            category=category,  # type: ignore[arg-type]
            equipment_name=equipment_name.strip(),
            serial=serial.strip(),
            qr_status="PENDING",  # v1.5+ 신규 등록은 부착 대기 — 첫 스캔 시 ASSIGNED 자동 전환
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

    type_options = data.load_inspection_types(active_only=True) + ["기타"]
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

    # v1.6: 일일 점검(화기작업구간 점검 의도)은 작업 구간을 매번 새로 잡아야 하므로
    # 자유 점검 모드를 기본 ON으로 자동 활성화. 사용자가 풀어 다시 선택할 수도 있음.
    is_daily = (type_choice == "일일 점검")
    if is_daily and not st.session_state.get("_task_dlg_daily_seeded"):
        st.session_state["task_dlg_free_mode"] = True
        st.session_state["_task_dlg_daily_seeded"] = True
    elif not is_daily:
        st.session_state.pop("_task_dlg_daily_seeded", None)

    # 점검 유형 → 적용 가능 장비 후보 (자유 점검이어도 목록은 항상 표시, 비활성화만)
    all_eq = data.load_equipment()
    if type_choice == "기타":
        candidates = all_eq  # 기타는 전체에서 자유 선택
    else:
        candidates = [
            e for e in all_eq if resolved_type in (e.inspection_types or [])
        ]
    eq_indices = list(range(len(candidates)))

    # 자유 점검 체크박스가 목록 아래에 있으므로 session_state에서 미리 읽어 비활성화 판단
    free_mode = st.session_state.get("task_dlg_free_mode", False)

    # v1.7: 점검 유형이 바뀌면 대상 장비를 '전체 선택'으로 기본 세팅 (불필요한 것만 빼는 방식)
    last_type = st.session_state.get("task_dlg_last_type")
    if last_type != type_choice:
        st.session_state["task_dlg_eq_idxs"] = list(eq_indices)
        st.session_state["task_dlg_last_type"] = type_choice

    # '모두 선택' 버튼은 기본이 전체 선택이라 제거. '전체 해제'만 유지 (rerun 방지로 state만)
    _clr_col, _ = st.columns([1, 2.2])
    with _clr_col:
        if st.button("전체 해제", key="task_dlg_clear_all",
                     use_container_width=True, disabled=free_mode):
            st.session_state["task_dlg_eq_idxs"] = []

    sel_idxs = st.multiselect(
        f"대상 장비 (이 유형 해당 {len(candidates)}건 후보)",
        options=eq_indices,
        format_func=lambda i: (
            f"{candidates[i].location_id} · {candidates[i].equipment_name}"
        ),
        key="task_dlg_eq_idxs",
        placeholder="장비를 선택하세요 (여러 건 선택 가능)",
        disabled=free_mode,
    )

    # v1.5 자유 점검 옵션 — v1.7: 대상 장비 목록 바로 아래에 배치, 체크 시 목록 비활성화
    free_mode = st.checkbox(
        "자유 점검 (점검 대상 미선택)",
        key="task_dlg_free_mode",
        help=(
            "체크 시 회차 1건만 만들고 Task는 0개입니다. "
            "점검자가 안전점검 → [신규 Task 추가] 로 그때그때 등록 가능. "
            "일일 점검(화기작업구간) 선택 시 자동 활성화."
        ),
    )

    if free_mode:
        selected_eqs = []
        st.caption("자유 점검 — 회차만 등록되고 대상 장비는 점검 시작 시 선택합니다.")
    else:
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
