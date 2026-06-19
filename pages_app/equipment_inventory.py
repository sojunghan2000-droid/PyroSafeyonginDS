"""시설 관리 페이지 — 테이블 각 행에 QR 모달 진입 버튼."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from lib import auth, data
from lib.data import TASK_INSPECTION_TYPES
from lib.inspection_dialog import EQ_FLOORS, equipment_dialog
from lib.qr import make_qr, payload_for, qr_png_bytes, sticker_sheet_pdf
from lib.ui import badge, fmt_date, page_header, render_kpi_row


# 테이블 컬럼 비율 (총합 = 1) — 작업 상태 컬럼 신설
COL_RATIOS = [1.0, 1.8, 0.9, 1.0, 0.9, 1.2, 0.9]


def _table_header_html() -> str:
    return (
        "<div style='display:grid; "
        f"grid-template-columns: {' '.join(f'{r}fr' for r in COL_RATIOS)}; "
        "gap: 0.4rem; padding: 0.6rem 0.4rem; "
        "color:#64748B; font-size:0.78rem; font-weight:600; "
        "border-bottom:1px solid #E2E8F0;'>"
        "<div>위치 ID</div>"
        "<div>시설 종류</div>"
        "<div>QR 상태</div>"
        "<div>최근 점검일</div>"
        "<div>Inspection Status</div>"
        "<div>작업 상태</div>"
        "<div>작업</div>"
        "</div>"
    )


# 작업 상태 칩 — 색상 + 라벨 우선순위 매핑
def _work_chip(eq, tasks, notices) -> tuple[str, str]:
    """장비별 가장 시급한 단건 칩 (color, label).
    우선순위: 통보서 대기 > 지연 > 진행 > 예정 > 최근 완료 > 작업 없음."""
    # 통보서 대기 (floor/zone 매칭 — 장비-통보서 직접 FK가 없으므로 위치 기준)
    pending_notices = sum(
        1 for n in notices
        if not n.action_done and n.floor == eq.floor and n.zone == eq.zone
    )
    if pending_notices:
        return "#DC2626", f"통보서 대기 {pending_notices}"

    # 장비 매칭 task — equipment_label에 location_id 또는 equipment_name 포함
    matching = [
        t for t in tasks
        if eq.location_id in t.equipment_label or eq.equipment_name in t.equipment_label
    ]
    overdue = [t for t in matching if t.status == "Overdue"]
    if overdue:
        return "#DC2626", f"지연 {len(overdue)}"
    in_prog = [t for t in matching if t.status == "In Progress"]
    if in_prog:
        return "#F97316", f"진행 {len(in_prog)}"
    scheduled = [t for t in matching if t.status == "Scheduled"]
    if scheduled:
        return "#3B82F6", f"예정 {len(scheduled)}"
    completed = [t for t in matching if t.status == "Completed"]
    if completed:
        last = max(t.due_date for t in completed)
        days = (data.TODAY - last).days
        return "#10B981", f"완료 ({days}d 전)" if days >= 0 else "완료"
    return "#94A3B8", "작업 없음"


def _work_chip_html(color: str, label: str) -> str:
    return (
        f"<div style='display:inline-block; padding:0.18rem 0.55rem; "
        f"border:1px solid {color}; color:{color}; background:{color}10; "
        f"border-radius:999px; font-size:0.78rem; font-weight:600;'>"
        f"{label}</div>"
    )


@st.dialog("점검 현황", width="large")
def _status_dialog(equipment_id: str) -> None:
    """장비별 점검 일정·지적사항·통보서 이력 (읽기 전용)."""
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
    matching_defs = [d for d in defs if d.floor == eq.floor and d.zone == eq.zone]

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

    # ── 점검 일정 ──
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem; "
        f"margin:0.7rem 0 0.3rem;'>점검 일정 ({len(matching_tasks)}건)</div>",
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

    # ── 지적사항 / 통보서 ──
    st.markdown(
        f"<div style='font-weight:700; color:#0F172A; font-size:1rem; "
        f"margin:1rem 0 0.3rem;'>지적사항 / 통보서 ({len(matching_defs) + len(matching_notices)}건)</div>",
        unsafe_allow_html=True,
    )
    if matching_defs or matching_notices:
        rows = []
        for d in matching_defs:
            rows.append(("지적", d.inspection_date, d.issue, d.resolution, d.notice_no or "-"))
        for n in matching_notices:
            status_text = "조치 완료" if n.action_done else "조치 대기"
            rows.append(("통보서", n.inspection_date, n.issue, status_text, n.notice_no))
        rows.sort(key=lambda r: r[1] or data.TODAY, reverse=True)
        header = (
            "<table style='width:100%; border-collapse:collapse;'>"
            "<thead><tr style='color:#64748B; font-size:0.78rem; text-align:left; "
            "border-bottom:1px solid #E2E8F0;'>"
            "<th style='padding:0.4rem 0.3rem;'>구분</th>"
            "<th style='padding:0.4rem 0.3rem;'>일자</th>"
            "<th style='padding:0.4rem 0.3rem;'>내용</th>"
            "<th style='padding:0.4rem 0.3rem;'>상태</th>"
            "<th style='padding:0.4rem 0.3rem;'>통보서 번호</th>"
            "</tr></thead><tbody>"
        )
        body = "".join(
            "<tr style='border-bottom:1px solid #F1F5F9;'>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{kind}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#334155;'>{fmt_date(dt)}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#0F172A;'>{issue}</td>"
            f"<td style='padding:0.5rem 0.3rem;'>{badge(status)}</td>"
            f"<td style='padding:0.5rem 0.3rem; color:#475569; font-size:0.8rem;'>{notice_no}</td>"
            "</tr>"
            for (kind, dt, issue, status, notice_no) in rows
        )
        st.markdown(header + body + "</tbody></table>", unsafe_allow_html=True)
    else:
        st.info("이 장비/구역에서 발급된 지적사항·통보서가 없습니다.")

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
        st.success("새 장비가 등록되었습니다. 테이블에서 QR을 확인하고 라벨을 인쇄하세요.")

    if eq_btn_clicked:
        equipment_dialog()

    render_kpi_row([
        ("전체 시설", f"{kpi['total']:,}", f"이번 달 +{kpi['new_this_month']}건", "default"),
        ("최근 점검 (지난 48시간)", f"{kpi['recently_inspected']:,}", "", "default"),
        ("미조치 항목", f"{kpi['pending_issues']}", "긴급 점검 알림", "alert"),
        ("QR 적용률", f"{kpi['qr_coverage']:.1f}%", "QR 부착률", "default"),
    ])

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    f1, f2, _, tab_col = st.columns([0.8, 0.8, 0.4, 3.5])
    with f1:
        floor_filter = st.selectbox(
            "Filter",
            ["전체 층"] + sorted({e.floor for e in eq}),
            label_visibility="collapsed",
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

    # ---------- 테이블 (st.columns 기반) ----------
    st.markdown(_table_header_html(), unsafe_allow_html=True)

    # 작업 상태 계산용 전체 task/notice 한 번만 로드
    all_tasks = data.load_tasks()
    all_notices = data.load_notices()

    # 클릭 처리는 루프 후 마지막 한 번만 (dialog는 한 번에 하나)
    open_status_for: str | None = None

    for e in rows:
        cols = st.columns(COL_RATIOS, vertical_alignment="center")
        with cols[0]:
            st.markdown(
                f"<span style='font-weight:600; color:#0F172A;'>{e.location_id}</span>",
                unsafe_allow_html=True,
            )
        with cols[1]:
            st.markdown(
                f"<div style='font-weight:600; color:#0F172A;'>{e.equipment_name}</div>"
                f"<div style='color:#64748B; font-size:0.8rem;'>SN: {e.serial}</div>",
                unsafe_allow_html=True,
            )
        with cols[2]:
            st.markdown(badge(e.qr_status), unsafe_allow_html=True)
        with cols[3]:
            st.markdown(
                f"<span style='color:#334155;'>{fmt_date(e.last_inspection)}</span>",
                unsafe_allow_html=True,
            )
        with cols[4]:
            st.markdown(badge(e.health_status), unsafe_allow_html=True)
        with cols[5]:
            color, label = _work_chip(e, all_tasks, all_notices)
            # 칩 클릭 = 점검 현황 팝업. 버튼 라벨로 칩 디자인 흉내내기 위해 secondary 버튼 + CSS는 어려우므로
            # 시각적 칩 표시 + 별도 버튼 두 줄. 한 줄에 모두 담기 위해 버튼 라벨 자체에 라벨 사용.
            if st.button(label, key=f"status_btn_{e.equipment_id}",
                         use_container_width=True):
                open_status_for = e.equipment_id
        with cols[6]:
            if st.button("QR", key=f"qr_btn_{e.equipment_id}", use_container_width=True):
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
