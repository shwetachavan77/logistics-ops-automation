"""
Seed realistic call data for dashboard demo.
Called from app startup when DEMO_MODE=true.
"""

import random
from datetime import datetime, timedelta
from app.db.database import Database
from app.models.schemas import CallOutcome, Sentiment

OUTCOME_WEIGHTS = {
    CallOutcome.BOOKED: 32,
    CallOutcome.CARRIER_DECLINED: 22,
    CallOutcome.NO_MATCH: 18,
    CallOutcome.NEGOTIATION_FAILED: 10,
    CallOutcome.VERIFICATION_FAILED: 8,
    CallOutcome.GENERAL_INQUIRY: 10,
}

SENTIMENT_WEIGHTS = {
    Sentiment.POSITIVE: 40,
    Sentiment.NEUTRAL: 35,
    Sentiment.NEGATIVE: 20,
    Sentiment.AGGRESSIVE: 5,
}

CARRIER_NAMES = [
    "J&R Transport LLC", "Eagle Express Inc", "Midwest Haulers",
    "Lone Star Freight", "Pacific Coast Logistics", "Thunder Road Trucking",
    "Blue Line Carriers", "Swift Move LLC", "Great Plains Transport",
    "Sunset Trucking Co", "Iron Horse Freight", "Liberty Logistics",
    "Pioneer Carriers Inc", "Delta Transport", "Golden State Express",
    "Northwind Trucking", "Crestline Haulers", "Summit Freight LLC",
    "Roadmaster Transport", "Atlas Carrier Group"
]

LOAD_IDS = [f"LD-{i}" for i in range(1001, 1016)]


def _weighted_choice(weights_dict):
    items = list(weights_dict.keys())
    weights = list(weights_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


async def seed_demo_calls():
    """Seed 50 demo call records if table is empty."""
    async with Database.pool.acquire() as conn:
        existing = await conn.fetchval("SELECT COUNT(*) FROM calls")
        if existing > 0:
            print(f"Calls table already has {existing} records, skipping seed")
            return

    calls = []
    now = datetime.utcnow()

    for i in range(50):
        outcome = _weighted_choice(OUTCOME_WEIGHTS)
        sentiment = _weighted_choice(SENTIMENT_WEIGHTS)
        timestamp = now - timedelta(
            days=random.randint(0, 13),
            hours=random.randint(6, 18),
            minutes=random.randint(0, 59)
        )

        load_id = random.choice(LOAD_IDS) if outcome != CallOutcome.VERIFICATION_FAILED else None
        mc = str(random.randint(100000, 999999))
        carrier = random.choice(CARRIER_NAMES)
        loadboard_rate = random.uniform(600, 3000)

        initial_offer = final_offer = agreed_rate = None
        rounds = 0

        if outcome == CallOutcome.BOOKED:
            rounds = random.randint(1, 3)
            discount = random.uniform(0, 0.15)
            agreed_rate = round(loadboard_rate * (1 - discount), 2)
            initial_offer = round(loadboard_rate * random.uniform(0.75, 0.95), 2)
            final_offer = agreed_rate
        elif outcome == CallOutcome.CARRIER_DECLINED:
            rounds = random.randint(1, 2)
            initial_offer = round(loadboard_rate * random.uniform(0.60, 0.80), 2)
            final_offer = initial_offer
        elif outcome == CallOutcome.NEGOTIATION_FAILED:
            rounds = 3
            initial_offer = round(loadboard_rate * random.uniform(0.65, 0.80), 2)
            final_offer = round(loadboard_rate * random.uniform(0.70, 0.84), 2)

        calls.append((
            f"call_{i+1:04d}", mc, carrier, load_id,
            outcome.value, sentiment.value,
            agreed_rate, rounds, initial_offer, final_offer,
            round(loadboard_rate, 2), random.randint(45, 480),
            None, timestamp
        ))

    async with Database.pool.acquire() as conn:
        await conn.executemany("""
            INSERT INTO calls (
                call_id, carrier_mc, carrier_name, load_id,
                outcome, sentiment, agreed_rate, negotiation_rounds,
                initial_offer, final_offer, loadboard_rate,
                call_duration_seconds, transcript, timestamp
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        """, calls)

    print(f"Seeded {len(calls)} call records")
