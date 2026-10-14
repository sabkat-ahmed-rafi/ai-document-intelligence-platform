import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest, new as new_hmac
from secrets import randbelow, token_urlsafe

import jwt

from core.config import settings
from .exceptions import TokenExpired

ALGORITHM = "HS256"
PASSWORD_RESET_CODE_LENGTH = 6
PASSWORD_RESET_CODE_EXPIRE_MINUTES = 10
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 10
PASSWORD_RESET_MAX_ATTEMPTS = 5
PASSWORD_RESET_RESEND_COOLDOWN_SECONDS = 60


def encode_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.ACCESS_TOKEN_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.ACCESS_TOKEN_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise TokenExpired("Invalid token type")
        return payload
    except jwt.InvalidTokenError:
        raise TokenExpired()


def encode_refresh_token(
    user_id: str,
    token_id: str,
    expires_at: datetime,
) -> str:
    payload = {
        "sub": user_id,
        "jti": token_id,
        "type": "refresh",
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.REFRESH_TOKEN_SECRET, algorithm=ALGORITHM)


def decode_refresh_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.REFRESH_TOKEN_SECRET,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "jti", "type", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise TokenExpired()

    if payload["type"] != "refresh":
        raise TokenExpired("Invalid token type")
    return payload


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    token_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = encode_refresh_token(user_id, token_id, expires_at)
    return token, token_id, expires_at


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_password_reset_code() -> str:
    return f"{randbelow(10 ** PASSWORD_RESET_CODE_LENGTH):0{PASSWORD_RESET_CODE_LENGTH}d}"


def hash_password_reset_code(request_id: str, code: str) -> str:
    value = f"{request_id}:{code}".encode("utf-8")
    return new_hmac(
        settings.PASSWORD_RESET_SECRET.encode("utf-8"),
        value,
        sha256,
    ).hexdigest()


def verify_password_reset_code(
    request_id: str,
    code: str,
    expected_hash: str,
) -> bool:
    actual_hash = hash_password_reset_code(request_id, code)
    return compare_digest(actual_hash, expected_hash)


def create_password_reset_token() -> tuple[str, str]:
    token = token_urlsafe(32)
    return token, hash_password_reset_token(token)


def hash_password_reset_token(token: str) -> str:
    return new_hmac(
        settings.PASSWORD_RESET_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        sha256,
    ).hexdigest()
