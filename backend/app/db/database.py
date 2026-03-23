"""PostgreSQL connection pool and schema setup."""

import os
import asyncpg
from typing import Optional
from contextlib import asynccontextmanager

# Connection config - pulled from environment for Docker flexibility
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://carrier_user:carrier_pass@localhost:5432/carrier_sales"
)


class Database:
    """
    Async PostgreSQL connection pool.
    We use asyncpg (not SQLAlchemy) for performance -
    voice agents need sub-100ms API responses.
    """
    pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def connect(cls):
        """Create connection pool on app startup."""
        cls.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=5,    # Keep 5 connections warm
            max_size=20,   # Scale up to 20 under load
        )
        await cls._create_tables()
        print("Connected to PostgreSQL")

    @classmethod
    async def disconnect(cls):
        """Clean shutdown."""
        if cls.pool:
            await cls.pool.close()
            print("Disconnected from PostgreSQL")

    @classmethod
    async def _create_tables(cls):
        """
        Create tables if they don't exist.
        In production you'd use Alembic migrations,
        but for a POC this keeps things simple.
        """
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

            # Index for fast load search by origin/destination
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loads_origin
                ON loads (LOWER(origin));
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loads_destination
                ON loads (LOWER(destination));
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_calls_timestamp
                ON calls (timestamp);
            """)

    @classmethod
    async def seed_loads(cls):
        """
        Populate the loads table with realistic sample data.
        These represent loads a freight brokerage would have
        available for carriers to haul.
        """
        async with cls.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM loads")
            if count > 0:
                print(f"Loads table already has {count} records, skipping seed")
                return

            sample_loads = [
                # High-volume lanes (common freight corridors)
                ("LD-1001", "Chicago, IL", "Dallas, TX", "2026-03-24 08:00", "2026-03-25 18:00",
                 "Dry Van", 2850.00, "No-touch freight, dock-to-dock", 42000, "Electronics", 24, 920, "48x40x48 pallets"),
                ("LD-1002", "Los Angeles, CA", "Phoenix, AZ", "2026-03-24 06:00", "2026-03-24 18:00",
                 "Reefer", 1450.00, "Temperature: 34°F, must maintain cold chain", 38000, "Produce", 18, 370, "Standard pallets"),
                ("LD-1003", "Atlanta, GA", "Miami, FL", "2026-03-25 07:00", "2026-03-26 12:00",
                 "Dry Van", 1800.00, "Residential delivery, liftgate required", 28000, "Furniture", 12, 660, "Various"),
                ("LD-1004", "Houston, TX", "Memphis, TN", "2026-03-24 10:00", "2026-03-25 08:00",
                 "Flatbed", 2200.00, "Oversized: requires tarps and straps", 45000, "Steel Coils", 4, 580, "8ft x 4ft rolls"),
                ("LD-1005", "Newark, NJ", "Boston, MA", "2026-03-24 14:00", "2026-03-25 06:00",
                 "Dry Van", 950.00, "Priority delivery, appointment required", 32000, "Consumer Goods", 30, 215, "48x40 pallets"),
                ("LD-1006", "Seattle, WA", "Portland, OR", "2026-03-25 09:00", "2026-03-25 15:00",
                 "Reefer", 750.00, "Frozen: -10°F, no stops", 25000, "Seafood", 10, 175, "Standard pallets"),
                ("LD-1007", "Dallas, TX", "Denver, CO", "2026-03-26 06:00", "2026-03-27 12:00",
                 "Dry Van", 2100.00, "Team drivers preferred", 40000, "Auto Parts", 36, 780, "Mixed pallets"),
                ("LD-1008", "Nashville, TN", "Charlotte, NC", "2026-03-25 11:00", "2026-03-26 07:00",
                 "Step Deck", 1650.00, "Height clearance: 10ft 6in", 35000, "Machinery", 2, 400, "12ft x 8ft x 10ft"),
                ("LD-1009", "Indianapolis, IN", "Columbus, OH", "2026-03-24 15:00", "2026-03-24 22:00",
                 "Dry Van", 650.00, "Short haul, same-day delivery", 20000, "Paper Products", 20, 175, "Standard pallets"),
                ("LD-1010", "Kansas City, MO", "St. Louis, MO", "2026-03-25 08:00", "2026-03-25 14:00",
                 "Box Truck", 450.00, "White glove delivery", 8000, "Medical Supplies", 8, 250, "Small boxes"),
                ("LD-1011", "Chicago, IL", "Atlanta, GA", "2026-03-26 07:00", "2026-03-27 16:00",
                 "Dry Van", 2400.00, None, 43000, "Beverages", 28, 720, "48x40 pallets"),
                ("LD-1012", "Los Angeles, CA", "Las Vegas, NV", "2026-03-24 12:00", "2026-03-24 20:00",
                 "Flatbed", 1100.00, "Construction materials, tarps required", 44000, "Lumber", 1, 270, "Bundled 20ft lengths"),
                ("LD-1013", "Miami, FL", "Jacksonville, FL", "2026-03-25 06:00", "2026-03-25 14:00",
                 "Reefer", 850.00, "Pharma: 36-46°F strict range", 15000, "Pharmaceuticals", 6, 345, "Insulated containers"),
                ("LD-1014", "Detroit, MI", "Chicago, IL", "2026-03-24 09:00", "2026-03-24 17:00",
                 "Dry Van", 700.00, "Auto parts assembly line delivery - time-critical", 30000, "Auto Parts", 16, 280, "Rack-loaded"),
                ("LD-1015", "Philadelphia, PA", "Washington, DC", "2026-03-26 10:00", "2026-03-26 18:00",
                 "Dry Van", 600.00, "Government contract, ID required at delivery", 22000, "Office Supplies", 14, 140, "Standard pallets"),
            ]

            await conn.executemany("""
                INSERT INTO loads (
                    load_id, origin, destination, pickup_datetime, delivery_datetime,
                    equipment_type, loadboard_rate, notes, weight, commodity_type,
                    num_of_pieces, miles, dimensions
                ) VALUES ($1, $2, $3, $4::timestamptz, $5::timestamptz, $6, $7, $8, $9, $10, $11, $12, $13)
            """, sample_loads)

            print(f"Seeded {len(sample_loads)} loads into database")
