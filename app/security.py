from __future__ import annotations

import asyncio
import base64
import hashlib
import ipaddress
import re
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> None:
    if len(password) < 12 or len(password) > 128:
        raise ValueError("密码长度必须为 12–128 位")
    classes = [
        bool(re.search(r"[a-z]", password)),
        bool(re.search(r"[A-Z]", password)),
        bool(re.search(r"\d", password)),
        bool(re.search(r"[^A-Za-z0-9]", password)),
    ]
    if sum(classes) < 3:
        raise ValueError("密码必须包含大小写字母、数字、符号中的至少三类")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_session_token() -> Tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, sha256_text(token)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def generate_access_key() -> Tuple[str, str, str, str]:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    plaintext = f"ts_sk_{prefix}_{secret}"
    return plaintext, prefix, sha256_text(plaintext), plaintext[-4:]


def access_key_prefix(value: str) -> str:
    match = re.fullmatch(r"ts_sk_([0-9a-f]{8})_[-_A-Za-z0-9]{32,}", value)
    if not match:
        raise ValueError("invalid access key")
    return match.group(1)


@dataclass
class EncryptedSecret:
    ciphertext: bytes
    nonce: bytes
    last4: str
    version: int


def encrypt_secret(plaintext: str, settings: Settings) -> EncryptedSecret:
    nonce = secrets.token_bytes(12)
    aad = f"token-station:v{settings.token_encryption_key_version}".encode()
    ciphertext = AESGCM(settings.encryption_key_bytes()).encrypt(
        nonce, plaintext.encode("utf-8"), aad
    )
    return EncryptedSecret(
        ciphertext=ciphertext,
        nonce=nonce,
        last4=plaintext[-4:] if len(plaintext) >= 4 else plaintext,
        version=settings.token_encryption_key_version,
    )


def decrypt_secret(ciphertext: bytes, nonce: bytes, version: int, settings: Settings) -> str:
    if version != settings.token_encryption_key_version:
        raise ValueError("unsupported encryption key version")
    aad = f"token-station:v{version}".encode()
    plaintext = AESGCM(settings.encryption_key_bytes()).decrypt(nonce, ciphertext, aad)
    return plaintext.decode("utf-8")


def is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value <= datetime.now(timezone.utc)


def _resolve_host(hostname: str, port: int) -> list[str]:
    return list(
        {item[4][0] for item in socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)}
    )


async def validate_upstream_url(url: str, allow_private: bool = False) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("上游地址必须是有效的 HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("上游地址不能包含凭证、查询参数或片段")
    port = parsed.port or 443
    try:
        addresses = await asyncio.to_thread(_resolve_host, parsed.hostname, port)
    except OSError as exc:
        raise ValueError("无法解析上游域名") from exc
    if not addresses:
        raise ValueError("上游域名没有可用地址")
    if not allow_private:
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                raise ValueError("上游域名解析到了非公网地址")
    normalized = f"https://{parsed.hostname}"
    if port != 443:
        normalized += f":{port}"
    path = parsed.path.rstrip("/")
    if path:
        normalized += path
    return normalized


def encode_secret_for_env() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
