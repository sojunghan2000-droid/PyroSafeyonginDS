"""점검 작업 — 상단 조치 카드(처리 대기 통보서) + 하단 신규 점검 폼 통합."""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib import data
from lib.data import Deficiency, Notice, add_deficiency, add_notice, next_notice_no
from lib.qr import make_qr, payload_for
from lib.ui import badge, fmt_date, page_header


INSPECTION_TYPES = ["임시소방시설", "피난로 등", "화기취급감독"]


# ---------- 조치 입력 카드 (1건) ----------

def _render_action_card(notice: Notice, focus: bool) -> None:
    """미완료 통보서 1건의 조치 입력 카드."""
    with st.expander(
        f"{notice.notice_no} · {notice.floor}/{notice.zone} · {notice.issue[:30]}",
        expanded=focus,
    ):
        st.markdown(
            f"<div style='color:#475569; font-size:0.92rem; line-height:1.7; margin-bottom:0.7rem;'>"
            f"<b>점검일</b> · {fmt_date(notice.inspection_date)}  &nbsp;&nbsp;|&nbsp;&nbsp;"
            f"<b>장소(구역)</b> · {notice.floor} / {notice.zone}<br>"
            f"<b>점검종류</b> · {notice.inspection_type}<br>"
            f"<b>지적사항</b> · {notice.issue}<br>"
            f"<b>제출자</b> · {notice.submitter} (서명)"
            "</div>",
            unsafe_allow_html=True,
        )

        photo = st.file_uploader(
            "조치 결과 사진",
            type=["jpg", "jpeg", "png"],
            key=f"act_photo_{notice.notice_no}",
        )
        if photo:
            st.image(photo, width=240)

        c1, c2 = st.columns([1, 1])
        with c1:
            confirmer = st.text_input(
                "확인자",
                value=notice.confirmer or "김소장",
                key=f"act_confirmer_{notice.notice_no}",
            )
        with c2:
            action_at = st.date_input(
                "조치 완료일",
                value=date.today(),
                key=f"act_at_{notice.notice_no}",
            )
        action_note = st.text_area(
            "조치 내용",
            placeholder="예: 적재물 이동 완료, 통로 확보",
            key=f"act_note_{notice.notice_no}",
        )

        if st.button(
            "조치 완료 등록",
            key=f"act_submit_{notice.notice_no}",
            type="primary",
            use_container_width=True,
        ):
            if not action_note.strip():
                st.error("조치 내용을 입력해 주세요.")
                return
            notice.action_done = True
            notice.action_at = action_at
            notice.action_note = action_note.strip()
            notice.action_photo = photo.getvalue() if photo else None
            notice.confirmer = confirmer
            st.session_state.pop("focus_notice", None)
            st.session_state.pop("action_target_notice", None)
            st.success(
                f"통보서 {notice.notice_no} 조치 완료 처리되었습니다. "
                "지적 관리 / 보고서 별지6에 즉시 반영됩니다."
            )
            st.rerun()


# ---------- 신규 점검 폼 ----------

