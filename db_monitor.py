"""DB 모니터 — 신규 Supabase 프로젝트(PyroSafe+FIRE-PASS) 전체 DB 읽기전용 대시보드.

Streamlit Cloud 별도 앱으로 배포. 데이터는 Supabase pooler 직결(psycopg2)로 조회하며
public 테이블뿐 아니라 auth/storage 스키마까지 읽는다. 읽기전용(SELECT only).
"""
from __future__ import annotations

import hmac

import streamlit as st

# PyroSafe 앱 소유 테이블(나머지 public 테이블은 FIRE-PASS/기타)
PYROSAFE_TABLES = {
    "equipment", "inspection_tasks", "inspection_rounds", "deficiencies",
    "notices", "malfunctions", "floor_spots", "inspection_types",
}


def verify_password(entered: str, expected: str) -> bool:
    """상수시간 비교로 비밀번호 판정. 빈 문자열은 항상 False."""
    if not entered or not expected:
        return False
    return hmac.compare_digest(entered, expected)


def main() -> None:
    st.set_page_config(page_title="DB 모니터", layout="wide")
    st.title("DB 모니터")
    st.info("구현 예정")


if __name__ == "__main__":
    main()
