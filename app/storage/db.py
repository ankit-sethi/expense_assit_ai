from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DB_URL

DATABASE_URL = DB_URL

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False  # turn True if debugging SQL
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
