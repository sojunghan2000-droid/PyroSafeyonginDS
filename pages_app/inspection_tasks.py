"""점검 일정 페이지 — v1.4 회차(Round) 단위 표시 + 회차 상세 모달."""
from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib import data, auth
from lib.inspection_dialog import task_dialog
from lib.ui import TASK_STATUS_KO, badge, fmt_date, page_header, render_kpi_row


# 탭 라벨 ↔ data 모델의 영문 status 매핑 (회차 status 동일 4종 사용)
TAB_TO_STATUS = {
    "진행 중": "In Progress",
    "예정": "Scheduled",
    "지연": "Overdue",
    "완료": "Completed",
}

ROW_COLS = [1.5, 1.7, 0.9, 1.0, 1.3, 0.9, 0.8]


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

    # 활성 Task 리스트
    st.markdown(
        f"<div style='font-weight:600; color:#0F172A; font-size:0.95rem; "
        f"margin:0.4rem 0 0.3rem;'>Task 목록 ({len(tasks_active)}건)</div>",
        unsafe_allow_html=True,
    )
    if not tasks_active:
        st.info("이 회차에 점검 대상 장비가 없습니다.")
    else:
        cols_ratio = [1.0, 2.6, 1.0, 1.0, 0.9]
        head = st.columns(cols_ratio)
        for col, txt in zip(head, ["작업 ID", "장비", "상태", "마감일", ""]):
            col.markdown(
                f"<div style='color:#64748B; font-size:0.76rem; "
                f"font-weight:600;'>{txt}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<hr style='margin:0.2rem 0; border-color:#E2E8F0;'>",
                    unsafe_allow_html=True)

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
            with row[4]:
                # 제외 폼 토글 (상세 내 인라인 확장)
                open_key = "round_dlg_exclude_open"
                is_open = st.session_state.get(open_key) == t.task_id
                if st.button("닫기" if is_open else "제외",
                             key=f"rnd_excl_{t.task_id}",
                             type="primary" if is_open else "secondary",
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


def render() -> None:
    rounds = data.load_rounds()
    tasks = data.load_tasks()
    active_tasks = [t for t in tasks if not t.excluded]

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "점검 일정",
            "점검 회차(Round) 단위로 일정을 관리합니다. 회차 행을 눌러 Task 진행 상황을 확인하세요.",
        )
    new_task_clicked = False
    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("신규 일정 등록", type="primary",
                         use_container_width=True, key="open_new_task"):
                new_task_clicked = True
        with b2:
            st.button("감사 로그 내보내기", use_container_width=True)

    submitted_round = st.session_state.pop("just_submitted_round", None)
    submitted_ids = st.session_state.pop("just_submitted_tasks", None)
    if submitted_round and submitted_ids:
        st.success(
            f"회차 {submitted_round} 등록 완료 · Task {len(submitted_ids)}건 "
            f"({submitted_ids[0]} ~ {submitted_ids[-1]})."
        )

    if new_task_clicked:
        task_dialog()

    # KPI — 회차 단위 + Task 단위 혼합
    total_rounds = len(rounds)
    overdue_rounds = sum(1 for r in rounds if r.status == "Overdue")
    in_prog_rounds = sum(1 for r in rounds if r.status == "In Progress")
    completed_rounds = sum(1 for r in rounds if r.status == "Completed")
    render_kpi_row([
        ("전체 회차", f"{total_rounds}", "활성 점검 일정", "default"),
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
            ["전체", "진행 중", "예정", "지연", "완료"],
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
    target_status = TAB_TO_STATUS.get(view)
    if target_status:
        visible = [r for r in visible if r.status == target_status]
    if type_filter != "전체 유형":
        visible = [r for r in visible if r.task_type == type_filter]

    # 헤더
    st.markdown(
        "<div style='display:grid; "
        f"grid-template-columns: {' '.join(f'{r}fr' for r in ROW_COLS)}; "
        "gap:0.4rem; padding:0.55rem 0.4rem; "
        "color:#64748B; font-size:0.78rem; font-weight:600; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<div>회차 ID</div>"
        "<div>점검 유형</div>"
        "<div>담당자</div>"
        "<div>마감일</div>"
        "<div>진행률</div>"
        "<div>상태</div>"
        "<div>작업</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    open_detail: str | None = None
    for r in visible:
        cols = st.columns(ROW_COLS, vertical_alignment="center")
        with cols[0]:
            st.markdown(
                f"<span style='color:#0F172A; font-weight:600; font-size:0.88rem;'>"
                f"{r.round_id}</span>",
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
        due_color = "#DC2626" if r.status == "Overdue" else "#334155"
        with cols[3]:
            st.markdown(
                f"<span style='color:{due_color}; font-weight:600;'>"
                f"{fmt_date(r.due_date)}</span>",
                unsafe_allow_html=True,
            )
        done, total = data.round_progress(r.round_id)
        with cols[4]:
            st.markdown(_progress_bar_html(done, total), unsafe_allow_html=True)
        with cols[5]:
            st.markdown(
                badge(TASK_STATUS_KO.get(r.status, r.status)),
                unsafe_allow_html=True,
            )
        with cols[6]:
            if st.button("상세", key=f"rnd_open_{r.round_id}",
                         use_container_width=True):
                open_detail = r.round_id

    if open_detail:
        _round_detail_dialog(open_detail)

    foot_l, _, _ = st.columns([3, 3, 2])
    with foot_l:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.85rem; padding-top:0.6rem;'>"
            f"{total_rounds}개 회차 중 {len(visible)}개 표시 · 활성 Task {len(active_tasks)}건</div>",
            unsafe_allow_html=True,
        )
