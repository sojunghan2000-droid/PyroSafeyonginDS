"""Supabase Auth 헬퍼 — 로그인 세션 관리 + 관리자 API 클라이언트.

로그인은 아이디(ID)+비밀번호. Supabase Auth는 이메일 기반이므로
아이디를 합성 이메일(`{username}@pyrosafe.local`)로 매핑해 저장한다.
아이디 원본은 user_metadata['username'], 이름은 user_metadata['name'].

역할(role)은 auth.users의 app_metadata['role']에 저장한다 ('admin' | 'user').
app_metadata는 service_role 키로만 수정 가능하므로 사용자가 스스로
권한을 올릴 수 없다.
"""
from __future__ import annotations

import json
import re
from urllib.parse import unquote

import streamlit as st
from supabase import Client, create_client

# 아이디 → 합성 이메일 도메인 (화면에 노출되지 않음)
ID_DOMAIN = "pyrosafe.local"
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,19}$")

# v1.9(260907): 새로고침해도 로그인 유지 — 브라우저 세션 쿠키(탭 종료 시 만료)에
# access/refresh 토큰을 담아두고, 앱 시작 시 session_state가 비어 있으면 이걸로 복구.
SESSION_COOKIE_NAME = "pyrosafe_session"


def _set_session_cookie(access_token: str, refresh_token: str) -> None:
    """로그인 성공 시 세션 쿠키 심기. Streamlit엔 쿠키 쓰기 API가 없어 작은 JS로 처리.
    max-age를 지정하지 않아 브라우저(탭) 종료 시 자동 만료되는 세션 쿠키가 된다."""
    payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    st.components.v1.html(
        f"<script>document.cookie = {json.dumps(SESSION_COOKIE_NAME)} + '='"
        f" + encodeURIComponent({json.dumps(payload)}) + '; path=/; SameSite=Lax';</script>",
        height=0,
    )


def _clear_session_cookie() -> None:
    st.components.v1.html(
        f"<script>document.cookie = {json.dumps(SESSION_COOKIE_NAME)}"
        " + '=; path=/; max-age=0; SameSite=Lax';</script>",
        height=0,
    )


def try_restore_session() -> None:
    """새로고침으로 session_state가 날아갔을 때 브라우저 세션 쿠키로 로그인 복구 시도.
    쿠키가 없거나 토큰이 만료/무효면 조용히 넘어가고(로그인 화면 노출), 예외를 띄우지 않는다."""
    if st.session_state.get("auth"):
        return
    raw = st.context.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        return
    try:
        tokens = json.loads(unquote(raw))
        c = anon_client()
        c.auth.set_session(tokens["access_token"], tokens["refresh_token"])
        s = c.auth.get_session()
        resp = c.auth.get_user()
        if not s or not resp or not resp.user:
            return
        u = resp.user
        meta = u.user_metadata or {}
        st.session_state["auth"] = {
            "user_id": u.id,
            "username": meta.get("username") or u.email.split("@")[0],
            "name": meta.get("name") or u.email.split("@")[0],
            "role": (u.app_metadata or {}).get("role", "user"),
            "access_token": s.access_token,
            "refresh_token": s.refresh_token,
        }
        # 쿠키 갱신(토큰 회전 대응)은 sync_session_cookie()가 뒤이어 일괄 처리한다.
    except Exception:
        pass


def username_to_email(username: str) -> str:
    return f"{username.strip().lower()}@{ID_DOMAIN}"


def _cfg() -> dict:
    return st.secrets["supabase"]


def anon_client() -> Client:
    """공개(anon) 키 클라이언트 — 로그인/본인 정보 변경용."""
    return create_client(_cfg()["url"], _cfg()["anon_key"])


def admin_client() -> Client:
    """service_role 클라이언트 — 사용자 관리(관리자 기능) 전용.

    호출 전 반드시 is_admin() 검사를 거칠 것.
    """
    return create_client(_cfg()["url"], _cfg()["service_role_key"])


def _friendly_error(e: Exception) -> str:
    msg = str(e)
    if "Invalid login credentials" in msg:
        return "아이디 또는 비밀번호가 올바르지 않습니다."
    if "Email not confirmed" in msg:
        return "이메일 인증이 완료되지 않은 계정입니다."
    if "For security purposes" in msg:
        return "요청이 너무 잦습니다. 잠시 후 다시 시도해 주세요."
    return f"인증 오류: {msg}"


def sign_in(username: str, password: str) -> tuple[bool, str]:
    """아이디+비밀번호 로그인. 성공 시 세션에 사용자 정보 저장."""
    try:
        res = anon_client().auth.sign_in_with_password(
            {"email": username_to_email(username), "password": password}
        )
    except Exception as e:  # supabase가 AuthApiError 등 다양한 예외를 던짐
        return False, _friendly_error(e)
    u = res.user
    meta = u.user_metadata or {}
    st.session_state["auth"] = {
        "user_id": u.id,
        "username": meta.get("username") or u.email.split("@")[0],
        "name": meta.get("name") or u.email.split("@")[0],
        "role": (u.app_metadata or {}).get("role", "user"),
        "access_token": res.session.access_token,
        "refresh_token": res.session.refresh_token,
    }
    # 쿠키는 여기서 바로 심지 않는다 — 로그인 직후 호출부(login.py)가 곧바로 st.rerun()을
    # 호출해서, 지금 그리려는 iframe 스크립트가 브라우저에서 실행될 틈도 없이 화면이
    # 통째로 갈아치워질 수 있다(경쟁 상태). 대신 sync_session_cookie()가 로그인 이후
    # "재실행이 뒤따르지 않는" 정상 렌더 시점(app.py)에 실제로 쿠키를 심는다.
    return True, ""


