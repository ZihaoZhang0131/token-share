import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_additive_migration_and_downgrade(tmp_path):
    path = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{path}"}
    root = Path(__file__).resolve().parents[1]
    for revision in ("0001", "head"):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", revision],
            env=env,
            cwd=root,
            check=True,
            capture_output=True,
        )
    with sqlite3.connect(path) as db:
        cols = {r[1]: r for r in db.execute("PRAGMA table_info(model_routes)")}
        assert cols["api_mode"][4] == "'chat'"
        assert "reasoning_effort" in cols
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0001"],
        env=env,
        cwd=root,
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(path) as db:
        assert "api_mode" not in {r[1] for r in db.execute("PRAGMA table_info(model_routes)")}
