"""도면 위젯 공통 — 컨트롤 토글 + 범례 + Plotly config.

Location 모달(`pages_app/dashboard.py`)과 위치 마스터(`pages_app/admin_center.py`)가
공유하는 도면 컴포넌트. 도면 인터랙션 토글(잠금/조작), 색상 범례,
Plotly config(Home=resetScale2d 명시, fullscreen 비활성)을 한곳에서 처리한다.
"""
from __future__ import annotations

import streamlit as st


# 도면 마커 색상 의미 (UI 범례 + 실제 marker color 동시 참조)
LEGEND_ITEMS = [
    ("#16A34A", "양호 — 점검 통과"),
    ("#DC2626", "불량 — 지적·조치 대기"),
    ("#F59E0B", "임박 — 마감 3일 이내 또는 점검 예정"),
    ("#94A3B8", "빈 spot — 장비 없음"),
    ("#EAB308", "결과 없음 — 점검 미실시"),
]


def floor_legend_html() -> str:
    """도면 색상 범례 HTML 한 줄. flex 레이아웃으로 도면 위/아래 어디든 배치 가능."""
    items_html = "".join(
        f"<span style='display:inline-flex; align-items:center; gap:0.3rem; "
        f"font-size:0.78rem; color:#475569;'>"
        f"<span style='display:inline-block; width:0.7rem; height:0.7rem; "
        f"border-radius:50%; background:{c}; "
        f"border:1px solid rgba(0,0,0,0.08);'></span>{label}</span>"
        for c, label in LEGEND_ITEMS
    )
    return (
        "<div style='display:flex; flex-wrap:wrap; gap:0.9rem; align-items:center; "
        "padding:0.4rem 0.6rem; background:#F8FAFC; border:1px solid #E2E8F0; "
        "border-radius:8px; margin:0.2rem 0;'>"
        f"{items_html}"
        "</div>"
    )


def control_toggle(key: str, default_locked: bool = False) -> bool:
    """도면 위에 표시할 잠금/조작 토글. True=잠금(staticPlot), False=조작 가능.

    session_state[key]에 상태 저장. 호출 측에서 plotly_chart config에 반영.
    """
    state_key = f"floor_lock_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_locked
    locked = st.session_state[state_key]
    label = "🔒 도면 잠금" if locked else "🔓 도면 조작"
    if st.button(
        label,
        key=f"floor_lock_btn_{key}",
        help=("잠금 상태 — pan/zoom 비활성. 클릭하면 조작 모드"
              if locked else
              "조작 가능 — 휠/드래그로 줌·팬. 클릭하면 잠금 모드"),
    ):
        st.session_state[state_key] = not locked
        st.rerun()
    return locked


def plotly_config(locked: bool = False) -> dict:
    """공통 Plotly config. locked=True면 정적 모드(인터랙션 비활성 + modebar 숨김)."""
    if locked:
        return {"staticPlot": True, "displayModeBar": False}
    return {
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
        ],
        # resetScale2d (🏠 Home) = "전체 도면 viewport에 fit" 으로 사용자가 인지하는 '전체화면 보기'
        # 기본 포함이므로 별도 add 불필요.
    }