def sign_up(name: str, username: str, password: str) -> tuple[bool, str]:
    """회원가입 (아이디 기반). 첫 가입자는 admin, 이후는 user 역할.

    admin API로 생성해 이메일 확인 절차를 생략하고 즉시 로그인 가능 상태로 만든다.
    성공 시 바로 sign_in까지 수행한다.
    """
    name = name.strip()
    username = username.strip().lower()
    if not name:
        return False, "이름을 입력해 주세요."
    if not USERNAME_RE.match(username):
        return False, ("아이디는 영문 소문자로 시작하고, 영문 소문자/숫자/밑줄(_)로 "
                       "3~20자여야 합니다.")
    if len(password) < 6:
        return False, "비밀번호는 6자 이상이어야 합니다."

    admin = admin_client()
    try:
        existing = admin.auth.admin.list_users()
        role = "admin" if len(existing) == 0 else "user"
        admin.auth.admin.create_user({
            "email": username_to_email(username),
            "password": password,
            "email_confirm": True,
            "user_metadata": {"name": name, "username": username},
            "app_metadata": {"role": role},
        })
    except Exception as e:
        msg = str(e)
        if "already been registered" in msg or "already registered" in msg:
            return False, "이미 사용 중인 아이디입니다. 로그인 탭을 이용해 주세요."
        return False, _friendly_error(e)

    return sign_in(username, password)


def current_user() -> dict | None:
    """로그인된 사용자 정보 (없으면 None)."""
    return st.session_state.get("auth")


def sync_session_cookie() -> None:
    """로그인된 상태의 매 렌더에서 세션 쿠키가 현재 토큰과 일치하는지 확인해 갱신.
    로그인 콜백(sign_in) 직후엔 st.rerun()이 곧바로 뒤따라 쿠키 스크립트가 실행될 틈이
    없을 수 있어, 대신 뒤따르는 재실행이 없는 정상 렌더 시점(app.py 최상단)에서 호출한다."""
    u = current_user()
    if not u:
        return
    token = u.get("access_token")
    if st.session_state.get("_cookie_synced_token") == token:
        return
    _set_session_cookie(u["access_token"], u["refresh_token"])
    st.session_state["_cookie_synced_token"] = token


def flush_pending_cookie_clear() -> bool:
    """sign_out()이 남긴 삭제 예약 플래그를 처리. 실제로 지웠으면 True.
    app.py의 로그인 게이트에서, try_restore_session()보다 먼저 호출해야
    방금 지운 쿠키를 그 자리에서 다시 복구해버리는 일이 없다."""
    if st.session_state.pop("_pending_cookie_clear", False):
        _clear_session_cookie()
        return True
    return False


def is_admin() -> bool:
    u = current_user()
    return bool(u and u.get("role") == "admin")


def sign_out() -> None:
    """로그아웃. 쿠키 삭제는 여기서 바로 하지 않는다 — 호출부가 곧바로 st.rerun()을
    호출해서 삭제 스크립트가 실행될 틈이 없으면, 다음 렌더의 try_restore_session()이
    아직 안 지워진 쿠키로 로그인을 되살려버린다(로그인 때와 동일한 경쟁 상태).
    대신 플래그만 남겨 app.py가 재실행이 뒤따르지 않는 시점에 실제로 지우게 한다."""
    st.session_state.pop("auth", None)
    st.session_state.pop("_cookie_synced_token", None)
    st.session_state["_pending_cookie_clear"] = True


def user_client() -> Client:
    """로그인 사용자 권한의 클라이언트 — 본인 비밀번호/이메일 변경용.

    set_session이 만료 토큰을 자동 갱신하므로 갱신된 토큰을 세션에 되저장한다.
    """
    auth = current_user()
    if not auth:
        raise RuntimeError("로그인 상태가 아닙니다.")
    c = anon_client()
    c.auth.set_session(auth["access_token"], auth["refresh_token"])
    s = c.auth.get_session()
    if s:
        auth["access_token"] = s.access_token
        auth["refresh_token"] = s.refresh_token
        # v1.9(260907): 토큰 회전 시 세션 쿠키도 최신 값으로 갱신.
        _set_session_cookie(s.access_token, s.refresh_token)
    return c


def avatar_initials() -> str:
    """상단바 아바타용 이니셜 (이름 첫 두 글자, 영문이면 대문자)."""
    u = current_user()
    if not u:
        return "?"
    name = u["name"].strip()
    return name[:2].upper() if name.isascii() else name[:2]
