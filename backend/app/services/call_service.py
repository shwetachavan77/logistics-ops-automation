"""Call logging and metrics aggregation."""

from datetime import datetime, timedelta
from typing import List, Optional
from app.db.database import Database
from app.models.schemas import CallLog, CallLogResponse, DashboardMetrics


async def log_call(call: CallLog) -> CallLogResponse:
    """
    Store a completed call record.
    Called by HappyRobot's webhook after Classify + Extract nodes run.
    """
    async with Database.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO calls (
                call_id, carrier_mc, carrier_name, load_id, outcome,
                sentiment, agreed_rate, negotiation_rounds, initial_offer,
                final_offer, loadboard_rate, call_duration_seconds,
                transcript, timestamp
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT (call_id) DO UPDATE SET
                outcome = EXCLUDED.outcome,
                sentiment = EXCLUDED.sentiment,
                agreed_rate = EXCLUDED.agreed_rate,
                negotiation_rounds = EXCLUDED.negotiation_rounds,
                transcript = EXCLUDED.transcript
        """,
            call.call_id, call.carrier_mc, call.carrier_name,
            call.load_id, str(call.outcome), str(call.sentiment),
            call.agreed_rate, call.negotiation_rounds,
            call.initial_offer, call.final_offer, call.loadboard_rate,
            call.call_duration_seconds, call.transcript, call.timestamp
        )

        # If the load was booked, mark it unavailable and queue confirmation
        if call.outcome == "booked" and call.load_id:
            await conn.execute(
                "UPDATE loads SET is_available = FALSE WHERE load_id = $1",
                call.load_id
            )
            # In production: send rate confirmation via SendGrid/Twilio
            print(f"BOOKING CONFIRMED: {call.carrier_name} (MC-{call.carrier_mc}) booked {call.load_id} at ${call.agreed_rate}. Rate confirmation queued.")

    return CallLogResponse(call_id=call.call_id, status="logged")


async def get_dashboard_metrics() -> DashboardMetrics:
    """
    Aggregate call data into dashboard-ready metrics.
    This powers the React dashboard.
    """
    async with Database.pool.acquire() as conn:
        # Total calls
        total = await conn.fetchval("SELECT COUNT(*) FROM calls")
        if total == 0:
            return _empty_metrics()

        # Calls by outcome
        outcome_rows = await conn.fetch(
            "SELECT outcome, COUNT(*) as cnt FROM calls GROUP BY outcome"
        )
        calls_by_outcome = {row["outcome"]: row["cnt"] for row in outcome_rows}

        # Calls by sentiment
        sentiment_rows = await conn.fetch(
            "SELECT sentiment, COUNT(*) as cnt FROM calls GROUP BY sentiment"
        )
        calls_by_sentiment = {row["sentiment"]: row["cnt"] for row in sentiment_rows}

        # Booking rate
        booked = calls_by_outcome.get("booked", 0)
        booking_rate = (booked / total * 100) if total > 0 else 0

        # Average negotiation rounds (for calls that had negotiation)
        avg_rounds = await conn.fetchval(
            "SELECT COALESCE(AVG(negotiation_rounds), 0) FROM calls WHERE negotiation_rounds > 0"
        )

        # Average discount from loadboard rate (for booked calls)
        avg_discount = await conn.fetchval("""
            SELECT COALESCE(
                AVG(
                    CASE WHEN loadboard_rate > 0
                    THEN ((loadboard_rate - agreed_rate) / loadboard_rate * 100)
                    ELSE 0 END
                ), 0
            ) FROM calls
            WHERE outcome = 'booked' AND agreed_rate IS NOT NULL
        """)

        # Total revenue booked
        revenue = await conn.fetchval(
            "SELECT COALESCE(SUM(agreed_rate), 0) FROM calls WHERE outcome = 'booked'"
        )

        # Calls over time (last 30 days, grouped by day)
        time_rows = await conn.fetch("""
            SELECT DATE(timestamp) as day, COUNT(*) as cnt
            FROM calls
            WHERE timestamp >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(timestamp)
            ORDER BY day
        """)
        calls_over_time = [
            {"date": row["day"].isoformat(), "count": row["cnt"]}
            for row in time_rows
        ]

        # Top lanes
        lane_rows = await conn.fetch("""
            SELECT
                l.origin, l.destination,
                COUNT(*) as call_count,
                SUM(CASE WHEN c.outcome = 'booked' THEN 1 ELSE 0 END) as bookings
            FROM calls c
            JOIN loads l ON c.load_id = l.load_id
            GROUP BY l.origin, l.destination
            ORDER BY call_count DESC
            LIMIT 5
        """)
        top_lanes = [
            {
                "origin": row["origin"],
                "destination": row["destination"],
                "calls": row["call_count"],
                "bookings": row["bookings"]
            }
            for row in lane_rows
        ]

        # Negotiation intelligence
        round1_closes = await conn.fetchval(
            "SELECT COUNT(*) FROM calls WHERE outcome = 'booked' AND negotiation_rounds = 1"
        )
        total_booked = await conn.fetchval(
            "SELECT COUNT(*) FROM calls WHERE outcome = 'booked'"
        )
        round1_close_rate = (round1_closes / total_booked * 100) if total_booked > 0 else 0

        floor_hits = await conn.fetchval("""
            SELECT COUNT(*) FROM calls
            WHERE outcome = 'booked' AND agreed_rate IS NOT NULL AND loadboard_rate IS NOT NULL
            AND agreed_rate <= loadboard_rate * 0.87
        """)
        floor_rate_hit_rate = (floor_hits / total_booked * 100) if total_booked > 0 else 0

        avg_rate_given_up = await conn.fetchval("""
            SELECT COALESCE(AVG(loadboard_rate - agreed_rate), 0)
            FROM calls
            WHERE outcome = 'booked' AND agreed_rate IS NOT NULL AND loadboard_rate IS NOT NULL
        """)

        avg_duration = await conn.fetchval(
            "SELECT COALESCE(AVG(call_duration_seconds), 0) FROM calls WHERE call_duration_seconds > 0"
        )

        total_carriers = await conn.fetchval(
            "SELECT COUNT(DISTINCT carrier_mc) FROM calls WHERE carrier_mc IS NOT NULL"
        )
        repeat_carriers = await conn.fetchval(
            "SELECT COUNT(*) FROM (SELECT carrier_mc FROM calls WHERE carrier_mc IS NOT NULL GROUP BY carrier_mc HAVING COUNT(*) > 1) sub"
        )
        repeat_carrier_rate = (repeat_carriers / total_carriers * 100) if total_carriers > 0 else 0

        loads_available = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = TRUE")
        loads_booked = await conn.fetchval("SELECT COUNT(*) FROM loads WHERE is_available = FALSE")
        total_loads = loads_available + loads_booked
        load_fill_rate = (loads_booked / total_loads * 100) if total_loads > 0 else 0

        avg_rpm = await conn.fetchval("""
            SELECT COALESCE(AVG(
                CASE WHEN l.miles > 0 THEN c.agreed_rate / l.miles ELSE NULL END
            ), 0)
            FROM calls c JOIN loads l ON c.load_id = l.load_id
            WHERE c.outcome = 'booked' AND c.agreed_rate IS NOT NULL
        """)

        return DashboardMetrics(
            total_calls=total,
            calls_by_outcome=calls_by_outcome,
            calls_by_sentiment=calls_by_sentiment,
            booking_rate=round(booking_rate, 1),
            avg_negotiation_rounds=round(float(avg_rounds), 1),
            avg_discount_from_loadboard=round(float(avg_discount), 1),
            revenue_booked=float(revenue),
            calls_over_time=calls_over_time,
            top_lanes=top_lanes,
            round1_close_rate=round(round1_close_rate, 1),
            floor_rate_hit_rate=round(floor_rate_hit_rate, 1),
            avg_rate_given_up=round(float(avg_rate_given_up)),
            avg_call_duration=round(float(avg_duration)),
            repeat_carrier_rate=round(repeat_carrier_rate, 1),
            load_fill_rate=round(load_fill_rate, 1),
            loads_available=loads_available,
            loads_booked=loads_booked,
            avg_rate_per_mile=f"{float(avg_rpm):.2f}",
        )


async def get_recent_calls(limit: int = 20) -> List[dict]:
    """Get recent call records for the dashboard table."""
    async with Database.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM calls
            ORDER BY timestamp DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]


def _empty_metrics() -> DashboardMetrics:
    """Return zero-state metrics when no calls exist yet."""
    return DashboardMetrics(
        total_calls=0,
        calls_by_outcome={},
        calls_by_sentiment={},
        booking_rate=0,
        avg_negotiation_rounds=0,
        avg_discount_from_loadboard=0,
        revenue_booked=0,
        calls_over_time=[],
        top_lanes=[],
    )
