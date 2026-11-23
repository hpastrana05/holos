from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import current_user, hash_password
from app.db.session import get_db
from app.models.models import Household, Role, User

router = APIRouter(prefix="/settings")
Db = Annotated[Session, Depends(get_db)]
Account = Annotated[User, Depends(current_user)]
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]
LoginName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=255, pattern=r"^\S+$"
    ),
]
Password = Annotated[str, Field(min_length=8, max_length=128)]
Pin = Annotated[str, Field(pattern=r"^[0-9]{4,8}$")]


def admin(user: Account) -> User:
    if user.role != Role.admin:
        raise HTTPException(
            403, "Solo los administradores del hogar pueden hacer cambios"
        )
    return user


Admin = Annotated[User, Depends(admin)]


class PublicUser(BaseModel):
    id: int
    name: str
    color: str
    avatar: str

    @classmethod
    def from_user(cls, user: User):
        return cls(
            id=user.id,
            name=user.display_name or f"Usuario {user.id}",
            color=user.color,
            avatar=user.avatar,
        )


class UserDetails(PublicUser):
    email: str
    role: Role
    is_active: bool
    has_pin: bool

    @classmethod
    def from_user(cls, user: User):
        return cls(
            **PublicUser.from_user(user).model_dump(),
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            has_pin=user.screen_pin_hash is not None,
        )


class UserFields(BaseModel):
    name: Name
    email: LoginName
    role: Role = Role.member
    color: str = Field(default="#b7a7ff", pattern=r"^#[0-9a-fA-F]{6}$")
    avatar: Literal["initial", "sun", "moon", "star", "heart"] = "initial"
    pin: Pin | None = None


class UserCreate(UserFields):
    password: Password


class UserEdit(UserFields):
    is_active: bool
    password: Password | None = None


class WeatherLocation(BaseModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)
    ]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @classmethod
    def from_household(cls, household: Household):
        return cls(
            name=household.weather_name,
            latitude=household.weather_latitude,
            longitude=household.weather_longitude,
        )


@router.get("/me", response_model=UserDetails)
def me(user: Account):
    return UserDetails.from_user(user)


@router.get("/users", response_model=list[UserDetails])
def users(user: Admin, db: Db):
    return [
        UserDetails.from_user(item)
        for item in db.query(User)
        .filter_by(household_id=user.household_id)
        .order_by(User.id)
    ]


def save_user(db: Session):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Ese correo o usuario ya está en uso") from error


@router.post("/users", response_model=UserDetails, status_code=201)
def create_user(data: UserCreate, user: Admin, db: Db):
    item = User(
        display_name=data.name,
        email=data.email,
        role=data.role,
        color=data.color,
        avatar=data.avatar,
        household_id=user.household_id,
        password_hash=hash_password(data.password),
        screen_pin_hash=hash_password(data.pin) if data.pin else None,
    )
    db.add(item)
    save_user(db)
    return UserDetails.from_user(item)


@router.put("/users/{user_id}", response_model=UserDetails)
def edit_user(user_id: int, data: UserEdit, user: Admin, db: Db):
    household_id = user.household_id
    item = db.query(User).filter_by(id=user_id, household_id=household_id).first()
    if not item:
        raise HTTPException(404, "Usuario no encontrado")
    changes = {
        "display_name": data.name,
        "email": data.email,
        "role": data.role,
        "color": data.color,
        "avatar": data.avatar,
        "is_active": data.is_active,
    }
    if data.password:
        changes["password_hash"] = hash_password(data.password)
    if "pin" in data.model_fields_set:
        changes["screen_pin_hash"] = hash_password(data.pin) if data.pin else None
    if "pin" in data.model_fields_set or not data.is_active:
        changes["screen_version"] = User.screen_version + 1

    statement = update(User).where(
        User.id == user_id, User.household_id == household_id
    )
    if not data.is_active or data.role != Role.admin:
        other_admins = (
            select(func.count())
            .select_from(User)
            .where(
                User.household_id == household_id,
                User.id != user_id,
                User.role == Role.admin,
                User.is_active.is_(True),
            )
            .scalar_subquery()
        )
        statement = statement.where(
            (User.role != Role.admin) | User.is_active.is_(False) | (other_admins > 0)
        )
    try:
        result = db.execute(
            statement.values(**changes).execution_options(synchronize_session=False)
        )
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Ese correo o usuario ya está en uso") from error
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, "Debe quedar un administrador activo en el hogar")
    save_user(db)
    return UserDetails.from_user(item)


@router.get("/weather-location", response_model=WeatherLocation)
def get_weather_location(user: Account, db: Db):
    return WeatherLocation.from_household(db.get(Household, user.household_id))


@router.put("/weather-location", response_model=WeatherLocation)
def set_weather_location(data: WeatherLocation, user: Admin, db: Db):
    household = db.get(Household, user.household_id)
    household.weather_name = data.name
    household.weather_latitude = data.latitude
    household.weather_longitude = data.longitude
    db.commit()
    return data
