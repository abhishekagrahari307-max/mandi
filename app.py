import os
import json
import urllib.request
import re
import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Request, WebSocket
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
import bcrypt
from jose import JWTError, jwt

import database as db
import prediction as pred_engine
import alerts as alert_engine

logger = logging.getLogger(__name__)
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT in {"prod", "production"}


def _load_jwt_secret() -> str:
    """Load the JWT signing key without ever falling back to a public constant."""
    configured_secret = os.environ.get("JWT_SECRET", "").strip()
    if configured_secret:
        if len(configured_secret.encode("utf-8")) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 bytes")
        return configured_secret
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET is required when ENVIRONMENT=production")

    logger.warning(
        "JWT_SECRET is not configured; using an ephemeral development key. "
        "Existing sessions will be invalid after restart."
    )
    return secrets.token_urlsafe(48)


SECRET_KEY = _load_jwt_secret()
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com").strip() or None

if ADMIN_PASSWORD:
    admin_password_bytes = ADMIN_PASSWORD.encode("utf-8")
    if not 12 <= len(admin_password_bytes) <= 72:
        raise RuntimeError("ADMIN_PASSWORD must be between 12 and 72 bytes")
elif IS_PRODUCTION:
    raise RuntimeError("ADMIN_PASSWORD is required when ENVIRONMENT=production")

cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
    ).split(",")
    if origin.strip()
]
if "*" in cors_origins:
    raise RuntimeError("CORS_ORIGINS must list explicit origins; wildcard access is not allowed")

# Initialize Database
db.init_db()

app = FastAPI(
    title="UP Mandi Enterprise REST API",
    description="UP Mandi Dashboard Version 2.0 Backend & REST API Engine",
    version="2.0.0"
)

# Permit only explicitly configured browser origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/login")

# ================= VALIDATION SCHEMAS =================

class RateCreate(BaseModel):
    district: str = Field(..., min_length=2, max_length=50, pattern=r"^[a-zA-Z\s]+$")
    district_hi: str = Field(..., min_length=2, max_length=50)
    mandi: str = Field(..., min_length=2, max_length=100)
    mandi_hi: str = Field(..., min_length=2, max_length=100)
    commodity: str = Field(..., min_length=2, max_length=100)
    commodity_hi: str = Field(..., min_length=2, max_length=100)
    variety: str = "FAQ"
    variety_hi: str = "सामान्य (FAQ)"
    grade: str = "FAQ"
    grade_hi: str = "FAQ"
    arrivals: int = Field(default=0, ge=0)
    min_price: float = Field(..., gt=0)
    max_price: float = Field(..., gt=0)
    modal_price: float = Field(..., gt=0)
    arrival_date: str = Field(..., pattern=r"^\d{2}/\d{2}/\d{4}$")

class Token(BaseModel):
    access_token: str
    token_type: str

class SubscribeRequest(BaseModel):
    contact_type: str
    contact_value: str = Field(..., min_length=5, max_length=100)
    district: str = "all"
    commodity: str = "all"

class InvoiceCreate(BaseModel):
    farmer_name: str = Field(default="Anonymous Farmer", min_length=3, max_length=100)
    crop_name: str = Field(..., min_length=2, max_length=100)
    weight: float = Field(..., gt=0)
    rate: float = Field(..., gt=0)
    commission_percent: float = Field(default=0.0, ge=0, le=10.0)
    labor_per_bag: float = Field(default=0.0, ge=0)
    bag_size_kg: float = Field(default=50.0, gt=0)
    transport_cost: float = Field(default=0.0, ge=0)
    cess_percent: float = Field(default=0.0, ge=0, le=10.0)

# LIVE AUCTION PYDANTIC SCHEMAS (PHASE 5)
class AuctionLotCreate(BaseModel):
    farmer_name: str = Field(..., min_length=3, max_length=100)
    crop_name: str = Field(..., min_length=2, max_length=100)
    quantity: float = Field(..., gt=0) # In Quintals
    starting_rate: float = Field(..., gt=0)

