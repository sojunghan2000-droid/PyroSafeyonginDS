"""로그인/회원가입 페이지 — 미로그인 시 앱 진입 전 게이트."""
from __future__ import annotations

import streamlit as st

from lib import auth


def _login_tab() -> None:
    with st.form("login_form"):
        username = st.text_input("아이디", placeholder="영문 소문자 아이디")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button(
            "로그인", type="primary", use_container_width=True
        )
    if submitted:
        if not username or not password:
            st.error("아이디와 비밀번호를 입력해 주세요.")
            return
        ok, err = auth.sign_in(username, password)
        if ok:
            st.rerun()
        else:
            st.error(err)


def _signup_tab() -> None:
    with st.form("signup_form"):
        name = st.text_input("이름", placeholder="홍길동")
        username = st.text_input("아이디", placeholder="영문 소문자/숫자, 3~20자",
                                 help="영문 소문자로 시작, 영문 소문자·숫자·밑줄(_) 3~20자",
                                 key="signup_id")
        password = st.text_input("비밀번호", type="password",
                                 help="6자 이상", key="signup_pw")
        password2 = st.text_input("비밀번호 확인", type="password",
                                  key="signup_pw2")
        submitted = st.form_submit_button(
            "회원가입", type="primary", use_container_width=True
        )
    if submitted:
        if not name or not username or not password:
            st.error("이름, 아이디, 비밀번호를 모두 입력해 주세요.")
            return
        if password != password2:
            st.error("비밀번호가 서로 일치하지 않습니다.")
            return
        ok, err = auth.sign_up(name, username, password)
        if ok:
            st.rerun()
        else:
            st.error(err)
    st.markdown(
        "<div style='color:#94A3B8; font-size:0.8rem; margin-top:0.5rem;'>"
        "첫 가입자는 관리자 권한이 부여됩니다. 이후 가입자는 일반 사용자이며, "
        "권한 변경은 관리자에게 요청하세요.</div>",
        unsafe_allow_html=True,
    )


def render() -> None:
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            """
            <div style='text-align:center; margin-top:10vh; margin-bottom:1.2rem;'>
                <div style='font-size:2rem; font-weight:700; color:#2563EB;'>PyroSafe</div>
                <div style='color:#64748B; font-size:0.95rem; margin-top:0.3rem;'>
                    용인덕성 AI DC · 소방시설 점검 관리
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        tab_login, tab_signup = st.tabs(["로그인", "회원가입"])
        with tab_login:
            _login_tab()
        with tab_signup:
            _signup_tab()
        st.markdown(
            "<div style='text-align:center; color:#94A3B8; font-size:0.8rem; margin-top:1rem;'>"
            "계정 문의는 안전 관리자에게 연락해 주세요.</div>",
            unsafe_allow_html=True,
        )
