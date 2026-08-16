import base64
import os
import secrets
import shutil
import tempfile
from pathlib import Path

TEST_DIR = Path(tempfile.mkdtemp(prefix="token-station-tests-"))
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DIR / 'test.db'}"
os.environ["REDIS_URL"] = ""
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SECURE_COOKIES"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-000000"
os.environ["TOKEN_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "InitialAdmin!234"


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TEST_DIR, ignore_errors=True)
