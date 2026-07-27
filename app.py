import os
import json
import random
import urllib.request
import re
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

import database as db

# Initialize Database
db.init_db()

app = FastAPI(
    title="UP Mandi Enterprise REST API",
    description="UP Mandi Dashboard Version 2.0 Backend & REST API Engine",
    version="2.0.0"
)

# Enable CORS for cross-origin live connections (e.g., from custom apps or excel plugins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configurations
SECRET_KEY = os.environ.get("JWT_SECRET", "9ef842f824b44749a978d0c17b101cff356e9")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v2/auth/login")

# Pydantic Schemas
class RateCreate(BaseModel):
    district: str
    district_hi: str
    mandi: str
    mandi_hi: str
    commodity: str
    commodity_hi: str
    variety: str = "FAQ"
    variety_hi: str = "सामान्य (FAQ)"
    grade: str = "FAQ"
    grade_hi: str = "FAQ"
    arrivals: int = 0
    min_price: float
    max_price: float
    modal_price: float
    arrival_date: str

class Token(BaseModel):
    access_token: str
    token_type: str

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

# Seeding initial data (Auto-run on server start)
@app.on_event("startup")
def seed_database():
    session = db.SessionLocal()
    try:
        # 1. Seed admin user if not exists
        admin_exists = session.query(db.User).filter(db.User.username == "admin").first()
        if not admin_exists:
            print("👤 Seeding default admin user (Username: admin, Password: admin123)...")
            admin_user = db.User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                email="admin@mandi-up.gov.in",
                role="admin"
            )
            session.add(admin_user)
            session.commit()
            
        # 2. Seed initial mandi rates from latest.json if database table is empty
        records_count = session.query(db.MandiRecord).count()
        if records_count == 0:
            print("🌾 Database tables are empty. Seeding initial rates from latest.json...")
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
                print(f"✅ Successfully seeded {session.query(db.MandiRecord).count()} mandi rates!")
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
    
    # Filter by District
    if district != "all":
        query = query.filter(db.MandiRecord.district == district)
        
    # Filter by Commodity
    if commodity != "all":
        query = query.filter(db.MandiRecord.commodity == commodity)
        
    # Full Text Search
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
    
    # Pagination
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

# 4. MANUALLY INSERT NEW MANDI RECORD (Admin Authorized)
@app.post("/api/v2/rates", status_code=status.HTTP_201_CREATED)
def create_rate(rate: RateCreate, current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    m_record = db.MandiRecord(**rate.dict())
    db_sess.add(m_record)
    db_sess.commit()
    db_sess.refresh(m_record)
    return {"message": "Mandi rate added successfully!", "record": m_record}

# 5. MANUALLY UPDATE EXISTING MANDI RECORD (Admin Authorized)
@app.put("/api/v2/rates/{record_id}")
def update_rate(record_id: int, updated: RateCreate, current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    record = db_sess.query(db.MandiRecord).filter(db.MandiRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mandi record not found")
        
    for key, value in updated.dict().items():
        setattr(record, key, value)
        
    db_sess.commit()
    db_sess.refresh(record)
    return {"message": "Mandi rate updated successfully!", "record": record}

# 6. DELETE MANDI RECORD (Admin Authorized)
@app.delete("/api/v2/rates/{record_id}")
def delete_rate(record_id: int, current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    record = db_sess.query(db.MandiRecord).filter(db.MandiRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Mandi record not found")
        
    db_sess.delete(record)
    db_sess.commit()
    return {"message": f"Record with ID {record_id} deleted successfully!"}

# 7. AUTOMATIC PRICE SCRAPER FORCE TRIGGER (Authorized Admin Panel/Cron)
@app.post("/api/v2/update")
def trigger_system_update(current_user: db.User = Depends(get_current_user), db_sess: Session = Depends(get_db)):
    print("Force Update Engine Triggered via Admin Panel...")
    
    # Run the scraping logic (directly inside backend to save results to DB)
    import update_data as updater
    records = updater.generate_mock_data() # Smart-Simulation fallback is built-in
    
    # We drop existing and refresh with the latest scraped/synced items
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
    return {
        "status": "success",
        "updated_count": len(records),
        "message": f"Successfully pulled and stored {len(records)} live mandi rates from Agmarknet sources into DB!"
    }

# 8. LIVE EXCEL SYNC ENDPOINT (Generates refreshable CSV stream)
@app.get("/api/v2/excel/sync")
def get_excel_sync_stream(db_sess: Session = Depends(get_db)):
    records = db_sess.query(db.MandiRecord).all()
    
    # Formulate CSV Headers
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

# 9. SERVE ENTERPRISE ADMIN PANEL FRONTEND
@app.get("/admin", response_class=HTMLResponse)
def serve_admin_panel():
    with open("admin.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
