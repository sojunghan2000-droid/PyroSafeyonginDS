"""공통 UI 컴포넌트 + PyroSafe 테마 CSS."""
from __future__ import annotations

from datetime import date
import streamlit as st
import streamlit.components.v1 as components


def _toggle_body_class(class_name: str, on: bool) -> None:
    """parent document body에 클래스를 추가/제거. st.markdown은 <script>를 strip하므로 iframe 사용."""
    op = "add" if on else "remove"
    components.html(
        f"<script>window.parent.document.body.classList.{op}('{class_name}');</script>",
        height=0,
        width=0,
    )


THEME_CSS = """
<style>
    /* === Global === */
    html, body, [class*="css"] {
        font-family: 'Pretendard', 'Malgun Gothic', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .main .block-container {
        padding-top: calc(1.2rem + 64px);
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    /* Streamlit 기본 헤더 정리 */
    header[data-testid="stHeader"] { background: transparent; }
    div[data-testid="stToolbar"] { display: none; }

    /* === Top Header Bar === */
    .ps-topbar {
        position: fixed; top: 0; left: 0; right: 0;
        height: 64px;
        background: #FFFFFF;
        border-bottom: 1px solid #E2E8F0;
        display: flex; align-items: center;
        padding: 0 1.75rem;
        gap: 1.5rem;
        z-index: 9000;
    }
    .ps-topbar-brand {
        font-size: 1.2rem; font-weight: 700; color: #2563EB;
        letter-spacing: -0.01em;
        flex-shrink: 0;
    }
    .ps-topbar-spacer { flex: 1; }
    .ps-topbar-actions {
        display: flex; align-items: center; gap: 0.75rem;
        flex-shrink: 0;
        /* 아바타 팝오버(.st-key-avatar_menu) 자리 확보 */
        margin-right: 52px;
    }
    .ps-icon-btn {
        width: 38px; height: 38px;
        border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        color: #64748B;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
        position: relative;
    }
    .ps-icon-btn:hover { background: #F1F5F9; color: #0F172A; }
    .ps-icon-btn .ps-dot {
        position: absolute; top: 8px; right: 9px;
        width: 8px; height: 8px; border-radius: 50%;
        background: #EF4444; border: 2px solid #FFFFFF;
    }
    /* 아바타 메뉴 — st.popover를 상단바 우측에 고정 배치 */
    .st-key-avatar_menu {
        position: fixed; top: 12px; right: 1.75rem;
        z-index: 9001;
        width: 40px;
    }
    .st-key-avatar_menu button[data-testid="stPopoverButton"] {
        width: 40px; height: 40px; min-height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #60A5FA, #2563EB) !important;
        color: #FFFFFF !important;
        font-weight: 700; font-size: 0.9rem;
        border: 2px solid #FFFFFF !important;
        box-shadow: 0 0 0 1px #E2E8F0;
        padding: 0 !important;
        justify-content: center;
    }
    .st-key-avatar_menu button[data-testid="stPopoverButton"] svg,
    .st-key-avatar_menu button[data-testid="stPopoverButton"] [data-testid="stIconMaterial"] {
        display: none;
    }
    /* 사이드바를 topbar 아래로 밀어내기 */
    section[data-testid="stSidebar"] { margin-top: 64px; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }

    /* === Sidebar === */
    section[data-testid="stSidebar"] {
        background: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

    /* Streamlit 네이티브 사이드바 collapse 버튼/헤더 숨김 (자체 mini/expanded 토글 사용) */
    [data-testid="stSidebarCollapseButton"] { display: none !important; }
    [data-testid="stSidebarHeader"] { display: none !important; }

    /* === 자체 사이드바 토글 버튼 (mini ↔ expanded) === */
    .ps-sb-toggle button {
        background: transparent !important;
        border: none !important;
        color: #64748B !important;
        width: 100% !important;
        padding: 0.3rem 0.5rem !important;
        font-size: 1.05rem !important;
        text-align: right !important;
        justify-content: flex-end !important;
        margin-bottom: 0.4rem !important;
    }
    .ps-sb-toggle button:hover {
        color: #2563EB !important;
        background: #EFF6FF !important;
    }
    /* mini 모드일 때 사이드바 폭 축소 + 라벨 정렬 */
    body.ps-sidebar-mini section[data-testid="stSidebar"] {
        width: 80px !important;
        min-width: 80px !important;
        max-width: 80px !important;
    }
    body.ps-sidebar-mini section[data-testid="stSidebar"] .block-container {
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
    }
    body.ps-sidebar-mini section[data-testid="stSidebar"] button {
        padding-left: 0 !important;
        padding-right: 0 !important;
        text-align: center !important;
        justify-content: center !important;
        font-size: 0.95rem !important;
    }
    body.ps-sidebar-mini .ps-sb-toggle button {
        justify-content: center !important;
    }
    /* mini 모드: 브랜드/부제는 visibility:hidden으로 자리만 유지 (버튼 Y좌표 일치).
       narrow sidebar에서 text-wrap으로 높이가 커지지 않도록 nowrap + overflow:hidden. */
    body.ps-sidebar-mini .ps-sb-brand,
    body.ps-sidebar-mini .ps-sb-sub {
        visibility: hidden !important;
        white-space: nowrap !important;
        overflow: hidden !important;
    }
    body.ps-sidebar-mini .ps-sb-foot {
        display: none !important;
    }
    .sidebar-brand {
        font-size: 1.25rem; font-weight: 700;
        color: #2563EB; line-height: 1.2;
        margin-bottom: 0.2rem;
    }
    .sidebar-sub { color: #64748B; font-size: 0.85rem; margin-bottom: 1.5rem; }
    .sidebar-nav-item {
        display: flex; align-items: center; gap: 0.6rem;
        padding: 0.55rem 0.85rem;
        border-radius: 8px;
        color: #334155; font-size: 0.92rem; font-weight: 500;
        margin-bottom: 0.18rem;
        cursor: pointer;
        text-decoration: none;
    }
    .sidebar-nav-item:hover { background: #E2E8F0; }
    .sidebar-nav-item.active { background: #DBEAFE; color: #1D4ED8; font-weight: 600; }
    .sidebar-foot { color: #94A3B8; font-size: 0.78rem; margin-top: 2rem; }

    /* === Sidebar buttons (Streamlit native) === */
    section[data-testid="stSidebar"] button[kind="secondary"],
    section[data-testid="stSidebar"] button[kind="primary"] {
        width: 100%;
        justify-content: flex-start !important;
        background: transparent;
        color: #334155;
        border: none;
        padding: 0.55rem 0.85rem;
        font-size: 0.92rem;
        font-weight: 500;
        border-radius: 8px;
        text-align: left;
        margin-bottom: 0.18rem;
    }
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: #E2E8F0;
        color: #0F172A;
    }
    /* 버튼 내부 flex container 좌측 정렬
       Streamlit 최신 버전: button > div (flex, jc:center) > span > stMarkdownContainer > p */
    section[data-testid="stSidebar"] button > div {
        justify-content: flex-start !important;
        text-align: left !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {
        text-align: left !important;
    }
    /* mini 모드: 번호만 표시되므로 가운데 정렬로 덮어쓰기 */
    body.ps-sidebar-mini section[data-testid="stSidebar"] button > div {
        justify-content: center !important;
        text-align: center !important;
    }
    body.ps-sidebar-mini section[data-testid="stSidebar"] button p,
    body.ps-sidebar-mini section[data-testid="stSidebar"] button [data-testid="stMarkdownContainer"] {
        text-align: center !important;
    }
    /* 사이드바 «/» 토글 버튼은 우측 정렬 유지 — Streamlit이 st.button(key=) 마다
       부여하는 .st-key-{key} 클래스로 타겟 (ps-sb-toggle div는 sibling으로 흩어짐) */
    section[data-testid="stSidebar"] .st-key-sb_toggle button > div {
        justify-content: flex-end !important;
        text-align: right !important;
    }
    section[data-testid="stSidebar"] .st-key-sb_toggle button p,
    section[data-testid="stSidebar"] .st-key-sb_toggle button [data-testid="stMarkdownContainer"] {
        text-align: right !important;
    }
    body.ps-sidebar-mini section[data-testid="stSidebar"] .st-key-sb_toggle button > div {
        justify-content: center !important;
        text-align: center !important;
    }
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: #DBEAFE !important;
        color: #1D4ED8 !important;
        font-weight: 600;
    }

    /* === Page header === */
    .page-title {
        font-size: 1.85rem; font-weight: 700; color: #0F172A;
        margin: 0 0 0.25rem 0;
    }
    .page-sub { color: #64748B; font-size: 0.95rem; margin-bottom: 1.25rem; }

    /* === KPI cards === */
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1.1rem 1.25rem;
        height: 100%;
    }
    .kpi-card.alert { background: #FEF2F2; border-color: #FCA5A5; }
    .kpi-card.primary { background: #2563EB; border-color: #2563EB; }
    .kpi-card.primary .kpi-label, .kpi-card.primary .kpi-value, .kpi-card.primary .kpi-hint {
        color: #FFFFFF;
    }
    .kpi-label {
        font-size: 0.78rem; color: #64748B;
        text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600;
        margin-bottom: 0.45rem;
    }
    .kpi-card.alert .kpi-label { color: #B91C1C; }
    .kpi-value {
        font-size: 2.2rem; font-weight: 700; color: #0F172A; line-height: 1.1;
    }
    .kpi-card.alert .kpi-value { color: #DC2626; }
    .kpi-hint { font-size: 0.82rem; color: #64748B; margin-top: 0.4rem; }
    .kpi-trend-up { color: #16A34A; font-weight: 600; }

    /* === Status badges === */
    .badge {
        display: inline-flex; align-items: center;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem; font-weight: 600;
        letter-spacing: 0.02em;
    }
    .badge-pass    { background: #DCFCE7; color: #15803D; }
    .badge-fail    { background: #FEE2E2; color: #B91C1C; }
    .badge-due     { background: #DBEAFE; color: #1D4ED8; }
    .badge-assigned{ background: #DCFCE7; color: #15803D; }
    .badge-pending { background: #FEF3C7; color: #B45309; }
    .badge-scheduled { background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; }
    .badge-progress  { background: #E0E7FF; color: #4338CA; }
    .badge-overdue   { background: #FEE2E2; color: #B91C1C; }
    .badge-completed { background: #DCFCE7; color: #15803D; }

    /* === Data table === */
    .ps-table {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        margin-top: 1rem;
    }

    /* === Mobile container === */
    .mobile-frame {
        max-width: 430px;
        margin: 0 auto;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 24px;
        padding: 1.25rem 1.1rem 5.5rem;
        min-height: 720px;
        position: relative;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.08);
    }
    .mobile-header {
        font-size: 1.05rem; font-weight: 700; color: #2563EB;
        margin-bottom: 1rem;
    }
    .mobile-title { font-size: 1.65rem; font-weight: 700; color: #0F172A; }
    .mobile-sub { color: #64748B; font-size: 0.9rem; margin-bottom: 1rem; }
    .mobile-cta {
        background: #EFF6FF;
        border: 1px solid #BFDBFE;
        border-radius: 12px;
        padding: 0.95rem 1rem;
        display: flex; justify-content: space-between; align-items: center;
        margin: 0.7rem 0 1.2rem;
    }
    .mobile-cta .cta-icon {
        width: 38px; height: 38px; border-radius: 10px;
        background: #2563EB; color: #FFFFFF;
        display: inline-flex; align-items: center; justify-content: center;
        font-size: 1.4rem; font-weight: 700;
    }
    .mobile-cta .cta-title { font-weight: 700; color: #0F172A; font-size: 1rem; }
    .mobile-cta .cta-sub { color: #64748B; font-size: 0.82rem; }
    .upcoming-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 0.85rem 0.95rem;
        margin-bottom: 0.6rem;
        display: flex; gap: 0.75rem; align-items: center;
    }
    .upcoming-icon {
        width: 38px; height: 38px; border-radius: 10px;
        background: #EFF6FF; color: #2563EB;
        display: inline-flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 1.05rem;
        flex-shrink: 0;
    }
    .upcoming-title { font-weight: 700; color: #0F172A; font-size: 0.95rem; }
    .upcoming-due { color: #64748B; font-size: 0.8rem; }
    .mobile-bottom-nav {
        position: sticky; bottom: 0;
        background: #FFFFFF; border-top: 1px solid #E2E8F0;
        padding: 0.6rem 0;
        display: grid; grid-template-columns: repeat(4, 1fr);
        text-align: center;
        margin: 1rem -1.1rem -5.5rem;
        border-radius: 0 0 24px 24px;
    }
    .mobile-bottom-nav .nav-item {
        color: #64748B; font-size: 0.78rem; padding: 0.4rem 0;
    }
    .mobile-bottom-nav .nav-item.active {
        color: #FFFFFF; background: #2563EB;
        border-radius: 10px; margin: 0 0.5rem; font-weight: 600;
    }

    /* === Buttons === */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #2563EB;
        border: 1px solid #2563EB;
        color: #FFFFFF;
        border-radius: 10px;
        font-weight: 600;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: #1D4ED8;
        border-color: #1D4ED8;
    }

    /* === Section divider === */
    hr.section-divider {
        border: none; border-top: 1px solid #E2E8F0; margin: 1.2rem 0;
    }
</style>
"""


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_topbar(active_page: str = "dashboard") -> None:
    html = """
<div class="ps-topbar">
    <div class="ps-topbar-brand">Samsung C&amp;T</div>
    <div class="ps-topbar-spacer"></div>
    <div class="ps-topbar-actions">
        <div class="ps-icon-btn" title="Notifications">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
            <span class="ps-dot"></span>
        </div>
        <div class="ps-icon-btn" title="Help">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
        </div>
    </div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    _render_avatar_menu()


def _render_avatar_menu() -> None:
    """상단바 우측 아바타 — 클릭 시 계정 메뉴 팝오버.

    상단바는 정적 HTML이라 그 안에 Streamlit 위젯을 둘 수 없으므로,
    팝오버를 본문에 렌더한 뒤 CSS(position: fixed)로 아바타 자리에 올린다.
    """
    from lib import auth

    user = auth.current_user()
    if not user:
        return
    with st.container(key="avatar_menu"):
        with st.popover(auth.avatar_initials()):
            role_label = "관리자" if user["role"] == "admin" else "일반 사용자"
            st.markdown(
                f"<div style='font-weight:700; color:#0F172A;'>{user['name']}</div>"
                f"<div style='color:#64748B; font-size:0.82rem; margin-bottom:0.6rem;'>"
                f"{user['username']} · {role_label}</div>",
                unsafe_allow_html=True,
            )
            if st.button("개인정보 변경", key="menu_profile", use_container_width=True):
                st.session_state["page"] = "settings"
                st.session_state["settings_tab"] = "profile"
                st.rerun()
            if auth.is_admin():
                if st.button("사용자 관리", key="menu_admin", use_container_width=True):
                    st.session_state["page"] = "settings"
                    st.session_state["settings_tab"] = "admin"
                    st.rerun()
            if st.button("로그아웃", key="menu_logout", use_container_width=True):
                auth.sign_out()
                st.rerun()


# ---------- Sidebar ----------

NAV_PAGES = [
    ("dashboard", "대시보드"),
    ("equipment", "시설 관리"),
    ("tasks", "점검 일정"),
    ("deficiencies", "지적·오동작 관리"),
    ("reports", "보고서"),
]

# 관리자 전용 메뉴 (auth.is_admin() == True 인 사용자에게만 노출)
NAV_PAGES_ADMIN = [
    ("admin", "관리자 메뉴"),
]


def render_sidebar(active: str) -> str:
    """사이드바를 렌더하고 사용자가 선택한 페이지 key를 반환.

    sidebar_mode 세션 상태("expanded" | "mini")에 따라
    풀 라벨 / 번호만 모드를 전환한다.
    """
    mode = st.session_state.get("sidebar_mode", "expanded")
    mini = mode == "mini"

    # body 클래스를 동기화해서 CSS가 mini 폭 적용
    _toggle_body_class("ps-sidebar-mini", mini)

    with st.sidebar:
        # 토글 버튼 (« 또는 »)
        toggle_icon = "»" if mini else "«"
        st.markdown('<div class="ps-sb-toggle">', unsafe_allow_html=True)
        if st.button(toggle_icon, key="sb_toggle", use_container_width=True):
            st.session_state["sidebar_mode"] = "expanded" if mini else "mini"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        # 브랜드 + 부제 (mini 모드에선 CSS로 숨김)
        st.markdown(
            """
            <div class="ps-sb-brand" style="font-size:1.25rem; font-weight:700; color:#2563EB; line-height:1.2; margin-bottom:0.2rem;">PyroSafe</div>
            <div class="ps-sb-sub" style="color:#64748B; font-size:0.85rem; margin-bottom:1.25rem;">용인덕성 AI DC</div>
            """,
            unsafe_allow_html=True,
        )

        # 번호 prefix nav
        selected = active
        for idx, (key, label) in enumerate(NAV_PAGES, start=1):
            btn_label = f"{idx}." if mini else f"{idx}. {label}"
            is_active = key == active
            btn_type = "primary" if is_active else "secondary"
            if st.button(btn_label, key=f"nav_{key}", type=btn_type, use_container_width=True):
                selected = key

        # 관리자 전용 메뉴 — is_admin() 사용자에게만 노출
        try:
            from lib import auth  # 순환 참조 회피: 함수 안에서 import
            show_admin = auth.is_admin()
        except Exception:
            show_admin = False
        if show_admin:
            st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
            for idx, (key, label) in enumerate(NAV_PAGES_ADMIN, start=1):
                btn_label = "A." if mini else f"A. {label}"
                is_active = key == active
                btn_type = "primary" if is_active else "secondary"
                if st.button(btn_label, key=f"nav_{key}",
                             type=btn_type, use_container_width=True):
                    selected = key

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="ps-sb-foot sidebar-foot">
                Settings · Support<br>
                v0.1 · 2026-05-27
            </div>
            """,
            unsafe_allow_html=True,
        )
    if selected != active:
        st.session_state["page"] = selected
        st.rerun()
    return selected


