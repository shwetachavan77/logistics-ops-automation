"""FMCSA carrier verification via SAFER system. Real API only — no mocks."""

import os
import httpx
from app.models.schemas import CarrierVerificationResponse


FMCSA_API_BASE = "https://mobile.fmcsa.dot.gov/qc/services"
FMCSA_API_KEY = os.getenv(
    "FMCSA_API_KEY",
    "cdc33e44d693a3a58451898d4ec9df862c65b954"
)


async def verify_carrier(mc_number: str) -> CarrierVerificationResponse:
    """
    Verify a carrier's authority via FMCSA SAFER system.
    Real API only — returns an ineligible response on any API failure
    rather than falling back to mock data.
    """
    clean_mc = mc_number.strip().upper().replace("MC", "").replace("-", "").replace(" ", "")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{FMCSA_API_BASE}/carriers/docket-number/{clean_mc}",
                params={"webKey": FMCSA_API_KEY},
                headers={"Accept": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                return _parse_fmcsa_response(clean_mc, data)

            if response.status_code == 404:
                return CarrierVerificationResponse(
                    mc_number=clean_mc,
                    is_eligible=False,
                    reason="MC number not found in FMCSA database"
                )

            # Any other status code — treat as lookup failure
            return CarrierVerificationResponse(
                mc_number=clean_mc,
                is_eligible=False,
                reason=f"FMCSA lookup returned status {response.status_code}. Please try again."
            )

    except httpx.TimeoutException:
        return CarrierVerificationResponse(
            mc_number=clean_mc,
            is_eligible=False,
            reason="FMCSA verification timed out. Please try again in a moment."
        )
    except Exception as e:
        print(f"FMCSA API error: {e}")
        return CarrierVerificationResponse(
            mc_number=clean_mc,
            is_eligible=False,
            reason="Unable to reach FMCSA for verification. Please try again."
        )


def _parse_fmcsa_response(mc_number: str, data: dict) -> CarrierVerificationResponse:
    """Parse the FMCSA API response into our schema."""
    try:
        content = data.get("content", [{}])
        carrier = content[0].get("carrier", {}) if content else {}

        if not carrier:
            return CarrierVerificationResponse(
                mc_number=mc_number,
                is_eligible=False,
                reason="No carrier data returned from FMCSA"
            )

        carrier_name = carrier.get("legalName", "Unknown")
        dot_number = str(carrier.get("dotNumber", ""))
        status = carrier.get("allowedToOperate", "N")
        safety_rating = carrier.get("safetyRating", "None")

        is_authorized = str(status).upper() in ("Y", "YES", "AUTHORIZED")

        return CarrierVerificationResponse(
            mc_number=mc_number,
            is_eligible=is_authorized,
            carrier_name=carrier_name,
            dot_number=dot_number,
            status="AUTHORIZED" if is_authorized else "NOT AUTHORIZED",
            safety_rating=safety_rating if safety_rating and safety_rating != "None" else None,
            insurance_on_file=is_authorized,
            reason=None if is_authorized else "Carrier is not authorized to operate"
        )
    except (KeyError, IndexError) as e:
        print(f"FMCSA parse error: {e}")
        return CarrierVerificationResponse(
            mc_number=mc_number,
            is_eligible=False,
            reason="Could not parse FMCSA response. Please try again."
        )
