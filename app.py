import os
import json
import urllib.request
import urllib.error
import re
import csv
import io
import hashlib
import logging
import secrets
from typing import Any
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
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,https://abhishekagrahari307-max.github.io"
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


class MandiAIRequest(BaseModel):
    """Chat request for the OpenRouter-powered mandi assistant.

    `userQuestion` is used by the public dashboard. `message` is accepted too
    so clients can call the endpoint with a more generic chat payload. Optional
    client-side mandiData is used only as a fallback when the server does not
    have a fresh local snapshot; the backend never requires API keys in the
    browser.
    """
    userQuestion: str | None = Field(default=None, max_length=600)
    message: str | None = Field(default=None, max_length=600)
    mandiData: Any | None = None


class SmartAIToolRequest(BaseModel):
    """Payload for advanced OpenRouter agri-tech tools.

    Images are accepted as browser-created data URLs and are forwarded directly
    to OpenRouter; they are never stored on disk by this application.
    """
    action: str = Field(
        ...,
        pattern=r"^(crop_disease|receipt_ocr|trend_advisor|transport_profit|weather_risk|scheme_advisor)$",
    )
    question: str | None = Field(default=None, max_length=1200)
    crop: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=120)
    imageData: str | None = Field(default=None, max_length=8_000_000)
    mandiData: Any | None = None
    historyData: Any | None = None
    sourceMandi: str | None = Field(default=None, max_length=120)
    destinationMandi: str | None = Field(default=None, max_length=120)
    sourcePrice: float | None = Field(default=None, ge=0)
    destinationPrice: float | None = Field(default=None, ge=0)
    distanceKm: float | None = Field(default=None, ge=0)
    quantityQuintal: float | None = Field(default=None, ge=0)
    transportCostPerKm: float | None = Field(default=None, ge=0)
    totalTransportCost: float | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


# Only providers the alert engine can actually deliver to. A subscription with
# any other channel could never receive a message, so it is rejected instead of
# being stored as a silently dead row.
SUPPORTED_CONTACT_TYPES = ("telegram", "whatsapp")
# Telegram chat ids are numeric (optionally negative for groups); WhatsApp
# numbers are digits with an optional leading +/country code.
TELEGRAM_ID_PATTERN = re.compile(r"^-?\d{5,20}$")
PHONE_PATTERN = re.compile(r"^\+?\d{10,15}$")


class SubscribeRequest(BaseModel):
    contact_type: str = Field(..., pattern=r"^(telegram|whatsapp)$")
    contact_value: str = Field(..., min_length=5, max_length=100)
    district: str = Field(default="all", max_length=60)
    commodity: str = Field(default="all", max_length=60)

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

# ================= OPENROUTER AI MANDI ASSISTANT HELPERS =================

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_DEFAULT_MODEL = "deepseek/deepseek-r1:free"
MAX_AI_CONTEXT_RECORDS = 120


