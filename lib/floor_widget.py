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
    """도면 위에 표시할 잠금/조작 토글. True=잠금, False=조작 가능.

    same-cycle 토글: button 클릭 시 session_state + 지역 locked를 즉시 갱신해
    같은 rerun에서 lock_overlay_css 분기와 호출 측 동작에 새 값이 반영된다.
    라벨은 한 박자 늦게 갱신될 수 있으나 동작 자체는 즉시 새 상태로 적용.

    NOTE: st.rerun() / on_click callback 모두 사용 금지 —
    dialog 내부에서 호출 시 모달이 닫힌다.
    """
    state_key = f"floor_lock_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_locked
    locked = st.session_state[state_key]
    # 동사형 라벨 — 클릭 시 무엇이 일어날지 명확히
    label = "🔓 도면 풀기" if locked else "🔒 도면 잠그기"
    help_txt = (
        "현재 잠금 — pan/zoom 비활성, modebar 숨김. 클릭하면 풀림"
        if locked else
        "현재 조작 가능 — 휠/드래그로 줌·팬. 클릭하면 잠금"
    )
    if st.button(
        label,
        key=f"floor_lock_btn_{key}",
        help=help_txt,
        type="primary" if locked else "secondary",
    ):
        locked = not locked
        st.session_state[state_key] = locked
    return locked


def plotly_config(locked: bool = False) -> dict:
    """공통 Plotly config — 항상 동일. locked 인자는 호환을 위해 받지만 무시.

    plotly_chart의 config가 변하면 streamlit이 컴포넌트를 재마운트하여
    Plotly의 uirevision 효과(줌/팬 보존)가 무력화된다. 따라서 잠금은 config가 아닌
    CSS overlay(pointer-events:none + modebar 숨김)로 구현 — lock_overlay_css() 참조.
    """
    return {
        "scrollZoom": True,
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
        ],
        # resetScale2d (🏠 Home) = "전체 도면 viewport에 fit"
    }


def lock_overlay_css() -> None:
    """잠금 시 호출 — 같은 스코프(페이지/dialog) 내 stPlotlyChart에
    pointer-events:none + modebar 숨김 + 잠금 배지를 주입한다.

    config / on_select / selection_mode 등 plotly_chart props가 변하지 않아
    Plotly 인스턴스가 재마운트되지 않고 줌/팬 상태가 그대로 유지된다.
    """
    st.markdown(
        """
        <style id="floor_lock_overlay">
        div[data-testid="stPlotlyChart"] {
            position: relative;
            pointer-events: none !important;
        }
        div[data-testid="stPlotlyChart"]::after {
            content: "🔒 잠금";
            position: absolute;
            top: 10px; right: 10px;
            background: rgba(15, 23, 42, 0.78);
            color: #FFFFFF;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            z-index: 50;
            pointer-events: none;
        }
        div[data-testid="stPlotlyChart"] .modebar,
        div[data-testid="stPlotlyChart"] .modebar-container {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
