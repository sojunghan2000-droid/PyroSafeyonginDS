"""한글 PDF 폰트 등록 — 번들 NanumGothic 우선, 시스템 폰트 폴백, 최후 다운로드.

런북: 260423-MPM repo / docs/runbook-pdf-korean-font.md (baseline b983c46, 2026-04-27)
- Windows: assets/fonts/NanumGothic.ttf 번들 → 시스템 malgun.ttf 폴백
- Streamlit Cloud(Linux): 번들 폰트 최우선 (packages.txt 미설치 환경 대응)
"""
from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

_REGISTERED = False
_BUNDLE_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_TMP = Path(tempfile.gettempdir())

_NANUM_URL_NORMAL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
)
_NANUM_URL_BOLD = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
)

_CANDIDATES_NORMAL = [
    _BUNDLE_DIR / "NanumGothic.ttf",
    Path("C:/Windows/Fonts/malgun.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/nanum/NanumGothic.ttf"),
    _TMP / "NanumGothic.ttf",
]
_CANDIDATES_BOLD = [
    _BUNDLE_DIR / "NanumGothicBold.ttf",
    Path("C:/Windows/Fonts/malgunbd.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    Path("/usr/share/fonts/nanum/NanumGothicBold.ttf"),
    _TMP / "NanumGothicBold.ttf",
]


def _download(url: str, dest: Path) -> bool:
    """폰트 다운로드. 최소 100KB 이상이면 유효 파일로 본다."""
    try:
        if dest.exists() and dest.stat().st_size > 100_000:
            return True
        if dest.exists():
            dest.unlink()
        urllib.request.urlretrieve(url, dest)
        return dest.exists() and dest.stat().st_size > 100_000
    except Exception:
        return False


def ensure_korean_fonts() -> tuple[str, str]:
    """등록된 (normal, bold) 폰트명을 반환. idempotent."""
    global FONT_NORMAL, FONT_BOLD, _REGISTERED
    if _REGISTERED:
        return FONT_NORMAL, FONT_BOLD

    if not any(p.exists() for p in _CANDIDATES_NORMAL[:-1]):
        _download(_NANUM_URL_NORMAL, _TMP / "NanumGothic.ttf")
    if not any(p.exists() for p in _CANDIDATES_BOLD[:-1]):
        _download(_NANUM_URL_BOLD, _TMP / "NanumGothicBold.ttf")

    for path in _CANDIDATES_NORMAL:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", str(path)))
                FONT_NORMAL = "KoreanFont"
                break
            except Exception:
                continue
    for path in _CANDIDATES_BOLD:
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont-Bold", str(path)))
                FONT_BOLD = "KoreanFont-Bold"
                break
            except Exception:
                continue

    _REGISTERED = True
    return FONT_NORMAL, FONT_BOLD


def is_korean_font_registered() -> bool:
    """진단용: 한글 폰트가 정상 등록됐는지."""
    return FONT_NORMAL == "KoreanFont"