def _read_json_file(path: str, fallback: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return fallback


def _records_from_client_snapshot(mandi_data: Any) -> list[dict[str, Any]]:
    """Accept a minimal client snapshot without trusting browser secrets.

    The static GitHub Pages build can send the already-visible JSON records to a
    separately hosted backend. This fallback keeps that mode useful, while the
    server-local data files remain the preferred source when available.
    """
    if isinstance(mandi_data, dict):
        records = mandi_data.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
        feeds = mandi_data.get("feeds")
        if isinstance(feeds, list):
            output: list[dict[str, Any]] = []
            for feed in feeds:
                if not isinstance(feed, dict):
                    continue
                for record in feed.get("records", []) if isinstance(feed.get("records"), list) else []:
                    if isinstance(record, dict):
                        output.append({
                            **record,
                            "source": record.get("source") or feed.get("name") or feed.get("id"),
                            "verification_level": "single_source",
                        })
            return output
    if isinstance(mandi_data, list):
        return [item for item in mandi_data if isinstance(item, dict)]
    return []


def _collect_ai_mandi_context(mandi_data: Any = None) -> dict[str, Any]:
    latest = _read_json_file("data/latest.json", {})
    source_prices = _read_json_file("data/source_prices.json", {})
    sources = _read_json_file("data/sources.json", {})

    verified_records = latest.get("records", []) if isinstance(latest, dict) else []
    if not isinstance(verified_records, list):
        verified_records = []
    verified_records = [record for record in verified_records if isinstance(record, dict)]

    single_source_records: list[dict[str, Any]] = []
    feeds = source_prices.get("feeds", []) if isinstance(source_prices, dict) else []
    if isinstance(feeds, list):
        for feed in feeds:
            if not isinstance(feed, dict):
                continue
            if feed.get("status") not in {"live", "cached"}:
                continue
            feed_records = feed.get("records", [])
            if not isinstance(feed_records, list):
                continue
            for record in feed_records:
                if not isinstance(record, dict):
                    continue
                # ── STATE FILTER: Only keep Uttar Pradesh records ──
                rec_state = str(record.get("state", ""))
                if rec_state and rec_state not in {"Uttar Pradesh", "UP", "U.P."}:
                    continue
                # ── OUTLIER REMOVAL: Common Rice > ₹8000 is data entry error ──
                commodity = str(record.get("commodity", "")).lower()
                variety = str(record.get("variety", "")).lower()
                modal = record.get("modal_price") or 0
                is_rice_common = (
                    ("rice" in commodity or "paddy" in commodity or "chawal" in commodity)
                    and ("common" in variety)
                )
                if is_rice_common and isinstance(modal, (int, float)) and modal > 8000:
                    continue
                single_source_records.append({
                    **record,
                    "source": record.get("source") or feed.get("name") or feed.get("id"),
                    "source_id": record.get("source_id") or feed.get("id"),
                    "verification_level": "single_source",
                })

    # GitHub Pages mode: let the page send the same public data it already
    # displays, but only if the deployed backend's own data files are empty.
    if not verified_records and not single_source_records:
        single_source_records = _records_from_client_snapshot(mandi_data)

    metadata = {
        "updated_at": latest.get("updated_at") if isinstance(latest, dict) else None,
        "last_checked_at": (
            latest.get("last_checked_at") if isinstance(latest, dict) else None
        ) or (sources.get("last_checked_at") if isinstance(sources, dict) else None),
        "is_live": latest.get("is_live") if isinstance(latest, dict) else None,
        "verified": latest.get("verified") if isinstance(latest, dict) else None,
        "minimum_price_source_matches": (
            latest.get("minimum_price_source_matches") if isinstance(latest, dict) else None
        ) or (sources.get("minimum_price_source_matches") if isinstance(sources, dict) else None),
    }
    return {
        "metadata": metadata,
        "verified_records": verified_records,
        "single_source_records": single_source_records,
    }


def _question_tokens(question: str) -> set[str]:
    cleaned = question.lower()
    tokens = set(re.findall(r"[a-zA-Z\u0900-\u097F0-9]+", cleaned))
    synonyms = {
        "गेहूं": ["wheat"], "गेहूँ": ["wheat"], "गेंहू": ["wheat"],
        "धान": ["paddy", "rice"], "चावल": ["rice", "paddy"],
        "आलू": ["potato"], "अलू": ["potato"],
        "मसूर": ["lentil", "masur"], "मसूरदाल": ["lentil", "masur"],
        "दाल": ["lentil", "gram"],
        "मक्का": ["maize"], "मोक्का": ["maize"], "mokka": ["maize"], "makka": ["maize"],
        "सबसे": ["highest", "lowest"], "सस्ता": ["lowest", "min"], "महंगा": ["highest", "max"],
        "मॉडल": ["modal"], "मोडल": ["modal"], "भाव": ["price"], "रेट": ["price"],
    }
    for token in list(tokens):
        for mapped in synonyms.get(token, []):
            tokens.add(mapped)
    return {token for token in tokens if len(token) > 1}


def _record_search_text(record: dict[str, Any]) -> str:
    fields = (
        "district", "district_hi", "district_reported", "mandi", "mandi_hi",
        "commodity", "commodity_hi", "variety", "variety_hi", "grade", "grade_hi",
        "arrival_date", "source", "source_id",
    )
    return " ".join(str(record.get(field, "")) for field in fields).lower()


def _rank_ai_records(records: list[dict[str, Any]], question: str) -> list[dict[str, Any]]:
    tokens = _question_tokens(question)

    def score(record: dict[str, Any]) -> tuple[int, float]:
        text = _record_search_text(record)
        token_score = sum(1 for token in tokens if token in text)
        try:
            price = float(record.get("modal_price") or 0)
        except (TypeError, ValueError):
            price = 0.0
        return (token_score, price)

    scored = [(score(record), record) for record in records]
    relevant = [record for (record_score, _), record in scored if record_score > 0]
    if relevant:
        return sorted(relevant, key=lambda record: score(record), reverse=True)[:MAX_AI_CONTEXT_RECORDS]
    return records[:MAX_AI_CONTEXT_RECORDS]


def _compact_ai_record(record: dict[str, Any], verified: bool) -> dict[str, Any]:
    return {
        "district": record.get("district"),
        "district_hi": record.get("district_hi"),
        "mandi": record.get("mandi"),
        "mandi_hi": record.get("mandi_hi"),
        "commodity": record.get("commodity"),
        "commodity_hi": record.get("commodity_hi"),
        "variety": record.get("variety"),
        "grade": record.get("grade"),
        "arrival_date": record.get("arrival_date"),
        "min_price": record.get("min_price"),
        "modal_price": record.get("modal_price"),
        "max_price": record.get("max_price"),
        "arrivals": record.get("arrivals"),
        "arrivals_unit": record.get("arrivals_unit"),
        "source": record.get("source"),
        "verification": "multi_source_verified" if verified else "single_source_not_cross_verified",
    }


def _build_openrouter_system_prompt(question: str, mandi_data: Any = None) -> str:
    context = _collect_ai_mandi_context(mandi_data)
    verified = _rank_ai_records(context["verified_records"], question)
    single_source = _rank_ai_records(context["single_source_records"], question)

    compact_context = {
        "metadata": context["metadata"],
        "verified_records": [_compact_ai_record(record, True) for record in verified],
        "single_source_records": [_compact_ai_record(record, False) for record in single_source],
        "rules": [
            "Use only the records in this JSON context. Do not invent a price, mandi, date, arrival or source.",
            "Prefer verified_records. Use single_source_records only when no verified match exists and clearly say it is not cross-verified.",
            "All prices are INR per quintal unless the record says otherwise.",
            "If the crop/mandi/district is missing from the context, say: Abhi official feed me ye bhav uplabdh nahi hai.",
            "Answer in simple Hindi/Hinglish and include mandi, district, commodity, modal/min/max price, date and source/verification where available.",
        ],
    }
    return (
        "Aap Uttar Pradesh Mandi ke official AI Sahayak hain. "
        "Niche verified/cross-checked aur single-source official mandi bhav JSON context diya gaya hai.\n"
        f"{json.dumps(compact_context, ensure_ascii=False)}"
    )


def _openrouter_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    site_url = os.environ.get("OPENROUTER_SITE_URL", "").strip()
    app_name = os.environ.get("OPENROUTER_APP_NAME", "UP Mandi Dashboard").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name
    return headers


def _configured_openrouter_model(vision: bool = False) -> str:
    if vision:
        return (
            os.environ.get("OPENROUTER_VISION_MODEL", "").strip()
            or os.environ.get("OPENROUTER_MODEL", "").strip()
            or "google/gemini-2.0-flash-exp:free"
        )
    return os.environ.get("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL).strip() or OPENROUTER_DEFAULT_MODEL


def _parse_positive_int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(os.environ.get(name, str(default)).strip())))
    except ValueError:
        return default


