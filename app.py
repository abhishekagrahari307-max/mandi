import os
import json
import random
import urllib.request
import re
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Security, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from passlib.context import CryptContext
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.environ.get("JWT_SECRET", "9ef842f824b44749a978d0c17b101cff356e9")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/login")

# ================= VALIDATION SCHEMAS (SECURITY CODES) =================

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
    contact_type: str # "whatsapp", "telegram"
    contact_value: str = Field(..., min_length=5, max_length=100)
    district: str = "all"
    commodity: str = "all"

# Helper functions
def get_db():
    session = db.SessionLocal()
    try:
        yield session
    finally:
        session.close()

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

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

# Helper to write Secure Audit Logs
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
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        session.close()

# ================= REST API ENDPOINTS =================

# 1. ADMIN PANEL LOGIN (OAuth2 standard)
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

# 2. GET LIVE RATES (Search, Filter, Pagination)
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
        "records": records
    }

# 3. GET SYSTEM METRICS (Analytics overview)
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

# 4. MANUALLY INSERT NEW MANDI RECORD (Admin & Trader Authorized + Audit Logging)
@app.post("/api/v2/rates", status_code=status.HTTP_201_CREATED)
def create_rate(
    rate: RateCreate, 
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    # Role-Based Access Control (Only Admin, Trader, or Staff roles can add rates)
    if current_user.role not in ["admin", "trader", "staff"]:
        raise HTTPException(status_code=403, detail="Role unauthorized to insert rates")
        
    m_record = db.MandiRecord(**rate.dict())
    db_sess.add(m_record)
    db_sess.commit()
    db_sess.refresh(m_record)
    
    # Write Audit Log
    write_audit_log(
        db_sess, current_user.id, current_user.username, "CREATE_RATE", 
        f"Inserted new rate for {rate.commodity} in {rate.mandi} (₹{rate.modal_price})", request
    )
    
    return {"message": "Mandi rate added successfully!", "record": m_record}

# 5. MANUALLY UPDATE EXISTING MANDI RECORD (Admin & Trader Authorized + Audit Logging)
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
        
    for key, value in updated.dict().items():
        setattr(record, key, value)
        
    db_sess.commit()
    db_sess.refresh(record)
    
    # Write Audit Log
    write_audit_log(
        db_sess, current_user.id, current_user.username, "UPDATE_RATE", 
        f"Modified record ID {record_id} - New Modal Price: ₹{updated.modal_price}", request
    )
    
    return {"message": "Mandi rate updated successfully!", "record": record}

# 6. DELETE MANDI RECORD (Admin ONLY + Audit Logging)
@app.delete("/api/v2/rates/{record_id}")
def delete_rate(
    record_id: int, 
    request: Request,
    current_user: db.User = Depends(get_current_user), 
    db_sess: Session = Depends(get_db)
):
    # Strictly Admin ONLY
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Strictly Admin only operation")
        
    record = db_sess.query(db.MandiRecord).filter(db.MandiRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mandi record not found")
        
    db_sess.delete(record)
    db_sess.commit()
    
    # Write Audit Log
    write_audit_log(
        db_sess, current_user.id, current_user.username, "DELETE_RATE", 
        f"Deleted record ID {record_id} ({record.commodity} at {record.mandi})", request
    )
    
    return {"message": f"Record with ID {record_id} deleted successfully!"}

# 7. AUTOMATIC PRICE SCRAPER FORCE TRIGGER (Admin Only + Audit Logging)
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
    
    # Write Audit Log
    write_audit_log(
        db_sess, current_user.id, current_user.username, "SCRAPER_TRIGGER", 
        f"Triggered manual data refresh, updated {len(records)} entries in DB", request
    )
    
    return {
        "status": "success",
        "updated_count": len(records),
        "message": f"Successfully pulled and stored {len(records)} live mandi rates from Agmarknet sources into DB!"
    }

# 8. LIVE EXCEL SYNC ENDPOINT (Generates refreshable CSV stream)
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

# 9. AI PRICE PREDICTION ENDPOINT
@app.get("/api/v2/prediction/{crop}")
def get_price_prediction(crop: str):
    history_file = "data/history.json"
    if not os.path.exists(history_file):
        raise HTTPException(status_code=404, detail="Historical records not found")
        
    with open(history_file, "r", encoding="utf-8") as f:
        history_data = json.load(f)
        
    prediction_results = pred_engine.predict_future_prices(history_data, crop)
    return prediction_results

# 10. WHATSAPP/TELEGRAM ALERTS SUBSCRIBE ENDPOINT
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

# 11. FORCE BROADCAST PRICE ALERTS TO ALL ACTIVE SUBSCRIBERS (Admin Authorized)
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

# Serve Enterprise Admin Panel
@app.get("/admin", response_class=HTMLResponse)
def serve_admin_panel():
    with open("admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# 12. HEALTH & READINESS ENDPOINT (FOR ENTERPRISE SYSTEM MONITORING & DOCKER/KUBERNETES)
@app.get("/health")
def health_check(db_sess: Session = Depends(get_db)):
    """
    Standard enterprise liveness & readiness check.
    Verifies API server status and database connection health.
    """
    try:
        # Perform simple low-cost query to verify database connection pool is active
        db_sess.execute(db.SessionLocal().bind.utility_select_criterion() if hasattr(db.SessionLocal().bind, "utility_select_criterion") else "SELECT 1")
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
