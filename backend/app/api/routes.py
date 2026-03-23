"""API routes for carrier verification, load search, negotiation, and call logging."""

from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.schemas import (
    CarrierVerificationRequest, CarrierVerificationResponse,
    LoadSearchRequest, LoadSearchResponse,
    NegotiationRequest, NegotiationResponse,
    CallLog, CallLogResponse,
    DashboardMetrics,
)
from app.services import fmcsa_service, load_service, negotiation_service, call_service

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/api", tags=["Carrier Sales"])


def clean_str(val):
    if val is None:
        return None
    val = str(val).strip()
    if val.lower() in ("null", "none", ""):
        return None
    return val


def clean_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().replace("$", "").replace(",", "")
        if val.lower() in ("null", "none", ""):
            return None
        try:
            return float(val)
        except ValueError:
            return None
    return None


def clean_int(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        val = val.strip()
        if val.lower() in ("null", "none", ""):
            return None
        try:
            return int(float(val))
        except ValueError:
            return None
    return None


@router.post("/verify-carrier", response_model=CarrierVerificationResponse)
@limiter.limit("30/minute")
async def verify_carrier(request: Request, payload: CarrierVerificationRequest):
    mc = clean_str(payload.mc_number)
    if not mc:
        raise HTTPException(status_code=400, detail="MC number is required")
    return await fmcsa_service.verify_carrier(mc)


@router.post("/search-loads", response_model=LoadSearchResponse)
@limiter.limit("60/minute")
async def search_loads(request: Request, payload: LoadSearchRequest):
    payload.origin = clean_str(payload.origin)
    payload.destination = clean_str(payload.destination)
    payload.equipment_type = clean_str(payload.equipment_type)
    payload.pickup_date = clean_str(payload.pickup_date)
    return await load_service.search_loads(payload)


@router.post("/negotiate", response_model=NegotiationResponse)
@limiter.limit("30/minute")
async def negotiate(request: Request, payload: NegotiationRequest):
    if payload.round_number > 3:
        return NegotiationResponse(
            accepted=False,
            message="We've reached the maximum negotiation rounds. Let me transfer you to a rep.",
            round_number=payload.round_number,
            final_round=True
        )
    return await negotiation_service.evaluate_offer(payload)


@router.post("/transfer")
@limiter.limit("10/minute")
async def transfer_call(request: Request, call_id: str, carrier_name: Optional[str] = None):
    return {
        "status": "success",
        "message": "Transfer was successful and now you can wrap up the conversation.",
        "call_id": clean_str(call_id) or call_id,
        "transferred_to": "Sales Representative"
    }


@router.post("/calls/log", response_model=CallLogResponse)
@limiter.limit("60/minute")
async def log_call(request: Request, call: CallLog):
    call.carrier_mc = clean_str(call.carrier_mc)
    call.carrier_name = clean_str(call.carrier_name)
    call.load_id = clean_str(call.load_id)
    call.agreed_rate = clean_float(call.agreed_rate)
    call.initial_offer = clean_float(call.initial_offer)
    call.final_offer = clean_float(call.final_offer)
    call.negotiation_rounds = clean_int(call.negotiation_rounds) or 0
    call.transcript = clean_str(call.transcript)
    return await call_service.log_call(call)


@router.get("/metrics", response_model=DashboardMetrics)
@limiter.limit("120/minute")
async def get_metrics(request: Request):
    return await call_service.get_dashboard_metrics()


@router.get("/calls/recent")
@limiter.limit("120/minute")
async def get_recent_calls(request: Request, limit: int = 20):
    calls = await call_service.get_recent_calls(limit)
    return {"calls": calls}


@router.get("/loads")
@limiter.limit("120/minute")
async def get_all_loads(request: Request):
    result = await load_service.search_loads(LoadSearchRequest())
    return {"loads": [l.model_dump() for l in result.loads]}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "carrier-sales-api"}
