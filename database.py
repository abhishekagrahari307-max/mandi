import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Index
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

# 1. USER TABLE FOR SECURE ADMIN PANEL LOGIN & ROLE-BASED ACCESS CONTROL (RBAC)
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="admin") # "admin", "trader", "farmer", "staff"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# 2. MANDI RECORD TABLE WITH ADVANCED DATABASE INDEXES (FOR ENTERPRISE PERFORMANCE)
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

    __table_args__ = (
        Index('idx_district_commodity', 'district', 'commodity'),
        Index('idx_mandi_commodity', 'mandi', 'commodity'),
    )

# 3. ALERTS SUBSCRIPTION TABLE
class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    contact_type = Column(String, nullable=False) # "whatsapp", "telegram", "email"
    contact_value = Column(String, nullable=False, index=True)
    district = Column(String, default="all")
    commodity = Column(String, default="all")
    is_active = Column(Boolean, default=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow)

# 4. ENTERPRISE AUDIT LOGS TABLE
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)
    username = Column(String, index=True, nullable=True)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

# 5. ENTERPRISE FINANCIAL INVOICES TABLE
class Invoice(Base):
    __tablename__ = "financial_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String, unique=True, index=True, nullable=False)
    farmer_name = Column(String, index=True, default="Anonymous Farmer")
    crop_name = Column(String, nullable=False)
    weight = Column(Float, nullable=False) # In Quintals
    rate = Column(Float, nullable=False) # Per Quintal
    gross_amount = Column(Float, nullable=False)
    commission_amount = Column(Float, default=0.0)
    labor_amount = Column(Float, default=0.0)
    mandi_tax_amount = Column(Float, default=0.0)
    transport_amount = Column(Float, default=0.0)
    net_payout = Column(Float, nullable=False)
    verification_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# 6. ENTERPRISE LIVE AUCTION TABLE (NEW PHASE 5 LIVE AUCTION ENGINE)
class AuctionLot(Base):
    __tablename__ = "auction_lots"
    
    id = Column(Integer, primary_key=True, index=True)
    lot_number = Column(String, unique=True, index=True, nullable=False)
    farmer_name = Column(String, default="Vijay Kumar")
    crop_name = Column(String, nullable=False)
    quantity = Column(Float, nullable=False) # In Quintals
    starting_rate = Column(Float, nullable=False) # Per Quintal
    highest_bid = Column(Float, nullable=False)
    highest_bidder = Column(String, nullable=True) # Username of trader with highest bid
    status = Column(String, default="active") # "active", "completed", "cancelled"
    created_at = Column(DateTime, default=datetime.utcnow)

# Initialize Database tables
def init_db():
    Base.metadata.create_all(bind=engine)
