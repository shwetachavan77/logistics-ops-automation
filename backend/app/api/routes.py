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
    result = await load_service.search_loads(LoadSearchRequest(), allow_broad=True)
    return {"loads": [l.model_dump() for l in result.loads]}


@router.post("/simulate")
@limiter.limit("10/minute")
async def simulate_calls(request: Request):
    """Add 5 random call entries for demo purposes. Cap at 100 non-booked."""
    import random
    from datetime import datetime, timedelta
    from app.db.database import Database

    async with Database.pool.acquire() as conn:
        # Count non-booked calls
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM calls WHERE outcome != 'booked' OR outcome IS NULL"
        )
        if count >= 100:
            return {"status": "cap_reached", "message": "Already at 100 non-booked calls", "total": count}

        to_add = min(5, 100 - count)

        carriers = [
            ("Eagle Express Inc", "482910"),
            ("Lone Star Freight", "391055"),
            ("Thunder Road Trucking", "558432"),
            ("Pacific Coast Logistics", "672190"),
            ("Blue Line Carriers", "223847"),
            ("Summit Freight LLC", "887654"),
            ("Great Plains Transport", "445512"),
            ("Liberty Logistics", "334521"),
            ("Northwind Trucking", "776543"),
            ("Iron Horse Freight", "999999"),
            ("Redwood Transport", "112233"),
            ("Cascade Haulers", "445566"),
            ("Prairie Wind Logistics", "778899"),
            ("Gulf Coast Carriers", "334455"),
            ("Mountain Pass Freight", "667788"),
        ]
        outcomes = ["booked", "carrier_declined", "no_match", "negotiation_failed", "verification_failed"]
        outcome_weights = [35, 25, 20, 12, 8]
        sentiments = ["positive", "neutral", "negative", "aggressive"]
        sentiment_weights = [40, 35, 18, 7]
        load_ids = ["LD-1001", "LD-1002", "LD-1003", "LD-1004", "LD-1005",
                     "LD-1006", "LD-1007", "LD-1008", "LD-1009", "LD-1010"]

        added = 0
        for _ in range(to_add):
            carrier = random.choice(carriers)
            outcome = random.choices(outcomes, weights=outcome_weights, k=1)[0]
            sentiment = random.choices(sentiments, weights=sentiment_weights, k=1)[0]
            load_id = random.choice(load_ids) if outcome != "verification_failed" else None
            hours_ago = random.randint(1, 336)
            ts = datetime.utcnow() - timedelta(hours=hours_ago)
            call_id = f"SIM-{ts.strftime('%Y%m%d')}-{random.randint(100,999)}"
            duration = random.randint(45, 420)
            rounds = 0
            agreed = None
            initial = None
            final = None
            lb_rate = None

            if outcome == "booked":
                lb_rate = random.choice([650, 750, 850, 950, 1100, 1450, 1650, 1800, 2100, 2200, 2400, 2850])
                rounds = random.randint(1, 3)
                discount = random.uniform(0, 0.08)
                agreed = round(lb_rate * (1 - discount))
                initial = round(lb_rate * random.uniform(0.8, 0.95))
                final = agreed
            elif outcome in ("carrier_declined", "negotiation_failed"):
                lb_rate = random.choice([650, 950, 1450, 1800, 2200, 2850])
                rounds = random.randint(1, 3)
                initial = round(lb_rate * random.uniform(0.7, 0.85))
                final = round(lb_rate * random.uniform(0.75, 0.9))

            try:
                await conn.execute("""
                    INSERT INTO calls (
                        call_id, carrier_mc, carrier_name, load_id, outcome,
                        sentiment, agreed_rate, negotiation_rounds, initial_offer,
                        final_offer, loadboard_rate, call_duration_seconds, timestamp
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (call_id) DO NOTHING
                """,
                    call_id, carrier[1], carrier[0], load_id, outcome,
                    sentiment, agreed, rounds, initial, final, lb_rate, duration, ts
                )
                added += 1
            except Exception:
                pass

        new_count = await conn.fetchval("SELECT COUNT(*) FROM calls")
        return {"status": "ok", "added": added, "total_calls": new_count}