def _call_openrouter_chat(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    vision: bool = False,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> tuple[str, str]:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OPENROUTER_API_KEY is not configured on the backend server",
        )

    selected_model = model or _configured_openrouter_model(vision=vision)
    resolved_max_tokens = max_tokens or _parse_positive_int_env("OPENROUTER_MAX_TOKENS", 700, 100, 1800)
    timeout_seconds = _parse_positive_int_env("OPENROUTER_TIMEOUT_SECONDS", 45, 5, 120)
    request_body = {
        "model": selected_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": resolved_max_tokens,
    }
    request = urllib.request.Request(
        OPENROUTER_API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers=_openrouter_headers(api_key),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:800]
        logger.warning("OpenRouter returned HTTP %s: %s", exc.code, error_body)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter AI server returned HTTP {exc.code}",
        ) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("OpenRouter request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter AI server connect nahi ho saka",
        ) from exc

    answer = ""
    choices = response_payload.get("choices") if isinstance(response_payload, dict) else None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            answer = str(message.get("content") or "").strip()
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenRouter AI server ne khaali jawab diya",
        )
    return answer, selected_model


def _fetch_open_meteo_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    params = (
        f"latitude={latitude:.5f}&longitude={longitude:.5f}"
        "&forecast_days=3"
        "&current=temperature_2m,precipitation,rain,wind_speed_10m"
        "&daily=weather_code,precipitation_sum,rain_sum,wind_speed_10m_max"
        "&timezone=Asia%2FKolkata"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weather API connect nahi ho saka",
        ) from exc


