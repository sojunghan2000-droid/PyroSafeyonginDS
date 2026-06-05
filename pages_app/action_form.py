"""조치 폼 — 발급된 통보서에 대한 후속 조치 등록 (사진/조치내용/확인자)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib import data
from lib.ui import badge, fmt_date, page_header


def _find_notice(notice_no: str):
    return next((n for n in data.load_notices() if n.notice_no == notice_no), None)


def render() -> None:
    target = st.session_state.get("action_target_notice")
    notice = _find_notice(target) if target else None

    if not notice:
        st.error("선택된 통보서가 없습니다. **지적 관리**에서 '조치 폼 →' 버튼을 눌러 진입하세요.")
        if st.button("← 지적 관리로", use_container_width=False):
            st.session_state["page"] = "deficiencies"
            st.rerun()
        return

    # 헤더 + 뒤로가기
    back_col, title_col = st.columns([0.15, 4])
    with back_col:
        if st.button("←", key="action_back", help="지적 관리로 돌아가기",
                     use_container_width=True):
            st.session_state["page"] = "deficiencies"
            st.session_state.pop("action_target_notice", None)
            st.rerun()
    with title_col:
        page_header(
            f"조치 폼 · {notice.notice_no}",
            "발급된 통보서에 대한 조치 결과를 등록합니다. "
            "제출 후 별지6 PDF에 사진과 함께 포함됩니다.",
        )

    if notice.action_done:
        st.success(
            f"이 통보서는 이미 조치 완료 처리되었습니다. "
            f"(완료일 {notice.action_at}, 메모: {notice.action_note or '-'})"
        )
        st.markdown("<div style='color:#64748B; font-size:0.85rem;'>"
                    "보고서 → 별지6 카드에서 PDF를 출력할 수 있습니다.</div>",
                    unsafe_allow_html=True)
        return

    # 통보서 정보 카드
    st.markdown(
        "<div class='ps-table' style='padding:1rem 1.2rem;'>"
        f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.4rem;'>"
        f"통보서 {notice.notice_no}</div>"
        f"<div style='color:#475569; font-size:0.92rem; line-height:1.7;'>"
        f"<b>점검일</b> · {fmt_date(notice.inspection_date)}<br>"
        f"<b>장소(구역)</b> · {notice.floor} / {notice.zone}<br>"
        f"<b>점검종류</b> · {notice.inspection_type}<br>"
        f"<b>지적사항</b> · {notice.issue}<br>"
        f"<b>제출자</b> · {notice.submitter} (서명)"
        "</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.4rem;'>"
        "조치 결과 입력</div>",
        unsafe_allow_html=True,
    )

    photo = st.file_uploader(
        "조치 결과 사진",
        type=["jpg", "jpeg", "png"],
        key=f"action_photo_{notice.notice_no}",
    )
    if photo:
        st.image(photo, width=240)

    c1, c2 = st.columns([1, 1])
    with c1:
        confirmer = st.text_input(
            "확인자", value=notice.confirmer or "김소장",
            key=f"action_confirmer_{notice.notice_no}",
        )
    with c2:
        action_at = st.date_input(
            "조치 완료일", value=date.today(),
            key=f"action_at_{notice.notice_no}",
        )

    action_note = st.text_area(
        "조치 내용",
        placeholder="예: 적재물 이동 완료, 통로 확보",
        key=f"action_note_{notice.notice_no}",
    )

    submitted = st.button(
        "조치 완료 등록", type="primary", use_container_width=True,
        key=f"action_submit_{notice.notice_no}",
    )

    if submitted:
        if not action_note.strip():
            st.error("조치 내용을 입력해 주세요.")
            return
        # notice 객체 mutation (시드/세션 양쪽 모두 같은 인스턴스를 가리키므로 반영됨)
        notice.action_done = True
        notice.action_at = action_at
        notice.action_note = action_note.strip()
        notice.action_photo = photo.getvalue() if photo else None
        notice.confirmer = confirmer
        st.success(
            f"통보서 {notice.notice_no} 조치 완료가 등록되었습니다. "
            "지적 관리 · 보고서 별지6에 즉시 반영됩니다."
        )
