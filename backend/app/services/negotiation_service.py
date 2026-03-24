"""Negotiation engine for carrier price offers. 3-round max strategy."""

from app.models.schemas import NegotiationRequest, NegotiationResponse
from app.services.load_service import get_load_by_id
from app.db.database import Database


# How much above loadboard rate we're willing to go
ROUND_1_CAP = 1.00    # Round 1: only accept at or below listed rate
ROUND_2_CAP = 1.05    # Round 2: willing to go 5% above
ROUND_3_CAP = 1.10    # Round 3: max 10% above, final offer


async def evaluate_offer(request: NegotiationRequest) -> NegotiationResponse:
    load = await get_load_by_id(request.load_id)
    if not load:
        return NegotiationResponse(
            accepted=False,
            message="I'm sorry, that load is no longer available.",
            round_number=request.round_number,
            final_round=True
        )

    rate = load.loadboard_rate
    offer = float(request.carrier_offer)

    await _log_negotiation(request, rate)

    # Round 1: Accept at or below listed rate
    if request.round_number == 1:
        if offer <= rate * ROUND_1_CAP:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=rate,
                message=(
                    f"I appreciate the offer of ${offer:,.2f}, but this load is posted "
                    f"at ${rate:,.2f}. That's ${rate / load.miles:.2f} per mile for "
                    f"{load.miles:.0f} miles. Can you work with ${rate:,.2f}?"
                ),
                round_number=1,
                final_round=False
            )

    # Round 2: Willing to flex 5% above
    elif request.round_number == 2:
        cap = rate * ROUND_2_CAP
        if offer <= cap:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=round(cap, 2),
                message=(
                    f"I understand. The best I can do is ${cap:,.2f}. "
                    f"That's a bit above our listed rate. Does that work for you?"
                ),
                round_number=2,
                final_round=False
            )

    # Round 3: Max 10% above, final
    elif request.round_number >= 3:
        cap = rate * ROUND_3_CAP
        if offer <= cap:
            return _accept(offer, request.round_number, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=None,
                message=(
                    f"I'm sorry, ${offer:,.2f} is above what we can do for this lane. "
                    f"My absolute max is ${cap:,.2f}. "
                    f"Would you like me to check if we have other loads available?"
                ),
                round_number=3,
                final_round=True
            )

    return NegotiationResponse(
        accepted=False,
        message="Let me transfer you to a sales representative for further discussion.",
        round_number=request.round_number,
        final_round=True
    )


def _accept(offer: float, round_number: int, loadboard_rate: float) -> NegotiationResponse:
    return NegotiationResponse(
        accepted=True,
        message=(
            f"Great, ${offer:,.2f} works for us! Let me transfer you to a "
            f"sales representative to finalize the booking and get your "
            f"rate confirmation sent over."
        ),
        round_number=round_number,
        final_round=True,
        agreed_rate=offer
    )


async def _log_negotiation(request: NegotiationRequest, loadboard_rate: float):
    try:
        async with Database.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO negotiations (call_id, load_id, round_number, carrier_offer, accepted)
                VALUES ($1, $2, $3, $4, $5)
            """, request.call_id, request.load_id, int(request.round_number),
                float(request.carrier_offer), False)
    except Exception as e:
        print(f"Failed to log negotiation: {e}")
