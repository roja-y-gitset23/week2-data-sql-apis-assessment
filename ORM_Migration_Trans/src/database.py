
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:Tommyset%40123@localhost:5432/orders_db",
)  # change user:password if needed

engine = create_engine(
    DATABASE_URL,
    pool_size=5,         # connections kept open
    max_overflow=10,     # extra connections allowed under load
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass