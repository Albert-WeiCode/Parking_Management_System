import hashlib
import hmac
import os
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import ADMIN_PASSWORD, ADMIN_USERNAME
from app.database import Base, SessionLocal


def hash_password(password: str, salt: str | None = None) -> str:
    salt_bytes = bytes.fromhex(salt) if salt else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt_bytes, 120_000)
    return f"{salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    actual = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(actual, expected)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class ParkingRecord(Base):
    __tablename__ = "parking_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), index=True)
    province: Mapped[str] = mapped_column(String(16), index=True)
    source: Mapped[str] = mapped_column(String(32), default="手工录入")
    note: Mapped[str] = mapped_column(Text, default="")
    entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    active_plate: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)


def seed_admin() -> None:
    with SessionLocal() as session:
        exists = session.query(User).filter(User.username == ADMIN_USERNAME).first()
        if not exists:
            session.add(
                User(
                    username=ADMIN_USERNAME,
                    password_hash=hash_password(ADMIN_PASSWORD),
                )
            )
            session.commit()


class ParkingSetting(Base):
    __tablename__ = "parking_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer, default=100)
