from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Annotated

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import bearer, verify_password
from app.models.models import Household, User
from app.schemas import Token
from app.services.weather import Forecast, WeatherCache, WeatherUnavailable
from app.settings_routes import Db, Pin, PublicUser, WeatherLocation

router = APIRouter(prefix="/screen")
weather = WeatherCache(httpx.Client(timeout=5.0))
pin_attempts: dict[int, tuple[int, float]] = {}
pin_lock = Lock()


class ScreenLogin(BaseModel):
    user_id: int
    pin: Pin | None = None


def household_users(db: Db):
    return (
        db.query(User)
        .join(Household)
        .filter(
            Household.name == settings.household_name,
            User.is_active.is_(True),
        )
    )


@router.get("/users", response_model=list[PublicUser])
def users(db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return [
        PublicUser.from_user(user)
        for user in household_users(db).order_by(User.display_name, User.id)
    ]


@router.post("/session", response_model=Token)
def start_session(data: ScreenLogin, db: Db, response: Response):
    user = household_users(db).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no disponible")
    if user.screen_pin_hash:
        if data.pin is None:
            raise HTTPException(
                401,
                detail={
                    "code": "pin_required",
                    "message": "Introduce el PIN de pantalla",
                },
            )
        with pin_lock:
            now = monotonic()
            count, expires = pin_attempts.get(user.id, (0, 0))
            if expires <= now:
                count, expires = 0, now + 60
            if count >= 5:
                raise HTTPException(429, "Demasiados intentos. Espera un minuto.")
            pin_attempts[user.id] = (count + 1, expires)
        if not verify_password(data.pin, user.screen_pin_hash):
            raise HTTPException(
                401, detail={"code": "invalid_pin", "message": "PIN incorrecto"}
            )
        with pin_lock:
            pin_attempts.pop(user.id, None)
    response.headers["Cache-Control"] = "no-store"
    return Token(
        access_token=jwt.encode(
            {
                "sub": str(user.id),
                "scope": "screen",
                "version": user.screen_version,
                "exp": datetime.now(UTC) + timedelta(days=30),
            },
            settings.secret_key,
            algorithm="HS256",
        )
    )


def screen_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)], db: Db
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "scope", "version"]},
        )
        if payload["scope"] != "screen":
            raise jwt.InvalidTokenError()
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError) as error:
        raise HTTPException(401, "Sesión de pantalla no válida") from error
    user = household_users(db).filter(User.id == user_id).first()
    if not user or user.screen_version != payload["version"]:
        raise HTTPException(401, "Sesión de pantalla no disponible")
    return user


@router.get("/weather", response_model=Forecast)
def screen_weather(
    user: Annotated[User, Depends(screen_user)], db: Db, response: Response
):
    household = db.get(Household, user.household_id)
    location = WeatherLocation.from_household(household)
    response.headers["Cache-Control"] = "no-store"
    try:
        return weather.get(household.id, location)
    except WeatherUnavailable as error:
        raise HTTPException(503, "El tiempo no está disponible ahora") from error
