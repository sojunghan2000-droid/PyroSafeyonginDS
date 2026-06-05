"""QR 코드 생성 헬퍼.

페이로드: 딥링크 URL `{BASE_URL}/inspect?eq={equipment_id}`
스캐너가 즉시 점검 폼을 열도록 설계.
"""
from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import qrcode
from qrcode.constants import ERROR_CORRECT_H

if TYPE_CHECKING:
    from PIL.Image import Image

    from lib.data import Equipment


BASE_URL = "https://pyrosafe.app"


def payload_for(equipment: "Equipment") -> str:
    """장비 → QR에 인코딩될 URL."""
    return f"{BASE_URL}/inspect?eq={equipment.equipment_id}"


def make_qr(
    equipment: "Equipment",
    *,
    box_size: int = 8,
    border: int = 2,
) -> "Image":
    """장비용 QR을 PIL Image로 반환. error correction H로 30% 손상 복구.

    box_size : 한 모듈(셀)의 픽셀 크기. 8이면 약 250×250px 출력.
    border   : 외곽 quiet zone (모듈 단위).
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload_for(equipment))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def qr_png_bytes(equipment: "Equipment", **kwargs) -> bytes:
    """장비용 QR을 PNG 바이트로 반환."""
    img = make_qr(equipment, **kwargs)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------- 스티커 시트 PDF (A4 4×6 = 24개) ----------

def sticker_sheet_pdf(equipments: list["Equipment"]) -> bytes:
    """선택된 장비들로 A4 한 페이지당 4×6 스티커 시트를 생성.

    각 스티커: QR + 장비ID + 위치(층/구역) + 카테고리
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as RImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER

    from lib.fonts import ensure_korean_fonts

    font_normal, font_bold = ensure_korean_fonts()
    s_id = ParagraphStyle("id", fontName=font_bold, fontSize=8.5, leading=10, alignment=TA_CENTER)
    s_meta = ParagraphStyle("meta", fontName=font_normal, fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.HexColor("#475569"))

    COLS = 4
    ROWS = 6
    PER_PAGE = COLS * ROWS

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=8 * mm, rightMargin=8 * mm,
        topMargin=8 * mm, bottomMargin=8 * mm,
    )
    cell_w = (A4[0] - 16 * mm) / COLS
    # 여유 24mm로 ReportLab 자동 page-break 방지
    cell_h = (A4[1] - 24 * mm) / ROWS

    def _make_cell(eq):
        if eq is None:
            return ""
        # PIL QR → BytesIO → ReportLab Image
        img = make_qr(eq, box_size=8, border=1)
        ib = BytesIO()
        img.save(ib, format="PNG")
        ib.seek(0)
        qr_img = RImage(ib, width=28 * mm, height=28 * mm)
        meta = Paragraph(
            f"{eq.equipment_id}<br/>"
            f"{eq.floor} / {eq.zone}<br/>"
            f"{eq.category}",
            s_meta,
        )
        inner = Table(
            [[qr_img], [meta]],
            colWidths=[cell_w - 4 * mm],
            rowHeights=[30 * mm, cell_h - 32 * mm],
        )
        inner.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ]))
        return inner

    # 페이지별로 4×6 표 생성
    elements = []
    for page_start in range(0, len(equipments), PER_PAGE):
        page_items = equipments[page_start:page_start + PER_PAGE]
        page_items = page_items + [None] * (PER_PAGE - len(page_items))
        grid = []
        for r in range(ROWS):
            row = [_make_cell(page_items[r * COLS + c]) for c in range(COLS)]
            grid.append(row)
        table = Table(grid, colWidths=[cell_w] * COLS, rowHeights=[cell_h] * ROWS)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 1 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1 * mm),
        ]))
        elements.append(table)

    doc.build(elements)
    return buf.getvalue()
