"""DB 모니터 — 신규 Supabase 프로젝트(PyroSafe+FIRE-PASS) 전체 DB 읽기전용 대시보드.

Streamlit Cloud 별도 앱으로 배포. 데이터는 Supabase pooler 직결(psycopg2)로 조회하며
public 테이블뿐 아니라 auth/storage 스키마까지 읽는다. 읽기전용(SELECT only).
"""
from __future__ import annotations

import hmac

import pandas as pd
import plotly.express as px
import psycopg2  # noqa: F401 — 배포/런타임 커넥션에 사용(Task 6)
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


def main() -> None:
    st.set_page_config(page_title="DB 모니터", layout="wide")
    st.title("DB 모니터")
    st.info("구현 예정")


if __name__ == "__main__":
    main()
