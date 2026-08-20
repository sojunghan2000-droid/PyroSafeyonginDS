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


def test_fetch_created_at_tables(conn):
    tabs = db_monitor.fetch_created_at_tables(conn)
    assert "deficiencies" in tabs
    assert "zones" not in tabs          # created_at 없음


def test_fetch_daily_sums_to_rowcount(conn):
    df = db_monitor.fetch_daily(conn, "deficiencies", None)
    assert list(df.columns) == ["d", "c"]
    assert int(df["c"].sum()) == 17     # deficiencies 총 17건(이관 검증값)
