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


def clean_str(val: Optional[str]) -> Optional[str]:
    """Normalize voice agent payloads: null, 'null', '' all become None."""
    if val is None:
        return None
    val = val.strip()
    if val.lower() in ("null", "none", ""):
        return None
    return val


def clean_float(val) -> Optional[float]:
    """Parse numeric values that might arrive as strings from voice agent."""
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


def clean_int(val) -> Optional[int]:
    """Parse integer values that might arrive as strings from voice agent."""
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


# Carrier verification

@router.post("/verify-carrier", response_model=CarrierVerificationResponse)
@limiter.limit("30/minute")
async def verify_carrier(request: CarrierVerificationRequest, request: Request):
    """Verify a carrier's MC number against FMCSA."""
    mc = clean_str(request.mc_number)
    if not mc:
        raise HTTPException(status_code=400, detail="MC number is required")
    result = await fmcsa_service.verify_carrier(mc)
    return result


# Load search

@router.post("/search-loads", response_model=LoadSearchResponse)
@limiter.limit("60/minute")
async def search_loads(request: LoadSearchRequest, request: Request):
    """Search available loads matching carrier criteria."""
    request.origin = clean_str(request.origin)
    request.destination = clean_str(request.destination)
    request.equipment_type = clean_str(request.equipment_type)
    request.pickup_date = clean_str(request.pickup_date)
    result = await load_service.search_loads(request)
    return result


# Negotiation

@router.post("/negotiate", response_model=NegotiationResponse)
@limiter.limit("30/minute")
async def negotiate(request: NegotiationRequest, request: Request):
    """Evaluate a carrier's price offer. Max 3 rounds."""
    if request.round_number > 3:
        return NegotiationResponse(
            accepted=False,
            message="We've reached the maximum negotiation rounds. Let me transfer you to a rep.",
            round_number=request.round_number,
            final_round=True
        )
    result = await negotiation_service.evaluate_offer(request)
    return result


# Transfer (mock)

@router.post("/transfer")
@limiter.limit("10/minute")
async def transfer_call(request: Request, call_id: str, carrier_name: Optional[str] = None):
    """Mock call transfer to sales rep."""
    return {
        "status": "success",
        "message": "Transfer was successful and now you can wrap up the conversation.",
        "call_id": clean_str(call_id) or call_id,
        "transferred_to": "Sales Representative"
    }


# Call logging webhook

@router.post("/calls/log", response_model=CallLogResponse)
@limiter.limit("60/minute")
async def log_call(call: CallLog, request: Request):
    """Log a completed call with extracted/classified data."""
    call.carrier_mc = clean_str(call.carrier_mc)
    call.carrier_name = clean_str(call.carrier_name)
    call.load_id = clean_str(call.load_id)
    call.agreed_rate = clean_float(call.agreed_rate)
    call.initial_offer = clean_float(call.initial_offer)
    call.final_offer = clean_float(call.final_offer)
    call.negotiation_rounds = clean_int(call.negotiation_rounds) or 0
    call.transcript = clean_str(call.transcript)
    return await call_service.log_call(call)


# Dashboard metrics

@router.get("/metrics", response_model=DashboardMetrics)
@limiter.limit("120/minute")
async def get_metrics(request: Request):
    """Aggregated metrics for the dashboard."""
    return await call_service.get_dashboard_metrics()


@router.get("/calls/recent")
@limiter.limit("120/minute")
async def get_recent_calls(request: Request, limit: int = 20):
    """Recent calls for the dashboard table."""
    calls = await call_service.get_recent_calls(limit)
    return {"calls": calls}


# Loads list

@router.get("/loads")
@limiter.limit("120/minute")
async def get_all_loads(request: Request):
    """List all loads."""
    result = await load_service.search_loads(LoadSearchRequest())
    return {"loads": [l.model_dump() for l in result.loads]}


# Health check

@router.get("/health")
async def health():
    return {"status": "healthy", "service": "carrier-sales-api"}
