"""Negotiation engine for carrier price offers. 3-round max."""

from app.models.schemas import NegotiationRequest, NegotiationResponse
from app.services.load_service import get_load_by_id
from app.db.database import Database

# How much above loadboard rate we're willing to go
ROUND_1_CAP = 1.00    # only accept at or below listed rate
ROUND_2_CAP = 1.05    # willing to go 5% above
ROUND_3_CAP = 1.10    # max 10% above, final offer
QUOTE_DISCOUNT = 0.80  # agent quotes 20% below, counters start here


async def evaluate_offer(request: NegotiationRequest) -> NegotiationResponse:
    load = await get_load_by_id(str(request.load_id))
    if not load:
        return NegotiationResponse(
            accepted=False,
            message="I'm sorry, that load is no longer available.",
            round_number=int(request.round_number),
            final_round=True
        )

    rate = load.loadboard_rate
    offer = float(request.carrier_offer)
    round_num = int(request.round_number)

    if round_num == 1:
        if offer <= rate * ROUND_1_CAP:
            await _log_negotiation(request, rate, counter_offer=None, accepted=True)
            return _accept(offer, round_num, rate)
        else:
            counter = round(rate * QUOTE_DISCOUNT, 2)
            await _log_negotiation(request, rate, counter_offer=counter, accepted=False)
            return NegotiationResponse(
                accepted=False,
                counter_offer=counter,
                message=(
                    f"I appreciate the offer of ${offer:,.2f}, but the best I can do "
                    f"right now is ${counter:,.2f}. That's ${counter / load.miles:.2f} per mile for "
                    f"{load.miles:.0f} miles. Can you work with that?"
                ),
                round_number=1,
                final_round=False
            )

    elif round_num == 2:
        cap = rate * ROUND_2_CAP
        if offer <= cap:
            await _log_negotiation(request, rate, counter_offer=None, accepted=True)
            return _accept(offer, round_num, rate)
        else:
            counter = round(rate * 0.95, 2)
            await _log_negotiation(request, rate, counter_offer=counter, accepted=False)
            return NegotiationResponse(
                accepted=False,
                counter_offer=counter,
                message=(
                    f"I hear you. Let me see what I can do. "
                    f"How about ${counter:,.2f}? That's the best I can stretch to."
                ),
                round_number=2,
                final_round=False
            )

    elif round_num >= 3:
        cap = rate * ROUND_3_CAP
        if offer <= cap:
            await _log_negotiation(request, rate, counter_offer=None, accepted=True)
            return _accept(offer, round_num, rate)
        else:
            await _log_negotiation(request, rate, counter_offer=round(rate, 2), accepted=False)
            return NegotiationResponse(
                accepted=False,
                counter_offer=round(rate, 2),
                message=(
                    f"I really can't go higher than ${rate:,.2f} on this one. "
                    f"That's my absolute best. Want to go with that, or should I check other loads?"
                ),
                round_number=3,
                final_round=True
            )

    return NegotiationResponse(
        accepted=False,
        message="Let me transfer you to a sales representative for further discussion.",
        round_number=round_num,
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


async def _log_negotiation(request: NegotiationRequest, loadboard_rate: float, counter_offer: float = None, accepted: bool = False):
    try:
        async with Database.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO negotiations (call_id, load_id, round_number, carrier_offer, our_counter, accepted)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, str(request.call_id), str(request.load_id), int(request.round_number),
                float(request.carrier_offer), counter_offer, accepted)
    except Exception as e:
        print(f"Failed to log negotiation: {e}")
