"""Pydantic schemas for loads, calls, negotiations, alerts, and API payloads."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum


class CallOutcome(str, Enum):
    BOOKED = "booked"
    CARRIER_DECLINED = "carrier_declined"
    NO_MATCH = "no_match"
    VERIFICATION_FAILED = "verification_failed"
    NEGOTIATION_FAILED = "negotiation_failed"
    UNKNOWN = "unknown"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    AGGRESSIVE = "aggressive"


class EquipmentType(str, Enum):
    DRY_VAN = "Dry Van"
    REEFER = "Reefer"
    FLATBED = "Flatbed"
    STEP_DECK = "Step Deck"
    POWER_ONLY = "Power Only"
    BOX_TRUCK = "Box Truck"


class Load(BaseModel):
    load_id: str = Field(..., description="Unique identifier for the load")
    origin: str = Field(..., description="Starting location (city, state)")
    destination: str = Field(..., description="Delivery location (city, state)")
    pickup_datetime: datetime
    delivery_datetime: datetime
    equipment_type: str
    loadboard_rate: float
    notes: Optional[str] = None
    weight: Optional[float] = None
    commodity_type: Optional[str] = None
    num_of_pieces: Optional[int] = None
    miles: Optional[float] = None
    dimensions: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "load_id": "LD-1001",
                "origin": "Chicago, IL",
                "destination": "Dallas, TX",
                "pickup_datetime": "2026-03-24T08:00:00",
                "delivery_datetime": "2026-03-25T18:00:00",
                "equipment_type": "Dry Van",
                "loadboard_rate": 2850.00,
                "weight": 42000,
                "commodity_type": "Electronics",
                "num_of_pieces": 24,
                "miles": 920,
                "dimensions": "48x40x48 pallets"
            }
        }


# FMCSA verification

class CarrierVerificationRequest(BaseModel):
    mc_number: Union[str, int, float] = Field(..., description="Motor Carrier number to verify")


class CarrierVerificationResponse(BaseModel):
    mc_number: str
    is_eligible: bool
    carrier_name: Optional[str] = None
    dot_number: Optional[str] = None
    status: Optional[str] = None
    safety_rating: Optional[str] = None
    insurance_on_file: Optional[bool] = None
    reason: Optional[str] = None


# Load search

class LoadSearchRequest(BaseModel):
    origin: Optional[str] = None
    destination: Optional[str] = None
    equipment_type: Optional[str] = None
    pickup_date: Optional[str] = None


class LoadSearchResponse(BaseModel):
    loads: List[Load]
    total_found: int


# Negotiation

class NegotiationRequest(BaseModel):
    call_id: Union[str, int] = Field(..., description="Unique call identifier")
    load_id: Union[str, int] = Field(..., description="Which load being negotiated")
    carrier_offer: Union[str, int, float] = Field(..., description="Carrier's asking price in USD")
    round_number: Union[str, int] = Field(..., description="Negotiation round (1-3)")


class NegotiationResponse(BaseModel):
    accepted: bool
    counter_offer: Optional[float] = None
    message: str
    round_number: int
    final_round: bool = False
    agreed_rate: Optional[float] = None


# Call logging

class CallLog(BaseModel):
    call_id: str
    carrier_mc: Optional[str] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    outcome: str = "unknown"
    sentiment: str = "neutral"
    agreed_rate: Optional[float] = None
    negotiation_rounds: int = 0
    initial_offer: Optional[float] = None
    final_offer: Optional[float] = None
    loadboard_rate: Optional[float] = None
    call_duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="before")
    @classmethod
    def clean_inputs(cls, data):
        if isinstance(data, dict):
            # Convert carrier_mc to string
            if "carrier_mc" in data and data["carrier_mc"] is not None:
                data["carrier_mc"] = str(data["carrier_mc"])
            # Default outcome if missing
            if "outcome" not in data or not data.get("outcome"):
                data["outcome"] = "unknown"
            # Clean empty strings to None for numeric fields
            for f in ["agreed_rate", "initial_offer", "final_offer", "loadboard_rate"]:
                v = data.get(f)
                if v is not None and isinstance(v, str):
                    v = v.strip().replace("$", "").replace(",", "")
                    if v.lower() in ("", "null", "none"):
                        data[f] = None
                    else:
                        try:
                            data[f] = float(v)
                        except ValueError:
                            data[f] = None
            # Clean negotiation_rounds
            nr = data.get("negotiation_rounds")
            if nr is not None:
                if isinstance(nr, str):
                    try:
                        data["negotiation_rounds"] = int(float(nr))
                    except (ValueError, TypeError):
                        data["negotiation_rounds"] = 0
                elif isinstance(nr, float):
                    data["negotiation_rounds"] = int(nr)
        return data


class CallLogResponse(BaseModel):
    call_id: str
    status: str = "logged"


# Missed opportunity alert

class MissedOpportunityAlert(BaseModel):
    call_id: str
    carrier_mc: Optional[str] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    final_offer: Optional[Union[str, int, float]] = None
    loadboard_rate: Optional[Union[str, int, float]] = None
    gap: Optional[float] = None
    message: Optional[str] = None


# Rate confirmation

class RateConfirmation(BaseModel):
    call_id: str
    carrier_mc: Optional[str] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    agreed_rate: Optional[Union[str, int, float]] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    pickup_datetime: Optional[str] = None
    equipment_type: Optional[str] = None


class RateConfirmationResponse(BaseModel):
    status: str = "confirmation_sent"
    confirmation_id: str
    message: str


# Carrier history / scoring

class CarrierHistoryResponse(BaseModel):
    carrier_mc: str
    total_calls: int
    total_bookings: int
    booking_rate: float
    avg_negotiation_rounds: float
    avg_agreed_rate: Optional[float] = None
    last_call_date: Optional[str] = None
    reliability_score: Optional[float] = None
    lanes: List[dict] = []


# Dashboard metrics

class DashboardMetrics(BaseModel):
    total_calls: int
    calls_by_outcome: dict
    calls_by_sentiment: dict
    booking_rate: float
    avg_negotiation_rounds: float
    avg_discount_from_loadboard: float
    revenue_booked: float
    calls_over_time: List[dict]
    top_lanes: List[dict]
    # Negotiation intelligence
    round1_close_rate: float = 0
    floor_rate_hit_rate: float = 0
    avg_rate_given_up: float = 0
    avg_call_duration: float = 0
