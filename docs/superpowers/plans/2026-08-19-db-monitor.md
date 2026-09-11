# DB 모니터 (db_monitor.py) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 신규 Supabase 프로젝트(ivpzfrvboazpbcejpqwc, PyroSafe+FIRE-PASS 공유) DB 전체를 웹에서 읽기전용으로 보는, 비밀번호로 보호된 Streamlit 모니터링 앱을 만든다.

**Architecture:** 단일 파일 `db_monitor.py`. 순수 SQL 조회 함수들(psycopg2 커넥션을 인자로 받음) + Streamlit UI(`main()`), `if __name__ == "__main__"` 가드로 분리해 테스트가 UI 실행 없이 조회 함수만 import 가능. DB는 Supabase pooler 직결(psycopg2)이라 PostgREST 미노출 테이블·auth·storage 스키마까지 조회.

**Tech Stack:** Python 3.13, Streamlit, psycopg2-binary, pandas, plotly, pytest(로컬 테스트), tomllib(stdlib).

## Global Constraints

- 대상 DB pooler: host `aws-0-ap-south-1.pooler.supabase.com`, port `5432`, dbname `postgres`, user `postgres.ivpzfrvboazpbcejpqwc`, sslmode `require`. DB 비밀번호는 secrets에만.
- 읽기전용: `SELECT` 만. `INSERT/UPDATE/DELETE/DDL` 금지.
- 비밀·접속정보는 `.streamlit/secrets.toml`(gitignored)와 Streamlit Cloud Secrets에만. 리포에 값 커밋 금지.
- 테이블명은 `information_schema` 로 얻은 화이트리스트에서만 사용(사용자 자유 입력 SQL 없음).
- PyroSafe 테이블 집합(정확히 이 8개): `equipment, inspection_tasks, inspection_rounds, deficiencies, notices, malfunctions, floor_spots, inspection_types`. 나머지 public 테이블은 FIRE-PASS/기타.
- `db_monitor.py`는 `app.py`/`lib/` 를 import 하지 않는다(프로덕션 앱과 무결합).
- 커밋은 브랜치 `feat/db-monitor`.

---

## File Structure

- Create: `db_monitor.py` — 앱 전체(조회 함수 + UI). 리포 루트.
- Create: `tests/conftest.py` — DB 커넥션 fixture(secrets.toml [db] 로딩, 없으면 skip).
- Create: `tests/test_db_monitor.py` — 조회 함수 통합 테스트(라이브 DB, 알려진 값 검증).
- Create: `.streamlit/secrets.toml.example` — [monitor]/[db] 키 구조(값 없이).
- Modify: `.streamlit/secrets.toml` — [monitor]/[db] 섹션 추가(gitignored, 커밋 안 됨).
- Modify: `requirements.txt` — `psycopg2-binary` 추가.

---

## Task 1: 스캐폴딩 + 비밀번호 게이트

**Files:**
- Modify: `requirements.txt`
- Create: `.streamlit/secrets.toml.example`
- Modify: `.streamlit/secrets.toml` (gitignored)
- Create: `db_monitor.py`
- Create: `tests/test_db_monitor.py`

**Interfaces:**
- Produces: `verify_password(entered: str, expected: str) -> bool` — 상수시간 비교로 게이트 판정.
- Produces: `PYROSAFE_TABLES: set[str]` — PyroSafe 8테이블 집합.
- Produces: `main() -> None` — Streamlit 엔트리(가드 안에서 호출).

- [ ] **Step 1: requirements.txt에 psycopg2-binary 추가**

`requirements.txt` 끝에 한 줄 추가:

```
psycopg2-binary>=2.9.9
```

- [ ] **Step 2: secrets 예시 파일 생성**

`.streamlit/secrets.toml.example`:

```toml
# DB 모니터(db_monitor.py) 전용 secrets. 실제 값은 .streamlit/secrets.toml(gitignored) 또는
# Streamlit Cloud App Settings → Secrets 에 넣는다. 이 파일은 구조만 문서화(값 없음).

[monitor]
password = "CHANGE_ME"          # 모니터 접속 비밀번호

[db]
host = "aws-0-ap-south-1.pooler.supabase.com"
port = 5432
dbname = "postgres"
user = "postgres.ivpzfrvboazpbcejpqwc"
password = "CHANGE_ME"          # 대상 프로젝트 DB 비밀번호
```

