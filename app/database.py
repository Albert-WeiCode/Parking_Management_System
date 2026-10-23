from urllib.parse import quote_plus

import pymysql
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import (
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    user = quote_plus(MYSQL_USER)
    password = quote_plus(MYSQL_PASSWORD)
    credentials = f"{user}:{password}" if password else user
    return (
        f"mysql+pymysql://{credentials}@{MYSQL_HOST}:{MYSQL_PORT}/"
        f"{MYSQL_DATABASE}?charset=utf8mb4"
    )


engine = create_engine(_database_url(), pool_pre_ping=True, pool_recycle=1800)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_database() -> None:
    connection = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        connection.close()


def init_database() -> None:
    from app import models

    ensure_database()
    Base.metadata.create_all(bind=engine)
    migrate_parking_records()
    models.seed_admin()
    with SessionLocal() as session:
        if session.get(models.ParkingSetting, 1) is None:
            session.add(models.ParkingSetting(id=1, capacity=100))
            session.commit()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def migrate_parking_records():
    """Add nullable visit fields; old records stay historical, never assumed present."""
    columns = {column["name"] for column in inspect(engine).get_columns("parking_records")}
    with engine.begin() as connection:
        for name, sql_type in (("entered_at", "DATETIME"), ("exited_at", "DATETIME"), ("active_plate", "VARCHAR(32)")):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE parking_records ADD COLUMN {name} {sql_type} NULL"))
        indexes = inspect(connection).get_indexes("parking_records")
        names = {item["name"] for item in indexes}
        for column in ("entered_at", "exited_at"):
            if f"ix_parking_records_{column}" not in names:
                connection.execute(text(f"CREATE INDEX ix_parking_records_{column} ON parking_records ({column})"))
        unique_columns = [item["column_names"] for item in inspect(connection).get_unique_constraints("parking_records")]
        unique_columns += [item["column_names"] for item in indexes if item.get("unique")]
        if ["active_plate"] not in unique_columns:
            connection.execute(text("CREATE UNIQUE INDEX uq_parking_records_active_plate ON parking_records (active_plate)"))
