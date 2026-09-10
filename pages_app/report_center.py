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
    # 260907: 가설컨테이너 사무실 점검은 별지5 법정 3종에 해당하지 않아 여기서 제외하고
    # "점검결과 보고 · 사진대지"에서 다룬다.
    deficiencies = [
        d for d in deficiencies
        if data.INSPECTION_KIND_CONTAINER not in d.inspection_types
    ]
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
    """Deficiency 또는 Notice 양쪽에서 조치 사진 bytes를 가져옴 (호환).
    Deficiency는 action_photo_path(조치 후) 우선, 없으면 photo_path(발견 시) 폴백
    — 조치 미확정(action_immediate=False) 상태에서도 최소 발견 사진은 표시."""
    # 신모델: Deficiency.action_photo_path → Storage 다운로드 (없으면 photo_path 폴백)
    path = getattr(item, "action_photo_path", None) or getattr(item, "photo_path", None)
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


# ---------- 사진 다운로드 공용 헬퍼 (photo_path/action_photo_path/inspection_photo_path 공용) ----------

def _download_photo(path: str | None) -> bytes | None:
    """임의의 Storage 경로에서 사진 bytes를 가져옴."""
    if not path:
        return None
    try:
        return data._db().storage.from_(data.ACTION_PHOTO_BUCKET).download(path)
    except Exception:
        return None


# ---------- 점검결과 보고 / 사진대지 전·후 — 260907 신규 (분리된 독립 PDF 2종) ----------

def _report_photos_for(d) -> tuple[str | None, str | None]:
    """점검결과 보고용 대표 사진(최대 2장) — 결과 무관 점검사진 우선, 없으면 조치 전/후
    사진으로 대체. 1/2번째는 같은 종류에서만 짝지어 반환한다(종류를 섞지 않음)."""
    if d.inspection_photo_path:
        return d.inspection_photo_path, d.inspection_photo_path2
    if d.photo_path:
        return d.photo_path, d.photo_path2
    if d.action_photo_path:
        return d.action_photo_path, d.action_photo_path2
    return None, None


