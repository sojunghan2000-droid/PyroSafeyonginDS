"""점검 일정 페이지 — v1.4 회차(Round) 단위 표시 + 회차 상세 모달."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import streamlit as st

from lib import data, auth
from lib.inspection_dialog import (
    add_task_to_round_dialog, task_dialog, task_inspect_dialog,
)
from lib.ui import TASK_STATUS_KO, badge, fmt_date, page_header, render_kpi_row


# 탭 라벨 ↔ data 모델의 영문 status 매핑 (회차 status 동일 4종 사용)
TAB_TO_STATUS = {
    "진행 중": "In Progress",
    "예정": "Scheduled",
    "지연": "Overdue",
    "완료": "Completed",
}

ROW_COLS = [1.5, 1.7, 0.9, 1.0, 1.3, 0.9, 0.8]


def _audit_log_xlsx() -> bytes:
    """점검 결과(Deficiency) 감사 로그를 Excel(.xlsx) 바이트로 생성.
    별지5 원본 데이터를 감사 제출용 평면 표로 정리 (점검일 최신순)."""
    defs = data.load_deficiencies()
    task_round = {t.task_id: (t.round_id or "") for t in data.load_tasks()}
    recs = []
    for d in sorted(defs, key=lambda x: x.inspection_date or data.TODAY,
                    reverse=True):
        is_good = (d.issue or "").strip() in ("", "양호")
        ng = [k for k, v in (d.checklist_items or {}).items() if v == "NG"]
        reasons = list(d.defect_codes or [])
        if d.defect_other:
            reasons.append(f"기타: {d.defect_other}")
        recs.append({
            "점검일": fmt_date(d.inspection_date),
            "점검 ID": (task_round.get(d.task_id) or "-") if d.task_id else "-",
            "작업 ID": d.task_id or "-",
            "층": d.floor,
            "구역": d.zone,
            "점검종류": " / ".join(d.inspection_types or []),
            "결과": "양호" if is_good else "지적",
            "지적내용": "" if is_good else (d.issue or ""),
            "불량사유": ", ".join(reasons),
            "checklist NG": ", ".join(ng),
            "조치상태": d.resolution or "",
            "조치완료일": fmt_date(d.action_at) if d.action_at else "",
            "점검자": d.inspector or "",
            "확인자": d.confirmer or "",
            "통보서번호": d.notice_no or "",
            "기록 ID": d.deficiency_id,
        })
    df = pd.DataFrame(recs, columns=[
        "점검일", "점검 ID", "작업 ID", "층", "구역", "점검종류", "결과",
        "지적내용", "불량사유", "checklist NG", "조치상태", "조치완료일",
        "점검자", "확인자", "통보서번호", "기록 ID",
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="점검결과 감사로그")
    return buf.getvalue()


def _progress_bar_html(done: int, total: int) -> str:
    if total == 0:
        return ("<div style='color:#94A3B8; font-size:0.78rem;'>장비 없음</div>")
    pct = int(done / total * 100)
    color = ("#10B981" if pct == 100
             else "#F59E0B" if pct > 0 else "#94A3B8")
    return (
        f"<div style='color:#475569; font-size:0.78rem; margin-bottom:0.2rem;'>"
        f"{done}/{total} ({pct}%)</div>"
        f"<div style='background:#F1F5F9; border-radius:4px; "
        f"height:6px; width:100%; overflow:hidden;'>"
        f"<div style='background:{color}; height:6px; "
        f"width:{pct}%;'></div></div>"
    )


@st.dialog("회차 상세", width="large")
def _round_detail_dialog(round_id: str) -> None:
    """회차의 Task 리스트 + 각 Task 옆 [제외] 버튼 + 제외 로그."""
    r = data.get_round(round_id)
    if not r:
        st.error("회차를 찾을 수 없습니다.")
        return

    tasks_active = data.tasks_of_round(round_id)
    tasks_all = data.tasks_of_round(round_id, include_excluded=True)
    excluded = [t for t in tasks_all if t.excluded]
    done, total = data.round_progress(round_id)

    # 헤더
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.15rem;'>"
        f"{r.round_id} · {r.task_type}</div>"
        f"<div style='color:#475569; font-size:0.88rem; margin:0.3rem 0 0.6rem;'>"
        f"담당 <b>{r.assignee or '미지정'}</b> · 마감 "
        f"<b>{fmt_date(r.due_date)}</b> · 진행 <b>{done}/{total}</b> "
        f"· 상태 {badge(TASK_STATUS_KO.get(r.status, r.status))}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if r.note:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.83rem; "
            f"margin-bottom:0.5rem;'>비고: {r.note}</div>",
            unsafe_allow_html=True,
        )

    # 취소 상태 배너
    if r.cancelled:
        st.markdown(
            f"<div style='background:#FEF2F2; border:1px solid #FECACA; "
            f"border-radius:8px; padding:0.5rem 0.8rem; margin:0.2rem 0 0.6rem;'>"
            f"<b style='color:#B91C1C;'>취소됨</b>"
            f"<span style='color:#7F1D1D; font-size:0.85rem;'> · 사유: "
            f"{r.cancel_reason or '-'}"
            f"{(' · ' + fmt_date(r.cancelled_at)) if r.cancelled_at else ''}"
            f"{(' · ' + r.cancelled_by) if r.cancelled_by else ''}</span></div>",
            unsafe_allow_html=True,
        )

    # 회차 단위 별지5 PDF 다운로드 (지적사항이 1건 이상일 때만 활성)
    round_task_ids = {t.task_id for t in data.tasks_of_round(round_id, include_excluded=True)}
    round_defs = [d for d in data.load_deficiencies() if d.task_id in round_task_ids]
    _sp, c_cancel, c_pdf = st.columns([2, 1, 1])
    with c_cancel:
        _cancel_supported = data.round_cancel_supported()
        can_cancel = _cancel_supported and (not r.cancelled) and r.status != "Completed"
        if can_cancel:
            if st.button("점검 취소", key=f"round_cancel_btn_{round_id}",
                         use_container_width=True):
                st.session_state[f"round_cancel_open_{round_id}"] = True
        else:
            _cancel_help = (
                "회차 취소 컬럼 마이그레이션이 필요합니다." if not _cancel_supported
                else "완료·기취소 회차는 취소할 수 없습니다."
            )
            st.button("점검 취소", key=f"round_cancel_dis_{round_id}",
                      use_container_width=True, disabled=True, help=_cancel_help)
    with c_pdf:
        if round_defs:
            from pages_app.report_center import _build_pdf_byeolji5
            st.download_button(
                f"별지5 PDF ({len(round_defs)}건)",
                data=_build_pdf_byeolji5(round_id=round_id),
                file_name=f"별지 5. 안전점검 결과 지적 내역서 ({round_id}).pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"rnd_pdf_{round_id}",
            )
        else:
            st.button(
                "별지5 PDF (0건)",
                use_container_width=True,
                disabled=True,
                key=f"rnd_pdf_disabled_{round_id}",
            )

    # 점검 취소 사유 입력 (인라인 — 모달 안 모달 불가 회피)
    if st.session_state.get(f"round_cancel_open_{round_id}"):
        _reason = st.text_area(
            "취소 사유", key=f"round_cancel_reason_{round_id}",
            placeholder="예: 일정 중복 생성 / 작업 취소로 점검 불필요",
        )
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            if st.button("취소 확정", type="primary", use_container_width=True,
                         key=f"round_cancel_confirm_{round_id}",
                         disabled=not _reason.strip()):
                _by = (auth.current_user() or {}).get("name") or "관리자"
                if data.cancel_round(round_id, _reason, _by):
                    st.session_state.pop(f"round_cancel_open_{round_id}", None)
                    st.rerun()
                else:
                    st.error("취소할 수 없는 회차입니다 (완료/기취소).")
        with _cc2:
            if st.button("닫기", use_container_width=True,
                         key=f"round_cancel_close_{round_id}"):
                st.session_state.pop(f"round_cancel_open_{round_id}", None)
                st.rerun()

    # 활성 Task 리스트 헤더 + [+ 추가] 버튼
    hl, hr = st.columns([3, 1])
    with hl:
        st.markdown(
            f"<div style='font-weight:600; color:#0F172A; font-size:0.95rem; "
            f"margin:0.4rem 0 0.3rem;'>Task 목록 ({len(tasks_active)}건)</div>",
            unsafe_allow_html=True,
        )
    add_clicked = False
    with hr:
        if st.button("+ Task 추가", key=f"rnd_add_tsk_{round_id}",
                     use_container_width=True, disabled=r.cancelled):
            add_clicked = True
    if not tasks_active:
        st.info("이 회차에 점검 대상 장비가 없습니다.")
    else:
        # 컬럼 7개 — 결과 컬럼 추가 (Completed Task만 채움)
        cols_ratio = [0.7, 1.5, 0.7, 0.7, 2.2, 0.9, 0.6]
        head = st.columns(cols_ratio)
        for col, txt in zip(head,
                            ["작업 ID", "장비", "상태", "마감일", "결과", "", ""]):
            col.markdown(
                f"<div style='color:#64748B; font-size:0.76rem; "
                f"font-weight:600;'>{txt}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<hr style='margin:0.2rem 0; border-color:#E2E8F0;'>",
                    unsafe_allow_html=True)

        # Task → Deficiency 매핑 (Completed Task 결과 카드 노출용)
        def_by_task = {d.task_id: d for d in round_defs if d.task_id}

        for t in tasks_active:
            row = st.columns(cols_ratio, vertical_alignment="center")
            row[0].markdown(
                f"<span style='color:#334155; font-size:0.85rem;'>{t.task_id}</span>",
                unsafe_allow_html=True,
            )
            row[1].markdown(
                f"<span style='color:#0F172A; font-size:0.86rem;'>"
                f"{t.equipment_label}</span>",
                unsafe_allow_html=True,
            )
            row[2].markdown(badge(TASK_STATUS_KO.get(t.status, t.status)),
                            unsafe_allow_html=True)
            row[3].markdown(
                f"<span style='color:#334155; font-size:0.82rem;'>"
                f"{fmt_date(t.due_date)}</span>",
                unsafe_allow_html=True,
            )
            # 결과 컬럼 — Completed Task에만 inline 결과 카드 (한 행 안에 모든 정보)
            with row[4]:
                # 오동작 우선 확인 (Malfunction)
                mal_match = (
                    next(
                        (m for m in data.load_malfunctions()
                         if m.task_id == t.task_id), None,
                    )
                    if t.status == "Completed" else None
                )
                if mal_match:
                    m = mal_match
                    mal_status = "조치 완료" if m.action_done else "조치 대기"
                    extra = (
                        f"<div style='color:#92400E; font-size:0.78rem; "
                        f"margin-top:0.15rem;'>⚠️ {m.detail}</div>"
                    )
                    if m.action_done and m.action_note:
                        extra += (
                            f"<div style='color:#15803D; font-size:0.78rem; "
                            f"margin-top:0.1rem;'>✅ {m.action_note}</div>"
                        )
                    st.markdown(
                        f"<div style='padding:0.35rem 0.55rem; background:#F8FAFC; "
                        f"border-left:3px solid #DC2626; border-radius:6px;'>"
                        f"<span style='background:#FEE2E2; color:#DC2626; "
                        f"padding:0.05rem 0.45rem; border-radius:999px; "
                        f"font-size:0.72rem; font-weight:700;'>오동작</span> "
                        f"<span style='background:#FEF3C7; color:#92400E; "
                        f"padding:0.05rem 0.4rem; border-radius:999px; "
                        f"font-size:0.7rem; font-weight:600; margin-left:0.2rem;'>"
                        f"{mal_status}</span>"
                        f"<span style='color:#475569; font-size:0.78rem; "
                        f"margin-left:0.3rem;'>"
                        f"{m.confirmer or '-'} · {fmt_date(m.occurred_on)} · {m.category}"
                        f"</span>{extra}</div>",
                        unsafe_allow_html=True,
                    )
                elif t.status == "Completed":
                    d = def_by_task.get(t.task_id)
                    if d:
                        is_good = (d.resolution == "완료" and not d.notice_no)
                        badge_color = "#16A34A" if is_good else "#DC2626"
                        badge_bg = "#DCFCE7" if is_good else "#FEE2E2"
                        badge_txt = "양호" if is_good else "불량"
                        types_str = ", ".join(d.inspection_types) if d.inspection_types else "-"
                        insp_date = fmt_date(d.inspection_date) if d.inspection_date else "-"
                        extra_html = ""
                        if not is_good and d.issue:
                            extra_html += (
                                f"<div style='color:#92400E; font-size:0.78rem; "
                                f"margin-top:0.15rem;'>"
                                f"⚠️ {d.issue}</div>"
                            )
                        if d.action_done and d.action_note:
                            extra_html += (
                                f"<div style='color:#15803D; font-size:0.78rem; "
                                f"margin-top:0.1rem;'>"
                                f"✅ {d.action_note}"
                                f"{' · ' + d.confirmer if d.confirmer else ''}</div>"
                            )
                        st.markdown(
                            f"<div style='padding:0.35rem 0.55rem; background:#F8FAFC; "
                            f"border-left:3px solid {badge_color}; border-radius:6px;'>"
                            f"<span style='background:{badge_bg}; color:{badge_color}; "
                            f"padding:0.05rem 0.45rem; border-radius:999px; "
                            f"font-size:0.72rem; font-weight:700;'>{badge_txt}</span> "
                            f"<span style='color:#475569; font-size:0.78rem; "
                            f"margin-left:0.3rem;'>"
                            f"{d.inspector or '-'} · {insp_date}"
                            f" · {types_str}</span>"
                            f"{extra_html}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            "<span style='color:#94A3B8; font-size:0.78rem;'>"
                            "결과 없음</span>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(
                        "<span style='color:#94A3B8; font-size:0.78rem;'>-</span>",
                        unsafe_allow_html=True,
                    )
            with row[5]:
                # 점검 시작 — 회차 모달 안 인라인 펼침 (모달 호출 X)
                # callback 패턴 — button 그려지기 전에 session_state 갱신되어 같은
                # rerun에서 라벨/인라인 영역 분기 모두 새 값으로 동기화됨
                disabled = (t.status == "Completed")
                inline_key = "round_inline_start_for"
                is_inline_open = (
                    st.session_state.get(inline_key) == t.task_id
                )

                def _toggle_inline(_tid=t.task_id):
                    cur = st.session_state.get(inline_key)
                    st.session_state[inline_key] = (
                        None if cur == _tid else _tid
                    )

                st.button(
                    ("닫기" if is_inline_open else
                     ("점검 시작 →" if not disabled else "점검 완료")),
                    key=f"rnd_start_{t.task_id}",
                    type="primary",
                    use_container_width=True,
                    disabled=disabled,
                    on_click=_toggle_inline,
                )
            with row[6]:
                # 제외 폼 토글 (상세 내 인라인 확장)
                open_key = "round_dlg_exclude_open"
                is_open = st.session_state.get(open_key) == t.task_id
                if st.button("닫기" if is_open else "제외",
                             key=f"rnd_excl_{t.task_id}",
                             type="secondary",
                             use_container_width=True):
                    st.session_state[open_key] = (
                        None if is_open else t.task_id
                    )

            if st.session_state.get("round_dlg_exclude_open") == t.task_id:
                with st.container(border=True):
                    reason = st.text_input(
                        "제외 사유",
                        key=f"rnd_excl_reason_{t.task_id}",
                        placeholder="예: 장비 회수 / 점검 대상 아님",
                    )
                    if st.button("제외 확정", type="primary",
                                 use_container_width=True,
                                 key=f"rnd_excl_save_{t.task_id}"):
                        if not reason.strip():
                            st.error("제외 사유를 입력해 주세요.")
                        else:
                            me = auth.current_user() or {}
                            data.exclude_task(
                                t.task_id, reason.strip(),
                                me.get("name") or me.get("username") or "(관리자)",
                            )
                            st.session_state["round_dlg_exclude_open"] = None
                            st.success(f"{t.task_id} 점검 대상에서 제외했습니다.")

            # 인라인 점검 입력 영역 — [점검 시작 →] 클릭으로 펼침
            if (st.session_state.get("round_inline_start_for") == t.task_id
                    and t.status != "Completed"):
                with st.container(border=True):
                    from lib.inspection_dialog import task_inspect_inline
                    task_inspect_inline(t.task_id)

    # 제외 로그
    if excluded:
        st.markdown(
            f"<div style='font-weight:600; color:#64748B; font-size:0.88rem; "
            f"margin:0.8rem 0 0.3rem;'>제외 로그 ({len(excluded)}건)</div>",
            unsafe_allow_html=True,
        )
        for t in excluded:
            cols = st.columns([1.0, 2.6, 1.4, 1.0])
            cols[0].markdown(
                f"<span style='color:#94A3B8; text-decoration:line-through; "
                f"font-size:0.82rem;'>{t.task_id}</span>",
                unsafe_allow_html=True,
            )
            cols[1].markdown(
                f"<span style='color:#94A3B8; text-decoration:line-through; "
                f"font-size:0.82rem;'>{t.equipment_label}</span>",
                unsafe_allow_html=True,
            )
            cols[2].markdown(
                f"<span style='color:#64748B; font-size:0.78rem;'>"
                f"{t.excluded_reason or '-'} · {t.excluded_by or '-'}</span>",
                unsafe_allow_html=True,
            )
            with cols[3]:
                if st.button("복구", key=f"rnd_restore_{t.task_id}",
                             use_container_width=True):
                    data.restore_task(t.task_id)
                    st.success(f"{t.task_id} 복구했습니다.")

    # [+ Task 추가] 클릭 시 회차 모달 닫고 외부 모달로 (dialog nesting 불가 회피)
    if add_clicked:
        st.session_state["_open_add_task_to_round"] = round_id
        st.rerun()


def render() -> None:
    rounds = data.load_rounds()
    tasks = data.load_tasks()
    active_tasks = [t for t in tasks if not t.excluded]

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "안전점검 관리",
            "안전점검 회차(Round) 단위로 점검을 진행합니다. 회차 [상세]에서 [점검 시작]으로 별지5 결과를 기록하세요.",
        )
    new_task_clicked = False
    mal_clicked = False
    with action_col:
        # 상단 3버튼 — 높이 통일 + 글자 길면 자동 줄바꿈 (잘림 방지)
        st.markdown(
            "<style>"
            ".st-key-open_new_task button,.st-key-open_new_malfunction_insp button,"
            ".st-key-audit_log_export button{"
            "white-space:normal!important;min-height:3.1rem;height:100%;"
            "line-height:1.2;padding:0.3rem 0.4rem!important;}"
            ".st-key-open_new_task button p,.st-key-open_new_malfunction_insp button p,"
            ".st-key-audit_log_export button p{white-space:normal!important;"
            "word-break:keep-all;}"
            "</style>",
            unsafe_allow_html=True,
        )
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("신규 일정 등록", type="primary",
                         use_container_width=True, key="open_new_task"):
                new_task_clicked = True
        with b2:
            if st.button("오동작 등록", use_container_width=True,
                         key="open_new_malfunction_insp"):
                mal_clicked = True
        with b3:
            st.download_button(
                "감사 로그 내보내기",
                data=_audit_log_xlsx(),
                file_name=f"감사로그_점검결과_{data.TODAY:%Y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet",
                use_container_width=True,
                key="audit_log_export",
                help="점검 결과(별지5 원본) 전체를 Excel(.xlsx)로 내려받습니다.",
            )

    submitted_round = st.session_state.pop("just_submitted_round", None)
    submitted_ids = st.session_state.pop("just_submitted_tasks", None)
    if submitted_round and submitted_ids:
        st.success(
            f"회차 {submitted_round} 등록 완료 · Task {len(submitted_ids)}건 "
            f"({submitted_ids[0]} ~ {submitted_ids[-1]})."
        )

    completed_task = st.session_state.pop("just_completed_task", None)
    if completed_task:
        st.success(f"{completed_task} 점검 완료. 작업 조치 관리에서 후속 처리 가능.")

    if new_task_clicked:
        task_dialog()

    # 오동작 등록 — 안전점검 우상단 진입점 (v1.5+)
    if mal_clicked:
        from lib.inspection_dialog import malfunction_dialog
        malfunction_dialog()
    if st.session_state.pop("just_submitted_malfunction", False):
        st.success("오동작이 별지9에 등록되었습니다. [작업 조치 관리]에서 조치 입력하세요.")

    # 회차 상세 내 [점검 시작] 클릭 시 띄울 모달
    open_task = st.session_state.pop("_open_task_inspect", None)
    if open_task:
        task_inspect_dialog(open_task)

    # 회차 상세 내 [+ Task 추가] 클릭 시 띄울 모달
    open_add = st.session_state.pop("_open_add_task_to_round", None)
    if open_add:
        add_task_to_round_dialog(open_add)

    added_tsk = st.session_state.pop("just_added_task", None)
    if added_tsk:
        st.success(f"신규 Task {added_tsk} 가 회차에 추가되었습니다.")

    # KPI — 회차 단위 + Task 단위 혼합 (취소 회차 제외)
    active_rounds = [r for r in rounds if not r.cancelled]
    cancelled_cnt = len(rounds) - len(active_rounds)
    total_rounds = len(active_rounds)
    overdue_rounds = sum(1 for r in active_rounds if r.status == "Overdue")
    in_prog_rounds = sum(1 for r in active_rounds if r.status == "In Progress")
    completed_rounds = sum(1 for r in active_rounds if r.status == "Completed")
    render_kpi_row([
        ("전체 회차", f"{total_rounds}",
         f"활성 점검 일정{f' · 취소 {cancelled_cnt}' if cancelled_cnt else ''}", "default"),
        ("지연", f"{overdue_rounds}", "즉시 조치 필요",
         "alert" if overdue_rounds else "default"),
        ("진행 중", f"{in_prog_rounds}", "현재 활성", "default"),
        ("완료", f"{completed_rounds}", "최근 완료", "default"),
    ])

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    filter_col, _, tab_col = st.columns([2.5, 2, 3])
    with tab_col:
        view = st.radio(
            "tab",
            ["전체", "진행 중", "예정", "지연", "완료", "취소"],
            horizontal=True,
            label_visibility="collapsed",
            key="tasks_view",
        )
    with filter_col:
        type_options = ["전체 유형"] + sorted({r.task_type for r in rounds})
        type_filter = st.selectbox(
            "점검 유형",
            type_options,
            label_visibility="collapsed",
        )

    visible = rounds
    if view == "취소":
        visible = [r for r in visible if r.cancelled]
    else:
        target_status = TAB_TO_STATUS.get(view)
        if target_status:
            # 특정 상태 탭 — 취소 회차 제외
            visible = [r for r in visible if not r.cancelled and r.status == target_status]
        # "전체"는 취소 포함 전부 노출 (취소됨 배지로 구분)
    if type_filter != "전체 유형":
        visible = [r for r in visible if r.task_type == type_filter]

    # 헤더
    st.markdown(
        "<div style='display:grid; "
        f"grid-template-columns: {' '.join(f'{r}fr' for r in ROW_COLS)}; "
        "gap:0.4rem; padding:0.55rem 0.4rem; "
        "color:#64748B; font-size:0.78rem; font-weight:600; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<div>점검 ID</div>"
        "<div>점검 유형</div>"
        "<div>담당자</div>"
        "<div>마감일</div>"
        "<div>진행률</div>"
        "<div>상태</div>"
        "<div>작업</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    from datetime import timedelta
    today = data.TODAY
    soon_cutoff = today + timedelta(days=3)
    focus_round = st.session_state.pop("focus_round", None)

    open_detail: str | None = None
    for r in visible:
        is_soon = (
            r.status != "Completed"
            and r.due_date is not None
            and today <= r.due_date <= soon_cutoff
        )
        is_focused = (focus_round == r.round_id)
        cols = st.columns(ROW_COLS, vertical_alignment="center")
        with cols[0]:
            badges = ""
            if is_soon:
                days_left = (r.due_date - today).days
                day_txt = "오늘 마감" if days_left == 0 else f"D-{days_left}"
                badges = (
                    f" <span style='background:#FFEDD5; color:#9A3412; "
                    f"border:1px solid #F97316; padding:0.1rem 0.4rem; "
                    f"border-radius:6px; font-size:0.7rem; font-weight:700; "
                    f"margin-left:0.3rem;'>임박 · {day_txt}</span>"
                )
            focus_style = (
                "outline:2px solid #2563EB; outline-offset:2px; border-radius:4px; "
                if is_focused else ""
            )
            st.markdown(
                f"<span style='color:#0F172A; font-weight:600; font-size:0.88rem; "
                f"{focus_style}'>{r.round_id}</span>{badges}",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"<span style='color:#0F172A;'>{r.task_type}</span>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            assignee_label = r.assignee or "미지정"
            assignee_style = ("color:#94A3B8; font-style:italic;"
                              if r.assignee in ("", "Unassigned", "미지정")
                              else "color:#334155;")
            st.markdown(
                f"<span style='{assignee_style}'>{assignee_label}</span>",
                unsafe_allow_html=True,
            )
        due_color = (
            "#DC2626" if r.status == "Overdue"
            else "#D97706" if is_soon
            else "#334155"
        )
        with cols[3]:
            st.markdown(
                f"<span style='color:{due_color}; font-weight:600;'>"
                f"{fmt_date(r.due_date)}</span>",
                unsafe_allow_html=True,
            )
        done, total = data.round_progress(r.round_id)
        with cols[4]:
            if r.cancelled:
                st.markdown("<span style='color:#CBD5E1;'>—</span>",
                            unsafe_allow_html=True)
            else:
                st.markdown(_progress_bar_html(done, total), unsafe_allow_html=True)
        with cols[5]:
            if r.cancelled:
                st.markdown(
                    "<span style='background:#FEE2E2; color:#B91C1C; "
                    "padding:0.15rem 0.5rem; border-radius:6px; font-size:0.8rem; "
                    "font-weight:600;'>취소됨</span>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    badge(TASK_STATUS_KO.get(r.status, r.status)),
                    unsafe_allow_html=True,
                )
        with cols[6]:
            if st.button("점검", key=f"rnd_open_{r.round_id}",
                         use_container_width=True, type="primary"):
                open_detail = r.round_id

    if open_detail:
        _round_detail_dialog(open_detail)

    foot_l, _, _ = st.columns([3, 3, 2])
    with foot_l:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.85rem; padding-top:0.6rem;'>"
            f"{len(rounds)}개 회차 중 {len(visible)}개 표시 · 활성 Task {len(active_tasks)}건</div>",
            unsafe_allow_html=True,
        )