- [ ] **Step 3: 로컬 secrets.toml에 [monitor]/[db] 섹션 추가**

`.streamlit/secrets.toml` 파일 끝에 아래를 추가한다(기존 `[supabase]` 섹션은 그대로 둔다). `<DB_PW>` 는 대상 프로젝트 DB 비밀번호(인계 문서의 값), `<MON_PW>` 는 원하는 모니터 접속 비밀번호로 채운다:

```toml

# === DB 모니터(db_monitor.py) 전용 ===
[monitor]
password = "<MON_PW>"

[db]
host = "aws-0-ap-south-1.pooler.supabase.com"
port = 5432
dbname = "postgres"
user = "postgres.ivpzfrvboazpbcejpqwc"
password = "<DB_PW>"
```

이 파일은 gitignored 이므로 커밋되지 않는다. (`git check-ignore .streamlit/secrets.toml` 로 확인 가능.)

- [ ] **Step 4: 실패하는 테스트 작성**

`tests/test_db_monitor.py`:

```python
import db_monitor


def test_verify_password_correct():
    assert db_monitor.verify_password("secret", "secret") is True


def test_verify_password_wrong():
    assert db_monitor.verify_password("nope", "secret") is False


def test_verify_password_empty():
    assert db_monitor.verify_password("", "secret") is False


def test_pyrosafe_tables_set():
    assert "equipment" in db_monitor.PYROSAFE_TABLES
    assert "companies" not in db_monitor.PYROSAFE_TABLES
    assert len(db_monitor.PYROSAFE_TABLES) == 8
```

- [ ] **Step 5: 테스트 실패 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'db_monitor'` 또는 attribute 없음.

- [ ] **Step 6: db_monitor.py 최소 구현**

`db_monitor.py`:

```python
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
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 4개 PASS.

- [ ] **Step 8: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add requirements.txt .streamlit/secrets.toml.example db_monitor.py tests/test_db_monitor.py
git commit -m "feat(db-monitor): 스캐폴딩 + 비밀번호 게이트(verify_password)"
```

(참고: `.streamlit/secrets.toml` 은 gitignored 이라 add 되지 않는다 — 정상.)

---

## Task 2: 조회 커넥션 + 개요(테이블 현황)

**Files:**
- Modify: `db_monitor.py`
- Create: `tests/conftest.py`
- Modify: `tests/test_db_monitor.py`

**Interfaces:**
- Consumes: `PYROSAFE_TABLES`.
- Produces: `db_conn_params() -> dict` — st.secrets["db"] → psycopg2 kwargs dict.
- Produces: `fetch_tables(conn) -> list[str]` — public BASE TABLE 이름 목록(정렬).
- Produces: `fetch_counts(conn, tables: list[str]) -> list[dict]` — 각 `{"table","group","rows","last_created"}`. `group` 은 "PyroSafe"|"FIRE-PASS". `last_created` 는 created_at 없으면 None, 조회 오류면 문자열 "error".
- Produces: `render_overview(conn) -> None`.

- [ ] **Step 1: conftest.py 작성 (DB fixture)**

`tests/conftest.py`:

```python
import pathlib
import tomllib

import psycopg2
import pytest

SECRETS = pathlib.Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"


@pytest.fixture(scope="session")
def conn():
    if not SECRETS.exists():
        pytest.skip("no .streamlit/secrets.toml")
    cfg = tomllib.loads(SECRETS.read_text(encoding="utf-8"))
    if "db" not in cfg:
        pytest.skip("no [db] section in secrets.toml")
    db = cfg["db"]
    c = psycopg2.connect(
        host=db["host"], port=db["port"], dbname=db["dbname"],
        user=db["user"], password=db["password"], sslmode="require",
        connect_timeout=10,
    )
    yield c
    c.close()
```

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_db_monitor.py` 에 추가:

