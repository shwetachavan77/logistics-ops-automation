"""Load search - matches carrier criteria to available freight."""

from typing import Optional, List
from datetime import datetime
from app.db.database import Database
from app.models.schemas import Load, LoadSearchRequest, LoadSearchResponse


async def search_loads(request: LoadSearchRequest, allow_broad: bool = False) -> LoadSearchResponse:
    """
    Search available loads matching carrier criteria.
    Fuzzy match on city names since carriers give partial info.
    """
    async with Database.pool.acquire() as conn:
        # Build dynamic query based on what the carrier told us
        conditions = ["is_available = TRUE"]
        params = []
        param_idx = 1

        # Words that mean "no preference"
        skip_words = {"anywhere", "any", "anywher", "anything", "any location", "any city",
                      "any state", "any where", "all", "everywhere", "whatever", "wherever",
                      "doesn't matter", "doesnt matter", "dont care", "don't care",
                      "no preference", "open", "flexible", "not sure", "idk", "i don't know",
                      "none", "n/a", "na", "null", "undefined", ""}

        def is_vague(val):
            v = val.lower().strip()
            if v in skip_words:
                return True
            if any(w in v for w in ["any", "anywhere", "don't care", "doesnt matter", "no preference", "whatever", "wherever"]):
                return True
            return False

        if request.origin:
            origin_clean = request.origin.lower().strip()
            if not is_vague(origin_clean):
                conditions.append(f"LOWER(origin) LIKE ${param_idx}")
                params.append(f"%{origin_clean}%")
                param_idx += 1

        if request.destination:
            dest_clean = request.destination.lower().strip()
            if not is_vague(dest_clean):
                conditions.append(f"LOWER(destination) LIKE ${param_idx}")
                params.append(f"%{dest_clean}%")
                param_idx += 1

        if request.equipment_type:
            equip_clean = request.equipment_type.lower().strip()
            if not is_vague(equip_clean):
                conditions.append(f"LOWER(equipment_type) LIKE ${param_idx}")
                params.append(f"%{equip_clean}%")
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

        # If no filters beyond is_available, search is too broad (voice agent only)
        if len(conditions) == 1 and not allow_broad:
            return LoadSearchResponse(
                loads=[],
                total_found=0
            )

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
