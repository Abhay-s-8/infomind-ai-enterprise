import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    s = get_settings()
    expires = datetime.now(UTC) + timedelta(minutes=s.access_token_minutes)
    payload = {"sub": user_id, "role": role, "exp": expires, "jti": uuid.uuid4().hex}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm), s.access_token_minutes * 60


def decode_access_token(token: str) -> dict:
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