```python
def test_fetch_tables_has_both_apps(conn):
    tables = db_monitor.fetch_tables(conn)
    assert "equipment" in tables          # PyroSafe
    assert "companies" in tables          # FIRE-PASS
    assert len(tables) >= 18


def test_fetch_counts_known_values(conn):
    rows = db_monitor.fetch_counts(conn, ["equipment", "inspection_tasks", "notices"])
    by = {r["table"]: r for r in rows}
    assert by["equipment"]["rows"] == 17
    assert by["inspection_tasks"]["rows"] == 39
    assert by["notices"]["rows"] == 7
    assert by["equipment"]["group"] == "PyroSafe"


def test_fetch_counts_missing_created_at(conn):
    # zones 는 created_at 컬럼이 없음 → last_created None, 오류 없이 처리
    rows = db_monitor.fetch_counts(conn, ["zones"])
    assert rows[0]["last_created"] is None
    assert rows[0]["group"] == "FIRE-PASS"
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 새 3개 테스트 FAIL(attribute 없음), 기존 4개 PASS.

- [ ] **Step 4: db_monitor.py에 조회 함수 + 개요 구현**

`import` 부에 추가:

```python
import pandas as pd
import psycopg2
```

`verify_password` 아래에 추가:

```python
def db_conn_params() -> dict:
    db = st.secrets["db"]
    return dict(host=db["host"], port=int(db["port"]), dbname=db["dbname"],
                user=db["user"], password=db["password"], sslmode="require",
                connect_timeout=10)


def _table_group(name: str) -> str:
    return "PyroSafe" if name in PYROSAFE_TABLES else "FIRE-PASS"


def fetch_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "select table_name from information_schema.tables "
            "where table_schema='public' and table_type='BASE TABLE' "
            "order by table_name"
        )
        return [r[0] for r in cur.fetchall()]


def _has_created_at(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "select 1 from information_schema.columns "
            "where table_schema='public' and table_name=%s and column_name='created_at'",
            (table,),
        )
        return cur.fetchone() is not None


def fetch_counts(conn, tables: list[str]) -> list[dict]:
    out = []
    for t in tables:
        rec = {"table": t, "group": _table_group(t), "rows": None, "last_created": None}
        try:
            with conn.cursor() as cur:
                cur.execute(f'select count(*) from public."{t}"')
                rec["rows"] = cur.fetchone()[0]
                if _has_created_at(conn, t):
                    cur.execute(f'select max(created_at) from public."{t}"')
                    val = cur.fetchone()[0]
                    rec["last_created"] = val.isoformat(sep=" ", timespec="minutes") if val else None
        except Exception as e:  # noqa: BLE001 — 한 테이블 오류가 전체를 깨지 않게
            conn.rollback()
            rec["rows"] = "error"
            rec["last_created"] = str(e)[:60]
        out.append(rec)
    return out


def render_overview(conn) -> None:
    st.subheader("개요")
    tables = fetch_tables(conn)
    rows = fetch_counts(conn, tables)
    df = pd.DataFrame(rows)
    total_rows = sum(r["rows"] for r in rows if isinstance(r["rows"], int))
    c1, c2 = st.columns(2)
    c1.metric("테이블 수", len(tables))
    c2.metric("총 행수", f"{total_rows:,}")
    for grp in ["PyroSafe", "FIRE-PASS"]:
        sub = df[df["group"] == grp]
        if sub.empty:
            continue
        st.markdown(f"**{grp}** ({len(sub)}개)")
        show = sub[["table", "rows", "last_created"]].rename(
            columns={"table": "테이블", "rows": "행수", "last_created": "최근 생성"})
        st.dataframe(show, use_container_width=True, hide_index=True)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 7개 PASS(기존 4 + 새 3). (secrets.toml 미설정 시 DB 테스트는 skip.)

