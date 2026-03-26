"""Pydantic schemas for loads, calls, negotiations, alerts, and API payloads."""

from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum


class CallOutcome(str, Enum):
    BOOKED = "booked"
    CARRIER_DECLINED = "carrier_declined"
    NO_MATCH = "no_match"
    VERIFICATION_FAILED = "verification_failed"
    NEGOTIATION_FAILED = "negotiation_failed"
    GENERAL_INQUIRY = "general_inquiry"
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
    carrier_mc: Optional[Union[str, int, float]] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    outcome: Optional[str] = "unknown"
    sentiment: Optional[str] = "neutral"
    agreed_rate: Optional[Union[str, int, float]] = None
    negotiation_rounds: Optional[Union[str, int]] = 0
    initial_offer: Optional[Union[str, int, float]] = None
    final_offer: Optional[Union[str, int, float]] = None
    loadboard_rate: Optional[Union[str, int, float]] = None
    call_duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    notes: Optional[str] = None
    sms_text: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
