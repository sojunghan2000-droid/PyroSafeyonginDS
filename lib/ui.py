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
    /* Streamlit 기본 헤더 완전 숨김 — Deploy 버튼·메뉴(⋮)는 커스텀 상단바와 중첩되므로 제거.
       배포는 git push 기반이라 Deploy 버튼이 사라져도 무방 (PRD_상단바 R2). */
    header[data-testid="stHeader"] { display: none !important; }
    div[data-testid="stToolbar"] { display: none !important; }

    /* Streamlit element의 "View fullscreen" (브라우저 전체화면) 버튼 숨김.
       도면 컨텍스트 손실 + Plotly Home 아이콘이 더 적합한 '전체 보기' 역할.
       (PRD R12 도면 UX) */
    button[title="View fullscreen"],
    button[title="Exit fullscreen"],
    button[kind="elementToolbarButton"][aria-label*="fullscreen" i] {
        display: none !important;
    }
    div[data-testid="stElementToolbar"] { display: none !important; }

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
    .ps-icon-btn a { color: inherit; display: inline-flex;
                     align-items: center; justify-content: center;
                     width: 100%; height: 100%; }
    .ps-icon-btn .ps-dot {
        position: absolute; top: 8px; right: 9px;
        width: 8px; height: 8px; border-radius: 50%;
        background: #EF4444; border: 2px solid #FFFFFF;
    }
    .ps-icon-btn .ps-badge {
        position: absolute; top: 2px; right: 0;
        min-width: 18px; height: 18px;
        padding: 0 5px;
        border-radius: 9px;
        background: #DC2626; color: #FFFFFF;
        font-size: 0.68rem; font-weight: 700;
        display: inline-flex; align-items: center; justify-content: center;
        border: 2px solid #FFFFFF;
        line-height: 1;
    }

    /* 상단바 알림 벨 — 가장 왼쪽 (도움말 ↔ 알림 위치 교환, 폭 차이 보정으로 right 9.5rem) */
    .st-key-notify_btn {
        position: fixed; top: 13px; right: 9.5rem;
        z-index: 9001;
        width: 52px;
    }
    .st-key-notify_btn button {
        width: 52px; height: 38px; min-height: 38px;
        border-radius: 999px !important;
        background: transparent !important;
        border: none !important;
        color: #64748B !important;
        padding: 0 0.5rem !important;
        font-size: 0.85rem !important;
        font-weight: 700 !important;
        line-height: 1 !important;
    }
    .st-key-notify_btn button:hover {
        background: #F1F5F9 !important;
        color: #0F172A !important;
    }
    /* st.popover trigger의 chevron(expand_more) 숨김 — 알림 벨에는 불필요 */
    .st-key-notify_btn button div[aria-hidden="true"] {
        display: none !important;
    }
    /* 1+ 카운트 표시 시 빨강 강조 (body 클래스 기반 토글) */
    body.ps-has-alerts .st-key-notify_btn button {
        color: #DC2626 !important;
        font-weight: 700 !important;
    }

    /* 알림 popover 안 카드형 버튼 — 카드 전체가 클릭 영역.
       wrapper key 패턴 .st-key-notify_card_ 로 매칭. */
    [class*="st-key-notify_card_"] button {
        text-align: left !important;
        padding: 0.7rem 0.85rem !important;
        background: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        font-weight: 500 !important;
        height: auto !important;
        min-height: 0 !important;
        line-height: 1.45 !important;
    }
    [class*="st-key-notify_card_"] button > div {
        align-items: flex-start !important;
        justify-content: flex-start !important;
    }
    [class*="st-key-notify_card_"] button p {
        margin: 0 !important;
        text-align: left !important;
    }
    [class*="st-key-notify_card_"] button:hover {
        background: #F1F5F9 !important;
        border-color: #2563EB !important;
        cursor: pointer !important;
    }

    /* 상단바 도움말 버튼 — 알림 벨과 자리 교환 (가운데로 이동) */
    .st-key-help_btn {
        position: fixed; top: 13px; right: 5.5rem;
        z-index: 9001;
        width: 38px;
    }
    .st-key-help_btn button {
        width: 38px; height: 38px; min-height: 38px;
        border-radius: 50% !important;
        background: transparent !important;
        border: none !important;
        color: #64748B !important;
        padding: 0 !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        line-height: 1 !important;
    }
    .st-key-help_btn button:hover {
        background: #F1F5F9 !important;
        color: #0F172A !important;
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
    .st-key-avatar_menu button[data-testid="stPopoverButton"] [data-testid="stIconMaterial"],
    .st-key-avatar_menu button[data-testid="stPopoverButton"] div[aria-hidden="true"] {
        display: none !important;
    }
    /* 사이드바를 topbar 아래로 밀어내기 */
    section[data-testid="stSidebar"] { margin-top: 64px; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 0.5rem; }

    /* === Sidebar === */
    section[data-testid="stSidebar"] {
        background: #F8FAFC;
        border-right: 1px solid #E2E8F0;
    }
    /* PyroSafe 좌측을 상단바(.ps-topbar, left=28px)와 정확히 정렬.
       실측 결과 사이드바 실제 컨텐츠 래퍼는 stSidebarUserContent(기본 left=20px)이고
       .block-container는 사이드바에 존재하지 않음(그래서 이전 규칙은 무효였음).
       +8px 좌패딩으로 20 → 28px 맞춤. mini 모드는 제외(버튼 중앙정렬 유지). */
    body:not(.ps-sidebar-mini) section[data-testid="stSidebar"]
        [data-testid="stSidebarUserContent"] {
        padding-left: 8px !important;
    }

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

    /* KPI 한 줄 가로 슬라이드 — 모바일에서 카드가 wrap 되지 않고 좌우 스크롤 */
    .kpi-row-scroll {
        display: flex;
        flex-wrap: nowrap;
        gap: 0.6rem;
        overflow-x: auto;
        padding: 0 0.1rem 0.5rem;
        scroll-snap-type: x mandatory;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: thin;
    }
    .kpi-row-scroll .kpi-card {
        flex: 1 0 0;
        min-width: 160px;
        scroll-snap-align: start;
    }
    @media (max-width: 768px) {
        .kpi-row-scroll .kpi-card {
            flex: 0 0 75%;
        }
    }

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


def _notify_count() -> tuple[int, int, int]:
    """알림 카운트 = (조치 대기 통보서, 지연 태스크, 마감 임박 회차).
    마감 임박 = 오늘부터 3일 이내 + 미완료. 데이터 로드 실패 시 (0,0,0)."""
    try:
        from datetime import timedelta
        from lib import data
        pending = sum(1 for n in data.load_notices() if not n.action_done)
        overdue = sum(1 for t in data.load_tasks() if t.status == "Overdue")
        today = data.TODAY
        deadline = today + timedelta(days=3)
        soon = sum(
            1 for r in data.load_rounds()
            if r.status != "Completed"
            and r.due_date is not None
            and today <= r.due_date <= deadline
        )
        return pending, overdue, soon
    except Exception:
        return 0, 0, 0


def render_topbar(_active_page: str | None = None) -> None:
    """전역 상단바 렌더. 인자는 하위 호환용으로만 받고 사용하지 않는다 (PRD R6)."""
    html = """
<div class="ps-topbar">
    <div class="ps-topbar-brand">Samsung C&amp;T</div>
    <div class="ps-topbar-spacer"></div>
</div>
"""
    st.markdown(html, unsafe_allow_html=True)
    _render_help_button()
    _render_notify_button()
    _render_avatar_menu()


# ---- FAQ 콘텐츠 ----
_HELP_FAQ = [
    ("알림 벨의 숫자는 무엇인가요?",
     "조치 대기 지적사항 + 지연 태스크 + 마감 임박 회차의 합입니다. 클릭하면 popover에서 "
     "각 항목 카드를 보고 클릭으로 해당 페이지(작업 조치 관리 또는 안전점검 관리)로 이동합니다."),
    ("점검은 어떻게 시작하나요? (v1.5+)",
     "(1) **🔍 안전점검 관리** → 회차 행 **[점검]** 클릭 → 회차 상세 모달.\n"
     "(2) 각 Task 행의 **[점검 시작 →]** 버튼 클릭 → **행 아래 인라인 입력 영역**이 펼쳐집니다 "
     "(모달 안 모달이 아닌, 같은 모달에서 인라인).\n"
     "(3) 점검 종류 / 양호·불량·오동작 / 지적사항 / 즉시 조치 입력 → [점검 결과 제출].\n"
     "(4) QR 진입: 대시보드 [📷 점검 (QR 스캔)] 또는 장비 부착 QR 스티커 카메라 스캔."),
    ("점검 결과는 어떻게 선택하나요? (v1.6)",
     "**양호 / 불량 / 오동작** 3가지 중 1개 선택.\n"
     "(1) **양호** — Deficiency 1행 (양호)로 별지5 기록\n"
     "(2) **불량** — 지적사항 + 통보서 자동 발급, 별지5/6 기록. 현장 즉시 조치 가능\n"
     "(3) **오동작** — 시설 자체 오작동, **별지9** 기록. 조치는 [작업 조치 관리]에서 별도 시점에\n"
     "※ **불량 시 조치 사진 첨부 필수 (v1.6)** — 미첨부 시 저장 차단."),
    ("오동작은 어떻게 등록·조치하나요? (v1.5+)",
     "(1) **등록 2가지 경로**:\n"
     "  · 점검 중 발견: 점검 시작 인라인 입력에서 결과 = '오동작' 선택\n"
     "  · 점검 외 발견: **🔍 안전점검 관리** 우상단 **[오동작 등록]** 버튼\n"
     "(2) **조치**: **🛠️ 작업 조치 관리** 통합 리스트의 오동작 행 (조치 대기) → **[조치 입력 →]**"),
    ("화기작업구간 점검은 어떻게 진행하나요? (v1.7)",
     "**6단계 흐름** (일일/수시):\n"
     "(1) **🔍 안전점검 관리** → **[+ 신규 점검 회차]** → 점검 주기 **'일일 점검'** 선택 → "
     "자유 등록 모드 자동 활성화(체크 해제 가능) → 저장\n"
     "(2) 회차 **[점검]** → **[+ Task 추가]** → **📍 신규 위치 점검** 탭 → **🆕 신규 위치 추가** 토글 ON → "
     "도면에서 작업 구간 클릭 + 위치 설명(예: SEC1 용접) 입력 후 등록 "
     "(업체명은 메모 또는 위치 설명에 함께 기재)\n"
     "(3) Task 행 **[점검 시작 →]** → 점검 종류에서 **'화기작업구간 점검'** 선택\n"
     "(4) **세부 checklist 12개 라디오 입력 (v1.7)** — 4 카테고리(방화포/소화기/화재감시자/가연물) × "
     "3항목을 각각 **OK / NG / N/A** 로 표기. NG가 하나라도 있으면 결과가 자동 '불량'으로 강제됨 "
     "(양호 저장 차단)\n"
     "(5) **불량 시** — 사유 multiselect (6종: 방화포 미비치/파손, 소화기 부족·충전·고장, "
     "화재감시자 부재·불안전 행동, 가연물 정리정돈 미흡, 주변 간섭사항 존재, 기타) 선택. "
     "'기타' 선택 시 상세 텍스트 필수\n"
     "(6) **조치 사진 첨부 필수** → 저장. NG 항목 요약이 **별지5 PDF에 자동 포함**"),
    ("가설컨테이너 사무실 점검은? (v1.7)",
     "**월간 점검 회차에 포함**. 위치 마스터 spot 기반.\n"
     "(1) 월간 회차 [점검] → 해당 Task [점검 시작 →] → 점검 종류 = **'가설컨테이너 사무실 점검'** 선택\n"
     "(2) **세부 checklist 7개 라디오 입력 (v1.7)** — 소화기·환기팬·차단기·감지기·접지·쓰레기통·"
     "**일일점검체크리스트 작성** 7항목을 각각 **OK / NG / N/A** 로 표기. NG가 하나라도 있으면 "
     "결과가 자동 '불량'으로 강제됨 (양호 저장 차단)\n"
     "(3) **불량 시** — 사유 multiselect (7종: 소화기 비치·점검 불량, 환기팬 설치·작동, "
     "외부 차단기·시건, 감지기 작동, 접지, 철제쓰레기통 미사용·인화성물질 보관, 기타) 선택. "
     "'기타' 선택 시 상세 텍스트 필수\n"
     "(4) **조치 사진 첨부 필수** → 저장. NG 항목 요약이 **별지5 PDF에 자동 포함**"),
    ("화기작업/가설컨테이너 점검의 세부 checklist가 뭔가요? (v1.7)",
     "점검 종류를 **'화기작업구간 점검'** 또는 **'가설컨테이너 사무실 점검'** 으로 선택하면 "
     "**상세 항목이 자동으로 라디오(OK/NG/N/A)** 로 나타납니다.\n"
     "(1) **화기작업구간** — 4 카테고리(방화포/소화기/화재감시자/가연물) × 3항목 = **12개**\n"
     "(2) **가설컨테이너 사무실** — 소화기·환기팬·차단기·감지기·접지·쓰레기통·일일점검체크리스트 "
     "작성 = **7개**\n"
     "(3) **NG가 하나라도 있으면** — 결과가 자동으로 **'불량'** 힌트 표시, 그 상태에서 결과 "
     "'양호'로 저장을 시도하면 **차단**됩니다.\n"
     "(4) NG로 표시된 항목 요약이 **별지5 PDF에 자동 포함**되어 감사 근거로 남습니다."),
    ("양호인데 세부 항목이 다 필요한가요? (v1.7)",
     "네, **양호로 저장하는 경우에도** 각 항목의 O/X(OK/NG/N/A) 근거를 남겨야 합니다.\n"
     "(1) **감사 근거** — 어떤 항목을 확인했는지가 로그와 별지5 PDF에 반영됩니다.\n"
     "(2) **해당 없음은 N/A** — 이번 점검 대상에 해당하지 않는 항목은 **N/A**로 표시하면 "
     "불량 판정에 영향을 주지 않습니다.\n"
     "(3) **OK/N/A만 있으면** 결과 '양호' 저장이 가능하고, **NG가 하나라도 있으면** 자동 "
     "'불량'으로 강제됩니다."),
    ("불량 사유 카탈로그는 어디서 관리되나요? (v1.6)",
     "**점검 종류별 시스템 내장 카탈로그** — 사용자가 별도 정의할 필요 없음.\n"
     "(1) **화기작업구간 점검** — 6종 사유 (방화포·소화기·감시자·가연물·간섭·기타)\n"
     "(2) **가설컨테이너 사무실 점검** — 7종 사유 (소화기·환기팬·차단기·감지기·접지·쓰레기통·기타)\n"
     "(3) **multiselect 입력**으로 복수 선택 가능 → 사유별 통계·집계 가능\n"
     "(4) **'기타' 선택 시 상세 텍스트 필수** (form validation)\n"
     "기타 점검 종류는 자유 텍스트 지적사항으로 입력."),
    ("도면에 없는 위치는 어떻게 등록하나요? (v1.5+)",
     "회차 [점검] → Task 추가 모달 → 📍 신규 위치 점검 탭 → 상단 **🆕 신규 위치 추가** 토글 ON → "
     "도면 빈 곳 클릭 → 좌표 픽업 + 위치 설명 입력 → [신규 위치 + Task 추가].\n"
     "관리자는 **⚙️ 위치 마스터 spot 목록의 [승인] 버튼**(임시 spot 행에만 노출, v1.7) → "
     "속성 변경 모달('정식 전환' 기본 체크)에서 방이름·좌표 확인·수정 후 저장으로 정식화."),
    ("점검 회차(Round)는 무엇인가요?",
     "v1.5부터 신규 일정 등록 시 1개 회차(점검 ID `INS-YYYYMMDD-NNN`) + Task N개가 한 번에 "
     "생성됩니다. 점검 주기 4종(주간/월간/분기/연간)은 시설 종류와 직교라 한 회차에 여러 시설 "
     "포함 가능. 회차 단위로 진행률·상태가 자동 집계되며, 회차 단위 별지5 PDF 출력 가능. "
     "**자유 점검**(대상 미선택)은 회차만 만들고 [+ Task 추가]로 동적 등록."),
    ("QR 코드는 어디서 발급하나요?",
     "🧯 시설 관리 → 각 장비 행의 **[속성]** 버튼 → 모달에서 QR PNG 다운로드 (장비 속성 + "
     "위치 변경 + QR 모두 한 모달). 여러 장비 일괄 출력은 상단 [QR 스티커 일괄 출력] (A4 4×6 시트)."),
    ("QR 발급·부착 절차는 어떻게 되나요? (v1.5+)",
     "**5단계 워크플로**:\n"
     "(1) **신규 등록** — 🧯 시설 관리 [+ 신규 장비 등록] → QR 상태 = **PENDING (부착 대기)**\n"
     "(2) **PDF 출력** — 📄 보고서 → QR 스티커 시트 PDF (A4 4×6 = 24매/장) 또는 행 [속성] 모달에서 개별 PNG\n"
     "(3) **인쇄** — 자체 프린터 또는 인쇄소\n"
     "(4) **현장 부착** — 장비에 스티커 부착\n"
     "(5) **첫 스캔** — 모바일 카메라로 스캔하는 순간 자동으로 **PENDING → ASSIGNED** 전환.\n"
     "    \"실제로 부착됐고 누군가 읽었다\"는 신호로 시스템이 자동 인지.\n"
     "**QR 적용률 KPI**는 ASSIGNED 비율 — 발급률이 아닌 **실제 부착·검증률**을 의미."),
    ("QR 스캔했더니 '어느 회차 점검인가요?'가 떠요 (v1.7)",
     "스캔한 장비에 **진행 중(미완료) 점검 회차가 2건 이상**이면, 어느 회차의 점검인지 "
     "고르는 목록이 먼저 나타납니다.\n"
     "(1) **1건** — 자동으로 그 회차에 연결\n"
     "(2) **2건 이상** — 회차 ID·점검 종류·마감·상태 목록에서 선택 (또는 '회차 미연결(단독 기록)')\n"
     "(3) **0건** — 회차 없이 단독 점검 기록\n"
     "선택한 회차의 Task에 결과가 연결되어 진행률·별지5에 정확히 반영됩니다."),
    ("불량 점검 결과의 후속 조치는 어떻게 하나요?",
     "(1) 점검 입력에서 '현장에서 즉시 조치 완료'를 체크하면 즉시 별지5에 조치 단계까지 기록.\n"
     "(2) 미조치는 **🛠️ 작업 조치 관리** 페이지의 **[조치 입력 →]** 버튼으로 별도 시점에 "
     "조치 결과(내용/사진/확인자)를 입력."),
    ("PDF는 어디서 출력하나요?",
     "(1) **📄 보고서** → 별지5/6/9 전체 PDF.\n"
     "(2) 안전점검 관리 회차 [점검] 모달 → **[별지5 PDF (N건)]** — 그 회차만의 회차 단위 지적내역서.\n"
     "(별지5 지적사항 컬럼 형식: '장비명 (양호)' 또는 '장비명 (지적사항)')."),
    ("위치(spot)는 어떻게 정의하나요? (v1.7)",
     "**주 경로 — 시설 관리(장비 등록)**: 🧯 시설 관리 → [신규 장비 등록] → 위치 지정 "
     "**'신규 위치 만들기'** → 도면 빈 곳 클릭으로 좌표 픽업 + 위치 설명 입력 → 등록 시 spot이 함께 생성됩니다.\n"
     "**현장 경로 — 신규 위치 점검**: 점검 중 도면에 없는 위치는 '신규 위치 점검' 탭에서 신규 생성.\n"
     "**⚙️ 위치 마스터 = 관리·검증 전용**: 등록된 spot의 사용 여부 확인, 신규(임시) 위치 정식 전환("
     "임시 spot 행 **[승인]** 버튼 → 속성 변경 모달에서 확인·수정 후 저장, v1.7), "
     "[속성 변경]에서 도면 클릭으로 정밀 좌표 조정·삭제. (초기 세팅용 [+ 신규 위치] 버튼도 유지)"),
    ("장비 ID · spot ID · 위치는 어떻게 다른가요? (v1.7)",
     "**장비 ID(EQ-NNNN)** = 자산(장비) 고유번호. **spot ID(SPOT-층-NNN)** = 도면 위 위치의 "
     "마스터 키. 둘은 다른 개념입니다 (장비 = 물건 / spot = 자리).\n"
     "(1) **🧯 시설 관리** 표 첫 컬럼 = **장비 ID** (자산 대장이므로 장비 고유번호가 대표값)\n"
     "(2) **⚙️ 위치 마스터** spot 목록 = **spot ID**(위치 식별) + 그 자리에 배치된 **장비 ID**(없으면 -)\n"
     "(3) 위치의 짧은 표시(예: 1F-01)는 spot ID에서 파생된 별칭이며, 데이터 매칭·별지 서식은 "
     "내부적으로 이 위치값을 그대로 사용합니다."),
    ("음성 입력(STT)은 어떻게 사용하나요?",
     "모바일 키보드의 마이크 버튼을 누르면 음성→텍스트가 자동 변환됩니다. "
     "지적사항·조치 내용 입력란 어디서나 사용 가능합니다."),
    ("데이터가 자동 저장되나요?",
     "모든 입력은 Supabase에 즉시 저장됩니다. 조치 사진은 Storage 버킷(action-photos)에 "
     "영구 보관되어 새로고침·재로그인 후에도 그대로 유지됩니다."),
]


@st.dialog("도움말 — PyroSafe 사용 가이드", width="large")
def _help_dialog() -> None:
    st.markdown(
        "<div style='color:#64748B; font-size:0.88rem; margin-bottom:0.6rem;'>"
        "자주 묻는 질문 18개. 추가 안내는 안전 관리자에게 문의하세요."
        "</div>",
        unsafe_allow_html=True,
    )
    for q, a in _HELP_FAQ:
        with st.expander(q):
            st.markdown(a)


def _render_help_button() -> None:
    if st.button("?", key="help_btn", help="도움말 / FAQ"):
        _help_dialog()


def _render_notify_button() -> None:
    """상단바 알림 벨 — st.popover (아바타 메뉴와 동일 패턴).
    트리거: 카운트 표시 + 색 강조. 본문: 조치 대기 통보서 + 지연 태스크 리스트."""
    pending, overdue, soon = _notify_count()
    total = pending + overdue + soon
    if total == 0:
        label = "🔔"
        title = "알림 없음"
    else:
        label = f"🔔 {total if total <= 99 else '99+'}"
        title = (
            f"조치 대기 {pending}건 · 지연 태스크 {overdue}건 · "
            f"마감 임박 회차 {soon}건"
        )

    with st.container(key="notify_btn"):
        with st.popover(label, help=title, use_container_width=False):
            _notify_panel()

    # 카운트가 1+일 때만 빨강 강조 클래스 토글
    _toggle_body_class("ps-has-alerts", total > 0)


def _notify_panel() -> None:
    """알림 popover 내부 콘텐츠. 조치 대기 통보서 + 지연 태스크 + 마감 임박 회차.
    각 행 클릭 시 해당 페이지로 라우팅."""
    from datetime import timedelta
    from lib import data
    notices = [n for n in data.load_notices() if not n.action_done]
    tasks = [t for t in data.load_tasks() if t.status == "Overdue"]
    today = data.TODAY
    deadline = today + timedelta(days=3)
    rounds_soon = [
        r for r in data.load_rounds()
        if r.status != "Completed"
        and r.due_date is not None
        and today <= r.due_date <= deadline
    ]
    rounds_soon.sort(key=lambda r: r.due_date)
    total = len(notices) + len(tasks) + len(rounds_soon)

    # popover 내부 최소 폭 보장 — 트리거(40px) 기준으로 너무 좁아지지 않도록
    st.markdown(
        f"<div style='min-width:380px; max-width:480px;'>"
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem;'>알림</div>"
        f"<div style='color:#64748B; font-size:0.82rem; margin-bottom:0.6rem;'>"
        f"총 {total}건 · 통보서 {len(notices)} · 지연 태스크 {len(tasks)} · "
        f"마감 임박 {len(rounds_soon)}"
        f"</div></div>",
        unsafe_allow_html=True,
    )
    if total == 0:
        st.info("현재 알림이 없습니다.")
        return

    # ─ 조치 대기 통보서 ─ (카드 전체가 클릭 영역)
    if notices:
        st.markdown(
            "<div style='font-weight:600; color:#0F172A; font-size:0.88rem; "
            "margin:0.2rem 0 0.3rem;'>조치 대기 통보서</div>",
            unsafe_allow_html=True,
        )
        for n in notices:
            label = (
                f"**{n.notice_no} · {n.floor}/{n.zone} · {n.inspection_type}**  \n"
                f"{n.issue}  \n"
                f":gray[제출자 {n.submitter} · 확인자 {n.confirmer} · "
                f"발급일 {fmt_date(n.inspection_date)}]"
            )
            with st.container(key=f"notify_card_n_{n.notice_no}"):
                if st.button(label,
                             key=f"notify_btn_n_{n.notice_no}",
                             use_container_width=True):
                    st.session_state["page"] = "deficiencies"
                    st.session_state["unified_type"] = "조치 대기만"
                    st.session_state["focus_notice"] = n.notice_no
                    st.rerun()

    # ─ 지연 태스크 ─ (카드 전체가 클릭 영역)
    if tasks:
        st.markdown(
            "<div style='font-weight:600; color:#0F172A; font-size:0.88rem; "
            "margin:0.5rem 0 0.3rem;'>지연 태스크</div>",
            unsafe_allow_html=True,
        )
        for t in tasks:
            today = data.TODAY
            try:
                delta = (today - t.due_date).days
            except Exception:
                delta = None
            delay_txt = (
                f" :red[**(-{delta}일 지연)**]" if delta and delta > 0 else ""
            )
            label = (
                f"**{t.task_id} · {t.equipment_label}**  \n"
                f"{t.task_type}  \n"
                f":gray[담당 {t.assignee or '미지정'} · 마감 "
                f"{fmt_date(t.due_date)}]{delay_txt}"
            )
            with st.container(key=f"notify_card_t_{t.task_id}"):
                if st.button(label,
                             key=f"notify_btn_t_{t.task_id}",
                             use_container_width=True):
                    st.session_state["page"] = "tasks"
                    st.session_state["tasks_view"] = "지연"
                    st.session_state["focus_task"] = t.task_id
                    st.rerun()

    # ─ 마감 임박 회차 (3일 이내) ─
    if rounds_soon:
        st.markdown(
            "<div style='font-weight:600; color:#0F172A; font-size:0.88rem; "
            "margin:0.5rem 0 0.3rem;'>마감 임박 회차 (3일 이내)</div>",
            unsafe_allow_html=True,
        )
        for r in rounds_soon:
            days = (r.due_date - today).days
            day_txt = "오늘 마감" if days == 0 else f"{days}일 남음"
            day_color = ":red" if days <= 1 else ":orange"
            done, total = data.round_progress(r.round_id)
            label = (
                f"**{r.round_id} · {r.task_type}**  \n"
                f"진행 {done}/{total} · "
                f":gray[담당 {r.assignee or '미지정'} · 마감 "
                f"{fmt_date(r.due_date)}] {day_color}[**{day_txt}**]"
            )
            with st.container(key=f"notify_card_r_{r.round_id}"):
                if st.button(label,
                             key=f"notify_btn_r_{r.round_id}",
                             use_container_width=True):
                    st.session_state["page"] = "tasks"
                    st.session_state["focus_round"] = r.round_id
                    st.rerun()


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
                    st.session_state["page"] = "admin"
                    st.session_state["admin_tab"] = "사용자 관리"
                    st.rerun()
            if st.button("로그아웃", key="menu_logout", use_container_width=True):
                auth.sign_out()
                st.rerun()


# ---------- Sidebar ----------

NAV_PAGES = [
    ("dashboard", "대시보드", "🏠"),
    ("equipment", "시설 관리", "🧯"),
    ("tasks", "안전점검 관리", "🔍"),
    ("deficiencies", "작업 조치 관리", "🛠️"),
    ("reports", "보고서", "📄"),
]

# 관리자 전용 메뉴 (auth.is_admin() == True 인 사용자에게만 노출).
# (page_key, admin_tab_label) — admin_tab 은 admin_center 의 라디오 섹션과 매칭.
NAV_ADMIN_HEADER = ("admin", "관리자 메뉴")
NAV_ADMIN_SUB = [
    ("admin", "위치 마스터"),
    ("admin", "사용자 관리"),
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
        toggle_icon = "»" if mini else "«"

        if mini:
            # 미니 모드: 토글(»)만 (브랜드 숨김) — 80px 폭이라 컬럼 미사용
            st.markdown('<div class="ps-sb-toggle">', unsafe_allow_html=True)
            if st.button(toggle_icon, key="sb_toggle", use_container_width=True):
                st.session_state["sidebar_mode"] = "expanded"
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            # 확장 모드: 브랜드(좌) + « 토글(우)을 같은 줄에 배치.
            # vertical_alignment=center 로 브랜드 2줄 블록 세로 중앙에 «를 맞춰 상하 균형
            bcol, tcol = st.columns([1, 0.34], vertical_alignment="center")
            with bcol:
                st.markdown(
                    """
                    <div class="ps-sb-brand" style="font-size:1.25rem; font-weight:700; color:#2563EB; line-height:1.2; margin-bottom:0.2rem;">PyroSafe</div>
                    <div class="ps-sb-sub" style="color:#64748B; font-size:0.85rem;">용인덕성 AI DC</div>
                    """,
                    unsafe_allow_html=True,
                )
            with tcol:
                st.markdown('<div class="ps-sb-toggle">', unsafe_allow_html=True)
                if st.button(toggle_icon, key="sb_toggle", use_container_width=True):
                    st.session_state["sidebar_mode"] = "mini"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            # 브랜드 줄과 네비게이션 사이 여백
            st.markdown("<div style='height:0.9rem;'></div>", unsafe_allow_html=True)

        # 이모지 prefix nav (mini 모드에선 이모지만)
        selected = active
        for key, label, emoji in NAV_PAGES:
            btn_label = emoji if mini else f"{emoji} {label}"
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
            header_key, header_label = NAV_ADMIN_HEADER
            is_active_header = header_key == active
            header_btn_label = "⚙️" if mini else f"⚙️ {header_label}"
            if st.button(
                header_btn_label,
                key="nav_admin_header",
                type="primary" if is_active_header else "secondary",
                use_container_width=True,
            ):
                selected = header_key
            # 하위 탭(위치 마스터 / 사용자 관리) 전환은 본문 라디오 + 아바타 popover로 일원화.

        st.markdown('<hr class="section-divider">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="ps-sb-foot sidebar-foot">
                Settings · Support<br>
                v1.5+ · 2026-06-23
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


def render_kpi_row(cards: list[tuple[str, str, str, str]],
                   scrollable: bool = False) -> None:
    """cards: list of (label, value, hint, variant).
    scrollable=True 면 flex nowrap + overflow-x auto 컨테이너로 렌더 (모바일 좌우 슬라이드)."""
    if scrollable:
        # st.columns 대신 단일 HTML 블록으로 출력해야 flex 컨테이너가 살아남는다.
        html = ['<div class="kpi-row-scroll">']
        for label, value, hint, variant in cards:
            html.append(kpi_card(label, value, hint, variant))
        html.append('</div>')
        st.markdown("".join(html), unsafe_allow_html=True)
        return

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


# ---------- 사진 입력 (파일 업로드 + 카메라 촬영) ----------

def photo_input(label: str, key: str,
                accept_types: list[str] | None = None,
                help_text: str | None = None):
    """조치 사진용 사진 입력. 파일 업로드 / 카메라 촬영 두 탭으로 제공.
    카메라 촬영본이 있으면 그것을, 없으면 업로드 파일을 반환.
    반환 객체는 .getvalue()로 bytes를 얻을 수 있는 UploadedFile 호환."""
    if accept_types is None:
        accept_types = ["jpg", "jpeg", "png"]

    st.markdown(
        f"<div style='font-size:0.88rem; color:#475569; font-weight:600; "
        f"margin-bottom:0.25rem;'>{label}</div>"
        + (f"<div style='color:#94A3B8; font-size:0.78rem; "
           f"margin-bottom:0.3rem;'>{help_text}</div>" if help_text else ""),
        unsafe_allow_html=True,
    )
    tab_file, tab_cam = st.tabs(["파일 업로드", "카메라 촬영"])
    with tab_file:
        uploaded = st.file_uploader(
            label,
            type=accept_types,
            key=f"{key}_file",
            label_visibility="collapsed",
        )
    with tab_cam:
        camera = st.camera_input(
            label,
            key=f"{key}_camera",
            label_visibility="collapsed",
        )
    # 카메라 촬영본 우선 (가장 최근 입력으로 가정)
    return camera if camera is not None else uploaded


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
