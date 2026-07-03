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
    ("#F97316", "임박 — 마감 3일 이내 또는 점검 예정"),
    ("#94A3B8", "빈 spot — 장비 없음"),
    ("#EAB308", "결과 없음 — 점검 미실시"),
]


def legend_html(items) -> str:
    """(color, label) 목록으로 인라인 색상 범례 HTML 생성.
    화면마다 실제 마커에 맞는 범례를 전달해 사용 (건강상태 외 spot 선택 등)."""
    items_html = "".join(
        f"<span style='display:inline-flex; align-items:center; gap:0.3rem; "
        f"font-size:0.78rem; color:#475569;'>"
        f"<span style='display:inline-block; width:0.7rem; height:0.7rem; "
        f"border-radius:50%; background:{c}; "
        f"border:1px solid rgba(0,0,0,0.08);'></span>{label}</span>"
        for c, label in items
    )
    return (
        "<div style='display:flex; flex-wrap:wrap; gap:0.9rem; align-items:center; "
        "padding:0.4rem 0.6rem; background:#F8FAFC; border:1px solid #E2E8F0; "
        "border-radius:8px; margin:0.2rem 0;'>"
        f"{items_html}"
        "</div>"
    )


def floor_legend_html() -> str:
    """도면 색상 범례 (대시보드 장비 건강상태 5종). flex 레이아웃."""
    return legend_html(LEGEND_ITEMS)


def control_toggle(key: str, default_locked: bool = True) -> bool:
    """도면 위에 표시할 잠금/조작 토글. True=잠금, False=조작 가능.

    기본값 True (잠금) — 사용자가 의도적으로 풀어야 도면 조작 가능. 의도치 않은
    pan/zoom으로 viewport가 흐트러지는 것 방지.

    st.toggle 위젯 사용 — 클릭 시 streamlit이 ON/OFF UI를 즉시 전환하고
    같은 rerun에서 새 값을 반환. session_state에도 자동 저장(widget key 동일).
    """
    state_key = f"floor_lock_btn_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = default_locked
    locked = st.toggle(
        "🔒 도면 잠금",
        value=st.session_state[state_key],
        key=state_key,
        help="ON = 잠금(pan/zoom 비활성·modebar 숨김) / OFF = 조작 가능",
    )
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

    Plotly가 SVG 자식 (nsewdrag, scatter trace 등)에 inline pointer-events:all 을
    설정하므로, 부모만 none으로 만들면 자식의 inline이 우선해 클릭이 통과한다.
    따라서 자식 전부에 `pointer-events: none !important` 강제.

    config / on_select / selection_mode 등 plotly_chart props가 변하지 않아
    Plotly 인스턴스가 재마운트되지 않고 줌/팬 상태가 그대로 유지된다.
    """
    st.markdown(
        """
        <style id="floor_lock_overlay">
        div[data-testid="stPlotlyChart"] {
            position: relative;
        }
        /* SVG 내부 모든 인터랙티브 요소(nsewdrag, point, etc) 차단 */
        div[data-testid="stPlotlyChart"],
        div[data-testid="stPlotlyChart"] * {
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
            pointer-events: none !important;
        }
        div[data-testid="stPlotlyChart"] .modebar,
        div[data-testid="stPlotlyChart"] .modebar-container {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
