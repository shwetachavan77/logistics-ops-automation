"""Negotiation engine for carrier price offers. 3-round max strategy."""

from app.models.schemas import NegotiationRequest, NegotiationResponse
from app.services.load_service import get_load_by_id
from app.db.database import Database


# Pricing thresholds (configurable per deployment)
ROUND_1_TARGET = 1.00    # 100% - try to get full rate
ROUND_2_TARGET = 0.95    # 95%  - willing to give up 5%
ROUND_3_FLOOR = 0.85     # 85%  - absolute minimum


async def evaluate_offer(request: NegotiationRequest) -> NegotiationResponse:
    """
    Evaluate a carrier's price offer and decide what to do.

    This gets called by HappyRobot's tool integration each time
    the carrier makes or updates their price offer.
    """
    # Get the load to know our pricing
    load = await get_load_by_id(request.load_id)
    if not load:
        return NegotiationResponse(
            accepted=False,
            message="I'm sorry, that load is no longer available.",
            round_number=request.round_number,
            final_round=True
        )

    rate = load.loadboard_rate
    offer = request.carrier_offer

    # Log this negotiation round
    await _log_negotiation(request, load.loadboard_rate)

    # Round 1
    if request.round_number == 1:
        if offer >= rate * ROUND_1_TARGET:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=rate,
                message=(
                    f"I appreciate the offer of ${offer:,.2f}, but this load is posted "
                    f"at ${rate:,.2f}. That's ${rate / load.miles:.2f} per mile for "
                    f"{load.miles:.0f} miles. Can you come up to ${rate:,.2f}?"
                ),
                round_number=1,
                final_round=False
            )

    # Round 2
    elif request.round_number == 2:
        target = rate * ROUND_2_TARGET
        if offer >= target:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=round(target, 2),
                message=(
                    f"I understand. The best I can do is ${target:,.2f} - "
                    f"that's already a discount from our listed rate. "
                    f"Does that work for you?"
                ),
                round_number=2,
                final_round=False
            )

    # Round 3
    elif request.round_number >= 3:
        floor = rate * ROUND_3_FLOOR
        if offer >= floor:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=None,
                message=(
                    f"I'm sorry, ${offer:,.2f} is below our minimum for this lane. "
                    f"I can't go below ${floor:,.2f}. "
                    f"Would you like me to check if we have other loads available?"
                ),
                round_number=3,
                final_round=True
            )

    # Fallback (shouldn't reach here)
    return NegotiationResponse(
        accepted=False,
        message="Let me transfer you to a sales representative for further discussion.",
        round_number=request.round_number,
        final_round=True
    )


def _accept(offer: float, round_number: int, loadboard_rate: float) -> NegotiationResponse:
    """Build an acceptance response."""
    return NegotiationResponse(
        accepted=True,
        message=(
            f"Great, ${offer:,.2f} works for us! Let me transfer you to a "
            f"sales representative to finalize the booking and get your "
            f"rate confirmation and load details sent over."
        ),
        round_number=round_number,
        final_round=True,
        agreed_rate=offer
    )


async def _log_negotiation(request: NegotiationRequest, loadboard_rate: float):
    """Record each negotiation round for analytics."""
    try:
        async with Database.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO negotiations (call_id, load_id, round_number, carrier_offer, accepted)
                VALUES ($1, $2, $3, $4, $5)
            """, request.call_id, request.load_id, request.round_number,
                request.carrier_offer, False)  # Updated to True on acceptance via call log
    except Exception as e:
        print(f"Failed to log negotiation: {e}")
