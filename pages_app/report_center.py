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

def _build_pdf_byeolji5() -> bytes:
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
    data_start = len(rows)
    for d in deficiencies:
        type_lines = [
            f"• {t}( {'O' if t in d.inspection_types else '&nbsp;'} )" for t in types_all
        ]
        rows.append([
            Paragraph(f"{d.floor}<br/>{d.zone}", s["cell"]),
            Paragraph("<br/>".join(type_lines), s["left"]),
            Paragraph(d.issue, s["left"]),
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

def _build_pdf_byeolji6(notice=None) -> bytes:
    """별지6 통보서 PDF. notice를 지정하면 그 통보서, 미지정 시 최신 1건."""
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

    COL_W = [22 * mm, 38 * mm, 60 * mm, 60 * mm]  # 180mm 합

    if notice is None:
        notices = data.load_notices()
        notice = notices[0] if notices else None

    n = notice
    notice_no = n.notice_no if n else ""
    inspection_date = n.inspection_date.strftime("%Y년 %m월 %d일") if n else ""
    submitter = n.submitter if n else ""
    confirmer = n.confirmer if n else ""

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
        photo_cell = _photo_image(n.action_photo, max_w_mm=58, max_h_mm=70)
        if photo_cell is None:
            photo_cell = Paragraph("사진첨부", s["cell"])
        rows.append([
            Paragraph(f"{n.floor}<br/>{n.zone}", s["cell"]),
            Paragraph(n.inspection_type, s["cell"]),
            Paragraph(n.issue, s["left"]),
            photo_cell,
        ])
    else:
        rows.append(["", "", "", ""])
    row_heights.append(75 * mm)

    # row 4: 조치 내용 / 완료일 (있으면 표시)
    if n and n.action_done:
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

    doc.build([main])
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
                   "현장 점검에서 발견된 모든 지적사항(완료/불가)을 일괄 PDF로 출력합니다.")
    _, mid5, _ = st.columns([1, 2, 1])
    with mid5:
        st.markdown(_card_header("별지5", "안전점검 결과 지적내역서"), unsafe_allow_html=True)
        st.download_button(
            "Download 별지5 PDF",
            data=_build_pdf_byeolji5(),
            file_name="별지 5. 안전점검 결과 지적 내역서.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )
    _spacer()

    # ---------- 별지6 ----------
    _section_title("별지6 · 안전점검 조치 결과 통보서",
                   "조치 완료된 통보서를 1건씩 선택해 PDF로 출력합니다. 사진과 조치 내용이 자동 포함됩니다.")
    _, mid6, _ = st.columns([1, 2, 1])
    with mid6:
        st.markdown(_card_header("별지6", "안전점검 조치 결과 통보서"), unsafe_allow_html=True)
        notices = data.load_notices()
        done = [n for n in notices if n.action_done]
        pending = [n for n in notices if not n.action_done]
        if not notices:
            st.info("발급된 통보서가 없습니다.")
        elif not done:
            st.warning(
                f"발급된 통보서 {len(pending)}건 — 모두 조치 미완료. "
                "**지적 관리**에서 '조치 폼'을 먼저 작성하세요."
            )
        else:
            opts = [
                f"{n.notice_no} · {n.floor}/{n.zone} · {n.issue[:18]}"
                for n in done
            ]
            sel_idx = st.selectbox(
                "통보서 선택 (조치 완료된 항목만)",
                options=range(len(opts)),
                format_func=lambda i: opts[i],
                key="notice_select",
                label_visibility="collapsed",
            )
            sel_notice = done[sel_idx]
            st.download_button(
                f"Download {sel_notice.notice_no}",
                data=_build_pdf_byeolji6(sel_notice),
                file_name=f"별지 6. 안전점검 조치 결과 통보서 ({sel_notice.notice_no}).pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
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
