"""Negotiation engine for carrier price offers. 3-round max."""

from app.models.schemas import NegotiationRequest, NegotiationResponse
from app.services.load_service import get_load_by_id
from app.db.database import Database

# How much above loadboard rate we're willing to go
ROUND_1_CAP = 1.00    # only accept at or below listed rate
ROUND_2_CAP = 1.05    # willing to go 5% above
ROUND_3_CAP = 1.10    # max 10% above, final offer


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

    await _log_negotiation(request, rate)

    if round_num == 1:
        if offer <= rate * ROUND_1_CAP:
            return _accept(offer, round_num, rate)
        else:
            counter = round(rate)
            return NegotiationResponse(
                accepted=False,
                counter_offer=counter,
                message=(
                    f"I appreciate the offer of ${round(offer):,.0f}, but this load is posted "
                    f"at ${counter:,.0f}. That's ${rate / load.miles:.2f} per mile for "
                    f"{load.miles:.0f} miles. Can you work with ${counter:,.0f}?"
                ),
                round_number=1,
                final_round=False
            )

    elif round_num == 2:
        cap = round(rate * ROUND_2_CAP)
        if offer <= cap:
            return _accept(offer, round_num, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=cap,
                message=(
                    f"I understand. The best I can do is ${cap:,.0f}. "
                    f"That's a bit above our listed rate. Does that work for you?"
                ),
                round_number=2,
                final_round=False
            )

    elif round_num >= 3:
        cap = round(rate * ROUND_3_CAP)
        if offer <= cap:
            return _accept(offer, round_num, rate)
        else:
            return NegotiationResponse(
                accepted=False,
                counter_offer=None,
                message=(
                    f"I'm sorry, ${round(offer):,.0f} is above what we can do for this lane. "
                    f"My absolute max is ${cap:,.0f}. "
                    f"Would you like me to check if we have other loads available?"
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
            f"Great, ${round(offer):,.0f} works for us! Let me transfer you to a "
            f"sales representative to finalize the booking and get your "
            f"rate confirmation sent over."
        ),
        round_number=round_number,
        final_round=True,
        agreed_rate=round(offer)
    )


async def _log_negotiation(request: NegotiationRequest, loadboard_rate: float):
    try:
        async with Database.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO negotiations (call_id, load_id, round_number, carrier_offer, accepted)
                VALUES ($1, $2, $3, $4, $5)
            """, str(request.call_id), str(request.load_id), int(request.round_number),
                float(request.carrier_offer), False)
    except Exception as e:
        print(f"Failed to log negotiation: {e}")