- [ ] **Step 6: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add db_monitor.py tests/conftest.py tests/test_db_monitor.py
git commit -m "feat(db-monitor): 개요 탭 — 테이블 현황(행수·최근 생성) + DB 조회 함수"
```

---

## Task 3: 추이 차트

**Files:**
- Modify: `db_monitor.py`
- Modify: `tests/test_db_monitor.py`

**Interfaces:**
- Consumes: `fetch_tables`.
- Produces: `fetch_created_at_tables(conn) -> list[str]` — created_at(timestamptz) 컬럼 있는 public 테이블.
- Produces: `fetch_daily(conn, table: str, days: int | None) -> pandas.DataFrame` — 컬럼 `["d","c"]`(d=date, c=int). days=None 이면 전체.
- Produces: `render_trends(conn) -> None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db_monitor.py` 에 추가:

```python
def test_fetch_created_at_tables(conn):
    tabs = db_monitor.fetch_created_at_tables(conn)
    assert "deficiencies" in tabs
    assert "zones" not in tabs          # created_at 없음


def test_fetch_daily_sums_to_rowcount(conn):
    df = db_monitor.fetch_daily(conn, "deficiencies", None)
    assert list(df.columns) == ["d", "c"]
    assert int(df["c"].sum()) == 17     # deficiencies 총 17건(이관 검증값)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -k "created_at_tables or fetch_daily" -v`
Expected: 2개 FAIL(attribute 없음).

- [ ] **Step 3: db_monitor.py에 추이 구현**

`import` 부에 추가:

```python
import plotly.express as px
```

`render_overview` 아래에 추가:

```python
def fetch_created_at_tables(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "select table_name from information_schema.columns "
            "where table_schema='public' and column_name='created_at' "
            "and data_type like 'timestamp%' order by table_name"
        )
        return [r[0] for r in cur.fetchall()]


def fetch_daily(conn, table: str, days):
    allowed = set(fetch_created_at_tables(conn))
    if table not in allowed:
        raise ValueError(f"table not allowed: {table}")
    sql = f'select date(created_at) d, count(*) c from public."{table}"'
    params = []
    if days:
        sql += " where created_at >= now() - (%s || ' days')::interval"
        params.append(str(days))
    sql += " group by 1 order by 1"
    with conn.cursor() as cur:
        cur.execute(sql, params)
        data = cur.fetchall()
    return pd.DataFrame(data, columns=["d", "c"])


def render_trends(conn) -> None:
    st.subheader("추이")
    tabs = fetch_created_at_tables(conn)
    defaults = [t for t in ["deficiencies", "inspection_tasks", "malfunctions"] if t in tabs]
    col1, col2 = st.columns([2, 1])
    table = col1.selectbox("테이블", tabs, index=(tabs.index(defaults[0]) if defaults else 0))
    period = col2.selectbox("기간", ["최근 30일", "최근 90일", "전체"], index=2)
    days = {"최근 30일": 30, "최근 90일": 90, "전체": None}[period]
    df = fetch_daily(conn, table, days)
    if df.empty:
        st.info("데이터 없음")
        return
    fig = px.bar(df, x="d", y="c", labels={"d": "일자", "c": "건수"})
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"총 {int(df['c'].sum()):,}건")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 9개 PASS.

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add db_monitor.py tests/test_db_monitor.py
git commit -m "feat(db-monitor): 추이 탭 — created_at 일자별 건수 plotly 차트"
```

---

## Task 4: 읽기전용 테이블 브라우저

**Files:**
- Modify: `db_monitor.py`
- Modify: `tests/test_db_monitor.py`

**Interfaces:**
- Consumes: `fetch_tables`.
- Produces: `fetch_rows(conn, table: str, limit: int) -> pandas.DataFrame` — 화이트리스트 검증 후 `SELECT *`. created_at 있으면 최신순.
- Produces: `filter_df(df: pandas.DataFrame, query: str) -> pandas.DataFrame` — 전 컬럼 문자열 부분일치(대소문자 무시).
- Produces: `render_browser(conn) -> None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db_monitor.py` 에 추가:

```python
def test_fetch_rows_limit_and_columns(conn):
    df = db_monitor.fetch_rows(conn, "equipment", 5)
    assert len(df) == 5
    assert "equipment_id" in df.columns


def test_fetch_rows_rejects_unknown_table(conn):
    import pytest
    with pytest.raises(ValueError):
        db_monitor.fetch_rows(conn, "no_such_table; drop table x", 5)


def test_filter_df():
    import pandas as pd
    df = pd.DataFrame({"a": ["Apple", "banana"], "b": [1, 2]})
    out = db_monitor.filter_df(df, "app")
    assert len(out) == 1 and out.iloc[0]["a"] == "Apple"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -k "fetch_rows or filter_df" -v`
