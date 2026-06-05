"""Malfunction Log — 별지9 소방시설 오동작 관리대장."""
from __future__ import annotations

import streamlit as st

from lib import data
from lib.ui import fmt_date, page_header, render_kpi_row


TEMP_CATEGORIES = ["소화기", "간이소화장치", "비상경보장치", "가스누설경보기", "간이피난유도선", "방화포"]
OTHER_CATEGORIES = ["감지기", "발신기", "수신기", "확산소화기", "유도등", "기타"]


def render() -> None:
    rows = data.load_malfunctions()

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "오동작 관리대장",
            "별지9 소방시설 오동작 관리대장 · 임시소방시설 6종 + 기타 소방시설.",
        )
    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            st.button("Log Malfunction", type="primary", use_container_width=True)
        with b2:
            st.button("Export 별지9 PDF", use_container_width=True)

    render_kpi_row([
        ("Total Records", f"{len(rows)}", "이번 달 기록", "default"),
        ("임시소방시설", "6종", "법적 기준 항목", "default"),
        ("그 외 소방시설", f"{len(OTHER_CATEGORIES)}종", "기타 관리 항목", "default"),
        ("Open Items", f"{len(rows)}", "Active malfunctions", "alert"),
    ])

    header = (
        "<table style='width:100%; border-collapse:collapse;'>"
        "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<th style='padding:0.6rem 0.4rem; width:20%;'>소방시설 구분</th>"
        "<th style='padding:0.6rem 0.4rem; width:14%;'>일자</th>"
        "<th style='padding:0.6rem 0.4rem;'>오동작 내용</th>"
        "<th style='padding:0.6rem 0.4rem; width:14%;'>조치결과</th>"
        "<th style='padding:0.6rem 0.4rem; width:12%;'>확인자</th>"
        "</tr></thead><tbody>"
    )
    body = []
    for cat in TEMP_CATEGORIES:
        match = [r for r in rows if r.category == cat]
        if match:
            for r in match:
                body.append(
                    "<tr style='border-bottom:1px solid #F1F5F9;'>"
                    f"<td style='padding:0.7rem 0.4rem; font-weight:600; color:#0F172A;'>{cat}</td>"
                    f"<td style='padding:0.7rem 0.4rem; color:#334155;'>{fmt_date(r.occurred_on)}</td>"
                    f"<td style='padding:0.7rem 0.4rem; color:#0F172A;'>{r.detail}</td>"
                    f"<td style='padding:0.7rem 0.4rem; color:#334155;'>{r.action}</td>"
                    f"<td style='padding:0.7rem 0.4rem; color:#334155;'>{r.confirmer}</td>"
                    "</tr>"
                )
        else:
            body.append(
                "<tr style='border-bottom:1px solid #F1F5F9;'>"
                f"<td style='padding:0.7rem 0.4rem; font-weight:600; color:#0F172A;'>{cat}</td>"
                "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
                "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
                "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
                "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
                "</tr>"
            )

    body2 = []
    for cat in OTHER_CATEGORIES:
        body2.append(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.7rem 0.4rem; font-weight:600; color:#0F172A;'>{cat}</td>"
            "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
            "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
            "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
            "<td style='padding:0.7rem 0.4rem; color:#CBD5E1;'>-</td>"
            "</tr>"
        )

    full_html = (
        "<div class='ps-table'>"
        "<div style='font-weight:700; color:#0F172A; margin-bottom:0.5rem;'>임시소방시설 6가지 (법적기준)</div>"
        f"{header}{''.join(body)}</tbody></table>"
        "<div style='font-weight:700; color:#0F172A; margin:1.2rem 0 0.5rem;'>그 외 소방시설</div>"
        f"{header}{''.join(body2)}</tbody></table>"
        "</div>"
    )
    st.markdown(full_html, unsafe_allow_html=True)
