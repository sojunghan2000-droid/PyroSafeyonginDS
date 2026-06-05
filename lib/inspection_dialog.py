"""신규 점검 모달 — 지적·오동작 관리에서 호출.

`@st.dialog`로 점검 폼을 띄운다.
"""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib import data
from lib.data import Deficiency, Malfunction, Notice, add_deficiency, add_malfunction, add_notice, next_notice_no
from lib.qr import make_qr, payload_for
from lib.ui import badge


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
            action_photo_now = st.file_uploader(
                "조치 사진 (선택)",
                type=["jpg", "jpeg", "png"],
                key="dlg_action_photo",
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
            ))

        new_def_id = f"D-NEW-{len(st.session_state.get('added_deficiencies', [])) + 1}"
        add_deficiency(Deficiency(
            deficiency_id=new_def_id,
            inspection_date=inspect_date, inspector=inspector,
            floor=eq.floor, zone=eq.zone,
            inspection_types=types_selected,  # type: ignore[arg-type]
            issue=issue.strip() or "양호",
            resolution=("완료" if (result == "양호" or action_immediate) else "불가"),  # type: ignore[arg-type]
            confirmer=confirmer if (result == "양호" or action_immediate) else None,
            notice_no=new_no,
        ))

        # 모달 닫기 (rerun으로 페이지 갱신)
        st.session_state.pop("inspect_target", None)
        st.session_state["just_submitted_inspection"] = True
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

        new_id = f"M-NEW-{len(st.session_state.get('added_malfunctions', [])) + 1}"
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