class BidSubmit(BaseModel):
    lot_number: str
    bid_amount: float = Field(..., gt=0)
    trader_name: str

# Helper functions
def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

def _password_to_bcrypt_bytes(password: str) -> bytes:
    """Encode passwords safely for bcrypt.

    bcrypt has a hard 72-byte input limit. Newer bcrypt releases raise an
    exception for longer values, so validate it ourselves to keep startup and
    login behavior deterministic across dependency versions.
    """
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must be 72 bytes or fewer for bcrypt")
    return password_bytes


def pydantic_to_dict(model: BaseModel) -> dict:
    """Return a plain dict for both Pydantic v1 and v2 models."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()

def sqlalchemy_to_dict(model) -> dict:
    """Serialize a SQLAlchemy model using its mapped table columns."""
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_password_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _password_to_bcrypt_bytes(plain_password),
            hashed_password.encode("utf-8")
        )
    except (TypeError, ValueError):
        return False

def create_access_token(data: dict):
    to_encode = data.copy()
    issued_at = datetime.utcnow()
    expire = issued_at + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"iat": issued_at, "exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db_sess: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db_sess.query(db.User).filter(db.User.username == username).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

def write_audit_log(db_sess: Session, user_id: int, username: str, action: str, details: str, request: Request):
    ip = request.client.host if request.client else "Unknown"
    log_entry = db.AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        details=details,
        ip_address=ip
    )
    db_sess.add(log_entry)
    db_sess.commit()

# Seeding initial data (Auto-run on server start)
@app.on_event("startup")
def seed_database():
    session = db.SessionLocal()
    try:
        # Create or update the configured administrator. There is deliberately
        # no built-in password: production startup already requires one.
        if ADMIN_PASSWORD:
            admin_user = session.query(db.User).filter(
                db.User.username == ADMIN_USERNAME
            ).first()
            if admin_user is None:
                admin_user = db.User(
                    username=ADMIN_USERNAME,
                    hashed_password=get_password_hash(ADMIN_PASSWORD),
                    email=ADMIN_EMAIL,
                    role="admin",
                    is_active=True,
                )
                session.add(admin_user)
            elif not verify_password(ADMIN_PASSWORD, admin_user.hashed_password):
                admin_user.hashed_password = get_password_hash(ADMIN_PASSWORD)
                admin_user.email = ADMIN_EMAIL
                admin_user.role = "admin"
                admin_user.is_active = True

            # Disable the formerly hard-coded account when a differently named
            # administrator is configured in an existing database.
            if ADMIN_USERNAME != "admin":
                legacy_admin = session.query(db.User).filter(
                    db.User.username == "admin"
                ).first()
                if legacy_admin is not None:
                    legacy_admin.is_active = False
            session.commit()
        else:
            logger.warning(
                "ADMIN_PASSWORD is not configured; no administrator account "
                "will be created in development mode."
            )
            
        # Seed initial mandi rates
        records_count = session.query(db.MandiRecord).count()
        if records_count == 0:
            latest_file = "data/latest.json"
            if os.path.exists(latest_file):
                with open(latest_file, "r", encoding="utf-8") as f:
                    latest_data = json.load(f)
                    records = latest_data.get("records", []) if latest_data.get("verified") else []
                    if not records:
                        logger.warning("Skipping rate seed: no verified official snapshot is available")
                    for r in records:
                        m_record = db.MandiRecord(
                            district=r.get("district"),
                            district_hi=r.get("district_hi"),
                            mandi=r.get("mandi"),
                            mandi_hi=r.get("mandi_hi"),
                            commodity=r.get("commodity"),
                            commodity_hi=r.get("commodity_hi"),
                            variety=r.get("variety", "FAQ"),
                            variety_hi=r.get("variety_hi", "सामान्य (FAQ)"),
                            grade=r.get("grade", "FAQ"),
                            grade_hi=r.get("grade_hi", "FAQ"),
                            arrivals=r.get("arrivals"),
                            arrivals_unit=r.get("arrivals_unit"),
                            arrivals_unit_hi=r.get("arrivals_unit_hi"),
                            min_price=r.get("min_price"),
                            max_price=r.get("max_price"),
                            modal_price=r.get("modal_price"),
                            price_unit=r.get("price_unit", "Quintal"),
                            arrival_date=r.get("arrival_date")
                        )
                        session.add(m_record)
                session.commit()

    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        session.close()

# ================= REST API ENDPOINTS =================

@app.post("/api/v2/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db_sess: Session = Depends(get_db)):
    user = db_sess.query(db.User).filter(db.User.username == form_data.username).first()
    if not user or not user.is_active or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v2/rates")
def get_rates(
    district: str = "all", 
    commodity: str = "all", 
    search: str = "", 
    page: int = 1, 
    limit: int = 50,
    db_sess: Session = Depends(get_db)
):
    query = db_sess.query(db.MandiRecord)
    if district != "all":
        query = query.filter(db.MandiRecord.district == district)
    if commodity != "all":
        query = query.filter(db.MandiRecord.commodity == commodity)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            db.MandiRecord.district.like(search_pattern) |
            db.MandiRecord.district_hi.like(search_pattern) |
            db.MandiRecord.mandi.like(search_pattern) |
            db.MandiRecord.mandi_hi.like(search_pattern) |
            db.MandiRecord.commodity.like(search_pattern) |
            db.MandiRecord.commodity_hi.like(search_pattern)
        )
    total_records = query.count()
    offset = (page - 1) * limit
    records = query.order_by(db.MandiRecord.modal_price.desc()).offset(offset).limit(limit).all()
    return {
        "total": total_records,
        "page": page,
        "limit": limit,
        "records": [sqlalchemy_to_dict(record) for record in records]
    }

@app.get("/api/v2/analytics/metrics")
def get_metrics(db_sess: Session = Depends(get_db)):
    total = db_sess.query(db.MandiRecord).count()
    active_mandis = db_sess.query(db.MandiRecord.mandi).distinct().count()
    avg_price = db_sess.query(db.MandiRecord).with_entities(db.MandiRecord.modal_price).all()
    avg_val = sum([p[0] for p in avg_price]) / len(avg_price) if avg_price else 0
    return {
        "total_records": total,
        "active_mandis": active_mandis,
        "avg_modal_price": round(avg_val, 2)
    }

@app.post("/api/v2/rates", status_code=status.HTTP_201_CREATED)
def create_rate(
    rate: RateCreate, 
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "trader", "staff"]:
        raise HTTPException(status_code=403, detail="Role unauthorized to insert rates")
        
    m_record = db.MandiRecord(**pydantic_to_dict(rate))
    db_sess.add(m_record)
    db_sess.commit()
    db_sess.refresh(m_record)
    
    write_audit_log(
        db_sess, current_user.id, current_user.username, "CREATE_RATE", 
        f"Inserted new rate for {rate.commodity} in {rate.mandi} (₹{rate.modal_price})", request
    )
    return {"message": "Mandi rate added successfully!", "record": sqlalchemy_to_dict(m_record)}

@app.put("/api/v2/rates/{record_id}")
def update_rate(
    record_id: int, 
    updated: RateCreate, 
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=403, detail="Role unauthorized to modify rates")
        
    record = db_sess.query(db.MandiRecord).filter(db.MandiRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mandi record not found")
        
    for key, value in pydantic_to_dict(updated).items():
        setattr(record, key, value)
        
    db_sess.commit()
    db_sess.refresh(record)
    
    write_audit_log(
        db_sess, current_user.id, current_user.username, "UPDATE_RATE", 
        f"Modified record ID {record_id} - New Modal Price: ₹{updated.modal_price}", request
    )
    return {"message": "Mandi rate updated successfully!", "record": sqlalchemy_to_dict(record)}

@app.delete("/api/v2/rates/{record_id}")
def delete_rate(
    record_id: int, 
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Strictly Admin only operation")
        
    record = db_sess.query(db.MandiRecord).filter(db.MandiRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mandi record not found")
        
    deleted_commodity = record.commodity
    deleted_mandi = record.mandi
    db_sess.delete(record)
    db_sess.commit()
    
    write_audit_log(
        db_sess, current_user.id, current_user.username, "DELETE_RATE", 
        f"Deleted record ID {record_id} ({deleted_commodity} at {deleted_mandi})", request
    )
    return {"message": f"Record with ID {record_id} deleted successfully!"}

@app.post("/api/v2/update")
def trigger_system_update(
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Role unauthorized to trigger scrapers")
        
    print("Official update pipeline triggered via Admin Panel...")
    import update_data as updater
    updater.main()
    with open("data/latest.json", "r", encoding="utf-8") as handle:
        latest_payload = json.load(handle)
    if not latest_payload.get("verified") or not latest_payload.get("is_live"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fresh verified government snapshot was available; database was not changed",
        )
    records = latest_payload.get("records", [])
    if not records:
        raise HTTPException(status_code=503, detail="Official update returned no records")

    db_sess.query(db.MandiRecord).delete()
    for r in records:
        m_record = db.MandiRecord(
            district=r["district"],
            district_hi=r["district_hi"],
            mandi=r["mandi"],
            mandi_hi=r["mandi_hi"],
            commodity=r["commodity"],
            commodity_hi=r["commodity_hi"],
            variety=r["variety"],
            variety_hi=r["variety_hi"],
            grade=r["grade"],
            grade_hi=r["grade_hi"],
            arrivals=r["arrivals"],
            arrivals_unit=r["arrivals_unit"],
            arrivals_unit_hi=r["arrivals_unit_hi"],
            min_price=r["min_price"],
            max_price=r["max_price"],
            modal_price=r["modal_price"],
            price_unit=r["price_unit"],
            arrival_date=r["arrival_date"]
        )
        db_sess.add(m_record)
        
    db_sess.commit()
    
    write_audit_log(
        db_sess, current_user.id, current_user.username, "SCRAPER_TRIGGER", 
        f"Triggered manual data refresh, updated {len(records)} entries in DB", request
    )
    return {
        "status": "success",
        "updated_count": len(records),
        "message": f"Successfully pulled and stored {len(records)} live mandi rates from Agmarknet sources into DB!"
    }

@app.get("/api/v2/excel/sync")
def get_excel_sync_stream(db_sess: Session = Depends(get_db)):
    records = db_sess.query(db.MandiRecord).all()
    csv_headers = "Record_ID,District,Mandi,Commodity,Variety,Grade,Arrivals,Min_Price,Modal_Price,Max_Price,Date,Last_Sync\n"
    def generate_csv_rows():
        yield csv_headers
        for r in records:
            row = f"{r.id},{r.district},{r.mandi},{r.commodity},{r.variety},{r.grade},{r.arrivals},{r.min_price},{r.modal_price},{r.max_price},{r.arrival_date},{datetime.utcnow().isoformat()}\n"
            yield row
    return StreamingResponse(
        generate_csv_rows(), 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment; filename=UP_Mandi_Live_Sync.csv"}
    )

@app.get("/api/v2/prediction/{crop}")
def get_price_prediction(crop: str):
    history_file = "data/history.json"
    latest_file = "data/latest.json"
    if not os.path.exists(history_file) or not os.path.exists(latest_file):
        raise HTTPException(status_code=404, detail="Historical records not found")

    with open(latest_file, "r", encoding="utf-8") as handle:
        latest_metadata = json.load(handle)
    if not latest_metadata.get("verified"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Predictions are disabled until verified official price history is available",
        )

    with open(history_file, "r", encoding="utf-8") as handle:
        history_data = json.load(handle)
    try:
        return pred_engine.predict_future_prices(history_data, crop)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

@app.post("/api/v2/alerts/subscribe")
def subscribe_price_alerts(sub: SubscribeRequest, db_sess: Session = Depends(get_db)):
    existing = db_sess.query(db.AlertSubscription).filter(
        db.AlertSubscription.contact_type == sub.contact_type,
        db.AlertSubscription.contact_value == sub.contact_value
    ).first()
    
    if existing:
        existing.district = sub.district
        existing.commodity = sub.commodity
        existing.is_active = True
        db_sess.commit()
        return {"status": "success", "message": "सफलतापूर्वक आपकी सबरक्रिप्शन प्रोफाइल अपडेट कर दी गई है!"}
        
    new_sub = db.AlertSubscription(
        contact_type=sub.contact_type,
        contact_value=sub.contact_value,
        district=sub.district,
        commodity=sub.commodity
    )
    db_sess.add(new_sub)
    db_sess.commit()
    
    welcome_text = "🌾 <b>Welcome to UP Mandi Price Alerts!</b> 🌾\nYour subscription was saved. Alerts contain only available verified rates."
    delivered = False
    if sub.contact_type == "telegram":
        delivered = alert_engine.send_telegram_alert(sub.contact_value, welcome_text)
    elif sub.contact_type == "whatsapp":
        delivered = alert_engine.send_whatsapp_alert(sub.contact_value, welcome_text)

    return {
        "status": "subscribed",
        "welcome_delivered": delivered,
        "message": (
            "Subscription saved and welcome alert delivered."
            if delivered
            else "Subscription saved; alert provider is unavailable or not configured."
        ),
    }

@app.post("/api/v2/alerts/broadcast")
def trigger_alerts_broadcast(current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    records = db_sess.query(db.MandiRecord).all()
    subscriptions = db_sess.query(db.AlertSubscription).filter(db.AlertSubscription.is_active == True).all()
    
    broadcast_count = alert_engine.broadcast_price_alerts(records, subscriptions)
    return {
        "status": "success",
        "broadcast_sent_count": broadcast_count,
        "message": f"Successfully broadcasted live price updates to {broadcast_count} subscribers!"
    }

# ================= PHASE 4 FINANCIAL BILLING & INVOICING ENDPOINTS =================

@app.post("/api/v2/financials/invoice", status_code=status.HTTP_201_CREATED)
def create_financial_invoice(
    invoice: InvoiceCreate,
    request: Request,
    current_user: db.User = Depends(get_current_user),
    db_sess: Session = Depends(get_db)
):
    total_kg = invoice.weight * 100
    total_bags = int(round(total_kg / invoice.bag_size_kg))
    
    gross_val = invoice.weight * invoice.rate
    comm_amt = (gross_val * invoice.commission_percent) / 100
    labor_amt = total_bags * invoice.labor_per_bag
    tax_amt = (gross_val * invoice.cess_percent) / 100
    
    total_expenses = comm_amt + labor_amt + tax_amt + invoice.transport_cost
    net_payout = max(0.0, gross_val - total_expenses)

    date_prefix = datetime.utcnow().strftime("%Y%m%d")
    unique_suffix = secrets.token_hex(2).upper()
    inv_number = f"VKT-{date_prefix}-{unique_suffix}"

    raw_hash_data = f"{inv_number}|{invoice.farmer_name}|{invoice.crop_name}|{net_payout:.2f}|internal_estimate_v1"
    verification_hash = hashlib.sha256(raw_hash_data.encode()).hexdigest()[:16].upper()

    db_invoice = db.Invoice(
        invoice_number=inv_number,
        farmer_name=invoice.farmer_name,
        crop_name=invoice.crop_name,
        weight=invoice.weight,
        rate=invoice.rate,
        gross_amount=gross_val,
        commission_amount=comm_amt,
        labor_amount=labor_amt,
        mandi_tax_amount=tax_amt,
        transport_amount=invoice.transport_cost,
        net_payout=net_payout,
        verification_hash=verification_hash
    )
    
    db_sess.add(db_invoice)
    db_sess.commit()
    db_sess.refresh(db_invoice)

    write_audit_log(
        db_sess, current_user.id, current_user.username, "ISSUE_BILL",
        f"Generated internal estimate {inv_number} for {invoice.farmer_name} - Net Payout: ₹{net_payout:.2f}", request
    )
    return {
        "status": "success",
        "message": "Internal calculation estimate saved; this is not a government mandi receipt or tax invoice.",
        "invoice": sqlalchemy_to_dict(db_invoice)
    }

@app.get("/api/v2/financials/reports")
def get_financial_reports(current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    if current_user.role not in ["admin", "trader"]:
        raise HTTPException(status_code=403, detail="Role unauthorized to view financial turnovers")

    invoices = db_sess.query(db.Invoice).all()
    total_gross = sum(i.gross_amount for i in invoices)
    total_commission = sum(i.commission_amount for i in invoices)
    total_mandi_tax = sum(i.mandi_tax_amount for i in invoices)
    total_net_payout = sum(i.net_payout for i in invoices)
    total_bills_issued = len(invoices)

    return {
        "total_gross_turnover": round(total_gross, 2),
        "total_commission_earned": round(total_commission, 2),
        "total_mandi_taxes_paid": round(total_mandi_tax, 2),
        "total_cash_liquid_payout": round(total_net_payout, 2),
        "total_bills_issued": total_bills_issued,
        "recent_invoices": [sqlalchemy_to_dict(invoice) for invoice in invoices[-10:]]
    }

# ================= OFFICIAL e-NAM AUCTION SNAPSHOT =================

@app.get("/api/v2/auction/lots")
def get_active_auction_lots():
    """Return the latest authorised e-NAM snapshot without inventing lots."""
    try:
        with open("data/auction.json", "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {
            "status": "temporarily_unavailable",
            "message_en": "The authorised e-NAM feed is unavailable.",
            "message_hi": "अधिकृत e-NAM feed उपलब्ध नहीं है।",
            "portal_url": "https://www.enam.gov.in/web/",
            "lots": [],
        }


@app.post("/api/v2/auction/bid")
async def submit_auction_bid(bid: BidSubmit):
    """Never accept a local or simulated bid for an official auction."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "message": "Bids must be authenticated and submitted on the official e-NAM portal.",
            "portal_url": "https://www.enam.gov.in/web/",
        },
    )