def _render_new_inspection(eq_all) -> None:
    # URL deep link로 장비 사전 선택 (?eq=EQ-0001)
    qp = st.query_params
    preselected_id = qp.get("eq")
    if preselected_id and "inspect_target" not in st.session_state:
        match = next((e for e in eq_all if e.equipment_id == preselected_id), None)
        if match:
            st.session_state["inspect_target"] = match.equipment_id

    options = [f"{e.equipment_id} · {e.location_id} · {e.equipment_name}" for e in eq_all]
    id_to_idx = {e.equipment_id: i for i, e in enumerate(eq_all)}
    default_idx = id_to_idx.get(st.session_state.get("inspect_target"), 0)
    sel_label = st.selectbox("점검 대상 장비", options=options, index=default_idx, key="inspect_sel")
    sel_id = sel_label.split(" · ")[0]
    eq = next(e for e in eq_all if e.equipment_id == sel_id)
    st.session_state["inspect_target"] = eq.equipment_id

    # 장비 정보 + QR
    info_col, qr_col = st.columns([2.4, 1])
    with info_col:
        st.markdown(
            "<div class='ps-table' style='padding:1rem 1.2rem;'>"
            f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.4rem;'>{eq.equipment_name}</div>"
            f"<div style='color:#475569; font-size:0.92rem; line-height:1.7;'>"
            f"<b>장비 ID</b> · {eq.equipment_id}<br>"
            f"<b>위치</b> · {eq.location_id} (층 {eq.floor} / 구역 {eq.zone})<br>"
            f"<b>카테고리</b> · {eq.category}<br>"
            f"<b>현재 상태</b> · {badge(eq.health_status)} {badge(eq.qr_status)}"
            "</div></div>",
            unsafe_allow_html=True,
        )
    with qr_col:
        st.image(make_qr(eq, box_size=6), width=170)
        st.markdown(
            f"<div style='font-size:0.72rem; color:#94A3B8; text-align:center; margin-top:-0.3rem;'>"
            f"{payload_for(eq)}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    # 점검 정보
    c1, c2 = st.columns([1, 1])
    with c1:
        inspector = st.text_input("점검자", value="박소방", placeholder="이름 (서명)",
                                  key="inspector_input")
    with c2:
        inspect_date = st.date_input("점검일", value=date.today(), key="inspect_date_input")

    st.markdown(
        "<div style='font-weight:600; color:#334155; margin-top:0.6rem;'>점검 종류 (별지5)</div>",
        unsafe_allow_html=True,
    )
    type_cols = st.columns(3)
    types_selected = []
    for col, t in zip(type_cols, INSPECTION_TYPES):
        with col:
            if st.checkbox(t, key=f"chk_{eq.equipment_id}_{t}"):
                types_selected.append(t)

    st.markdown(
        "<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin:1rem 0 0.4rem;'>점검 결과</div>",
        unsafe_allow_html=True,
    )
    result = st.radio("결과", ["양호", "불량"], horizontal=True,
                      label_visibility="collapsed", key="result_radio")

    issue = ""
    resolution = "완료"
    confirmer = inspector
    action_immediate = False     # 점검자가 현장에서 즉시 조치 완료했는지
    action_note_now = ""
    action_photo_now = None

    if result == "불량":
        issue = st.text_area("지적사항",
                             placeholder="예: 1-A계단 피난구 유도등 점등 불량",
                             key="issue_input")
        st.info(
            f"통보서 자동 발급 (다음 번호: **{next_notice_no(inspect_date)}**)"
        )
        action_immediate = st.checkbox(
            "현장에서 즉시 조치 완료",
            value=False,
            key="action_immediate_chk",
            help="체크 시 통보서가 즉시 완료 처리되어 별지6 PDF로 바로 출력 가능합니다.",
        )
        if action_immediate:
            confirmer = st.text_input("확인자 (선택)", value=inspector, key="confirmer_input")
            action_note_now = st.text_area(
                "조치 내용 (선택)",
                placeholder="예: 적재물 이동, 흡연자에게 중단 요청 등",
                key="action_note_now",
            )
            action_photo_now = st.file_uploader(
                "조치 사진 (선택)",
                type=["jpg", "jpeg", "png"],
                key="action_photo_now",
            )
            resolution = "완료"
        else:
            st.markdown(
                "<div style='color:#64748B; font-size:0.85rem;'>"
                "→ 통보서는 미완료 상태로 발급되며, 페이지 상단 \"처리 대기 통보서\" 카드 "
                "또는 조치 담당자가 별도 시점에 조치 입력할 수 있습니다."
                "</div>",
                unsafe_allow_html=True,
            )
            resolution = "불가"

    note = st.text_area("비고 (선택)", placeholder="추가 메모", key="note_input")

    if st.button("점검 결과 제출", type="primary", use_container_width=True,
                 key="submit_inspection"):
        if not types_selected:
            st.error("점검 종류를 최소 1개 선택해야 합니다.")
            return
        if result == "불량" and not issue.strip():
            st.error("불량인 경우 지적사항을 입력해 주세요.")
            return

        new_no = None
        if result == "불량":
            # 불량이면 무조건 통보서 발급
            new_no = next_notice_no(inspect_date)
            photo_bytes = action_photo_now.getvalue() if action_photo_now else None
            add_notice(Notice(
                notice_no=new_no,
                inspection_date=inspect_date,
                floor=eq.floor,
                zone=eq.zone,
                inspection_type=types_selected[0],  # type: ignore[arg-type]
                issue=issue.strip(),
                photo_path=None,
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
            inspection_date=inspect_date,
            inspector=inspector,
            floor=eq.floor,
            zone=eq.zone,
            inspection_types=types_selected,  # type: ignore[arg-type]
            issue=issue.strip() or "양호",
            resolution=resolution if result == "불량" else "완료",  # type: ignore[arg-type]
            confirmer=confirmer if (result == "양호" or action_immediate) else None,
            notice_no=new_no,
        ))

        if result == "불량" and action_immediate:
            msg = f"점검 결과 + 통보서({new_no})가 **즉시 완료** 처리되었습니다."
        elif result == "불량":
            msg = f"점검 결과 저장 + 통보서({new_no}) 발급 — 후속 조치 대기 상태입니다."
            st.session_state["focus_notice"] = new_no
        else:
            msg = "점검 결과(양호)가 저장되었습니다."
        st.success(msg)
        st.rerun()


# ---------- 페이지 진입 ----------

def render() -> None:
    """레거시 진입점 — 처리 대기 통보서만 표시.

    신규 점검 입력은 지적·오동작 관리로 이동되어 있음. URL deeplink 등으로
    여기 진입하는 경우 지적·오동작 관리로 자동 라우팅 + 모달 오픈.
    """
    # QR deeplink로 진입한 경우 → 지적·오동작 관리 + 모달 자동 오픈
    if st.session_state.get("inspect_target"):
        st.session_state["page"] = "deficiencies"
        st.session_state["_open_inspect_dialog"] = True
        st.rerun()
        return

    page_header(
        "점검 작업",
        "처리 대기 통보서의 후속 조치를 등록합니다. (신규 점검 입력은 지적·오동작 관리에서)",
    )

    notices = data.load_notices()
    pending = [n for n in notices if not n.action_done]
    focus = st.session_state.get("focus_notice") or st.session_state.get("action_target_notice")

    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.1rem; margin-bottom:0.3rem;'>"
        f"처리 대기 통보서 <span style='color:#DC2626;'>{len(pending)}건</span></div>"
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.6rem;'>"
        "현장에서 발급된 통보서 중 조치가 등록되지 않은 항목입니다. 카드를 펼쳐 사진과 조치 내용을 입력하세요."
        "</div>",
        unsafe_allow_html=True,
    )

    if not pending:
        st.success("처리 대기 통보서가 없습니다. 모든 발급 통보서가 완료 처리되었습니다.")
    else:
        for n in pending:
            _render_action_card(n, focus=(n.notice_no == focus))
