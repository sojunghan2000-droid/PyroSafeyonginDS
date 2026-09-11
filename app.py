"""PyroSafe Inspection Management — 용인덕성 AI DC.

Streamlit 진입점. 사이드바에서 페이지를 전환한다.
"""
from __future__ import annotations

import streamlit as st

from lib import auth
from lib.ui import apply_theme, render_sidebar, render_topbar
from pages_app import (
    admin_center,
    dashboard,
    equipment_inventory,
    inspection_form,
    inspection_tasks,
    deficiency_manager,
    report_center,
    field_mobile,
    login,
    settings,
)

st.set_page_config(
    page_title="PyroSafe · 용인덕성 AI DC",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

PAGE_RENDERERS = {
    "dashboard": dashboard.render,
    "equipment": equipment_inventory.render,
    "inspection": inspection_form.render,
    "tasks": inspection_tasks.render,
    "deficiencies": deficiency_manager.render,
    "reports": report_center.render,
    "field": field_mobile.render,
    "settings": settings.render,
    "admin": admin_center.render,
}

# 로그인 게이트 — 미로그인 시 로그인 화면만 표시.
# v1.9(260907): 새로고침으로 session_state가 비었으면 브라우저 세션 쿠키로 우선 복구 시도.
# URL의 ?eq= (QR 딥링크)는 그대로 유지되므로 로그인 후 아래 분기에서 처리된다.
if not auth.current_user():
    # 방금 로그아웃한 경우, 쿠키를 지우기도 전에 복구해버리지 않도록 삭제부터 처리.
    if not auth.flush_pending_cookie_clear():
        auth.try_restore_session()
if not auth.current_user():
    login.render()
    st.stop()
# 로그인 콜백 직후의 st.rerun()과 경쟁하지 않는, 뒤따르는 재실행이 없는 지점에서 쿠키 동기화.
auth.sync_session_cookie()

qp = st.query_params

if "page" not in st.session_state:
    # v1.9(260909): 새로고침으로 session_state가 비었을 때, 직전에 보던 화면을
    # URL의 ?page= 로 복원 (QR 딥링크 ?eq= 와 같은 패턴). 값이 없거나 알 수 없는
    # 페이지면 기존처럼 대시보드로 시작.
    restored_page = qp.get("page")
    st.session_state["page"] = restored_page if restored_page in PAGE_RENDERERS else "dashboard"

# URL deep link: ?eq=EQ-0001 → 지적·오동작 관리 + 신규 점검 모달 자동 오픈
# eq 값이 바뀔 때마다 발동 (브라우저에서 다른 장비 QR 스캔 시도 가능)
eq_param = qp.get("eq")
if eq_param and st.session_state.get("_last_eq_param") != eq_param:
    st.session_state["page"] = "deficiencies"
    st.session_state["inspect_target"] = eq_param
    st.session_state["_open_inspect_dialog"] = True
    st.session_state["_last_eq_param"] = eq_param
    # v1.5+ QR 부착 워크플로 — 첫 스캔이 곧 "실제 부착 완료" 신호
    # PENDING 장비라면 ASSIGNED로 자동 전환 (이미 ASSIGNED면 no-op)
    from lib import data as _data
    try:
        if _data.mark_qr_assigned(eq_param):
            st.session_state["_qr_just_assigned"] = eq_param
    except Exception:
        # 잘못된 eq_param이거나 DB 에러여도 점검 흐름은 계속 진행
        pass


render_topbar(st.session_state["page"])
active = render_sidebar(st.session_state["page"])

# 현재 페이지를 주소창 ?page= 에 반영 — 새로고침해도 같은 화면으로 복원되도록.
if qp.get("page") != active:
    st.query_params["page"] = active

PAGE_RENDERERS.get(active, dashboard.render)()