Expected: 3개 FAIL.

- [ ] **Step 3: db_monitor.py에 브라우저 구현**

`render_trends` 아래에 추가:

```python
def fetch_rows(conn, table: str, limit: int):
    allowed = set(fetch_tables(conn))
    if table not in allowed:
        raise ValueError(f"table not allowed: {table}")
    order = " order by created_at desc nulls last" if _has_created_at(conn, table) else ""
    with conn.cursor() as cur:
        cur.execute(f'select * from public."{table}"{order} limit %s', (int(limit),))
        cols = [d[0] for d in cur.description]
        data = cur.fetchall()
    return pd.DataFrame(data, columns=cols)


def filter_df(df, query: str):
    q = (query or "").strip().lower()
    if not q:
        return df
    mask = df.astype(str).apply(lambda col: col.str.lower().str.contains(q, na=False))
    return df[mask.any(axis=1)]


def render_browser(conn) -> None:
    st.subheader("브라우저")
    tables = fetch_tables(conn)
    col1, col2 = st.columns([2, 1])
    table = col1.selectbox("테이블", tables, key="browse_table")
    limit = col2.slider("행 수", 10, 500, 100, step=10)
    q = st.text_input("검색(전 컬럼 부분일치)")
    df = fetch_rows(conn, table, limit)
    df = filter_df(df, q)
    st.caption(f"{len(df)}행 표시")
    st.dataframe(df, use_container_width=True, hide_index=True)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 12개 PASS.

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add db_monitor.py tests/test_db_monitor.py
git commit -m "feat(db-monitor): 브라우저 탭 — 읽기전용 테이블 조회+검색"
```

---

## Task 5: 운영(Storage·Auth) 상태

**Files:**
- Modify: `db_monitor.py`
- Modify: `tests/test_db_monitor.py`

**Interfaces:**
- Produces: `fetch_storage(conn) -> list[dict]` — 각 `{"bucket","public","objects","bytes"}`.
- Produces: `fetch_auth(conn, limit: int) -> tuple[int, list[dict]]` — (총수, 최근 로그인 목록 `{"email","last_sign_in","role"}`).
- Produces: `render_ops(conn) -> None`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_db_monitor.py` 에 추가:

```python
def test_fetch_storage(conn):
    buckets = db_monitor.fetch_storage(conn)
    names = {b["bucket"] for b in buckets}
    assert "attachments" in names
    att = next(b for b in buckets if b["bucket"] == "attachments")
    assert att["objects"] >= 1
    assert att["bytes"] >= 0


