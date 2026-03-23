"""PostgreSQL connection pool and schema setup."""

import os
import asyncpg
from datetime import datetime
from typing import Optional

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://carrier_user:carrier_pass@localhost:5432/carrier_sales"
)


class Database:
    pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def connect(cls):
        cls.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,
            max_size=20,
        )
        await cls._create_tables()
        print("Connected to PostgreSQL")

    @classmethod
    async def disconnect(cls):
        if cls.pool:
            await cls.pool.close()
            print("Disconnected from PostgreSQL")

    @classmethod
    async def _create_tables(cls):
        async with cls.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS loads (
                    load_id TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    pickup_datetime TIMESTAMPTZ NOT NULL,
                    delivery_datetime TIMESTAMPTZ NOT NULL,
                    equipment_type TEXT NOT NULL,
                    loadboard_rate NUMERIC(10,2) NOT NULL,
                    notes TEXT,
                    weight NUMERIC(10,2),
                    commodity_type TEXT,
                    num_of_pieces INTEGER,
                    miles NUMERIC(10,2),
                    dimensions TEXT,
                    is_available BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS calls (
                    call_id TEXT PRIMARY KEY,
                    carrier_mc TEXT,
                    carrier_name TEXT,
                    load_id TEXT,
                    outcome TEXT NOT NULL,
                    sentiment TEXT DEFAULT 'neutral',
                    agreed_rate NUMERIC(10,2),
                    negotiation_rounds INTEGER DEFAULT 0,
                    initial_offer NUMERIC(10,2),
                    final_offer NUMERIC(10,2),
                    loadboard_rate NUMERIC(10,2),
                    call_duration_seconds INTEGER,
                    transcript TEXT,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS negotiations (
                    id SERIAL PRIMARY KEY,
                    call_id TEXT NOT NULL,
                    load_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    carrier_offer NUMERIC(10,2) NOT NULL,
                    our_counter NUMERIC(10,2),
                    accepted BOOLEAN NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loads_origin ON loads (LOWER(origin));
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loads_destination ON loads (LOWER(destination));
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON calls (timestamp);
            """)

    @classmethod
    async def seed_loads(cls):
        async with cls.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM loads")
            if count > 0:
                print(f"Loads table already has {count} records, skipping seed")
                return

            dt = datetime

            sample_loads = [
                ("LD-1001", "Chicago, IL", "Dallas, TX", dt(2026,3,24,8,0), dt(2026,3,25,18,0),
                 "Dry Van", 2850.00, "No-touch freight, dock-to-dock", 42000, "Electronics", 24, 920, "48x40x48 pallets"),
                ("LD-1002", "Los Angeles, CA", "Phoenix, AZ", dt(2026,3,24,6,0), dt(2026,3,24,18,0),
                 "Reefer", 1450.00, "Temperature: 34F, must maintain cold chain", 38000, "Produce", 18, 370, "Standard pallets"),
                ("LD-1003", "Atlanta, GA", "Miami, FL", dt(2026,3,25,7,0), dt(2026,3,26,12,0),
                 "Dry Van", 1800.00, "Residential delivery, liftgate required", 28000, "Furniture", 12, 660, "Various"),
                ("LD-1004", "Houston, TX", "Memphis, TN", dt(2026,3,24,10,0), dt(2026,3,25,8,0),
                 "Flatbed", 2200.00, "Oversized: requires tarps and straps", 45000, "Steel Coils", 4, 580, "8ft x 4ft rolls"),
                ("LD-1005", "Newark, NJ", "Boston, MA", dt(2026,3,24,14,0), dt(2026,3,25,6,0),
                 "Dry Van", 950.00, "Priority delivery, appointment required", 32000, "Consumer Goods", 30, 215, "48x40 pallets"),
                ("LD-1006", "Seattle, WA", "Portland, OR", dt(2026,3,25,9,0), dt(2026,3,25,15,0),
                 "Reefer", 750.00, "Frozen: -10F, no stops", 25000, "Seafood", 10, 175, "Standard pallets"),
                ("LD-1007", "Dallas, TX", "Denver, CO", dt(2026,3,26,6,0), dt(2026,3,27,12,0),
                 "Dry Van", 2100.00, "Team drivers preferred", 40000, "Auto Parts", 36, 780, "Mixed pallets"),
                ("LD-1008", "Nashville, TN", "Charlotte, NC", dt(2026,3,25,11,0), dt(2026,3,26,7,0),
                 "Step Deck", 1650.00, "Height clearance: 10ft 6in", 35000, "Machinery", 2, 400, "12ft x 8ft x 10ft"),
                ("LD-1009", "Indianapolis, IN", "Columbus, OH", dt(2026,3,24,15,0), dt(2026,3,24,22,0),
                 "Dry Van", 650.00, "Short haul, same-day delivery", 20000, "Paper Products", 20, 175, "Standard pallets"),
                ("LD-1010", "Kansas City, MO", "St. Louis, MO", dt(2026,3,25,8,0), dt(2026,3,25,14,0),
                 "Box Truck", 450.00, "White glove delivery", 8000, "Medical Supplies", 8, 250, "Small boxes"),
                ("LD-1011", "Chicago, IL", "Atlanta, GA", dt(2026,3,26,7,0), dt(2026,3,27,16,0),
                 "Dry Van", 2400.00, None, 43000, "Beverages", 28, 720, "48x40 pallets"),
                ("LD-1012", "Los Angeles, CA", "Las Vegas, NV", dt(2026,3,24,12,0), dt(2026,3,24,20,0),
                 "Flatbed", 1100.00, "Construction materials, tarps required", 44000, "Lumber", 1, 270, "Bundled 20ft lengths"),
                ("LD-1013", "Miami, FL", "Jacksonville, FL", dt(2026,3,25,6,0), dt(2026,3,25,14,0),
                 "Reefer", 850.00, "Pharma: 36-46F strict range", 15000, "Pharmaceuticals", 6, 345, "Insulated containers"),
                ("LD-1014", "Detroit, MI", "Chicago, IL", dt(2026,3,24,9,0), dt(2026,3,24,17,0),
                 "Dry Van", 700.00, "Auto parts assembly line delivery, time-critical", 30000, "Auto Parts", 16, 280, "Rack-loaded"),
                ("LD-1015", "Philadelphia, PA", "Washington, DC", dt(2026,3,26,10,0), dt(2026,3,26,18,0),
                 "Dry Van", 600.00, "Government contract, ID required at delivery", 22000, "Office Supplies", 14, 140, "Standard pallets"),
            ]

            await conn.executemany("""
                INSERT INTO loads (
                    load_id, origin, destination, pickup_datetime, delivery_datetime,
                    equipment_type, loadboard_rate, notes, weight, commodity_type,
                    num_of_pieces, miles, dimensions
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """, sample_loads)

            print(f"Seeded {len(sample_loads)} loads into database")