def _safe_image_data_url(image_data: str | None) -> str:
    value = (image_data or "").strip()
    if not value.startswith("data:image/") or ";base64," not in value[:80]:
        raise HTTPException(status_code=422, detail="A valid base64 image data URL is required")
    return value


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


@app.post("/api/v2/mandi-ai")
@app.post("/api/mandi-ai")
def ask_mandi_ai(payload: MandiAIRequest):
    """Answer Hindi mandi questions using OpenRouter with official price data.

    The OpenRouter API key is read only from the server environment. It is never
    accepted from, or returned to, the browser.
    """
    question = (payload.userQuestion or payload.message or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="userQuestion is required")

    context = _collect_ai_mandi_context(payload.mandiData)
    if not context["verified_records"] and not context["single_source_records"]:
        return {
            "answer": "अभी official feed me koi mandi bhav uplabdh nahi hai. DATA_GOV_IN_API_KEY और official feeds configure होने के बाद मैं live bhav बता पाऊँगा।",
            "model": None,
            "data_status": "no_official_records",
        }

    answer, model = _call_openrouter_chat([
        {"role": "system", "content": _build_openrouter_system_prompt(question, payload.mandiData)},
        {"role": "user", "content": question},
    ])

    return {
        "answer": answer,
        "model": model,
        "data_status": "verified_and_source_records_available",
    }


@app.post("/api/chat")
def chat_alias(payload: MandiAIRequest):
    """Compatibility endpoint for simple OpenAI-style website chat demos."""
    result = ask_mandi_ai(payload)
    return {
        "reply": result.get("answer") if isinstance(result, dict) else "",
        "answer": result.get("answer") if isinstance(result, dict) else "",
        "model": result.get("model") if isinstance(result, dict) else None,
        "data_status": result.get("data_status") if isinstance(result, dict) else None,
    }


