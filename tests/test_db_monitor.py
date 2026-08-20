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
