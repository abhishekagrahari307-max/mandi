import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite Database for portable runs in workspace, can easily swap to PostgreSQL/MySQL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./mandi_v2.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 1. USER TABLE FOR SECURE ADMIN PANEL LOGIN
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="admin") # admin, editor, viewer
    created_at = Column(DateTime, default=datetime.utcnow)

# 2. MANDI RECORD TABLE WITH ALL EXTRA DETAILS (Variety, Grade, Arrivals)
class MandiRecord(Base):
    __tablename__ = "mandi_records"
    
    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, default="Uttar Pradesh")
    district = Column(String, index=True, nullable=False)
    district_hi = Column(String, index=True, nullable=False)
    mandi = Column(String, index=True, nullable=False)
    mandi_hi = Column(String, index=True, nullable=False)
    commodity = Column(String, index=True, nullable=False)
    commodity_hi = Column(String, index=True, nullable=False)
    variety = Column(String, default="FAQ")
    variety_hi = Column(String, default="सामान्य (FAQ)")
    grade = Column(String, default="FAQ")
    grade_hi = Column(String, default="FAQ")
    arrivals = Column(Integer, default=0)
    arrivals_unit = Column(String, default="Tonnes")
    arrivals_unit_hi = Column(String, default="टन")
    min_price = Column(Float, nullable=False)
    max_price = Column(Float, nullable=False)
    modal_price = Column(Float, nullable=False)
    price_unit = Column(String, default="Quintal")
    arrival_date = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Initialize Database tables
def init_db():
    Base.metadata.create_all(bind=engine)