@app.post("/api/v2/ai-tools")
@app.post("/api/ai-tools")
def run_smart_ai_tool(payload: SmartAIToolRequest):
    """Advanced OpenRouter tools: vision, trends, transport, weather and schemes."""
    action = payload.action
    base_question = (payload.question or "").strip()
    crop = (payload.crop or "").strip()
    location = (payload.location or "").strip()

    if action == "crop_disease":
        image_url = _safe_image_data_url(payload.imageData)
        prompt = (
            "Is crop/leaf photo ko dhyan se analyze kijiye. Hindi me batayein: "
            "1) sambhavit fasal aur rog/keeda, 2) lakshan, 3) turant organic/IPM upay, "
            "4) pesticide ya fungicide ke liye safe generic guidance aur dose ko label/local krishi adhikari se verify karne ki warning, "
            "5) kab expert ya KVK se milna chahiye. Agar image clear nahi hai to clear photo maangien. "
            "Kabhi bhi banned/unsafe chemical ka exact prescription na dein."
        )
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap Hindi bolne wale krishi rog pehchan sahayak hain. Safety-first, practical aur non-alarming answer dein."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt + (f"\nUser context: {base_question}" if base_question else "")},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ], vision=True, max_tokens=900)
        return {"answer": answer, "model": model, "action": action}

    if action == "receipt_ocr":
        image_url = _safe_image_data_url(payload.imageData)
        prompt = (
            "Is mandi parcha/receipt image se OCR karke Hindi me summary dein. "
            "Fasal, mandi, date, weight/quintal, rate, amount, fees, trader/farmer name agar dikh rahe hon to nikalein. "
            "Pehle 'JSON:' ke baad ek valid JSON object dein with keys: crop, mandi, date, quantity_quintal, rate_per_quintal, total_amount, fees, party_name, confidence. "
            "Phir 'Summary:' ke baad simple Hindi explanation. Agar field clear nahi hai to null rakhein; guess na karein."
        )
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap OCR aur mandi khata assistant hain. Sirf image me dikh rahe data ko extract karein; uncertain values ko null rakhein."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ], vision=True, max_tokens=900)
        return {"answer": answer, "model": model, "action": action}

    if action == "trend_advisor":
        context = {
            "crop": crop,
            "question": base_question,
            "mandi_context": _collect_ai_mandi_context(payload.mandiData),
            "history": payload.historyData if payload.historyData is not None else _read_json_file("data/history.json", {}),
            "rules": [
                "Use only provided mandi/history data. Do not promise guaranteed future prices.",
                "Give a cautious sell/hold/watch suggestion in Hindi with reasons and risk disclaimer.",
                "If data is insufficient, say that trend advice is not reliable yet.",
            ],
        }
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap mandi price trend analyst hain. Farmers ko simple Hindi me cautious, data-based advice dein."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ], max_tokens=900)
        return {"answer": answer, "model": model, "action": action}

    if action == "transport_profit":
        source_price = float(payload.sourcePrice or 0)
        destination_price = float(payload.destinationPrice or 0)
        quantity = float(payload.quantityQuintal or 0)
        distance = float(payload.distanceKm or 0)
        cost_per_km = float(payload.transportCostPerKm or 0)
        total_transport = float(payload.totalTransportCost or 0)
        if total_transport <= 0 and distance > 0 and cost_per_km > 0:
            total_transport = distance * cost_per_km
        transport_per_q = (total_transport / quantity) if quantity > 0 else 0
        net_gain_per_q = destination_price - source_price - transport_per_q
        total_net_gain = net_gain_per_q * quantity if quantity > 0 else 0
        calc_context = {
            "source_mandi": payload.sourceMandi,
            "destination_mandi": payload.destinationMandi,
            "source_price_per_q": source_price,
            "destination_price_per_q": destination_price,
            "distance_km": distance,
            "quantity_quintal": quantity,
            "transport_cost_per_km": cost_per_km,
            "total_transport_cost": total_transport,
            "transport_cost_per_quintal": round(transport_per_q, 2),
            "net_gain_per_quintal": round(net_gain_per_q, 2),
            "total_net_gain": round(total_net_gain, 2),
            "question": base_question,
        }
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap mandi transport profit calculator hain. Calculation ko verify karke simple Hindi me final recommendation dein."},
            {"role": "user", "content": json.dumps(calc_context, ensure_ascii=False)},
        ], max_tokens=700)
        return {"answer": answer, "model": model, "action": action, "calculation": calc_context}

    if action == "weather_risk":
        if payload.latitude is None or payload.longitude is None:
            raise HTTPException(status_code=422, detail="latitude and longitude are required for weather risk")
        weather = _fetch_open_meteo_forecast(payload.latitude, payload.longitude)
        context = {
            "location": location,
            "crop": crop,
            "weather_forecast": weather,
            "mandi_context": _collect_ai_mandi_context(payload.mandiData),
            "question": base_question,
            "rules": [
                "Explain rain/wind/heat risk in Hindi for harvest, storage and mandi transport.",
                "Do not invent mandi price drops; only say risk may affect quality/arrival if weather suggests it.",
                "Give practical steps like tarpaulin, drying, storage, transport timing.",
            ],
        }
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap weather + mandi risk warning assistant hain."},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ], max_tokens=850)
        return {"answer": answer, "model": model, "action": action, "weather": weather}

    if action == "scheme_advisor":
        prompt = {
            "farmer_question": base_question,
            "location": location,
            "crop": crop,
            "instructions": [
                "Hindi me PM-KISAN, PM Fasal Bima Yojana, KCC, state agriculture subsidy, soil health card etc. ke liye eligibility-style guidance dein.",
                "Official portal/department se final verification aur documents check karne ko bolen.",
                "Personal/legal/financial guarantee na dein; step-by-step apply checklist dein.",
            ],
        }
        answer, model = _call_openrouter_chat([
            {"role": "system", "content": "Aap sarkari yojana sahayak hain. Clear Hindi guidance, documents list aur official verification disclaimer dein."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ], max_tokens=900)
        return {"answer": answer, "model": model, "action": action}

    raise HTTPException(status_code=422, detail="Unsupported AI tool action")


@app.post("/api/v2/rates")
def create_rate(current_user: db.User = Depends(get_current_user)):
    """Official price records are read-only and cannot be entered manually."""
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Manual rates are disabled; prices must come from a verified government feed",
    )