@app.websocket("/api/v2/auction/ws/{username}")
async def websocket_auction_endpoint(websocket: WebSocket, username: str):
    """Close the legacy simulated socket and direct users to official e-NAM."""
    await websocket.accept()
    await websocket.send_json({
        "event": "OFFICIAL_PORTAL_REQUIRED",
        "message": "Real bids are available only through authenticated e-NAM access.",
        "portal_url": "https://www.enam.gov.in/web/",
    })
    await websocket.close(code=1008)

# ================= SERVER HEALTH ENDPOINTS =================

@app.get("/health")
def health_check(db_sess: Session = Depends(get_db)):
    try:
        db_sess.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": "active"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connectivity check failed: {str(e)}"
        )

# Serve Enterprise Admin Panel
@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def serve_admin_panel():
    with open("admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Serve the public dashboard and static PWA assets when running via FastAPI/Docker.
# GitHub Pages can still serve the same files directly, but the API server should
# not return 404 for the app shell or its local JSON/image assets.
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/manifest.json", include_in_schema=False)
def serve_manifest():
    return FileResponse("manifest.json", media_type="application/manifest+json")

@app.get("/sw.js", include_in_schema=False)
def serve_service_worker():
    return FileResponse("sw.js", media_type="application/javascript")

if os.path.isdir("data"):
    app.mount("/data", StaticFiles(directory="data"), name="data")
if os.path.isdir("images"):
    app.mount("/images", StaticFiles(directory="images"), name="images")