def _build_pdf_inspection_photo_report(round_id: str | None = None) -> bytes:
    """점검결과 보고 — 사진이 하나라도 등록된 점검은 전부(점검종류 구분 없이) 포함."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle, Spacer

    s = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )

    deficiencies = data.load_deficiencies()
    if round_id:
        round_tasks = {t.task_id for t in data.tasks_of_round(round_id, include_excluded=True)}
        deficiencies = [d for d in deficiencies if d.task_id in round_tasks]

    # 사진이 하나라도(inspection_photo_path/photo_path/action_photo_path 무엇이든) 있으면 포함.
    with_any_photo = [d for d in deficiencies if _report_photos_for(d)[0]]

    flowables = []
    flowables.append(Paragraph("점검결과 보고", s["title"]))
    flowables.append(Paragraph(
        "위치사면: ______________&nbsp;&nbsp;&nbsp; 점검일: ______________&nbsp;&nbsp;&nbsp; "
        "점검자: ______________&nbsp;&nbsp;&nbsp; 조치완료일: ______________",
        s["left"],
    ))
    flowables.append(Spacer(1, 3 * mm))
    # 원본 양식 기준: 점검구간 1개당 사진 2칸(점검사진). v1.9(260907): 2번째 사진이 실제로
    # 등록되어 있으면 그대로 채우고, 없으면 비워둔다(수기로 추가 사진을 붙일 여백).
    # 표 틀은 데이터 유무와 무관하게 항상 노출 — 데이터가 없거나 적으면 빈 행으로 채워 최소
    # 5행(별지5의 "빈 행" 관례와 동일한 취지) 이상을 유지한다.
    COL_W_A = [30 * mm, 75 * mm, 75 * mm]  # 180mm 합
    rows = [[Paragraph("점검구간", s["h"]), Paragraph("점검 사진", s["h"]), ""]]
    row_heights = [8 * mm]
    span_styles = [("SPAN", (1, 0), (2, 0))]
    for d in with_any_photo:
        p1, p2 = _report_photos_for(d)
        photo1 = _photo_image(_download_photo(p1), max_w_mm=70, max_h_mm=48)
        photo2 = _photo_image(_download_photo(p2), max_w_mm=70, max_h_mm=48) if p2 else None
        caption = Paragraph(d.issue or "", s["cell"])  # 원본 양식처럼 사진 밑에 설명(지적사항) 표기
        cell1 = [photo1, caption] if photo1 else [caption]
        cell2 = [photo2] if photo2 else [Paragraph("", s["cell"])]
        rows.append([
            Paragraph(f"{d.floor}<br/>{d.zone}", s["cell"]),
            cell1,
            cell2,
        ])
        row_heights.append(60 * mm)
    while len(rows) - 1 < 5:
        rows.append(["", "", ""])
        row_heights.append(60 * mm)
    tbl = Table(rows, colWidths=COL_W_A, rowHeights=row_heights, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
    ] + span_styles))
    flowables.append(tbl)

    doc.build(flowables)
    return buf.getvalue()


def _build_pdf_before_after_report(round_id: str | None = None) -> bytes:
    """사진대지 전/후 — 조치 전 사진(photo_path)이 있는 점검은 전부 포함.
    조치 후 사진(action_photo_path)은 등록되어 있고 조치 전과 다른 사진일 때만 채우고,
    없으면 해당 칸만 비워둔다(행 자체는 제외하지 않음)."""
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

    deficiencies = data.load_deficiencies()
    if round_id:
        round_tasks = {t.task_id for t in data.tasks_of_round(round_id, include_excluded=True)}
        deficiencies = [d for d in deficiencies if d.task_id in round_tasks]

    # "전" 사진(photo_path)이 있으면 전부 포함 — "후"는 있으면 채우고 없으면 빈칸.
    with_before = [d for d in deficiencies if d.photo_path]

    flowables = []
    flowables.append(Paragraph("지적사항 조치 전/후 사진대지", s["title"]))
    # 표 틀은 데이터 유무와 무관하게 항상 노출 — 최소 5행 유지.
    COL_W_B = [30 * mm, 75 * mm, 75 * mm]
    rows = [[Paragraph("점검구간", s["h"]), Paragraph("조치 前", s["h"]), Paragraph("조치 後", s["h"])]]
    row_heights = [8 * mm]
    for d in with_before:
        # v1.9(260907): 전/후 각각 최대 2장(사진2가 있으면 같은 칸에 세로로 함께 표시)
        # + 점검결과 보고와 동일하게 사진 밑에 지적사항(issue) 캡션 표시
        caption_text = d.issue or ""
        before1 = _photo_image(_download_photo(d.photo_path), max_w_mm=70, max_h_mm=22)
        before2 = (
            _photo_image(_download_photo(d.photo_path2), max_w_mm=70, max_h_mm=22)
            if d.photo_path2 else None
        )
        # "전"은 photo_path가 있다고 필터링된 상태라, 사진이 안 뜨면 다운로드 실패로 간주.
        before_photos = [p for p in (before1, before2) if p]
        before_body = before_photos if before_photos else [Paragraph("사진 로드 실패", s["cell"])]
        before_cell = before_body + [Paragraph(caption_text, s["cell"])]

        has_after = d.action_photo_path and d.action_photo_path != d.photo_path
        after1 = (
            _photo_image(_download_photo(d.action_photo_path), max_w_mm=70, max_h_mm=22)
            if has_after else None
        )
        has_after2 = d.action_photo_path2 and d.action_photo_path2 != d.photo_path2
        after2 = (
            _photo_image(_download_photo(d.action_photo_path2), max_w_mm=70, max_h_mm=22)
            if has_after2 else None
        )
        after_photos = [p for p in (after1, after2) if p]
        # 후 사진이 원래 없으면(has_after=False) 빈 칸, 있는데 다운로드만 실패했으면 실패 문구.
        if after_photos:
            after_body = after_photos
        elif has_after or has_after2:
            after_body = [Paragraph("사진 로드 실패", s["cell"])]
        else:
            after_body = [Paragraph("", s["cell"])]
        # 점검결과 보고와 동일하게 캡션은 항상 표시(사진 로드 실패 여부와 무관).
        after_cell = after_body + [Paragraph(caption_text, s["cell"])]

        rows.append([
            Paragraph(f"{d.floor}<br/>{d.zone}", s["cell"]),
            before_cell,
            after_cell,
        ])
        row_heights.append(60 * mm)
    while len(rows) - 1 < 5:
        rows.append(["", "", ""])
        row_heights.append(60 * mm)
    tbl = Table(rows, colWidths=COL_W_B, rowHeights=row_heights, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
    ]))
    flowables.append(tbl)

    doc.build(flowables)
    return buf.getvalue()


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
    mid5, _ = st.columns([2, 1])
    with mid5:
        # 출력 범위 — 전체 또는 특정 회차만 (round_id 필터). 출력 기준은 점검 완료(Deficiency) 유지.
        # 260907: 가설컨테이너 사무실 점검은 별지5 대상이 아니므로 건수에서도 제외(PDF와 일치).
        _task_round = {t.task_id: t.round_id for t in data.load_tasks() if t.round_id}
        _cnt: dict[str, int] = {}
        for _d in data.load_deficiencies():
            if data.INSPECTION_KIND_CONTAINER in _d.inspection_types:
                continue
            _rid = _task_round.get(_d.task_id)
            if _rid:
                _cnt[_rid] = _cnt.get(_rid, 0) + 1
        _opts = {"전체 (모든 회차)": None}
        for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
            if getattr(_r, "cancelled", False) or _r.task_type == data.MAL_ROUND_TYPE:
                continue  # 취소·오동작 접수 회차 제외
            _opts[f"{_r.round_id} · {_r.task_type} · {_cnt.get(_r.round_id, 0)}건"] = _r.round_id
        _scope_col, _btn_col = st.columns([2.2, 1.3], vertical_alignment="bottom")
        with _scope_col:
            _sel_label = st.selectbox("출력 범위", list(_opts.keys()), key="byeolji5_scope")
        _sel_round = _opts[_sel_label]
        _fname = (f"별지 5. 안전점검 결과 지적 내역서 - {_sel_round}.pdf"
                  if _sel_round else "별지 5. 안전점검 결과 지적 내역서.pdf")
        with _btn_col:
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
    mid6, _ = st.columns([2, 1])
    with mid6:
        # v1.5: 자료원이 Notice → Deficiency.action_*. 통보서가 발급된(notice_no) +
        # 조치 완료(action_done)된 Deficiency가 별지6 출력 대상.
        # 260907: 가설컨테이너 사무실 점검은 법정 통보서 대상이 아니므로 제외 — 별지5와 동일한
        # 원칙, 조치 전/후 결과는 "점검결과 보고 · 사진대지" 섹션 B에서 다룬다.
        all_defs = [
            d for d in data.load_deficiencies()
            if d.notice_no and data.INSPECTION_KIND_CONTAINER not in d.inspection_types
        ]
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
            _scope_col6, _btn_col6 = st.columns([2.2, 1.3], vertical_alignment="bottom")
            with _scope_col6:
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
            with _btn_col6:
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

    # ---------- 점검결과 보고 (260907 신규, 별지5/6과 동일하게 독립 PDF) ----------
    _section_title("점검결과 보고",
                   "별지5 법정 서식 외 범용 사진 증빙 보고서. "
                   "사진이 하나라도 등록된 점검은 점검종류 구분 없이 모두 포함됩니다.")
    midp, _ = st.columns([2, 1])
    with midp:
        _task_roundp = {t.task_id: t.round_id for t in data.load_tasks() if t.round_id}
        _cntp: dict[str, int] = {}
        for _d in data.load_deficiencies():
            _ridp = _task_roundp.get(_d.task_id)
            if _ridp and _report_photos_for(_d)[0]:
                _cntp[_ridp] = _cntp.get(_ridp, 0) + 1
        _optsp = {f"전체 (모든 회차 · {sum(_cntp.values())}건)": None}
        for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
            if getattr(_r, "cancelled", False) or _r.task_type == data.MAL_ROUND_TYPE:
                continue
            if _cntp.get(_r.round_id, 0) > 0:
                _optsp[f"{_r.round_id} · {_r.task_type} · {_cntp[_r.round_id]}건"] = _r.round_id
        _scope_colp, _btn_colp = st.columns([2.2, 1.3], vertical_alignment="bottom")
        with _scope_colp:
            _sel_labelp = st.selectbox("출력 범위", list(_optsp.keys()), key="insp_photo_report_scope")
        _sel_roundp = _optsp[_sel_labelp]
        _fnamep = (f"점검결과 보고 - {_sel_roundp}.pdf" if _sel_roundp else "점검결과 보고.pdf")
        with _btn_colp:
            st.download_button(
                "Download 점검결과 보고 PDF",
                data=_build_pdf_inspection_photo_report(_sel_roundp),
                file_name=_fnamep,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="insp_photo_report_dl",
            )
    _spacer()

    # ---------- 사진대지 전/후 (260907 신규, 독립 PDF) ----------
    _section_title("사진대지 전/후",
                   "지적사항 조치 전/후 비교 사진대지. "
                   "조치 전 사진이 등록된 지적사항은 모두 포함되며, 조치 후 사진은 등록되면 함께 표시됩니다.")
    midba, _ = st.columns([2, 1])
    with midba:
        _task_roundba = {t.task_id: t.round_id for t in data.load_tasks() if t.round_id}
        _cntba: dict[str, int] = {}
        for _d in data.load_deficiencies():
            _ridba = _task_roundba.get(_d.task_id)
            if _ridba and _d.photo_path:
                _cntba[_ridba] = _cntba.get(_ridba, 0) + 1
        _optsba = {f"전체 (모든 회차 · {sum(_cntba.values())}건)": None}
        for _r in sorted(data.load_rounds(), key=lambda x: x.due_date, reverse=True):
            if getattr(_r, "cancelled", False) or _r.task_type == data.MAL_ROUND_TYPE:
                continue
            if _cntba.get(_r.round_id, 0) > 0:
                _optsba[f"{_r.round_id} · {_r.task_type} · {_cntba[_r.round_id]}건"] = _r.round_id
        _scope_colba, _btn_colba = st.columns([2.2, 1.3], vertical_alignment="bottom")
        with _scope_colba:
            _sel_labelba = st.selectbox("출력 범위", list(_optsba.keys()), key="before_after_report_scope")
        _sel_roundba = _optsba[_sel_labelba]
        _fnameba = (f"사진대지 전후 - {_sel_roundba}.pdf" if _sel_roundba else "사진대지 전후.pdf")
        with _btn_colba:
            st.download_button(
                "Download 사진대지 전/후 PDF",
                data=_build_pdf_before_after_report(_sel_roundba),
                file_name=_fnameba,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="before_after_report_dl",
            )
    _spacer()

    # ---------- QR 스티커 ----------
    _section_title("QR 스티커",
                   "장비의 QR 스티커를 A4 한 페이지당 4×6 그리드(24개)로 출력합니다. "
                   "전체 또는 특정 층만 선택할 수 있습니다.")
    midq, _ = st.columns([2, 1])
    with midq:
        _scope_colq, _btn_colq = st.columns([2.2, 1.3], vertical_alignment="bottom")
        with _scope_colq:
            _sel_floor_q = st.selectbox(
                "출력 범위", ["전체 (모든 층)"] + data.load_all_floors(),
                key="qr_sticker_floor",
            )
        _qr_eq = data.load_equipment()
        if _sel_floor_q != "전체 (모든 층)":
            _qr_eq = [e for e in _qr_eq if e.floor == _sel_floor_q]
        _fname_q = (
            f"QR 스티커 시트 ({_sel_floor_q}, 4x6).pdf"
            if _sel_floor_q != "전체 (모든 층)" else "QR 스티커 시트 (4x6).pdf"
        )
        with _btn_colq:
            st.download_button(
                f"Download QR 스티커 시트 · {len(_qr_eq)}건",
                data=sticker_sheet_pdf(_qr_eq),
                file_name=_fname_q,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