@router.post("/loads/refresh")
@limiter.limit("10/minute")
async def refresh_loads(request: Request):
    """Add 5 new random loads. Cap unbooked loads at 100."""
    import random
    from datetime import datetime, timedelta
    from app.db.database import Database

    cities = [
        "Chicago, IL", "Dallas, TX", "Los Angeles, CA", "Phoenix, AZ",
        "Atlanta, GA", "Miami, FL", "Houston, TX", "Memphis, TN",
        "Newark, NJ", "Boston, MA", "Seattle, WA", "Portland, OR",
        "Denver, CO", "Nashville, TN", "Charlotte, NC", "Indianapolis, IN",
        "Columbus, OH", "Kansas City, MO", "St. Louis, MO", "Detroit, MI",
        "Philadelphia, PA", "Washington, DC", "Jacksonville, FL",
        "Minneapolis, MN", "Tampa, FL", "San Antonio, TX", "Sacramento, CA",
        "Cincinnati, OH", "Pittsburgh, PA", "Louisville, KY",
    ]
    equipment = ["Dry Van", "Reefer", "Flatbed", "Step Deck", "Box Truck"]
    commodities = [
        "Electronics", "Produce", "Furniture", "Steel Coils", "Consumer Goods",
        "Seafood", "Auto Parts", "Machinery", "Paper Products", "Medical Supplies",
        "Beverages", "Lumber", "Pharmaceuticals", "Office Supplies", "Textiles",
        "Building Materials", "Frozen Foods", "Pet Supplies", "Industrial Equipment",
    ]

    async with Database.pool.acquire() as conn:
        unbooked = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = TRUE")
        if unbooked >= 100:
            return {"status": "cap_reached", "message": "Already at 100 unbooked loads", "total_unbooked": unbooked}

        to_add = min(5, 100 - unbooked)

        max_id = await conn.fetchval("SELECT MAX(CAST(REPLACE(load_id, 'LD-', '') AS INTEGER)) FROM loads")
        next_id = (max_id or 1015) + 1

        added = 0
        for i in range(to_add):
            load_id = f"LD-{next_id + i}"
            origin = random.choice(cities)
            dest = random.choice([c for c in cities if c != origin])
            equip = random.choice(equipment)
            miles = random.randint(150, 1200)
            rate = round(miles * random.uniform(2.0, 3.5), -1)
            weight = random.randint(8000, 45000)
            pieces = random.randint(1, 40)
            commodity = random.choice(commodities)
            pickup = datetime.utcnow() + timedelta(hours=random.randint(12, 96))
            delivery = pickup + timedelta(hours=random.randint(8, 36))

            notes_options = [
                "No-touch freight, dock-to-dock",
                "Appointment required",
                "Driver assist required",
                "Liftgate needed at delivery",
                "Tarps required",
                "Team drivers preferred",
                None,
            ]
            notes = random.choice(notes_options)

            try:
                await conn.execute("""
                    INSERT INTO loads (
                        load_id, origin, destination, pickup_datetime, delivery_datetime,
                        equipment_type, loadboard_rate, notes, weight, commodity_type,
                        num_of_pieces, miles, dimensions
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                    ON CONFLICT (load_id) DO NOTHING
                """,
                    load_id, origin, dest, pickup, delivery,
                    equip, rate, notes, weight, commodity,
                    pieces, miles, "Standard pallets"
                )
                added += 1
            except Exception:
                pass

        total = await conn.fetchval("SELECT COUNT(*) FROM loads")
        unbooked_new = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = TRUE")
        return {"status": "ok", "added": added, "total_loads": total, "unbooked": unbooked_new}


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "carrier-sales-api"}
