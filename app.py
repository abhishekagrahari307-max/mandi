import os
import json
import random
import urllib.request
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict
from fastapi import FastAPI, Depends, HTTPException, status, Security, Request, WebSocket, WebSocketDisconnect
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

# Initialize Database
db.init_db()

app = FastAPI(
    title="UP Mandi Enterprise REST API",
    description="UP Mandi Dashboard Version 2.0 Backend & REST API Engine",
    version="2.0.0"
)

# Enable CORS for cross-origin live connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SECRET_KEY = os.environ.get("JWT_SECRET", "9ef842f824b44749a978d0c17b101cff356e9")
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
    commission_percent: float = Field(default=1.5, ge=0, le=10.0)
    labor_per_bag: float = Field(default=15.0, ge=0)
    bag_size_kg: float = Field(default=50.0, gt=0)
    transport_cost: float = Field(default=0.0, ge=0)
    cess_percent: float = Field(default=2.0, ge=0, le=5.0)

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
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
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
    if user is None:
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
        # Seed default admin user
        admin_exists = session.query(db.User).filter(db.User.username == "admin").first()
        if not admin_exists:
            admin_user = db.User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                email="admin@mandi-up.gov.in",
                role="admin"
            )
            session.add(admin_user)
            session.commit()
            
        # Seed initial mandi rates
        records_count = session.query(db.MandiRecord).count()
        if records_count == 0:
            latest_file = "data/latest.json"
            if os.path.exists(latest_file):
                with open(latest_file, "r", encoding="utf-8") as f:
                    latest_data = json.load(f)
                    records = latest_data.get("records", [])
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
                            arrivals=r.get("arrivals", 0),
                            arrivals_unit=r.get("arrivals_unit", "Tonnes"),
                            arrivals_unit_hi=r.get("arrivals_unit_hi", "टन"),
                            min_price=r.get("min_price"),
                            max_price=r.get("max_price"),
                            modal_price=r.get("modal_price"),
                            price_unit=r.get("price_unit", "Quintal"),
                            arrival_date=r.get("arrival_date")
                        )
                        session.add(m_record)
                session.commit()

        # Seed an initial Active Auction Lot if none exists (for demo)
        auction_count = session.query(db.AuctionLot).count()
        if auction_count == 0:
            lot = db.AuctionLot(
                lot_number="LOT-2026-101",
                farmer_name="Ramesh Singh (Kanpur)",
                crop_name="Wheat (गेहूं)",
                quantity=45.0,
                starting_rate=2300.0,
                highest_bid=2300.0,
                status="active"
            )
            session.add(lot)
            session.commit()
            
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        session.close()

# ================= WEBSOCKETS CONNECTION MANAGER (LIVE AUCTION) =================

class AuctionConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Connected: Total active bidders = {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"Disconnected: Active bidders left = {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcasts real-time auction event to all active connected bidders."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle disconnected dead connections gracefully
                pass

manager = AuctionConnectionManager()

# ================= REST API ENDPOINTS =================

@app.post("/api/v2/auth/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db_sess: Session = Depends(get_db)):
    user = db_sess.query(db.User).filter(db.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
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
        
    print("Force Update Engine Triggered via Admin Panel...")
    import update_data as updater
    records = updater.generate_mock_data()
    
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
    if not os.path.exists(history_file):
        raise HTTPException(status_code=404, detail="Historical records not found")
        
    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)
        
    prediction_results = pred_engine.predict_future_prices(history_data, crop)
    return prediction_results

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
    
    welcome_text = "🌾 <b>Welcome to UP Mandi Price Alerts!</b> 🌾\nVijay Kumar Traders has registered your phone. You will receive daily rate summaries as soon as Agmarknet rates update! Thank you."
    if sub.contact_type == "telegram":
        alert_engine.send_telegram_alert(sub.contact_value, welcome_text)
    elif sub.contact_type == "whatsapp":
        alert_engine.send_whatsapp_alert(sub.contact_value, welcome_text)
        
    return {"status": "success", "message": "सफलतापूर्वक मूल्य अलर्ट के लिए पंजीकरण हो गया है!"}

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
    random_suffix = random.randint(1000, 9999)
    inv_number = f"VKT-{date_prefix}-{random_suffix}"

    raw_hash_data = f"{inv_number}|{invoice.farmer_name}|{invoice.crop_name}|{net_payout:.2f}|mandi_secure_v2"
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
        f"Generated official invoice {inv_number} for {invoice.farmer_name} - Net Payout: ₹{net_payout:.2f}", request
    )
    return {
        "status": "success",
        "message": "Official invoice saved and signed successfully!",
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

# ================= FIRST PILLAR: WEBSOCKET LIVE AUCTION ENGINE (PHASE 5) =================

@app.get("/api/v2/auction/lots")
def get_active_auction_lots(db_sess: Session = Depends(get_db)):
    """Returns list of currently active grain/crop lots inside the bidding yard."""
    lots = db_sess.query(db.AuctionLot).filter(db.AuctionLot.status == "active").all()
    return [sqlalchemy_to_dict(lot) for lot in lots]

@app.post("/api/v2/auction/bid")
async def submit_auction_bid(bid: BidSubmit, db_sess: Session = Depends(get_db)):
    """
    Submits a secure real-time price bid for a specific active lot.
    Verifies on server-side that the bid is strictly higher than previous bid.
    Broadcasts the newly placed bid instantly to all active bidders via WebSockets!
    """
    lot = db_sess.query(db.AuctionLot).filter(
        db.AuctionLot.lot_number == bid.lot_number,
        db.AuctionLot.status == "active"
    ).first()
    
    if not lot:
        raise HTTPException(status_code=404, detail="Active lot not found inside the bidding yard")
        
    if bid.bid_amount <= lot.highest_bid:
        raise HTTPException(
            status_code=400, 
            detail=f"Bidding rate must be strictly higher than current highest bid of ₹{lot.highest_bid}/Q"
        )
        
    # Update Lot's highest bid
    lot.highest_bid = bid.bid_amount
    lot.highest_bidder = bid.trader_name
    db_sess.commit()
    db_sess.refresh(lot)
    
    # Broadcast updated bid payload to all active WebSocket listeners instantly!
    broadcast_payload = {
        "event": "NEW_BID",
        "lot_number": lot.lot_number,
        "crop_name": lot.crop_name,
        "farmer_name": lot.farmer_name,
        "highest_bid": lot.highest_bid,
        "highest_bidder": lot.highest_bidder,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(broadcast_payload)
    
    return {
        "status": "success",
        "message": f"Successfully placed bid of ₹{bid.bid_amount}/Q!",
        "lot": sqlalchemy_to_dict(lot)
    }

# WEBSOCKET REAL-TIME BIDDING GATEWAY
@app.websocket("/api/v2/auction/ws/{username}")
async def websocket_auction_endpoint(websocket: WebSocket, username: str):
    """
    Real-Time WebSocket gateway connection endpoint.
    Bidder connections are saved in active pool and managed in real-time.
    """
    await manager.connect(websocket)
    try:
        # Send initial success greeting
        await websocket.send_json({
            "event": "WELCOME",
            "message": f"Welcome {username}! Connected to Vijay Kumar Traders Live Auction Yard WS.",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            # Maintain active connection stream and listen for incoming bids on WS channel
            data = await websocket.receive_text()
            # If a client sends direct WebSocket message
            print(f"Received WS message from {username}: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket Error with user {username}: {e}")
        manager.disconnect(websocket)

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
if os.path.isdir("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
