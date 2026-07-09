"""Report Center — 별지5/6/9 PDF 자동 출력 (단일 통합 Table 양식)."""
from __future__ import annotations

from io import BytesIO

import streamlit as st

from lib import data
from lib.fonts import ensure_korean_fonts, is_korean_font_registered
from lib.qr import sticker_sheet_pdf
from lib.ui import page_header


# ---------- 사진 셀 헬퍼 ----------

def _photo_image(photo_bytes: bytes | None, *, max_w_mm: float, max_h_mm: float):
    """업로드된 photo_bytes를 ReportLab Image로 변환. 비율 유지."""
    if not photo_bytes:
        return None
    try:
        from PIL import Image as PILImage
        from reportlab.lib.units import mm
        from reportlab.platypus import Image as RImage

        img = PILImage.open(BytesIO(photo_bytes))
        iw, ih = img.size
        # mm 기준 한계 vs 이미지 비율
        max_w_pt = max_w_mm * mm
        max_h_pt = max_h_mm * mm
        scale = min(max_w_pt / iw, max_h_pt / ih)
        return RImage(BytesIO(photo_bytes), width=iw * scale, height=ih * scale)
    except Exception:
        return None


# ---------- 공통 ParagraphStyle ----------

def _styles():
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle

    font_normal, font_bold = ensure_korean_fonts()
    return {
        "title": ParagraphStyle("title", fontName=font_bold, fontSize=13, leading=18, alignment=TA_LEFT),
        "inner_title": ParagraphStyle("inner_title", fontName=font_bold, fontSize=12, leading=16, alignment=TA_CENTER, textColor="white"),
        "h": ParagraphStyle("h", fontName=font_bold, fontSize=9.5, leading=12, alignment=TA_CENTER),
        "section": ParagraphStyle("section", fontName=font_bold, fontSize=10, leading=14, alignment=TA_CENTER),
        "cell": ParagraphStyle("cell", fontName=font_normal, fontSize=9, leading=12, alignment=TA_CENTER),
        "left": ParagraphStyle("left", fontName=font_normal, fontSize=9, leading=12, alignment=TA_LEFT),
    }


# ---------- 별지5 안전점검 결과 지적내역서 ----------

