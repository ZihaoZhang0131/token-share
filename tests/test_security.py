import pytest

from app.config import get_settings
from app.security import (
    decrypt_secret,
    encrypt_secret,
    generate_access_key,
    validate_password_strength,
    validate_upstream_url,
)


def test_secret_round_trip_and_access_key_shape():
    settings = get_settings()
    encrypted = encrypt_secret("sk-real-secret-1234", settings)
    assert encrypted.last4 == "1234"
    assert b"sk-real-secret" not in encrypted.ciphertext
    assert (
        decrypt_secret(encrypted.ciphertext, encrypted.nonce, encrypted.version, settings)
        == "sk-real-secret-1234"
    )
    plaintext, prefix, digest, last4 = generate_access_key()
    assert plaintext.startswith(f"ts_sk_{prefix}_")
    assert plaintext.endswith(last4)
    assert plaintext not in digest


def test_password_policy():
    validate_password_strength("StrongPassword!123")
    with pytest.raises(ValueError):
        validate_password_strength("short")


@pytest.mark.asyncio
async def test_private_upstream_is_rejected():
    with pytest.raises(ValueError, match="非公网"):
        await validate_upstream_url("https://127.0.0.1/v1")
