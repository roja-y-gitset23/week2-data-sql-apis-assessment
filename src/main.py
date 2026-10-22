import hashlib
import hmac
import os
from contextlib import asynccontextmanager

from fastapi import (APIRouter, BackgroundTasks, Depends, FastAPI, Form,
                     Header, HTTPException, Query, Request, Response, Security)
from fastapi.security import APIKeyHeader
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src import models  # noqa: F401  (registers the table)
from src.database import Base, engine, get_db
from src.models import Customer
from src.schemas import CustomerCreate, CustomerOut, CustomerPage


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Secured Customer API", lifespan=lifespan)

# ---------------- API key security ----------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Security(api_key_header)):
    if key is None:
        raise HTTPException(status_code=401, detail="Missing API key")
    expected = os.getenv("API_KEY", "")
    if not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid API key")


# ---------------- Customers (all protected) ----------------
router = APIRouter(prefix="/customers", dependencies=[Depends(verify_api_key)])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    if db.scalar(select(Customer).where(Customer.email == payload.email)):
        raise HTTPException(status_code=409, detail="Email already exists")
    customer = Customer(**payload.model_dump())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    db.refresh(customer)
    return customer


@router.get("", response_model=CustomerPage)
def list_customers(page: int = Query(1, ge=1),
                   per_page: int = Query(5, ge=1, le=100),
                   db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Customer))
    rows = db.scalars(
        select(Customer).order_by(Customer.id)
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return CustomerPage(page=page, per_page=per_page, total=total,
                        items=[CustomerOut.model_validate(r) for r in rows])


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerCreate,
                    db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    clash = db.scalar(select(Customer).where(
        Customer.email == payload.email, Customer.id != customer_id))
    if clash:
        raise HTTPException(status_code=409, detail="Email already exists")
    customer.name = payload.name
    customer.email = payload.email
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(customer)
    db.commit()
    return Response(status_code=204)


app.include_router(router)


# ---------------- Webhook (HMAC-SHA256) ----------------
def process_event(body: bytes):
    """Runs AFTER the 200 response has been sent."""
    print("Processing webhook event:", body[:100])


@app.post("/webhooks/order-events")
async def order_events(request: Request, background: BackgroundTasks,
                       x_signature: str | None = Header(default=None)):
    body = await request.body()
    secret = os.getenv("WEBHOOK_SECRET", "").encode()
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    received = (x_signature or "").removeprefix("sha256=")
    if not hmac.compare_digest(expected.encode(), received.encode()):
        raise HTTPException(status_code=401, detail="Invalid signature")
    background.add_task(process_event, body)  # work happens after the response
    return {"status": "received"}


# ---------------- Mock OAuth token endpoint (client credentials) ----------------
@app.post("/mock/token")
def mock_token(grant_type: str = Form(...), client_id: str = Form(...),
               client_secret: str = Form(...)):
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported_grant_type")
    return {"access_token": "mock-token-123", "token_type": "bearer",
            "expires_in": 3600}