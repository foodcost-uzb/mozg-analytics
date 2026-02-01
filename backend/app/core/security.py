import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenPayload(BaseModel):
    sub: str
    exp: datetime
    type: str  # "access" or "refresh"
    org_id: Optional[str] = None


class TokenData(BaseModel):
    user_id: str
    org_id: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return TokenPayload(**payload)
    except JWTError:
        return None


def verify_telegram_auth(auth_data: dict[str, str]) -> bool:
    """Verify Telegram Mini App authorization data."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return False

    check_hash = auth_data.pop("hash", None)
    if not check_hash:
        return False

    # Sort and format data
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(auth_data.items())
    )

    # Create secret key from bot token
    secret_key = hashlib.sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()

    # Calculate HMAC
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(calculated_hash, check_hash)
