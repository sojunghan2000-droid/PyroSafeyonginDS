"""Field Inspection 모바일 뷰. iframe(components.html)으로 렌더한다."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from lib import data


MOBILE_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<style>
    body {{
        font-family: 'Pretendard', 'Malgun Gothic', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #F8FAFC;
        margin: 0;
        padding: 1.5rem 0;
        display: flex;
        justify-content: center;
        color: #0F172A;
    }}
    .mobile-frame {{
        width: 400px;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 24px;
        padding: 1.25rem 1.1rem 0;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.08);
        overflow: hidden;
    }}
    .top-bar {{
        display:flex; justify-content:space-between; align-items:center;
        font-weight:700; color:#2563EB; font-size:1.05rem; margin-bottom:1rem;
    }}
    .top-bar .icons {{ color:#64748B; display:flex; gap:0.5rem; }}
    .title {{ font-size:1.65rem; font-weight:700; }}
    .sub {{ color:#64748B; font-size:0.9rem; margin-bottom:1rem; }}

    .kpi-row {{ display:grid; grid-template-columns:1fr 1fr; gap:0.6rem; margin-bottom:0.9rem; }}
    .kpi {{ border-radius:14px; padding:1rem; min-height:120px; }}
    .kpi.primary {{ background:#2563EB; color:#FFFFFF; }}
    .kpi.alert {{ background:#FEF2F2; border:1px solid #FCA5A5; }}
    .kpi .lbl {{ font-size:0.78rem; opacity:0.85; font-weight:600; }}
    .kpi .num {{ font-size:2.2rem; font-weight:800; line-height:1.1; margin-top:0.9rem; }}
    .kpi .hint {{ font-size:0.85rem; margin-top:0.2rem; opacity:0.9; }}
    .kpi.alert .num {{ color:#DC2626; }}
    .kpi.alert .hint {{ color:#B91C1C; }}
    .kpi.alert .lbl {{ color:#B91C1C; }}

    .cta {{
        background:#EFF6FF; border:1px solid #BFDBFE; border-radius:14px;
        padding:0.95rem 1rem; display:flex; justify-content:space-between; align-items:center;
        margin-bottom:1.2rem;
    }}
    .cta-left {{ display:flex; gap:0.75rem; align-items:center; }}
    .cta-icon {{
        width:40px; height:40px; border-radius:10px; background:#2563EB; color:#FFF;
        display:flex; align-items:center; justify-content:center; font-size:1.4rem; font-weight:800;
    }}
    .cta-title {{ font-weight:700; font-size:1rem; }}
    .cta-sub {{ color:#64748B; font-size:0.82rem; }}

    .section-head {{
        display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;
    }}
    .section-head .label {{
        color:#64748B; font-size:0.76rem; font-weight:700; letter-spacing:0.05em;
    }}
    .section-head .more {{ color:#2563EB; font-size:0.85rem; font-weight:600; }}

    .card {{
        background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px;
        padding:0.85rem 0.95rem; margin-bottom:0.6rem;
        display:flex; gap:0.75rem; align-items:center;
    }}
    .card-icon {{
        width:40px; height:40px; border-radius:10px; background:#EFF6FF; color:#2563EB;
        display:flex; align-items:center; justify-content:center; font-weight:800; font-size:1.05rem; flex-shrink:0;
    }}
    .card-icon.muted {{ background:#F1F5F9; color:#94A3B8; }}
    .card-body {{ flex:1; }}
    .card-title {{ font-weight:700; font-size:0.95rem; }}
    .card-title.muted {{ color:#64748B; }}
    .card-due {{ color:#64748B; font-size:0.8rem; }}
    .tag {{ background:#EFF6FF; color:#1D4ED8; font-size:0.72rem; font-weight:700;
            padding:0.2rem 0.55rem; border-radius:999px; letter-spacing:0.04em; }}
    .tag.planned {{ background:#F1F5F9; color:#475569; }}
    .dot-ok {{ color:#16A34A; font-size:1.1rem; }}

    .sync {{
        background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px;
        padding:0.7rem 0.9rem; margin-top:0.5rem; font-size:0.82rem; color:#1E3A8A;
    }}

    .bottom-nav {{
        display:grid; grid-template-columns:repeat(4,1fr); text-align:center;
        background:#FFFFFF; border-top:1px solid #E2E8F0;
        margin: 1rem -1.1rem 0; padding: 0.6rem 0 0.8rem; border-radius:0 0 24px 24px;
    }}
    .nav {{ color:#64748B; font-size:0.78rem; padding:0.4rem 0; }}
    .nav.active {{
        color:#FFFFFF; background:#2563EB; border-radius:10px; margin:0 0.5rem; font-weight:700;
    }}
</style>
</head>
<body>
<div class="mobile-frame">
    <div class="top-bar">
        <span>용인덕성 AI DC</span>
        <span class="icons"><span>♪</span><span>⌾</span></span>
    </div>
    <div class="title">용인덕성 AI DC</div>
    <div class="sub">Field Inspection Dashboard</div>
    <div class="kpi-row">
        <div class="kpi primary">
            <div class="lbl">✓</div>
            <div class="num">{inspections_today}</div>
            <div class="hint">Inspections Today</div>
        </div>
        <div class="kpi alert">
            <div class="lbl">⚠</div>
            <div class="num">{pending_def:02d}</div>
            <div class="hint">Pending Deficiencies</div>
        </div>
    </div>
    <div class="cta">
        <div class="cta-left">
            <div class="cta-icon">+</div>
            <div>
                <div class="cta-title">Start New Inspection</div>
                <div class="cta-sub">Scan QR or select manual entry</div>
            </div>
        </div>
        <div style="color:#94A3B8;">›</div>
    </div>
    <div class="section-head">
        <span class="label">UPCOMING TASKS</span>
        <span class="more">View All</span>
    </div>
    <div class="card">
        <div class="card-icon">▤</div>
        <div class="card-body">
            <div class="card-title">Floor 4 - Extinguisher Audit</div>
            <div class="card-due">Due: 14:30 Today</div>
        </div>
        <span class="tag">ZONE A</span>
    </div>
    <div class="card">
        <div class="card-icon">✱</div>
        <div class="card-body">
            <div class="card-title">Main Lobby - Sprinkler Test</div>
            <div class="card-due">Due: Tomorrow, 09:00</div>
        </div>
        <span class="tag planned">PLANNED</span>
    </div>
    <div class="card">
        <div class="card-icon muted">⟲</div>
        <div class="card-body">
            <div class="card-title muted">Server Room B - Smoke Sensor</div>
            <div class="card-due">Completed 2h ago</div>
        </div>
        <span class="dot-ok">●</span>
    </div>
    <div class="sync"><span style="color:#2563EB;">●</span> System synced with central database at 10:45 AM</div>
    <div class="bottom-nav">
        <div class="nav active">Home</div>
        <div class="nav">Scan QR</div>
        <div class="nav">Deficiencies</div>
        <div class="nav">Logs</div>
    </div>
</div>
</body>
</html>
"""


def render() -> None:
    kpi = data.field_kpis()
    html = MOBILE_HTML.format(
        inspections_today=kpi["inspections_today"],
        pending_def=kpi["pending_deficiencies"],
    )
    components.html(html, height=920, scrolling=False)
