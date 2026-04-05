from sqlalchemy import Column, String, Numeric, TIMESTAMP, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func, text
import uuid
from pgvector.sqlalchemy import Vector
from storage.db import Base


class Expense(Base):

    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    txn_date = Column(TIMESTAMP, nullable=False)

    amount = Column(Numeric(12,2), nullable=False)
    currency = Column(String, default="INR")

    merchant = Column(Text)
    category = Column(Text)
    sub_category = Column(Text)

    payment_method = Column(Text)
    bank_name = Column(Text)

    source = Column(Text)
    raw_text = Column(Text)
    
    embedding = Column(Vector(1536))

    created_at = Column(TIMESTAMP, server_default=func.now())


class MerchantMapping(Base):

    __tablename__ = "merchant_mappings"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    raw_pattern  = Column(Text, unique=True, nullable=False)
    clean_name   = Column(Text, nullable=False)
    category     = Column(Text, nullable=False)
    sub_category = Column(Text, nullable=False, server_default=text("''"))
    priority     = Column(Integer, nullable=False, server_default=text("0"))
    created_at   = Column(TIMESTAMP, server_default=func.now())
    updated_at   = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class Credit(Base):

    __tablename__ = "credits"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    txn_date       = Column(TIMESTAMP, nullable=False)
    amount         = Column(Numeric(12, 2), nullable=False)
    currency       = Column(String, default="INR")
    merchant       = Column(Text)
    category       = Column(Text)
    sub_category   = Column(Text)
    payment_method = Column(Text)
    bank_name      = Column(Text)
    source         = Column(Text)
    raw_text       = Column(Text)
    embedding      = Column(Vector(1536))
    created_at     = Column(TIMESTAMP, server_default=func.now())
