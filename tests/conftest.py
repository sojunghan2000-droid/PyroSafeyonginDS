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