def _build_pdf_byeolji5(round_id: str | None = None) -> bytes:
    """별지5 PDF. round_id 지정 시 그 회차의 지적사항만 필터링."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    COL_W = [22 * mm, 42 * mm, 60 * mm, 28 * mm, 28 * mm]  # 180mm 합

    # 행 데이터 구성
    rows = []
    row_heights = []
    bg_styles = []
    span_styles = []

    # row 0: 제목 (span 5)
    rows.append([Paragraph("별지 5 안전점검 결과 지적내역서", s["title"]), "", "", "", ""])
    row_heights.append(11 * mm)
    span_styles.append(("SPAN", (0, 0), (-1, 0)))

    # row 1: 점검일 | date(span 1-2) | 점검자 | name
    rows.append([
        Paragraph("점검일", s["h"]),
        Paragraph("2026년 05월 12일", s["cell"]), "",
        Paragraph("점검자", s["h"]),
        Paragraph("박소방 (서명)", s["cell"]),
    ])
    row_heights.append(10 * mm)
    span_styles.append(("SPAN", (1, 1), (2, 1)))
    bg_styles.append(("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#F1F5F9")))
    bg_styles.append(("BACKGROUND", (3, 1), (3, 1), colors.HexColor("#F1F5F9")))

    # row 2-3: 본문 헤더
    rows.append([
        Paragraph("장소<br/>(구역)", s["h"]),
        Paragraph("점검종류", s["h"]),
        Paragraph("지적사항", s["h"]),
        Paragraph("현장조치 결과", s["h"]), "",
    ])
    row_heights.append(7 * mm)
    rows.append([
        "", "", "",
        Paragraph("완료<br/>확인자", s["h"]),
        Paragraph("불가<br/>통보서 번호", s["h"]),
    ])
    row_heights.append(12 * mm)
    span_styles.append(("SPAN", (0, 2), (0, 3)))
    span_styles.append(("SPAN", (1, 2), (1, 3)))
    span_styles.append(("SPAN", (2, 2), (2, 3)))
    span_styles.append(("SPAN", (3, 2), (4, 2)))
    bg_styles.append(("BACKGROUND", (0, 2), (-1, 3), colors.HexColor("#F1F5F9")))

    # 데이터 행
    types_all = ["임시소방시설", "피난로 등", "화기취급감독"]
    deficiencies = data.load_deficiencies()
    # task_id → equipment_label 매핑 (지적사항 컬럼 prefix용)
    task_label_map = {t.task_id: t.equipment_label for t in data.load_tasks()}
    if round_id:
        round_tasks = {t.task_id for t in data.tasks_of_round(round_id, include_excluded=True)}
        deficiencies = [d for d in deficiencies if d.task_id in round_tasks]
    data_start = len(rows)
    for d in deficiencies:
        type_lines = [
            f"• {t}( {'O' if t in d.inspection_types else '&nbsp;'} )" for t in types_all
        ]
        # 지적사항 컬럼 형식: "장비명 (양호 또는 지적내용)" — v1.5+
        # v1.6: defect_codes 카탈로그가 있으면 "불량 — 사유: ..." 형태로 명시
        # v1.7: checklist_items의 NG 항목을 요약해 함께 표시
        eq_label = task_label_map.get(d.task_id, "")
        is_good = (d.resolution == "완료" and not d.notice_no)
        # NG 항목 추출: "카테고리|항목" 또는 "항목" 형식 키에서 "|" 이후만 사용
        ng_items = []
        ci = getattr(d, "checklist_items", None) or {}
        for k, v in ci.items():
            if str(v).upper() == "NG":
                label = k.split("|", 1)[1] if "|" in k else k
                ng_items.append(label)
        ng_summary = ", ".join(ng_items)
        if is_good:
            body = "양호"
        elif d.defect_codes:
            codes_display = [
                c if c != "기타" else (f"기타: {d.defect_other}" if d.defect_other else "기타")
                for c in d.defect_codes
            ]
            reasons = " · ".join(codes_display)
            # issue가 사유 join + ' — 추가내용' 형식이면 추가내용만 분리해 덧붙임
            extra = ""
            if d.issue and " — " in d.issue:
                extra = d.issue.split(" — ", 1)[1].strip()
            body = f"불량 — 사유: {reasons}"
            if extra:
                body = f"{body} ({extra})"
            if ng_summary:
                body = f"{body} [NG: {ng_summary}]"
        elif ng_summary:
            body = f"불량 — NG: {ng_summary}"
        else:
            body = d.issue or "지적사항 없음"
        issue_text = f"{eq_label} ({body})" if eq_label else body
        rows.append([
            Paragraph(f"{d.floor}<br/>{d.zone}", s["cell"]),
            Paragraph("<br/>".join(type_lines), s["left"]),
            Paragraph(issue_text, s["left"]),
            Paragraph(d.confirmer or "", s["cell"]) if d.resolution == "완료" else "",
            Paragraph(d.notice_no or "", s["cell"]) if d.resolution == "불가" else "",
        ])
        row_heights.append(18 * mm)

    # 빈 행 8개
    for _ in range(8):
        rows.append(["", "", "", "", ""])
        row_heights.append(18 * mm)

    # Table 생성 + 스타일
    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BOX", (0, 0), (-1, 0), 1.2, colors.black),  # 제목 박스 진하게
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, data_start), (-1, -1), 3),
        ("RIGHTPADDING", (0, data_start), (-1, -1), 3),
        ("TOPPADDING", (0, data_start), (-1, -1), 3),
        ("BOTTOMPADDING", (0, data_start), (-1, -1), 3),
        # 제목 셀 좌측 정렬 padding
        ("LEFTPADDING", (0, 0), (0, 0), 4 * mm),
    ] + bg_styles + span_styles

    main = Table(rows, colWidths=COL_W, rowHeights=row_heights, repeatRows=4)
    main.setStyle(TableStyle(style_cmds))

    doc.build([main])
    return buf.getvalue()


# ---------- 별지6 안전점검 조치 결과 통보서 ----------
# v1.5: 자료원이 Notice → Deficiency.action_* 로 변경됨 (별지6 데이터 흡수).
# 출력 양식은 동일 — 보고서 내용 변경 없음.

def _byeolji6_get_photo(item) -> bytes | None:
    """Deficiency 또는 Notice 양쪽에서 조치 사진 bytes를 가져옴 (호환)."""
    # 신모델: Deficiency.action_photo_path → Storage 다운로드
    path = getattr(item, "action_photo_path", None)
    if path:
        try:
            return data._db().storage.from_(data.ACTION_PHOTO_BUCKET).download(path)
        except Exception:
            return None
    # 구모델: Notice 객체면 기존 헬퍼
    if hasattr(item, "notice_no") and hasattr(data, "get_action_photo"):
        try:
            return data.get_action_photo(item)
        except Exception:
            return None
    return None


def _byeolji6_table(item):
    """단일 통보서를 표현하는 ReportLab Table 1개를 반환.
    item: v1.5 Deficiency(action_* 흡수) 또는 구 Notice 객체.
    합본 PDF 구성 시 통보서 사이에 PageBreak()를 삽입해 이어붙인다."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4  # noqa: F401 (col width 단위 정합)
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle

    s = _styles()
    COL_W = [22 * mm, 38 * mm, 60 * mm, 60 * mm]  # 180mm 합

    n = item
    notice_no = (n.notice_no if n else "") or ""
    inspection_date = n.inspection_date.strftime("%Y년 %m월 %d일") if n else ""
    submitter = (getattr(n, "submitter", None) or "박소방") if n else ""
    confirmer = (n.confirmer if n and n.confirmer else "김소장") if n else ""

    # 점검 종류: Notice는 inspection_type(단수), Deficiency는 inspection_types(복수)
    if n:
        if hasattr(n, "inspection_type") and getattr(n, "inspection_type", None):
            insp_type = n.inspection_type
        elif hasattr(n, "inspection_types") and n.inspection_types:
            insp_type = ", ".join(n.inspection_types)
        else:
            insp_type = ""
    else:
        insp_type = ""

    rows = []
    row_heights = []
    bg_styles = []
    span_styles = []

    # row 0: 제목 (span 4)
    rows.append([Paragraph("별지 6 안전점검 조치 결과 통보서", s["title"]), "", "", ""])
    row_heights.append(11 * mm)
    span_styles.append(("SPAN", (0, 0), (-1, 0)))

    # row 1: 점검일 | date | 통보서 번호 | notice no
    rows.append([
        Paragraph("점검일", s["h"]),
        Paragraph(inspection_date, s["cell"]),
        Paragraph("통보서 번호", s["h"]),
        Paragraph(notice_no, s["cell"]),
    ])
    row_heights.append(10 * mm)
    bg_styles.append(("BACKGROUND", (0, 1), (0, 1), colors.HexColor("#F1F5F9")))
    bg_styles.append(("BACKGROUND", (2, 1), (2, 1), colors.HexColor("#F1F5F9")))

    # row 2: 본문 헤더
    rows.append([
        Paragraph("장소<br/>(구역)", s["h"]),
        Paragraph("점검종류", s["h"]),
        Paragraph("지적사항", s["h"]),
        Paragraph("조치 결과 사진", s["h"]),
    ])
    row_heights.append(9 * mm)
    bg_styles.append(("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F1F5F9")))

    # row 3: 데이터 + 조치 결과 사진 (있으면 임베드)
    if n:
        photo_cell = _photo_image(_byeolji6_get_photo(n), max_w_mm=58, max_h_mm=70)
        if photo_cell is None:
            photo_cell = Paragraph("사진첨부", s["cell"])
        rows.append([
            Paragraph(f"{n.floor}<br/>{n.zone}", s["cell"]),
            Paragraph(insp_type, s["cell"]),
            Paragraph(n.issue, s["left"]),
            photo_cell,
        ])
    else:
        rows.append(["", "", "", ""])
    row_heights.append(75 * mm)

    # row 4: 조치 내용 / 완료일 (있으면 표시)
    if n and getattr(n, "action_done", False):
        rows.append([
            Paragraph("조치<br/>완료일", s["h"]),
            Paragraph(n.action_at.isoformat() if n.action_at else "-", s["cell"]),
            Paragraph(f"<b>조치 내용</b><br/>{n.action_note or '-'}", s["left"]),
            Paragraph(f"확인자<br/><b>{confirmer}</b>", s["cell"]),
        ])
        bg_styles.append(("BACKGROUND", (0, 3), (0, 3), colors.HexColor("#F1F5F9")))
    else:
        rows.append(["", "", "", ""])
    row_heights.append(40 * mm)

    # row 5: 푸터 (제출자 | 박소방 | 확인자 | 김소장)
    rows.append([
        Paragraph("제출자", s["h"]),
        Paragraph(f"{submitter} (서명)", s["cell"]),
        Paragraph("확인자", s["h"]),
        Paragraph(f"{confirmer} (서명)", s["cell"]),
    ])
    row_heights.append(12 * mm)
    bg_styles.append(("BACKGROUND", (0, 5), (0, 5), colors.HexColor("#F1F5F9")))
    bg_styles.append(("BACKGROUND", (2, 5), (2, 5), colors.HexColor("#F1F5F9")))

    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BOX", (0, 0), (-1, 0), 1.2, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 4 * mm),
        ("LEFTPADDING", (0, 3), (-1, 4), 3),
        ("RIGHTPADDING", (0, 3), (-1, 4), 3),
    ] + bg_styles + span_styles

    main = Table(rows, colWidths=COL_W, rowHeights=row_heights)
    main.setStyle(TableStyle(style_cmds))
    return main


