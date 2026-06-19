import pytest

from app.data.db import connect
from app.data.seed import ensure_seeded


@pytest.fixture
def seeded_conn(tmp_path):
    db = str(tmp_path / "crm.db")
    ensure_seeded(db)
    conn = connect(db)
    yield conn
    conn.close()
