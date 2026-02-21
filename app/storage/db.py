from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql://expense_user:UltraStrongPass@localhost:5432/expenses_db"

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False  # turn True if debugging SQL
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()