def test_fetch_auth(conn):
    total, recent = db_monitor.fetch_auth(conn, 10)
    assert total >= 1
    assert all("email" in r for r in recent)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -k "storage or fetch_auth" -v`
Expected: 2개 FAIL.

- [ ] **Step 3: db_monitor.py에 운영 구현**

`render_browser` 아래에 추가:

```python
def fetch_storage(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("select id, public from storage.buckets order by id")
        buckets = cur.fetchall()
        cur.execute(
            "select bucket_id, count(*), coalesce(sum((metadata->>'size')::bigint),0) "
            "from storage.objects group by bucket_id"
        )
        stats = {r[0]: (r[1], int(r[2])) for r in cur.fetchall()}
    out = []
    for bid, pub in buckets:
        objs, byts = stats.get(bid, (0, 0))
        out.append({"bucket": bid, "public": pub, "objects": objs, "bytes": byts})
    return out


def fetch_auth(conn, limit: int):
    with conn.cursor() as cur:
        cur.execute("select count(*) from auth.users")
        total = cur.fetchone()[0]
        cur.execute(
            "select email, last_sign_in_at, coalesce(raw_app_meta_data->>'role','') "
            "from auth.users order by last_sign_in_at desc nulls last limit %s",
            (int(limit),),
        )
        recent = [
            {"email": r[0],
             "last_sign_in": r[1].isoformat(sep=" ", timespec="minutes") if r[1] else None,
             "role": r[2]}
            for r in cur.fetchall()
        ]
    return total, recent


def _human_bytes(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def render_ops(conn) -> None:
    st.subheader("운영")
    st.markdown("**Storage**")
    buckets = fetch_storage(conn)
    st.dataframe(
        pd.DataFrame([
            {"버킷": b["bucket"], "공개": b["public"], "파일 수": b["objects"],
             "용량": _human_bytes(b["bytes"])}
            for b in buckets
        ]),
        use_container_width=True, hide_index=True,
    )
    st.markdown("**Auth**")
    total, recent = fetch_auth(conn, 20)
    st.metric("사용자 수", total)
    st.dataframe(
        pd.DataFrame(recent).rename(
            columns={"email": "이메일", "last_sign_in": "최근 로그인", "role": "역할"}),
        use_container_width=True, hide_index=True,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 14개 PASS.

- [ ] **Step 5: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add db_monitor.py tests/test_db_monitor.py
git commit -m "feat(db-monitor): 운영 탭 — Storage 버킷·용량 + Auth 사용자"
```

---

## Task 6: main() 조립 — 게이트·커넥션·탭·사이드바 + 로컬 스모크

**Files:**
- Modify: `db_monitor.py`

**Interfaces:**
- Consumes: `verify_password`, `db_conn_params`, `render_overview`, `render_trends`, `render_browser`, `render_ops`.
- Produces: `get_conn()` (`@st.cache_resource`), 완성된 `main()`.

- [ ] **Step 1: main() 완성 (게이트 + 캐시 커넥션 + 탭 + 사이드바)**

`db_monitor.py` 의 기존 `main()` 을 아래로 교체:

```python
@st.cache_resource
def get_conn():
    return psycopg2.connect(**db_conn_params())


@st.cache_data(ttl=60)
def _overview_data():
    conn = get_conn()
    tables = fetch_tables(conn)
    return fetch_counts(conn, tables)


def _password_gate() -> bool:
    if st.session_state.get("monitor_authed"):
        return True
    st.title("DB 모니터")
    pw = st.text_input("비밀번호", type="password")
    if st.button("접속"):
        if verify_password(pw, st.secrets["monitor"]["password"]):
            st.session_state["monitor_authed"] = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def main() -> None:
    st.set_page_config(page_title="DB 모니터", layout="wide")
    if not _password_gate():
        return

    with st.sidebar:
        st.caption("대상 프로젝트")
        st.code("ivpzfrvboazpbcejpqwc\nap-south-1", language=None)
        if st.button("새로고침"):
            st.cache_data.clear()
            st.rerun()
        if st.button("로그아웃"):
            st.session_state.pop("monitor_authed", None)
            st.rerun()

    try:
        conn = get_conn()
    except Exception as e:  # noqa: BLE001
        st.error("DB 연결 실패 — secrets 확인")
        st.exception(e)
        return

    st.title("DB 모니터")
    t1, t2, t3, t4 = st.tabs(["개요", "추이", "브라우저", "운영"])
    with t1:
        render_overview(conn)
    with t2:
        render_trends(conn)
    with t3:
        render_browser(conn)
    with t4:
        render_ops(conn)
```

주의: `render_overview` 는 캐시를 쓰도록 `_overview_data()` 를 사용하게 바꿔도 되지만, 여기서는 단순화를 위해 각 render 가 직접 conn 을 조회한다(ttl 캐시는 후속 개선 여지). `_overview_data` 는 사용하지 않으면 제거해도 무방하나, 개요를 캐시로 돌리려면 `render_overview` 를 `rows = _overview_data()` 로 바꾼다. **선택: `render_overview(conn)` 내부의 `tables=... ; rows=...` 두 줄을 `rows = _overview_data()` 로 교체하고 `df = pd.DataFrame(rows)` 아래 `tables` 참조를 `len({r['table'] for r in rows})` 로 바꾼다.** (캐시 적용.)

- [ ] **Step 2: 전체 테스트 재확인 (UI 변경이 함수 import를 깨지 않는지)**

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && python -m pytest tests/test_db_monitor.py -v`
Expected: 14개 PASS (import 시 UI 실행 안 됨 — `__main__` 가드 덕분).

- [ ] **Step 3: 로컬 스모크 실행**

`.streamlit/secrets.toml` 의 `[monitor].password` 와 `[db].password` 가 실제 값으로 채워져 있는지 확인 후:

Run: `cd "C:/Users/user/.claude-worktrees/260527 YIDSDC" && streamlit run db_monitor.py --server.headless true`
확인 항목(브라우저 http://localhost:8501):
1. 비밀번호 게이트 — 틀린 값 차단, 맞는 값 통과.
2. 개요 — equipment 17, inspection_tasks 39 등 표시, PyroSafe/FIRE-PASS 그룹 분리.
3. 추이 — deficiencies 차트 렌더, 총 17건.
4. 브라우저 — 테이블 선택·검색 동작.
5. 운영 — attachments 버킷(6파일), Auth 사용자 4명.
확인 후 Ctrl+C 로 종료.

- [ ] **Step 4: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add db_monitor.py
git commit -m "feat(db-monitor): main() 조립 — 게이트·캐시 커넥션·4탭·사이드바"
```

---

## Task 7: 배포 안내 문서

**Files:**
- Create: `docs/db-monitor-deploy.md`

- [ ] **Step 1: 배포 안내 작성**

`docs/db-monitor-deploy.md`:

```markdown
# DB 모니터 배포 (Streamlit Cloud)

같은 리포(YonginAIDC)에서 **별도 앱**으로 배포한다. PyroSafe 본 앱과 독립.

## 절차
1. `feat/db-monitor` 브랜치를 main 에 머지하고 push.
2. https://share.streamlit.io → **New app**.
   - Repository: `sojunghan2000-droid/YonginAIDC`
   - Branch: `main`
   - Main file path: `db_monitor.py`
3. **Advanced settings → Secrets** 에 아래 붙여넣기(값 실제로 채움):

   ```toml
   [monitor]
   password = "<모니터 접속 비밀번호>"

   [db]
   host = "aws-0-ap-south-1.pooler.supabase.com"
   port = 5432
   dbname = "postgres"
   user = "postgres.ivpzfrvboazpbcejpqwc"
   password = "<대상 DB 비밀번호>"
   ```
4. **Deploy** → 발급된 URL 접속 → 모니터 비밀번호로 로그인.

## 주의
- 읽기전용(SELECT). 쓰기 기능 없음.
- 대화에 노출된 DB 비밀번호·service_role 키는 rotate 권장. rotate 후 위 Secrets 의 `[db].password` 갱신.
- DB 비밀번호를 바꾸면 pooler 접속도 갱신 필요.
```

- [ ] **Step 2: 커밋**

```bash
cd "C:/Users/user/.claude-worktrees/260527 YIDSDC"
git add docs/db-monitor-deploy.md
git commit -m "docs(db-monitor): Streamlit Cloud 배포 안내"
```

---

## Self-Review (작성자 확인 완료)

- **Spec 커버리지**: §3.1 개요→Task2, §3.2 추이→Task3, §3.3 브라우저→Task4, §3.4 운영→Task5, §2 아키텍처/게이트→Task1·6, §6 보안(secrets/화이트리스트)→Task1·2·4, §10 배포→Task7. 전부 커버.
- **Placeholder**: secrets 값 자리표시자(`<DB_PW>` 등)는 의도적. 코드 스텝은 실제 구현 포함.
- **타입 일관성**: `fetch_tables`/`fetch_counts`/`fetch_created_at_tables`/`fetch_daily`/`fetch_rows`/`filter_df`/`fetch_storage`/`fetch_auth`/`_has_created_at`/`_table_group` 시그니처가 정의 태스크와 사용 태스크에서 일치. `verify_password(entered, expected)` 일관.
- **created_at 없는 테이블**(approvals/day_logs/drawings/zones): `fetch_counts`·`fetch_rows`·`fetch_created_at_tables` 모두 처리(검증 완료).
