"""도면 위에 QR 장비 위치를 표시하는 Plotly 시각화."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import plotly.graph_objects as go

    from lib.data import Equipment


# 상태별 색상
HEALTH_COLOR = {
    "PASS": "#16A34A",  # 초록
    "FAIL": "#DC2626",  # 빨강
    "DUE":  "#2563EB",  # 파랑
}

ZONE_FILL = "#F8FAFC"
ZONE_LINE = "#94A3B8"
ZONE_TEXT = "#475569"


def make_floor_figure(
    equipments: list["Equipment"],
    floor: str,
    zones: list[tuple[str, int, int, int, int]],
    *,
    compact: bool = False,
) -> "go.Figure":
    """도면 + 장비 마커 Plotly Figure 반환.

    equipments : 해당 층에 속한 장비 리스트
    floor      : 층 코드 (예: "B3")
    zones      : 도면 layout — (label, x, y, w, h) — 좌표/크기는 0~100
    compact    : True 시 썸네일 사이즈 + 마커 텍스트 생략 + 범례 숨김
    """
    import plotly.graph_objects as go

    fig = go.Figure()

    # 도면 외곽 (전체 사각형)
    fig.add_shape(
        type="rect", x0=0, y0=0, x1=100, y1=100,
        line=dict(color="#0F172A", width=2 if not compact else 1.4),
        fillcolor="#FFFFFF", layer="below",
    )

    zone_label_size = 9 if compact else 12

    # 각 zone 사각형 + 레이블
    for label, x, y, w, h in zones:
        fig.add_shape(
            type="rect", x0=x, y0=y, x1=x + w, y1=y + h,
            line=dict(color=ZONE_LINE, width=1, dash="dot"),
            fillcolor=ZONE_FILL, layer="below",
        )
        if not compact:
            fig.add_annotation(
                x=x + w / 2, y=y + h / 2,
                text=f"<b>{label}</b>",
                showarrow=False,
                font=dict(size=zone_label_size, color=ZONE_TEXT,
                          family="Pretendard, Malgun Gothic, sans-serif"),
            )

    # 장비 마커
    by_status: dict[str, list[Equipment]] = {"PASS": [], "FAIL": [], "DUE": []}
    for e in equipments:
        if e.health_status in by_status:
            by_status[e.health_status].append(e)

    marker_size = 14 if compact else 22

    for status, items in by_status.items():
        if not items:
            continue
        fig.add_trace(go.Scatter(
            x=[e.pixel_x for e in items],
            y=[e.pixel_y for e in items],
            mode="markers" if compact else "markers+text",
            marker=dict(
                size=marker_size,
                color=HEALTH_COLOR[status],
                line=dict(color="#FFFFFF", width=2),
                symbol="circle",
            ),
            text=[e.equipment_id.split("-")[-1] for e in items] if not compact else None,
            textposition="middle center",
            textfont=dict(color="#FFFFFF", size=9, family="Pretendard, Malgun Gothic, sans-serif"),
            name=status,
            showlegend=not compact,
            customdata=[
                [e.equipment_id, e.equipment_name, e.category, e.location_id,
                 e.last_inspection.isoformat() if e.last_inspection else "-"]
                for e in items
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b> · %{customdata[2]}<br>"
                "%{customdata[1]}<br>"
                "위치: %{customdata[3]}<br>"
                "최근 점검: %{customdata[4]}<extra></extra>"
            ),
        ))

    if compact:
        # 썸네일 레이아웃 — 작은 사이즈, 헤더 짧음, 범례 없음
        fail_n = sum(1 for e in equipments if e.health_status == "FAIL")
        title_text = f"<b>{floor}</b>  · 총 {len(equipments)}"
        if fail_n:
            title_text += f"  · <span style='color:#DC2626'>불량 {fail_n}</span>"
        fig.update_layout(
            title=dict(
                text=title_text,
                x=0.5, xanchor="center",
                font=dict(size=12, color="#0F172A",
                          family="Pretendard, Malgun Gothic, sans-serif"),
            ),
            xaxis=dict(visible=False, range=[-3, 103]),
            yaxis=dict(visible=False, range=[103, -3], scaleanchor="x", scaleratio=1),
            plot_bgcolor="#F8FAFC",
            paper_bgcolor="#FFFFFF",
            height=220,
            margin=dict(l=4, r=4, t=30, b=4),
            hoverlabel=dict(bgcolor="#FFFFFF", font_size=11,
                            font_family="Pretendard, Malgun Gothic, sans-serif"),
        )
        return fig

    # 일반(상세) 레이아웃
    fig.update_layout(
        title=dict(
            text=f"<b>{floor}</b> 도면 · 장비 위치",
            x=0.5, xanchor="center",
            font=dict(size=16, color="#0F172A", family="Pretendard, Malgun Gothic, sans-serif"),
        ),
        xaxis=dict(visible=False, range=[-3, 103]),
        yaxis=dict(visible=False, range=[103, -3], scaleanchor="x", scaleratio=1),
        plot_bgcolor="#F8FAFC",
        paper_bgcolor="#FFFFFF",
        height=600,
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            font=dict(size=12, family="Pretendard, Malgun Gothic, sans-serif"),
        ),
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12,
                        font_family="Pretendard, Malgun Gothic, sans-serif"),
    )
    return fig