@app.put("/api/v2/rates/{record_id}")
def update_rate(record_id: int, current_user: db.User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Manual rate edits are disabled; refresh the verified government feed",
    )


@app.delete("/api/v2/rates/{record_id}")
def delete_rate(record_id: int, current_user: db.User = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        detail="Official feed records are read-only",
    )


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

CSV_COLUMNS = (
    "Record_ID", "District", "Mandi", "Commodity", "Variety", "Grade",
    "Arrivals", "Min_Price", "Modal_Price", "Max_Price", "Date", "Last_Sync",
)


def _csv_safe(value) -> str:
    """Render a cell that stays in its own column and never executes.

    Two separate hazards are handled here:

    1. Official mandi and commodity names legitimately contain commas and
       quotes (for example "Arhar (Tur/Red Gram)(Whole)" or "Kanpur, Grain
       Market"). Interpolating them into an f-string shifted every later
       column, so prices landed under the wrong headers. The csv module now
       quotes them properly.
    2. A value beginning with =, +, - or @ is treated as a formula by Excel,
       Google Sheets and LibreOffice. Government feeds are upstream input, so
       such a cell is prefixed with an apostrophe to keep it plain text.
    """
    if value is None:
        return ""
    text_value = str(value)
    if text_value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text_value
    return text_value


@app.get("/api/v2/excel/sync")
def get_excel_sync_stream(db_sess: Session = Depends(get_db)):
    records = db_sess.query(db.MandiRecord).all()

    def generate_csv_rows():
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")

        def flush() -> str:
            buffer.seek(0)
            chunk = buffer.read()
            buffer.seek(0)
            buffer.truncate(0)
            return chunk

        writer.writerow(CSV_COLUMNS)
        yield flush()

        synced_at = datetime.utcnow().isoformat()
        for r in records:
            writer.writerow([_csv_safe(cell) for cell in (
                r.id, r.district, r.mandi, r.commodity, r.variety, r.grade,
                r.arrivals, r.min_price, r.modal_price, r.max_price,
                r.arrival_date, synced_at,
            )])
            yield flush()

    return StreamingResponse(
        generate_csv_rows(),
        media_type="text/csv; charset=utf-8",
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

def _validated_contact_value(contact_type: str, contact_value: str) -> str:
    """Reject a contact the alert engine could never deliver to.

    Storing "not-a-phone!!" or an HTML fragment produced a subscription that
    looked successful to the farmer but silently never sent anything.
    """
    cleaned = contact_value.strip().replace(" ", "").replace("-", "")
    pattern = TELEGRAM_ID_PATTERN if contact_type == "telegram" else PHONE_PATTERN
    if not pattern.fullmatch(cleaned):
        # Literal 422 rather than the status constant: Starlette renamed
        # HTTP_422_UNPROCESSABLE_ENTITY to ..._CONTENT and the old name now
        # emits a DeprecationWarning, while the new name is missing on older
        # releases. The numeric code is stable across both.
        raise HTTPException(
            status_code=422,
            detail=(
                "Enter a numeric Telegram chat id"
                if contact_type == "telegram"
                else "Enter a valid 10-15 digit mobile number"
            ),
        )
    return cleaned


@app.post("/api/v2/alerts/subscribe")
def subscribe_price_alerts(sub: SubscribeRequest, db_sess: Session = Depends(get_db)):
    sub.contact_value = _validated_contact_value(sub.contact_type, sub.contact_value)
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

# ================= OFFICIAL GOVERNMENT BENCHMARKS =================

@app.get("/api/v2/benchmarks")
def get_official_benchmarks():
    """Expose data/benchmarks.json: state benchmark, directory and portals.

    The state ticker is explicitly a state-level benchmark and is never mixed
    into mandi-wise prices. Nothing here is generated locally.
    """
    try:
        with open("data/benchmarks.json", "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No official benchmark snapshot is available yet",
        )


@app.get("/api/v2/sources")
def get_source_monitor():
    """Return the Government Source Monitor payload written by the pipeline."""
    try:
        with open("data/sources.json", "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No source-monitor snapshot is available yet",
        )


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
