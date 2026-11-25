from hashlib import sha256
from secrets import token_urlsafe
from time import time

from app.models.models import User
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

CODE_TTL = 600
CLEAR_CODE = {"telegram_code_hash": None, "telegram_code_expires": None}


def digest(code: str) -> str:
    return sha256(code.encode()).hexdigest()


def clear_expired(db: Session, now: int):
    expired = User.telegram_code_expires <= now
    if db.query(User.id).filter(expired).first():
        db.execute(update(User).where(expired).values(**CLEAR_CODE))
        db.commit()


def issue_code(db: Session, user_id: int) -> str | None:
    now = int(time())
    clear_expired(db, now)
    code = token_urlsafe(18)
    result = db.execute(
        update(User).where(User.id == user_id, User.is_active.is_(True), User.telegram_id.is_(None))
        .values(telegram_code_hash=digest(code), telegram_code_expires=now + CODE_TTL)
    )
    db.commit()
    return code if result.rowcount else None


def redeem_code(db: Session, telegram_id: int, code: str, now: int) -> bool:
    try:
        result = db.execute(
            update(User).where(
                User.telegram_code_hash == digest(code),
                User.telegram_code_expires > now,
                User.telegram_id.is_(None),
                User.is_active.is_(True),
            ).values(telegram_id=telegram_id, **CLEAR_CODE)
        )
        db.commit()
        return bool(result.rowcount)
    except IntegrityError:
        db.rollback()
        return False


def unlink(db: Session, user_id: int, telegram_id: int | None = None):
    statement = update(User).where(User.id == user_id)
    if telegram_id is not None:
        statement = statement.where(User.telegram_id == telegram_id)
    db.execute(statement.values(telegram_id=None, telegram_last_message=None, **CLEAR_CODE))
    db.commit()
