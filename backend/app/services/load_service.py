"""Load search - matches carrier criteria to available freight."""

from typing import Optional, List
from datetime import datetime
from app.db.database import Database
from app.models.schemas import Load, LoadSearchRequest, LoadSearchResponse


async def search_loads(request: LoadSearchRequest) -> LoadSearchResponse:
    """
    Search available loads matching carrier criteria.
    Fuzzy match on city names since carriers give partial info.
    """
    async with Database.pool.acquire() as conn:
        # Build dynamic query based on what the carrier told us
        conditions = ["is_available = TRUE"]
        params = []
        param_idx = 1

        if request.origin:
            # Fuzzy match: "Chicago" matches "Chicago, IL"
            conditions.append(f"LOWER(origin) LIKE ${param_idx}")
            params.append(f"%{request.origin.lower().strip()}%")
            param_idx += 1

        if request.destination:
            conditions.append(f"LOWER(destination) LIKE ${param_idx}")
            params.append(f"%{request.destination.lower().strip()}%")
            param_idx += 1

        if request.equipment_type:
            conditions.append(f"LOWER(equipment_type) LIKE ${param_idx}")
            params.append(f"%{request.equipment_type.lower().strip()}%")
            param_idx += 1

        if request.pickup_date:
            # Match loads with pickup on or after the requested date
            try:
                date_obj = datetime.fromisoformat(request.pickup_date.replace("Z", "+00:00"))
                conditions.append(f"pickup_datetime::date >= ${param_idx}::date")
                params.append(date_obj)
                param_idx += 1
            except ValueError:
                pass  # Skip bad date rather than failing the search

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT * FROM loads
            WHERE {where_clause}
            ORDER BY loadboard_rate DESC
            LIMIT 5
        """

        rows = await conn.fetch(query, *params)

        loads = [
            Load(
                load_id=row["load_id"],
                origin=row["origin"],
                destination=row["destination"],
                pickup_datetime=row["pickup_datetime"],
                delivery_datetime=row["delivery_datetime"],
                equipment_type=row["equipment_type"],
                loadboard_rate=float(row["loadboard_rate"]),
                notes=row["notes"],
                weight=float(row["weight"]) if row["weight"] else None,
                commodity_type=row["commodity_type"],
                num_of_pieces=row["num_of_pieces"],
                miles=float(row["miles"]) if row["miles"] else None,
                dimensions=row["dimensions"],
            )
            for row in rows
        ]

        return LoadSearchResponse(loads=loads, total_found=len(loads))


async def get_load_by_id(load_id: str) -> Optional[Load]:
    """Fetch a specific load - used during negotiation."""
    async with Database.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM loads WHERE load_id = $1", load_id
        )
        if not row:
            return None

        return Load(
            load_id=row["load_id"],
            origin=row["origin"],
            destination=row["destination"],
            pickup_datetime=row["pickup_datetime"],
            delivery_datetime=row["delivery_datetime"],
            equipment_type=row["equipment_type"],
            loadboard_rate=float(row["loadboard_rate"]),
            notes=row["notes"],
            weight=float(row["weight"]) if row["weight"] else None,
            commodity_type=row["commodity_type"],
            num_of_pieces=row["num_of_pieces"],
            miles=float(row["miles"]) if row["miles"] else None,
            dimensions=row["dimensions"],
        )
