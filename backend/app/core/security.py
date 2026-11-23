from datetime import datetime, timedelta, timezone

import jwt
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

password_hash = PasswordHash.recommended()
bearer = HTTPBearer()
def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed: str) -> bool: return password_hash.verify(password, hashed)
def create_token(user: User) -> str:
    payload = {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        if payload.get("scope", "access") != "access":
            raise jwt.InvalidTokenError()
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido") from error
    user = db.get(User, user_id)
    if not user or not user.is_active: raise HTTPException(status_code=401, detail="Usuario no disponible")
    return user