# ---------- KPI cards ----------

def kpi_card(label: str, value: str, hint: str = "", variant: str = "default") -> str:
    variant_class = {"alert": " alert", "primary": " primary"}.get(variant, "")
    hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
    return (
        f'<div class="kpi-card{variant_class}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'{hint_html}'
        f'</div>'
    )


def render_kpi_row(cards: list[tuple[str, str, str, str]]) -> None:
    """cards: list of (label, value, hint, variant)"""
    cols = st.columns(len(cards))
    for col, (label, value, hint, variant) in zip(cols, cards):
        with col:
            st.markdown(kpi_card(label, value, hint, variant), unsafe_allow_html=True)


# ---------- Badges ----------

BADGE_CLASS = {
    "PASS": "badge-pass",
    "FAIL": "badge-fail",
    "DUE": "badge-due",
    "ASSIGNED": "badge-assigned",
    "PENDING": "badge-pending",
    "Scheduled": "badge-scheduled",
    "In Progress": "badge-progress",
    "Overdue": "badge-overdue",
    "Completed": "badge-completed",
    "예정": "badge-scheduled",
    "진행 중": "badge-progress",
    "지연": "badge-overdue",
    "작업 완료": "badge-completed",
    "완료": "badge-pass",
    "불가": "badge-fail",
}

# 점검 작업 상태 영문 → 한글 표시 매핑 (data 모델의 값은 영문 그대로 유지)
TASK_STATUS_KO = {
    "Scheduled": "예정",
    "In Progress": "진행 중",
    "Overdue": "지연",
    "Completed": "작업 완료",
}


def badge(text: str) -> str:
    cls = BADGE_CLASS.get(text, "badge-scheduled")
    return f'<span class="badge {cls}">{text}</span>'


# ---------- Page header ----------

def page_header(title: str, sub: str = "", actions: list | None = None) -> None:
    """제목 + 부제목 + 우측 액션 버튼(Streamlit 버튼 리스트는 호출자가 별도 col에 배치)."""
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    if sub:
        st.markdown(f'<div class="page-sub">{sub}</div>', unsafe_allow_html=True)


def fmt_date(d: date | None) -> str:
    """ISO 8601 (YYYY-MM-DD)."""
    if d is None:
        return "-"
    return d.strftime("%Y-%m-%d")
