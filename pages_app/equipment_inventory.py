"""시설 관리 페이지 — 테이블 각 행에 QR 모달 진입 버튼."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import auth, data
from lib.data import TASK_INSPECTION_TYPES
from lib.inspection_dialog import EQ_FLOORS, SPOT_FLOORS, equipment_dialog
from lib.qr import make_qr, payload_for, qr_png_bytes, sticker_sheet_pdf
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 테이블 컬럼 비율 — v1.7: 7컬럼. 위치 등록/QR/최근 점검은 헤더에 ▾ 팝오버가 붙어 폭 여유 확보
COL_RATIOS = [1.0, 1.5, 1.0, 1.0, 1.3, 0.9, 0.8]

# 장비 건강상태 마커 색 (양호/불량/점검도래)
_EQ_HEALTH_COLOR = {"PASS": "#16A34A", "FAIL": "#DC2626", "DUE": "#3B82F6"}


def _equipment_floor_fig(floor: str, eq_list, height: int = 460):
    """시설 관리 층 도면 미리보기 (읽기 전용) — 장비를 건강상태 색 마커로 표시.
    height로 단일(460)/미니맵(180) 크기 구분."""
    import base64
    from pathlib import Path
    import plotly.graph_objects as go

    ASSETS = Path(__file__).resolve().parent.parent / "assets" / "floors"
    FIG_W, FIG_H = 2978, 2105
    p = ASSETS / f"{floor}.png"
    if not p.exists():
        return None
    uri = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

    fig = go.Figure()
    fig.add_layout_image(dict(
        source=uri, xref="x", yref="y",
        x=0, y=FIG_H, sizex=FIG_W, sizey=FIG_H,
        sizing="stretch", layer="below", opacity=1.0,
    ))

    xs, ys, cs, txt, cd = [], [], [], [], []
    for e in eq_list:
        if not (e.pixel_x or e.pixel_y):
            continue
        xs.append(e.pixel_x / 100 * FIG_W)
        ys.append(FIG_H - e.pixel_y / 100 * FIG_H)
        cs.append(_EQ_HEALTH_COLOR.get(e.health_status, "#94A3B8"))
        txt.append(e.location_id)
        cd.append((e.equipment_id, e.equipment_name, e.health_status, e.location_id))
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers+text",
            text=txt, textposition="top center",
            textfont=dict(size=10, color="#0F172A"),
            marker=dict(size=15, color=cs, line=dict(color="#FFFFFF", width=2)),
            customdata=cd,
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>%{customdata[3]} · %{customdata[0]}"
                "<br>상태: %{customdata[2]}<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_xaxes(visible=False, range=[0, FIG_W], constrain="domain")
    fig.update_yaxes(visible=False, range=[0, FIG_H], scaleanchor="x", scaleratio=1)
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor="#F8FAFC", height=height,
        showlegend=False, uirevision=f"eq_floor_{floor}",
    )
    return fig


def _set_eq_floor(target: str) -> None:
    """미니맵 [이 층 보기] 콜백 — 층 필터를 target 층으로 전환."""
    st.session_state["eq_floor_filter"] = target


# 3개 컬럼 헤더 ▾ 팝오버 내용 (뜻 + 조치) — 짧게 유지
_HINT_LOC_MD = ("**위치 등록** — 도면(spot)에 좌표가 등록됐는지 여부.\n\n"
                "미등록 → **[속성]** 또는 위치 마스터에서 도면 위치 지정.")
_HINT_QR_MD = ("**QR 상태** — PENDING(스티커 부착·첫 스캔 전) / "
               "ASSIGNED(현장 스캔 완료).\n\n"
               "PENDING → QR 스티커 부착 후 현장에서 스캔하면 자동 전환.")
_HINT_INSP_MD = ("**최근 점검** — 마지막 점검일 + 결과(PASS 양호 / FAIL 불량 / "
                 "DUE 점검 도래).\n\n"
                 "FAIL·DUE → 안전점검 관리에서 점검·조치 진행.")

_HDR_LABEL_CSS = "color:#64748B; font-size:0.78rem; font-weight:600; text-align:center;"


def _hdr_with_hint(col, label: str, tip_md: str) -> None:
    """헤더 컬럼: 라벨(가운데) + 옆에 작은 ▾ 설명 팝오버.
    [spacer, 라벨, ▾] 균형 배치로 라벨이 컬럼 정중앙에 오게 한다."""
    with col:
        sp, lc, pc = st.columns([0.32, 1, 0.32], vertical_alignment="center",
                                gap="small")
        lc.markdown(
            f"<div style='{_HDR_LABEL_CSS}'>{label}</div>",
            unsafe_allow_html=True,
        )
        with pc:
            # 라벨 "​"(폭 0) → 자동 ExpandMore ▾ 만 보임
            with st.popover("​", use_container_width=False):
                st.markdown(tip_md)


def _render_table_header() -> None:
    """테이블 헤더 — 라벨 + 위치 등록/QR 상태/최근 점검 3개 컬럼에 ▾ 설명 팝오버."""
    st.markdown(
        "<style>"
        ".st-key-eqhdr [data-testid='stPopoverButton']{"
        "background:transparent!important;border:none!important;box-shadow:none!important;"
        "padding:0 0.1rem!important;min-height:0!important;height:1.15rem!important;"
        "color:#94A3B8!important;}"
        ".st-key-eqhdr [data-testid='stPopoverButton']:hover{color:#334155!important;}"
        "</style>",
        unsafe_allow_html=True,
    )
    with st.container(key="eqhdr"):
        cols = st.columns(COL_RATIOS, vertical_alignment="center")
        cols[0].markdown(f"<div style='{_HDR_LABEL_CSS}'>장비 ID</div>",
                         unsafe_allow_html=True)
        cols[1].markdown(f"<div style='{_HDR_LABEL_CSS}'>시설 종류</div>",
                         unsafe_allow_html=True)
        _hdr_with_hint(cols[2], "위치 등록", _HINT_LOC_MD)
        _hdr_with_hint(cols[3], "QR 상태", _HINT_QR_MD)
        _hdr_with_hint(cols[4], "최근 점검", _HINT_INSP_MD)
        cols[5].markdown(f"<div style='{_HDR_LABEL_CSS}'>점검 이력</div>",
                         unsafe_allow_html=True)
        cols[6].markdown(f"<div style='{_HDR_LABEL_CSS}'>작업</div>",
                         unsafe_allow_html=True)
    st.markdown(
        "<hr style='margin:0.15rem 0 0.1rem; border:none; "
        "border-top:1px solid #E2E8F0;'>",
        unsafe_allow_html=True,
    )


# 장비별 완료 점검 결과 이력 (task_id로 정밀 매칭)
def _equipment_history(eq, tasks, defs) -> list[tuple]:
    """장비의 완료 점검 결과 이력을 최신순으로 반환.
    이 장비에 매칭되는 task의 task_id로 Deficiency를 정밀 매칭 (구역 단위 아님).
    각 원소: (inspection_date, types_str, is_good, detail, deficiency)."""
    task_ids = {
        t.task_id for t in tasks
        if eq.location_id in t.equipment_label or eq.equipment_name in t.equipment_label
    }
    rows = []
    for d in defs:
        if d.task_id and d.task_id in task_ids:
            is_good = (d.issue or "").strip() in ("", "양호")
            detail = "양호" if is_good else (d.issue or "지적사항")
            types_str = " / ".join(d.inspection_types) if d.inspection_types else "-"
            rows.append((d.inspection_date, types_str, is_good, detail, d))
    rows.sort(key=lambda r: r[0] or data.TODAY, reverse=True)
    return rows


@st.dialog("장비 점검 이력", width="large")
def _status_dialog(equipment_id: str) -> None:
    """장비별 점검 결과 이력·점검 일정·구역 통보서 (읽기 전용)."""
    eq = next((x for x in data.load_equipment() if x.equipment_id == equipment_id), None)
    if not eq:
        st.error("장비를 찾을 수 없습니다.")
        return

    tasks = data.load_tasks()
    notices = data.load_notices()
    defs = data.load_deficiencies()

    matching_tasks = [
        t for t in tasks
        if eq.location_id in t.equipment_label or eq.equipment_name in t.equipment_label
    ]
    matching_notices = [n for n in notices if n.floor == eq.floor and n.zone == eq.zone]
    history = _equipment_history(eq, tasks, defs)

    # 헤더
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1.15rem; margin-bottom:0.3rem;'>"
        f"{eq.equipment_id} · {eq.equipment_name}</div>"
        f"<div style='color:#475569; font-size:0.9rem; line-height:1.6; margin-bottom:0.8rem;'>"
        f"<b>위치</b> · {eq.location_id} ({eq.floor} / {eq.zone})  &nbsp;|&nbsp; "
        f"<b>카테고리</b> · {eq.category}  &nbsp;|&nbsp; "
        f"<b>시리얼</b> · {eq.serial}<br>"
        f"<b>현재 상태</b> · {badge(eq.health_status)} {badge(eq.qr_status)}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── 점검 결과 이력 (완료 점검, 최신순 — task_id 정밀 매칭) ──
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem; "
        f"margin:0.7rem 0 0.3rem;'>📋 점검 결과 이력 ({len(history)}건)</div>",
        unsafe_allow_html=True,
    )
    if history:
        hb = ""
        for (dt, types_str, is_good, detail, d) in history:
            rb = (
                "<span style='color:#16A34A; font-weight:600;'>양호</span>"
                if is_good else
                "<span style='color:#DC2626; font-weight:600;'>지적</span>"
            )
            content = "-" if is_good else detail
            hb += (
                "<tr style='border-bottom:1px solid #F1F5F9;'>"
                f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{fmt_date(dt)}</td>"
                f"<td style='padding:0.5rem 0.3rem; color:#0F172A;'>{types_str}</td>"
                f"<td style='padding:0.5rem 0.3rem;'>{rb}</td>"
                f"<td style='padding:0.5rem 0.3rem; color:#0F172A;'>{content}</td>"
                "</tr>"
            )
        hh = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.4rem 0.3rem;'>일자</th>"
            "<th style='padding:0.4rem 0.3rem;'>점검 유형</th>"
            "<th style='padding:0.4rem 0.3rem;'>결과</th>"
            "<th style='padding:0.4rem 0.3rem;'>지적 내용</th>"
            "</tr></thead><tbody>"
        )
        st.markdown(hh + hb + "</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("완료된 점검 이력이 없습니다. (점검 시작 → 결과 입력 시 누적됩니다)")

    # ── 점검 일정 (예정·진행 포함 전체) ──
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem; "
        f"margin:1rem 0 0.3rem;'>🗓️ 점검 일정 ({len(matching_tasks)}건)</div>",
        unsafe_allow_html=True,
    )
    if matching_tasks:
        header = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.4rem 0.3rem;'>작업 ID</th>"
            "<th style='padding:0.4rem 0.3rem;'>점검 유형</th>"
            "<th style='padding:0.4rem 0.3rem;'>담당자</th>"
            "<th style='padding:0.4rem 0.3rem;'>마감일</th>"
            "<th style='padding:0.4rem 0.3rem;'>상태</th>"
            "</tr></thead><tbody>"
        )
        from lib.ui import TASK_STATUS_KO
        body = "".join(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{t.task_id}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#0F172A;'>{t.task_type}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{t.assignee or '미지정'}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{fmt_date(t.due_date)}</td>"
            f"<td style='padding:0.5rem 0.3rem;'>{badge(TASK_STATUS_KO.get(t.status, t.status))}</td>"
            "</tr>"
            for t in sorted(matching_tasks, key=lambda x: x.due_date, reverse=True)
        )
        st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("이 장비에 매핑된 점검 일정이 없습니다.")

    # ── 구역 통보서 (층/구역 단위 — 장비 직접 FK 없어 위치 기준) ──
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem; "
        f"margin:1rem 0 0.3rem;'>📨 구역 통보서 ({len(matching_notices)}건)</div>",
        unsafe_allow_html=True,
    )
    if matching_notices:
        rows = []
        for n in matching_notices:
            status_text = "조치 완료" if n.action_done else "조치 대기"
            rows.append((n.inspection_date, n.issue, status_text, n.notice_no))
        rows.sort(key=lambda r: r[0] or data.TODAY, reverse=True)
        header = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.4rem 0.3rem;'>일자</th>"
            "<th style='padding:0.4rem 0.3rem;'>내용</th>"
            "<th style='padding:0.4rem 0.3rem;'>상태</th>"
            "<th style='padding:0.4rem 0.3rem;'>통보서 번호</th>"
            "</tr></thead><tbody>"
        )
        body = "".join(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{fmt_date(dt)}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#0F172A;'>{issue}</td>"
            f"<td style='padding:0.5rem 0.3rem;'>{badge(status)}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#475569; font-size:0.8rem;'>{notice_no}</td>"
            "</tr>"
            for (dt, issue, status, notice_no) in rows
        )
        st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("이 구역에서 발급된 통보서가 없습니다.")

    st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='color:#94A3B8; font-size:0.78rem; margin-bottom:0.4rem;'>"
        "이 현황판은 읽기 전용입니다. 신규 점검 입력은 아래 버튼으로 진행하세요.</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "점검 입력판으로 이동 →", type="primary",
        use_container_width=True, key=f"status_goto_{equipment_id}",
    ):
        st.session_state["inspect_target"] = equipment_id
        st.session_state["page"] = "deficiencies"
        st.session_state["_open_inspect_dialog"] = True
        st.rerun()


@st.dialog("QR 코드 미리보기", width="large")
def _qr_dialog(equipment_id: str) -> None:
    """선택된 장비의 QR 모달."""
    eq = next((x for x in data.load_equipment() if x.equipment_id == equipment_id), None)
    if not eq:
        st.error("장비를 찾을 수 없습니다.")
        return

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.image(make_qr(eq, box_size=10), width=240)
    with col_b:
        st.markdown(
            f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem; margin-bottom:0.5rem;'>"
            f"{eq.equipment_name}</div>"
            f"<div style='color:#475569; font-size:0.93rem; line-height:1.7;'>"
            f"<b>장비 ID</b> · {eq.equipment_id}<br>"
            f"<b>위치(구역)</b> · {eq.location_id} ({eq.floor} / {eq.zone})<br>"
            f"<b>카테고리</b> · {eq.category}<br>"
            f"<b>시리얼</b> · {eq.serial}<br>"
            f"<b>현재 상태</b> · {badge(eq.health_status)} {badge(eq.qr_status)}"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div style='color:#64748B; font-size:0.85rem; margin-top:0.75rem;'>"
            "QR 페이로드 (스캔 시 열리는 URL)</div>",
            unsafe_allow_html=True,
        )
        st.code(payload_for(eq), language="text")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='color:#64748B; font-size:0.85rem; font-weight:600;'>"
        "이 장비에 적용 가능한 점검 유형</div>"
        "<div style='color:#94A3B8; font-size:0.78rem; margin-bottom:0.3rem;'>"
        "점검 일정 등록 시 이 목록을 기준으로 자동 필터됩니다.</div>",
        unsafe_allow_html=True,
    )
    types_key = f"qr_dlg_types_{eq.equipment_id}"
    # session_state에 키가 없을 때만 현재 값으로 초기화 (편집 중 유지)
    if types_key not in st.session_state:
        st.session_state[types_key] = list(eq.inspection_types or [])
    edited_types = st.multiselect(
        "적용 점검 유형",
        options=TASK_INSPECTION_TYPES,
        key=types_key,
        label_visibility="collapsed",
        placeholder="적용 가능한 점검 유형 선택",
    )
    # dialog 안에서는 st.rerun()이 모달을 닫으므로 즉시 저장하고 toast/메시지로 안내
    if set(edited_types) != set(eq.inspection_types or []):
        if st.button("점검 유형 저장", use_container_width=True,
                     key=f"qr_dlg_save_types_{eq.equipment_id}"):
            data.set_equipment_inspection_types(eq.equipment_id, edited_types)
            st.success("점검 유형 저장 완료. 점검 일정 등록 시 즉시 반영됩니다.")

    # ── 위치 변경 (관리자만) ─────────────────────────────
    if auth.is_admin():
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='color:#64748B; font-size:0.85rem; font-weight:600;'>"
            "위치 변경 (관리자 전용)</div>"
            "<div style='color:#94A3B8; font-size:0.78rem; margin-bottom:0.3rem;'>"
            "층과 spot을 선택해 장비의 위치를 재지정합니다. "
            "저장 시 위치 ID도 새 형식 {floor}-{nn}으로 갱신됩니다.</div>",
            unsafe_allow_html=True,
        )
        all_spots = data.load_spots()
        floor_keys = sorted({s.floor for s in all_spots},
                            key=lambda f: EQ_FLOORS.index(f) if f in EQ_FLOORS else 999)
        if not floor_keys:
            st.info(
                "정의된 spot이 없습니다. 관리자 메뉴 → 위치 마스터에서 추가하세요."
            )
        else:
            mc1, mc2 = st.columns([1, 2])
            cur_floor = eq.floor if eq.floor in floor_keys else floor_keys[0]
            with mc1:
                move_floor = st.selectbox(
                    "층",
                    options=floor_keys,
                    index=floor_keys.index(cur_floor),
                    key=f"qr_dlg_move_floor_{eq.equipment_id}",
                )
            with mc2:
                spots_on_floor = [s for s in all_spots if s.floor == move_floor]
                if not spots_on_floor:
                    st.markdown(
                        "<div style='padding-top:1.7rem; color:#94A3B8; font-size:0.85rem;'>"
                        "이 층에 spot이 없습니다.</div>",
                        unsafe_allow_html=True,
                    )
                    sel_spot_obj = None
                else:
                    # 현재 spot이 이 층에 있으면 그것을 기본 선택
                    default_idx = 0
                    for i, s in enumerate(spots_on_floor):
                        if s.spot_id == eq.spot_id:
                            default_idx = i
                            break
                    move_spot_idx = st.selectbox(
                        "위치 (spot)",
                        options=range(len(spots_on_floor)),
                        index=default_idx,
                        format_func=lambda i: (
                            f"{spots_on_floor[i].room_name} "
                            f"({spots_on_floor[i].spot_id})"
                        ),
                        key=f"qr_dlg_move_spot_{eq.equipment_id}",
                    )
                    sel_spot_obj = spots_on_floor[move_spot_idx]

            if sel_spot_obj and sel_spot_obj.spot_id != eq.spot_id:
                new_loc = data.location_id_from_spot(sel_spot_obj.spot_id)
                st.markdown(
                    f"<div style='color:#475569; font-size:0.85rem;'>"
                    f"적용 시: <b>{eq.location_id}</b> → <b>{new_loc}</b> "
                    f"({sel_spot_obj.room_name})</div>",
                    unsafe_allow_html=True,
                )
                if st.button("위치 변경 저장", use_container_width=True,
                             key=f"qr_dlg_save_loc_{eq.equipment_id}"):
                    data.update_equipment_location(eq.equipment_id, sel_spot_obj)
                    st.success(
                        f"위치 변경 완료: {new_loc} ({sel_spot_obj.room_name})"
                    )

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    st.download_button(
        "PNG 다운로드",
        data=qr_png_bytes(eq, box_size=12),
        file_name=f"QR_{eq.equipment_id}_{eq.location_id}.png",
        mime="image/png",
        use_container_width=True,
        key=f"qr_dlg_dl_{eq.equipment_id}",
    )


def render() -> None:
    eq = data.load_equipment()
    kpi = data.equipment_kpis()

    title_col, action_col = st.columns([2.5, 1.5])
    with title_col:
        page_header(
            "시설 관리",
            "전 층 소방안전 시설 자산의 실시간 현황과 QR 부착 상태를 관리합니다.",
        )
    eq_btn_clicked = False
    with action_col:
        b1, b2 = st.columns(2)
        with b1:
            if st.button("신규 장비 등록", type="primary",
                         use_container_width=True, key="open_new_equipment"):
                eq_btn_clicked = True
        with b2:
            st.download_button(
                "QR 스티커 일괄 출력",
                data=sticker_sheet_pdf(eq),
                file_name="QR 스티커 시트 (4x6).pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    if st.session_state.pop("just_submitted_equipment", False):
        st.success(
            "새 장비가 등록되었습니다 (QR 상태: PENDING). "
            "보고서에서 QR 스티커 PDF 출력 → 현장 부착 → 첫 스캔 시 ASSIGNED로 자동 전환됩니다."
        )

    if eq_btn_clicked:
        equipment_dialog()

    qr_coverage = kpi.get("qr_coverage", 0.0)
    qr_variant = "alert" if qr_coverage < 100 else "default"
    qr_hint = "QR 부착률" if qr_coverage >= 100 else "미부착 장비 있음"
    render_kpi_row([
        ("전체 시설", f"{kpi['total']:,}", f"이번 달 +{kpi['new_this_month']}건", "default"),
        ("최근 점검 (지난 48시간)", f"{kpi['recently_inspected']:,}", "이틀 내 점검 완료", "default"),
        ("미조치 항목", f"{kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("QR 적용률", f"{qr_coverage:.1f}%", qr_hint, qr_variant),
    ])

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    f1, f2, _, tab_col = st.columns([0.8, 0.8, 0.4, 3.5])
    with f1:
        floor_filter = st.selectbox(
            "Filter",
            ["전체 층"] + sorted({e.floor for e in eq}),
            label_visibility="collapsed",
            key="eq_floor_filter",
        )
    with f2:
        sort_by = st.selectbox(
            "Sort",
            ["최근 점검순", "위치 순", "상태 순"],
            label_visibility="collapsed",
        )
    with tab_col:
        view = st.radio(
            "view",
            ["전체", "소화기·소화장치", "경보·감지", "소화전"],
            horizontal=True,
            label_visibility="collapsed",
        )

    cat_filter_map = {
        "소화기·소화장치": {"소화기", "확산소화기", "간이소화장치"},
        "경보·감지": {"비상경보장치", "가스누설경보기", "감지기", "발신기", "수신기"},
        "소화전": {"소화전"},
    }

    rows = eq
    if floor_filter != "전체 층":
        rows = [e for e in rows if e.floor == floor_filter]
    if view != "전체":
        rows = [e for e in rows if e.category in cat_filter_map.get(view, set())]

    if sort_by == "최근 점검순":
        rows = sorted(rows, key=lambda e: e.last_inspection or pd.Timestamp.min.date(), reverse=True)
    elif sort_by == "위치 순":
        rows = sorted(rows, key=lambda e: e.location_id)
    else:
        order = {"FAIL": 0, "DUE": 1, "PASS": 2}
        rows = sorted(rows, key=lambda e: order.get(e.health_status, 9))

    # ---------- 층 도면 미리보기 (읽기 전용, v1.7) ----------
    if floor_filter != "전체 층":
        _fig = _equipment_floor_fig(floor_filter, rows)
        if _fig is not None:
            st.markdown(
                f"<div style='margin-top:0.3rem; color:#475569; font-size:0.85rem;'>"
                f"🗺️ <b>{floor_filter}</b> 도면 · 장비 위치 "
                f"(🟢 양호 · 🔴 불량 · 🔵 점검도래)</div>",
                unsafe_allow_html=True,
            )
            st.plotly_chart(
                _fig, use_container_width=True,
                config={"displayModeBar": False, "staticPlot": True},
                key=f"eq_floor_fig_{floor_filter}",
            )
    else:
        # 전체 층 — 전 층 미니맵 그리드 + [이 층 보기] 드릴인
        st.markdown(
            "<div style='margin-top:0.3rem; color:#475569; font-size:0.85rem;'>"
            "🗺️ 전 층 도면 · 장비 위치 (🟢 양호 · 🔴 불량 · 🔵 점검도래) — "
            "<b>[이 층 보기]</b>로 상세 이동</div>",
            unsafe_allow_html=True,
        )
        # 관리자(위치 마스터) 화면처럼 전 층을 건물 순서로 2행 4열 그리드
        extra = [f for f in sorted({e.floor for e in eq}) if f not in SPOT_FLOORS]
        eq_floors = SPOT_FLOORS + extra
        n_cols = 4
        for row_start in range(0, len(eq_floors), n_cols):
            row_floors = eq_floors[row_start:row_start + n_cols]
            grid_cols = st.columns(n_cols)
            for gcol, fl in zip(grid_cols, row_floors):
                with gcol:
                    fl_eq = [e for e in rows if e.floor == fl]
                    st.markdown(
                        f"<div style='font-weight:600; color:#0F172A; font-size:0.82rem; "
                        f"margin-bottom:0.1rem;'>{fl} "
                        f"<span style='color:#94A3B8; font-weight:500;'>"
                        f"({len(fl_eq)})</span></div>",
                        unsafe_allow_html=True,
                    )
                    mini = _equipment_floor_fig(fl, fl_eq, height=170)
                    if mini is not None:
                        st.plotly_chart(
                            mini, use_container_width=True,
                            config={"displayModeBar": False, "staticPlot": True},
                            key=f"eq_mini_{fl}",
                        )
                    else:
                        st.caption("(도면 없음)")
                    st.button(
                        "이 층 보기", key=f"eq_drill_{fl}",
                        use_container_width=True,
                        on_click=_set_eq_floor, args=(fl,),
                    )

    # ---------- 테이블 (st.columns 기반) ----------
    # 헤더 — 위치 등록/QR 상태/최근 점검 3개 컬럼에 ▾ 설명 팝오버 (위젯)
    _render_table_header()

    # 점검 이력 계산용 전체 task/deficiency 한 번만 로드
    all_tasks = data.load_tasks()
    all_defs = data.load_deficiencies()

    # 클릭 처리는 루프 후 마지막 한 번만 (dialog는 한 번에 하나)
    open_status_for: str | None = None

    for e in rows:
        cols = st.columns(COL_RATIOS, vertical_alignment="center")
        with cols[0]:
            # 장비 ID(EQ-NNNN) — 자산 대장의 대표 식별자 (구 위치 ID 자리)
            st.markdown(
                f"<div style='font-weight:600; color:#0F172A; "
                f"text-align:center;'>{e.equipment_id}</div>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"<div style='font-weight:600; color:#0F172A; "
                f"text-align:center;'>{e.equipment_name}</div>"
                f"<div style='color:#64748B; font-size:0.8rem; "
                f"text-align:center;'>SN: {e.serial}</div>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            # 도면 위치(spot) 등록 여부 — 별도 컬럼, 이모지 없이 텍스트
            registered = bool(e.spot_id)
            loc_txt = (
                "<span style='color:#16A34A; font-weight:600; "
                "font-size:0.82rem;'>등록</span>"
                if registered else
                "<span style='color:#D97706; font-weight:600; "
                "font-size:0.82rem;'>미등록</span>"
            )
            st.markdown(f"<div style='text-align:center;'>{loc_txt}</div>",
                        unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f"<div style='text-align:center;'>{badge(e.qr_status)}</div>",
                        unsafe_allow_html=True)
        with cols[4]:
            # 최근 점검일 + 건강상태(점검 결과) 병합 — 가운데 정렬
            date_txt = fmt_date(e.last_inspection) if e.last_inspection else "미점검"
            st.markdown(
                f"<div style='color:#334155; text-align:center;'>{date_txt}</div>"
                f"<div style='margin-top:0.15rem; text-align:center;'>"
                f"{badge(e.health_status)}</div>",
                unsafe_allow_html=True,
            )
        with cols[5]:
            # 점검 이력 — 완료 점검 횟수 표시 + 클릭 시 이력 팝업
            hist = _equipment_history(e, all_tasks, all_defs)
            hist_label = f"이력 {len(hist)}회" if hist else "이력 —"
            if st.button(hist_label, key=f"hist_btn_{e.equipment_id}",
                         use_container_width=True):
                open_status_for = e.equipment_id
        with cols[6]:
            if st.button("속성", key=f"qr_btn_{e.equipment_id}", use_container_width=True):
                _qr_dialog(e.equipment_id)

    if open_status_for:
        _status_dialog(open_status_for)

    foot_l, _, foot_r = st.columns([3, 4, 1])
    with foot_l:
        st.markdown(
            f"<div style='color:#64748B; font-size:0.85rem; padding-top:0.6rem;'>"
            f"{kpi['total']:,}개 중 {len(rows)}개 표시</div>",
            unsafe_allow_html=True,
        )
    with foot_r:
        c1, c2 = st.columns(2)
        c1.button("‹", key="eq_prev", use_container_width=True)
        c2.button("›", key="eq_next", use_container_width=True)
