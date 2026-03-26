Negotiation Strategy: Inbound Carrier Sales

Assumptions

We are a freight brokerage. We connect shippers (who have freight) with carriers (who have trucks).

The loadboard_rate is the maximum we are willing to pay a carrier for a given load. This number comes from our internal load board and reflects market conditions, shipper contracts, and our margin requirements.

Carriers call us looking for loads. They want to be paid as much as possible for hauling freight. Their goal is to negotiate the rate UP.

Our goal is to pay as little as possible while still booking the load. We want to close deals at or below the loadboard_rate.

The carrier does not know our loadboard_rate. They only see the rate we quote them on the call. This information asymmetry is standard in freight brokerage and gives us room to negotiate.

Carriers are independent business owners. They evaluate loads based on rate per mile, deadhead distance, equipment requirements, and schedule fit. A carrier who feels they negotiated a fair rate is more likely to accept the load and become a repeat partner.

Strategy

1. Quote 20% below the loadboard rate

When the agent pitches a load to a carrier, the quoted rate is the loadboard_rate multiplied by 0.80 (20% discount). This is the opening offer.

Example: loadboard_rate is $2,200, agent quotes $1,760.

This creates a negotiation window between the quoted rate ($1,760) and our actual max ($2,200). The carrier has $440 of room to negotiate up without exceeding our budget.

2. Let the carrier negotiate up

Carriers almost always counter. They will ask for a higher rate. This is expected and desired. The agent uses the evaluate_offer tool to handle each counter, up to 3 rounds.

Round 1: Carrier counters. Agent responds based on evaluate_offer guidance.
Round 2: If carrier counters again, agent calls evaluate_offer with round 2.
Round 3: Final round. Agent follows the tool's accept or reject decision.

The evaluate_offer tool has its own caps:
- Round 1 cap: 100% of loadboard_rate (accept at or below listed rate)
- Round 2 cap: 105% of loadboard_rate (willing to go 5% above)
- Round 3 cap: 110% of loadboard_rate (absolute max, 10% above)

3. The carrier feels like they won

From the carrier's perspective, they called in, heard a rate of $1,760, negotiated up to $2,100, and feel they got a good deal. In reality, $2,100 is below our loadboard_rate of $2,200, so we also win.

This is a win-win outcome. The carrier got more than the initial quote. We paid less than our max budget.

4. Accept immediately when the carrier asks for less than loadboard rate

If a carrier's counter offer is at or below the loadboard_rate, the agent accepts without further negotiation. There is no reason to push back when the carrier is already within our budget.

5. Never reveal the strategy

The agent never mentions loadboard rates, budgets, margins, markups, discounts, caps, or negotiation rounds to the carrier. The quoted rate is presented as "the rate" with no qualifier. Internal pricing mechanics are never discussed.

Outcome Classification

After each call, the outcome is classified:
- booked: carrier agreed to a rate AND was transferred to a sales rep
- carrier_declined: carrier was verified but walked away from the rate or the load
- no_match: no loads matched the carrier's lane or equipment
- verification_failed: carrier's MC number failed FMCSA verification
- negotiation_failed: all 3 rounds exhausted without agreement
- general_inquiry: carrier called with questions but did not go through the booking flow

Revenue Impact

The 20% discount strategy means our average deal should close somewhere between the quoted rate (80% of loadboard) and the loadboard rate (100%). If carriers negotiate to roughly the midpoint, we save about 10% on average compared to quoting the full loadboard rate and having no room to negotiate.

Over time, this data is visible on the dashboard. The "Rate Preservation" metric shows what percentage of the loadboard rate we actually paid out. Higher is better for carriers, lower is better for our margins. The target range is 85-95%.
