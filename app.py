"""PyroSafe Inspection Management — 용인덕성 AI DC.

Streamlit 진입점. 사이드바에서 페이지를 전환한다.
"""
from __future__ import annotations

import streamlit as st

from lib.ui import apply_theme, render_sidebar, render_topbar
from pages_app import (
    dashboard,
    equipment_inventory,
    inspection_form,
    inspection_tasks,
    deficiency_manager,
    report_center,
    floor_map,
    field_mobile,
)

st.set_page_config(
    page_title="PyroSafe · 용인덕성 AI DC",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

if "page" not in st.session_state:
    st.session_state["page"] = "dashboard"

# URL deep link: ?eq=EQ-0001 → 지적·오동작 관리 + 신규 점검 모달 자동 오픈
# eq 값이 바뀔 때마다 발동 (브라우저에서 다른 장비 QR 스캔 시도 가능)
qp = st.query_params
eq_param = qp.get("eq")
if eq_param and st.session_state.get("_last_eq_param") != eq_param:
    st.session_state["page"] = "deficiencies"
    st.session_state["inspect_target"] = eq_param
    st.session_state["_open_inspect_dialog"] = True
    st.session_state["_last_eq_param"] = eq_param

render_topbar(st.session_state["page"])
active = render_sidebar(st.session_state["page"])

PAGE_RENDERERS = {
    "dashboard": dashboard.render,
    "equipment": equipment_inventory.render,
    "inspection": inspection_form.render,
    "tasks": inspection_tasks.render,
    "deficiencies": deficiency_manager.render,
    "reports": report_center.render,
    "floor_map": floor_map.render,
    "field": field_mobile.render,
}

PAGE_RENDERERS.get(active, dashboard.render)()