def _build_pdf_byeolji6_multi(notices) -> bytes:
    """여러 통보서를 한 PDF에 페이지별로 이어붙여 출력. notices가 비면
    빈 PDF (단건 함수와 동일한 안전 동작)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, SimpleDocTemplate

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    flowables = []
    items = list(notices) if notices else [None]
    for idx, n in enumerate(items):
        flowables.append(_byeolji6_table(n))
        if idx < len(items) - 1:
            flowables.append(PageBreak())
    doc.build(flowables)
    return buf.getvalue()


def _build_pdf_byeolji6(notice=None) -> bytes:
    """별지6 통보서 PDF (단건). v1.5: 자료원은 Deficiency.action_*.
    notice 미지정 시 최신 1건(통보서 발급 + 조치 완료) 의 Deficiency."""
    if notice is None:
        defs = [
            d for d in data.load_deficiencies()
            if d.notice_no and d.action_done
        ]
        notice = defs[0] if defs else None
    return _build_pdf_byeolji6_multi([notice])


# ---------- 별지9 소방시설 오동작 관리대장 ----------

TEMP_CATEGORIES = ["소화기", "간이소화장치", "비상경보장치", "가스누설경보기", "간이피난유도선", "방화포"]
OTHER_CATEGORIES = ["감지기", "발신기", "수신기", "확산소화기", "유도등", "기타"]


def _build_pdf_byeolji9() -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    COL_W = [32 * mm, 22 * mm, 70 * mm, 28 * mm, 28 * mm]  # 180mm 합

    rows = []
    row_heights = []
    bg_styles = []
    span_styles = []

    # row 0: 외부 제목 (span 5)
    rows.append([Paragraph("별지 9 소방시설 오동작 관리대장", s["title"]), "", "", "", ""])
    row_heights.append(11 * mm)
    span_styles.append(("SPAN", (0, 0), (-1, 0)))

    # row 1: 내부 타이틀 (남색 배경, span 5)
    rows.append([Paragraph("소방시설 오동작 관리대장", s["inner_title"]), "", "", "", ""])
    row_heights.append(11 * mm)
    span_styles.append(("SPAN", (0, 1), (-1, 1)))
    bg_styles.append(("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#1E3A8A")))

    # row 2: 헤더
    rows.append([
        Paragraph("소방시설 구분", s["h"]),
        Paragraph("일자", s["h"]),
        Paragraph("오동작내용", s["h"]),
        Paragraph("조치결과", s["h"]),
        Paragraph("확인자", s["h"]),
    ])
    row_heights.append(9 * mm)
    bg_styles.append(("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F1F5F9")))

    # 실제 데이터 행
    malfunctions = data.load_malfunctions()
    for m in malfunctions:
        rows.append([
            Paragraph(m.category, s["cell"]),
            Paragraph(m.occurred_on.strftime("%y.%m.%d"), s["cell"]),
            Paragraph(m.detail, s["left"]),
            Paragraph(m.action, s["cell"]),
            Paragraph(m.confirmer, s["cell"]),
        ])
        row_heights.append(10 * mm)

    # 임시소방시설 6종 라벨 + 6개 빈 행
    temp_label_idx = len(rows)
    rows.append([Paragraph("임시소방시설 6가지 (법적기준)", s["section"]), "", "", "", ""])
    row_heights.append(9 * mm)
    span_styles.append(("SPAN", (0, temp_label_idx), (-1, temp_label_idx)))
    bg_styles.append(("BACKGROUND", (0, temp_label_idx), (-1, temp_label_idx), colors.HexColor("#E2E8F0")))

    for cat in TEMP_CATEGORIES:
        rows.append([Paragraph(cat, s["cell"]), "", "", "", ""])
        row_heights.append(10 * mm)

    # 그 외 소방시설 라벨 + 6개 빈 행
    other_label_idx = len(rows)
    rows.append([Paragraph("그 외 소방시설", s["section"]), "", "", "", ""])
    row_heights.append(9 * mm)
    span_styles.append(("SPAN", (0, other_label_idx), (-1, other_label_idx)))
    bg_styles.append(("BACKGROUND", (0, other_label_idx), (-1, other_label_idx), colors.HexColor("#E2E8F0")))

    for cat in OTHER_CATEGORIES:
        rows.append([Paragraph(cat, s["cell"]), "", "", "", ""])
        row_heights.append(10 * mm)

    style_cmds = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("BOX", (0, 0), (-1, 0), 1.2, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 4 * mm),
        ("LEFTPADDING", (0, 3), (-1, -1), 3),
        ("RIGHTPADDING", (0, 3), (-1, -1), 3),
    ] + bg_styles + span_styles

    main = Table(rows, colWidths=COL_W, rowHeights=row_heights, repeatRows=3)
    main.setStyle(TableStyle(style_cmds))

    doc.build([main])
    return buf.getvalue()


# ---------- 페이지 렌더 ----------

def render() -> None:
    page_header(
        "보고서",
        "현장 점검 완료 시 별지5·별지6·별지9 PDF 자동 출력 (서류 작업 대체).",
    )

    ensure_korean_fonts()
    if not is_korean_font_registered():
        with st.expander("한글 폰트 진단 (관리자용)", expanded=False):
            st.warning(
                "한글 폰트(NanumGothic / 시스템 폰트) 등록 실패. PDF의 한글이 □로 출력될 수 있습니다."
            )

    def _card_header(name: str, sub: str) -> str:
        return (
            "<div style='background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px 12px 0 0;"
            " padding:1rem 1.1rem 0.5rem; border-bottom:none;'>"
            f"<div style='font-weight:700; color:#0F172A; font-size:1.1rem;'>{name}</div>"
            f"<div style='color:#64748B; font-size:0.88rem; margin-top:0.3rem;'>{sub}</div>"
            "</div>"
        )

    def _section_title(name: str, desc: str) -> None:
        st.markdown(
            f"<div style='font-weight:700; color:#0F172A; font-size:1.05rem;'>{name}</div>"
            f"<div style='color:#64748B; font-size:0.88rem; margin:0.2rem 0 0.6rem;'>{desc}</div>",
            unsafe_allow_html=True,
        )

    def _spacer(h: str = "1.4rem") -> None:
        st.markdown(f"<div style='height:{h};'></div>", unsafe_allow_html=True)

    # ---------- 별지5 ----------
    _section_title("별지5 · 안전점검 결과 지적내역서",
                   "점검이 완료된(결과 입력된) 지적사항을 PDF로 출력합니다. "
                   "전체 또는 특정 회차를 선택할 수 있습니다.")
    _, mid5, _ = st.columns([1, 2, 1])
    with mid5:
        st.markdown(_card_header("별지5", "안전점검 결과 지적내역서"), unsafe_allow_html=True)
        # 출력 범위 — 전체 또는 특정 회차만 (round_id 필터). 출력 기준은 점검 완료(Deficiency) 유지
        _task_round = {t.task_id: t.round_id for t in data.load_tasks() if t.round_id}
        _cnt: dict[str, int] = {}
        for _d in data.load_deficiencies():
            _rid = _task_round.get(_d.task_id)
            if _rid:
                _cnt[_rid] = _cnt.get(_rid, 0) + 1
        _opts = {"전체 (모든 회차)": None}
        for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
            if getattr(_r, "cancelled", False):
                continue  # 취소 회차 제외
            _opts[f"{_r.round_id} · {_r.task_type} · {_cnt.get(_r.round_id, 0)}건"] = _r.round_id
        _sel_label = st.selectbox("출력 범위", list(_opts.keys()), key="byeolji5_scope")
        _sel_round = _opts[_sel_label]
        _fname = (f"별지 5. 안전점검 결과 지적 내역서 - {_sel_round}.pdf"
                  if _sel_round else "별지 5. 안전점검 결과 지적 내역서.pdf")
        st.download_button(
            "Download 별지5 PDF",
            data=_build_pdf_byeolji5(_sel_round),
            file_name=_fname,
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
    _spacer()

    # ---------- 별지6 ----------
    _section_title("별지6 · 안전점검 조치 결과 통보서",
                   "조치 완료된 통보서를 전체 또는 특정 회차로 묶어 PDF로 출력합니다. "
                   "사진과 조치 내용이 자동 포함됩니다.")
    _, mid6, _ = st.columns([1, 2, 1])
    with mid6:
        st.markdown(_card_header("별지6", "안전점검 조치 결과 통보서"), unsafe_allow_html=True)
        # v1.5: 자료원이 Notice → Deficiency.action_*. 통보서가 발급된(notice_no) +
        # 조치 완료(action_done)된 Deficiency가 별지6 출력 대상.
        all_defs = [d for d in data.load_deficiencies() if d.notice_no]
        done = [d for d in all_defs if d.action_done]
        pending = [d for d in all_defs if not d.action_done]
        if not all_defs:
            st.info("발급된 통보서가 없습니다.")
        elif not done:
            st.warning(
                f"발급된 통보서 {len(pending)}건 — 모두 조치 미완료. "
                "**지적 관리**에서 '조치 폼'을 먼저 작성하세요."
            )
        else:
            # 출력 범위 — 전체 또는 특정 회차 (별지5와 동일 드롭다운 패턴).
            # 회차 매핑은 task_id → round_id, 카운트는 조치 완료 통보서 기준.
            _task_round6 = {t.task_id: t.round_id for t in data.load_tasks() if t.round_id}
            _cnt6: dict[str, int] = {}
            for _d in done:
                _rid6 = _task_round6.get(_d.task_id)
                if _rid6:
                    _cnt6[_rid6] = _cnt6.get(_rid6, 0) + 1
            _opts6 = {f"전체 (모든 회차 · {len(done)}건)": None}
            for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
                if getattr(_r, "cancelled", False):
                    continue  # 취소 회차 제외
                if _cnt6.get(_r.round_id, 0) > 0:
                    _opts6[f"{_r.round_id} · {_r.task_type} · {_cnt6[_r.round_id]}건"] = _r.round_id
            _sel_label6 = st.selectbox("출력 범위", list(_opts6.keys()),
                                       key="byeolji6_scope")
            _sel_round6 = _opts6[_sel_label6]
            if _sel_round6:
                _round_tasks6 = {
                    t.task_id
                    for t in data.tasks_of_round(_sel_round6, include_excluded=True)
                }
                sel_notices = [d for d in done if d.task_id in _round_tasks6]
            else:
                sel_notices = done

            n_sel = len(sel_notices)
            _today6 = data.TODAY.isoformat()
            if _sel_round6:
                _fname6 = (f"별지 6. 안전점검 조치 결과 통보서 "
                           f"({_sel_round6}, {n_sel}건).pdf")
            else:
                _fname6 = (f"별지 6. 안전점검 조치 결과 통보서 "
                           f"(전체 {n_sel}건, {_today6}).pdf")
            _btn_label6 = (f"Download 별지6 합본 PDF · {n_sel}건" if n_sel > 1
                           else f"Download 별지6 PDF · {n_sel}건")
            st.download_button(
                _btn_label6,
                data=_build_pdf_byeolji6_multi(sel_notices),
                file_name=_fname6,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="notice_dl",
            )

            if pending:
                st.markdown(
                    f"<div style='color:#94A3B8; font-size:0.78rem; margin-top:0.3rem;'>"
                    f"조치 대기 {len(pending)}건 (지적 관리에서 처리)</div>",
                    unsafe_allow_html=True,
                )
    _spacer()

    # ---------- 별지9 ----------
    _section_title("별지9 · 소방시설 오동작 관리대장",
                   "임시소방시설 6종 + 기타 6종 카테고리의 오동작 기록을 PDF로 출력합니다.")
    _, mid9, _ = st.columns([1, 2, 1])
    with mid9:
        st.markdown(_card_header("별지9", "소방시설 오동작 관리대장"), unsafe_allow_html=True)
        st.download_button(
            "Download 별지9 PDF",
            data=_build_pdf_byeolji9(),
            file_name="별지 9. 소방시설 오동작 관리대장.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
    _spacer()

    # ---------- QR 스티커 ----------
    _section_title("QR 스티커",
                   "전체 장비의 QR 스티커를 A4 한 페이지당 4×6 그리드(24개)로 출력합니다.")
    _, midq, _ = st.columns([1, 2, 1])
    with midq:
        st.markdown(_card_header("QR 스티커 시트", "전체 장비 · A4 4×6 그리드"), unsafe_allow_html=True)
        st.download_button(
            "Download QR 스티커 시트",
            data=sticker_sheet_pdf(data.load_equipment()),
            file_name="QR 스티커 시트 (4x6).pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
