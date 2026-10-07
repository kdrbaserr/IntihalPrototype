"""Password and opaque-session primitives; no plain credentials in persistence."""

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id: 64 MiB memory, three passes, four lanes; each hash gets a fresh salt.
password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    if not 15 <= len(password) <= 128:
        raise ValueError("Parola 15–128 karakter olmalı.")
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        valid = password_hasher.verify(encoded or DUMMY_PASSWORD_HASH, password)
        return valid and encoded is not None
    except (VerificationError, InvalidHashError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
