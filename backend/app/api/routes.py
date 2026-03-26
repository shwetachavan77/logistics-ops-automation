"""API routes for carrier sales automation."""

import uuid
from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.schemas import (
    CarrierVerificationRequest, CarrierVerificationResponse,
    LoadSearchRequest, LoadSearchResponse,
    NegotiationRequest, NegotiationResponse,
    CallLog, CallLogResponse,
    MissedOpportunityAlert,
    RateConfirmation, RateConfirmationResponse,
    CarrierHistoryResponse,
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


# ---- Core endpoints ----

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
    round_num = clean_int(payload.round_number) or 1
    if round_num > 3:
        return NegotiationResponse(
            accepted=False,
            message="We've reached the maximum negotiation rounds. Let me transfer you to a rep.",
            round_number=round_num,
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


# ---- Call logging ----

@router.post("/calls/log", response_model=CallLogResponse)
@limiter.limit("60/minute")
async def log_call(request: Request, call: CallLog):
    call.carrier_mc = clean_str(call.carrier_mc)
    call.carrier_name = clean_str(call.carrier_name)
    call.load_id = clean_str(call.load_id)
    call.outcome = clean_str(call.outcome) or "unknown"
    call.sentiment = clean_str(call.sentiment) or "neutral"
    call.agreed_rate = clean_float(call.agreed_rate)
    call.initial_offer = clean_float(call.initial_offer)
    call.final_offer = clean_float(call.final_offer)
    call.loadboard_rate = clean_float(call.loadboard_rate)
    call.negotiation_rounds = clean_int(call.negotiation_rounds) or 0
    call.transcript = clean_str(call.transcript)
    call.notes = clean_str(call.notes)
    call.sms_text = clean_str(call.sms_text)
    return await call_service.log_call(call)


# ---- V2: Missed opportunity alert ----

@router.post("/alerts/missed-opportunity")
@limiter.limit("30/minute")
async def missed_opportunity(request: Request, alert: MissedOpportunityAlert):
    """Log a near-miss deal for manual follow-up by sales reps."""
    final = clean_float(alert.final_offer)
    rate = clean_float(alert.loadboard_rate)
    gap = abs(final - rate) if final and rate else None

    record = {
        "call_id": alert.call_id,
        "carrier_mc": clean_str(alert.carrier_mc),
        "carrier_name": clean_str(alert.carrier_name),
        "load_id": clean_str(alert.load_id),
        "final_offer": final,
        "loadboard_rate": rate,
        "gap": gap,
        "message": f"Near-miss deal. Carrier offered ${final:,.2f}, cap was ${rate:,.2f}. Gap: ${gap:,.2f}. Consider manual follow-up." if final and rate and gap else "Near-miss deal. Consider manual follow-up.",
        "status": "alert_logged"
    }

    # Store as a call log with notes
    try:
        from app.db.database import Database
        async with Database.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO calls (call_id, carrier_mc, carrier_name, load_id, outcome, notes, timestamp)
                VALUES ($1, $2, $3, $4, 'negotiation_failed', $5, NOW())
                ON CONFLICT (call_id) DO UPDATE SET notes = EXCLUDED.notes
            """, alert.call_id + "_alert", clean_str(alert.carrier_mc),
                clean_str(alert.carrier_name), clean_str(alert.load_id), record["message"])
    except Exception as e:
        print(f"Failed to store alert: {e}")

    return record


# ---- V2: Rate confirmation ----

@router.post("/confirmations/rate", response_model=RateConfirmationResponse)
@limiter.limit("30/minute")
async def rate_confirmation(request: Request, conf: RateConfirmation):
    """Generate rate confirmation after a successful booking."""
    confirmation_id = f"RC-{uuid.uuid4().hex[:8].upper()}"
    agreed = clean_float(conf.agreed_rate)

    load = None
    load_id = clean_str(conf.load_id)
    if load_id:
        load = await load_service.get_load_by_id(load_id)

    origin = conf.origin or (load.origin if load else "TBD")
    destination = conf.destination or (load.destination if load else "TBD")
    equipment = conf.equipment_type or (load.equipment_type if load else "TBD")

    message = (
        f"Rate confirmation {confirmation_id} generated. "
        f"Carrier {conf.carrier_name or 'N/A'} (MC: {conf.carrier_mc or 'N/A'}) "
        f"booked load {load_id or 'N/A'}: {origin} to {destination}, "
        f"{equipment}, agreed rate ${agreed:,.2f}." if agreed else
        f"Rate confirmation {confirmation_id} generated for load {load_id or 'N/A'}."
    )

    return RateConfirmationResponse(
        status="confirmation_sent",
        confirmation_id=confirmation_id,
        message=message
    )


# ---- V2: Carrier history / scoring ----

@router.get("/carriers/{mc_number}/history", response_model=CarrierHistoryResponse)
@limiter.limit("30/minute")
async def carrier_history(request: Request, mc_number: str):
    """Get a carrier's call history and reliability score."""
    mc = clean_str(mc_number)
    if not mc:
        raise HTTPException(status_code=400, detail="MC number is required")

    from app.db.database import Database
    async with Database.pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) as total_calls,
                SUM(CASE WHEN outcome = 'booked' THEN 1 ELSE 0 END) as total_bookings,
                COALESCE(AVG(negotiation_rounds), 0) as avg_rounds,
                COALESCE(AVG(CASE WHEN agreed_rate IS NOT NULL THEN agreed_rate END), 0) as avg_rate,
                MAX(timestamp) as last_call
            FROM calls WHERE carrier_mc = $1
        """, mc)

        lanes = await conn.fetch("""
            SELECT l.origin, l.destination, COUNT(*) as count
            FROM calls c JOIN loads l ON c.load_id = l.load_id
            WHERE c.carrier_mc = $1
            GROUP BY l.origin, l.destination
            ORDER BY count DESC LIMIT 5
        """, mc)

    total = stats["total_calls"] or 0
    bookings = stats["total_bookings"] or 0
    booking_rate = (bookings / total * 100) if total > 0 else 0

    # Reliability score: weighted combination of booking rate and call frequency
    # Higher booking rate + more calls = higher score
    frequency_bonus = min(total / 10, 1.0)  # caps at 10 calls
    reliability = round((booking_rate * 0.7 + frequency_bonus * 30), 1)
    reliability = min(reliability, 100.0)

    return CarrierHistoryResponse(
        carrier_mc=mc,
        total_calls=total,
        total_bookings=bookings,
        booking_rate=round(booking_rate, 1),
        avg_negotiation_rounds=round(float(stats["avg_rounds"]), 1),
        avg_agreed_rate=round(float(stats["avg_rate"]), 2) if stats["avg_rate"] else None,
        last_call_date=stats["last_call"].isoformat() if stats["last_call"] else None,
        reliability_score=reliability,
        lanes=[{"origin": r["origin"], "destination": r["destination"], "count": r["count"]} for r in lanes]
    )


# ---- Dashboard ----

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


@router.post("/auth/login")
async def dashboard_login(request: Request):
    """Validate dashboard password. Returns API key on success for subsequent requests."""
    from app.api.auth import DASHBOARD_PASSWORD, API_KEY
    body = await request.json()
    pw = body.get("password", "")
    if pw == DASHBOARD_PASSWORD:
        return {"status": "ok", "api_key": API_KEY}
    raise HTTPException(status_code=403, detail="Invalid password")


@router.post("/reset")
@limiter.limit("5/minute")
async def reset_data(request: Request):
    """Clear all call history and reset loads to available."""
    from app.db.database import Database
    async with Database.pool.acquire() as conn:
        calls_deleted = await conn.fetchval("SELECT COUNT(*) FROM calls")
        await conn.execute("DELETE FROM calls")
        await conn.execute("DELETE FROM negotiations")
        loads_reset = await conn.fetchval("UPDATE loads SET is_available = TRUE RETURNING COUNT(*)")
        if loads_reset is None:
            loads_reset = await conn.fetchval("SELECT COUNT(*) FROM loads")
            await conn.execute("UPDATE loads SET is_available = TRUE")
    return {"status": "ok", "calls_deleted": calls_deleted or 0, "loads_reset": loads_reset or 0}


@router.post("/loads/refresh")
@limiter.limit("10/minute")
async def refresh_loads(request: Request):
    """Re-seed loads if running low."""
    from app.db.database import Database
    async with Database.pool.acquire() as conn:
        available = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = TRUE")
        total = await conn.fetchval("SELECT COUNT(*) FROM loads")
        if available >= 10:
            return {"status": "ok", "message": f"Already have {available} loads available", "added": 0, "unbooked": available}
        # Reset booked loads back to available
        await conn.execute("UPDATE loads SET is_available = TRUE")
        unbooked = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = TRUE")
    return {"status": "ok", "added": unbooked - available, "unbooked": unbooked}
