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
        if revision == "0001":
            with sqlite3.connect(path) as db:
                db.execute("""INSERT INTO model_routes
                    (id, public_name, upstream_model, provider_id, max_output_tokens,
                     tokenizer, active, created_at, updated_at)
                    VALUES ('legacy', 'legacy', 'custom', 'provider', 100000,
                            'cl100k_base', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""")
    with sqlite3.connect(path) as db:
        cols = {r[1]: r for r in db.execute("PRAGMA table_info(model_routes)")}
        assert cols["api_mode"][4] == "'chat'"
        assert "reasoning_effort" in cols
        assert "default_output_tokens" in cols
        assert db.execute("SELECT max_output_tokens, default_output_tokens FROM model_routes"
                          ).fetchone() == (100000, 100000)
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003"
    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0001"],
        env=env,
        cwd=root,
        check=True,
        capture_output=True,
    )
    with sqlite3.connect(path) as db:
        assert "api_mode" not in {r[1] for r in db.execute("PRAGMA table_info(model_routes)")}
