"""Inspection Tasks 페이지."""
from __future__ import annotations

import streamlit as st

from lib import data
from lib.ui import badge, fmt_date, page_header, render_kpi_row


def render() -> None:
    tasks = data.load_tasks()
    kpi = data.task_kpis()

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "점검 일정",
            "시설 안전점검 일정을 등록하고 진행 상황을 관리합니다.",
        )
    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            st.button("Schedule New Task", type="primary", use_container_width=True)
        with b2:
            st.button("Export Audit Log", use_container_width=True)

    render_kpi_row([
        ("Total Tasks", f"{kpi['total']}", "Active this week", "default"),
        ("Overdue", f"{kpi['overdue']}", "Immediate attention required", "alert"),
        ("In Progress", f"{kpi['in_progress']}", "Currently active", "default"),
        ("Completed", f"{kpi['completed']}", "Last 7 days", "default"),
    ])

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    tab_col, _, filter_col = st.columns([3, 2, 2.5])
    with tab_col:
        view = st.radio(
            "tab",
            ["All Tasks", "Ongoing", "Scheduled", "Overdue"],
            horizontal=True,
            label_visibility="collapsed",
        )
    with filter_col:
        eq_filter = st.text_input(
            "Filter by equipment",
            placeholder="Filter by equipment...",
            label_visibility="collapsed",
        )

    rows = tasks
    if view == "Ongoing":
        rows = [t for t in rows if t.status == "In Progress"]
    elif view == "Scheduled":
        rows = [t for t in rows if t.status == "Scheduled"]
    elif view == "Overdue":
        rows = [t for t in rows if t.status == "Overdue"]
    if eq_filter:
        rows = [t for t in rows if eq_filter.lower() in t.equipment_label.lower()]

    header_html = (
        "<table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<th style='padding:0.6rem 0.4rem;'>TASK ID</th>"
        "<th style='padding:0.6rem 0.4rem;'>EQUIPMENT / FACILITY</th>"
        "<th style='padding:0.6rem 0.4rem;'>TASK TYPE</th>"
        "<th style='padding:0.6rem 0.4rem;'>ASSIGNEE</th>"
        "<th style='padding:0.6rem 0.4rem;'>DUE DATE</th>"
        "<th style='padding:0.6rem 0.4rem;'>STATUS</th>"
        "<th style='padding:0.6rem 0.4rem;'>ACTIONS</th>"
        "</tr></thead><tbody>"
    )
    body = []
    for t in rows:
        due_color = "#DC2626" if t.status == "Overdue" else "#334155"
        assignee_style = "color:#94A3B8; font-style:italic;" if t.assignee == "Unassigned" else "color:#334155;"
        body.append(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.85rem 0.4rem; color:#334155;'>{t.task_id}</td>"
            f"<td style='padding:0.85rem 0.4rem; font-weight:600; color:#0F172A;'>{t.equipment_label}</td>"
            f"<td style='padding:0.85rem 0.4rem; color:#334155;'>{t.task_type}</td>"
            f"<td style='padding:0.85rem 0.4rem; {assignee_style}'>{t.assignee}</td>"
            f"<td style='padding:0.85rem 0.4rem; color:{due_color}; font-weight:600;'>{fmt_date(t.due_date)}</td>"
            f"<td style='padding:0.85rem 0.4rem;'>{badge(t.status)}</td>"
            "<td style='padding:0.85rem 0.4rem; color:#94A3B8;'>👁  ✎</td>"
            "</tr>"
        )
    st.markdown(header_html + "".join(body) + "</tbody></table>", unsafe_allow_html=True)

    foot_l, _, foot_r = st.columns([3, 3, 2])
    with foot_l:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.85rem; padding-top:0.6rem;'>"
            f"Showing 1–{len(rows)} of {kpi['total']} results</div>",
            unsafe_allow_html=True,
        )
    with foot_r:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.button("‹", key="tsk_prev", use_container_width=True)
        c2.button("1", key="tsk_1", type="primary", use_container_width=True)
        c3.button("2", key="tsk_2", use_container_width=True)
        c4.button("3", key="tsk_3", use_container_width=True)
        c5.button("›", key="tsk_next", use_container_width=True)
