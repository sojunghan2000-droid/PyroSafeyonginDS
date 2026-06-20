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

    st.markdown("<b style='color:#334155; font-size:0.92rem;'>점검 종류 (별지5)</b>",
                unsafe_allow_html=True)
    type_cols = st.columns(3)
    types_selected = []
    for col, t in zip(type_cols, INSPECTION_TYPES):
        with col:
            if st.checkbox(t, key=f"dlg_chk_{t}"):
                types_selected.append(t)

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


@st.dialog("회차에 Task 추가", width="large")
def add_task_to_round_dialog(round_id: str) -> None:
    """v1.5 자유 점검 회차에 Task 1건 동적 추가."""
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

    # 회차의 점검 유형에 맞는 장비 후보
    all_eq = data.load_equipment()
    if r.task_type in TASK_INSPECTION_TYPES:
        candidates = [
            e for e in all_eq if r.task_type in (e.inspection_types or [])
        ]
    else:
        candidates = all_eq

    # 이미 회차에 포함된 장비는 후보에서 제외 (location_id 기준)
    already_locs = {
        t.equipment_label.split(" - ")[0].strip()
        for t in data.tasks_of_round(round_id, include_excluded=True)
    }
    candidates = [c for c in candidates if c.location_id not in already_locs]

    if not candidates:
        st.info(
            f"이 점검 유형에 매핑된 장비 중 '회차에 미포함'인 후보가 없습니다. "
            "장비 마스터의 inspection_types를 확인하세요."
        )
        return

    eq_idx = st.selectbox(
        "추가할 장비",
        options=range(len(candidates)),
        format_func=lambda i: (
            f"{candidates[i].location_id} · {candidates[i].equipment_name} "
            f"({candidates[i].category})"
        ),
        key=f"add_tsk_eq_{round_id}",
    )
    sel_eq = candidates[eq_idx]
    note = st.text_input(
        "메모(선택)",
        key=f"add_tsk_note_{round_id}",
        placeholder=r.note,
    )

    if st.button(
        "추가", type="primary", use_container_width=True,
        key=f"add_tsk_submit_{round_id}",
    ):
        from lib.data import next_task_id, add_task, _refresh_round_status
        new_tsk = next_task_id()
        add_task(InspectionTask(
            task_id=new_tsk,
            equipment_label=f"{sel_eq.location_id} - {sel_eq.equipment_name}",
            task_type=r.task_type,
            assignee=r.assignee or "Unassigned",
            due_date=r.due_date,
            status="Scheduled",
            floor=sel_eq.floor,
            zone=sel_eq.zone,
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
    """v1.5 Task 단위 모바일 점검 입력 모달.
    회차 상세 모달의 [점검 시작] 버튼에서 호출."""
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

    st.markdown(
        "<b style='color:#334155; font-size:0.92rem;'>점검 종류 (별지5)</b>",
        unsafe_allow_html=True,
    )
    type_cols = st.columns(3)
    types_selected = []
    for col, ty in zip(type_cols, INSPECTION_TYPES):
        with col:
            if st.checkbox(ty, key=f"tsk_chk_{task_id}_{ty}"):
                types_selected.append(ty)

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

        # 사용 영역: floor/zone 은 장비 정보 또는 Task 정보 사용
        floor = eq.floor if eq else t.floor
        zone = eq.zone if eq else t.zone
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

        st.session_state["just_completed_task"] = t.task_id
        st.rerun()


@st.dialog("오동작 등록 (별지9)", width="large")
def malfunction_dialog() -> None:
    """별지9 소방시설 오동작 관리대장 row 추가 모달."""
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.5rem;'>"
        "운영 중 발생한 소방시설 오동작을 별지9에 기록합니다. 점검 결과와는 별개 사건입니다."
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
        confirmer = st.text_input("확인자", value="박소방", key="mal_dlg_confirmer")

    detail = st.text_area(
        "오동작 내용",
        placeholder="예: 점등 불량, 충수 상태 불량, 오작동 등",
        key="mal_dlg_detail",
    )
    action = st.text_input(
        "조치 결과",
        placeholder="예: 교체, 수원공급, 재점검 등",
        key="mal_dlg_action",
    )

    if st.button("등록", type="primary", use_container_width=True, key="mal_dlg_submit"):
        if not detail.strip():
            st.error("오동작 내용을 입력해 주세요.")
            return
        if not action.strip():
            st.error("조치 결과를 입력해 주세요.")
            return

        new_id = data.next_malfunction_id()
        add_malfunction(Malfunction(
            malfunction_id=new_id,
            category=category,  # type: ignore[arg-type]
            occurred_on=occurred,
            detail=detail.strip(),
            action=action.strip(),
            confirmer=confirmer,
        ))
        st.session_state["just_submitted_malfunction"] = True
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
