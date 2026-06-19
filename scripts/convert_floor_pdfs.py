"""PDF 평면도 → PNG 일괄 변환.

용도: 사용자 PC의 원본 도면 PDF 8장을 assets/floors/{floor}.png로 변환.
실행: ./venv/Scripts/python.exe scripts/convert_floor_pdfs.py
도면이 갱신되면 이 스크립트를 다시 실행 후 git commit.
"""
from __future__ import annotations

import sys
from pathlib import Path

import fitz  # type: ignore[import-not-found]


SRC_DIR = Path(
    r"C:\Users\user\Documents\마이지식\260619 용인덕성\0_FW_ FW_ FW_ dwg to dxf_260619"
)
DST_DIR = Path(__file__).resolve().parent.parent / "assets" / "floors"

# 파일명에서 층 코드 추론 (현장 약속에 따라 갱신 가능)
FILENAME_TO_FLOOR: dict[str, str] = {
    "A31-001 PIT 평면도.pdf": "PIT",
    "A31-002 지하2층 평면도.pdf": "B2",
    "A31-003 지하1층 평면도.pdf": "B1",
    "A31-004 1층 평면도.pdf": "1F",
    "A31-005 2층 평면도.pdf": "2F",
    "A31-006 3층 평면도.pdf": "3F",
    "A31-007 4층 평면도.pdf": "4F",
    "A31-008 지붕 평면도.pdf": "Roof",
}

# 도면을 충분히 키워 화면 확대 시 글자가 또렷하게 보이도록 한다.
RENDER_DPI = 180  # 1.5x ~ 2x 해상도


def convert_one(pdf_path: Path, out_png: Path) -> None:
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    matrix = fitz.Matrix(RENDER_DPI / 72, RENDER_DPI / 72)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    pix.save(str(out_png))
    doc.close()
    print(f"  OK {pdf_path.name} -> {out_png.name} "
          f"({pix.width}x{pix.height}, {out_png.stat().st_size // 1024} KB)")


def main() -> int:
    if not SRC_DIR.exists():
        print(f"[ERROR] 원본 PDF 폴더가 없음: {SRC_DIR}")
        return 1
    DST_DIR.mkdir(parents=True, exist_ok=True)

    converted = 0
    for fname, floor in FILENAME_TO_FLOOR.items():
        pdf_path = SRC_DIR / fname
        if not pdf_path.exists():
            print(f"  ! skip (파일 없음): {fname}")
            continue
        out_png = DST_DIR / f"{floor}.png"
        convert_one(pdf_path, out_png)
        converted += 1

    print(f"\n변환 완료: {converted} / {len(FILENAME_TO_FLOOR)}")
    print(f"출력 경로: {DST_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
