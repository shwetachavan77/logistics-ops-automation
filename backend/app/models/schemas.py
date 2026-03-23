"""Pydantic schemas for loads, calls, negotiations, and API payloads."""

from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum


# Enums for classification

class CallOutcome(str, Enum):
    """Call outcome tags for the classify node."""
    BOOKED = "booked"
    CARRIER_DECLINED = "carrier_declined"
    NO_MATCH = "no_match"
    VERIFICATION_FAILED = "verification_failed"
    NEGOTIATION_FAILED = "negotiation_failed"


class Sentiment(str, Enum):
    """Carrier sentiment from real-time analysis."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    AGGRESSIVE = "aggressive"


class EquipmentType(str, Enum):
    """Common trailer types."""
    DRY_VAN = "Dry Van"
    REEFER = "Reefer"
    FLATBED = "Flatbed"
    STEP_DECK = "Step Deck"
    POWER_ONLY = "Power Only"
    BOX_TRUCK = "Box Truck"


# Load model

class Load(BaseModel):
    """A freight load available for booking."""
    load_id: str = Field(..., description="Unique identifier for the load")
    origin: str = Field(..., description="Starting location (city, state)")
    destination: str = Field(..., description="Delivery location (city, state)")
    pickup_datetime: datetime = Field(..., description="When the load needs to be picked up")
    delivery_datetime: datetime = Field(..., description="When the load needs to be delivered")
    equipment_type: str = Field(..., description="Type of trailer needed")
    loadboard_rate: float = Field(..., description="Listed rate in USD")
    notes: Optional[str] = Field(None, description="Special instructions or notes")
    weight: Optional[float] = Field(None, description="Weight in pounds")
    commodity_type: Optional[str] = Field(None, description="Type of goods being shipped")
    num_of_pieces: Optional[int] = Field(None, description="Number of items/pallets")
    miles: Optional[float] = Field(None, description="Total distance in miles")
    dimensions: Optional[str] = Field(None, description="Size measurements if applicable")

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


# FMCSA Carrier verification

class CarrierVerificationRequest(BaseModel):
    """Request to verify a carrier's MC number."""
    mc_number: Union[str, int, float] = Field(..., description="Motor Carrier number to verify")


class CarrierVerificationResponse(BaseModel):
    """FMCSA verification result."""
    mc_number: str
    is_eligible: bool = Field(..., description="Whether carrier can haul for us")
    carrier_name: Optional[str] = None
    dot_number: Optional[str] = None
    status: Optional[str] = None
    safety_rating: Optional[str] = None
    insurance_on_file: Optional[bool] = None
    reason: Optional[str] = None


# Load search

class LoadSearchRequest(BaseModel):
    """What the carrier is looking for."""
    origin: Optional[str] = Field(None, description="Where they want to pick up")
    destination: Optional[str] = Field(None, description="Where they want to deliver")
    equipment_type: Optional[str] = Field(None, description="What trailer they have")
    pickup_date: Optional[str] = Field(None, description="When they're available")


class LoadSearchResponse(BaseModel):
    """Search results."""
    loads: List[Load]
    total_found: int


# Negotiation

class NegotiationRequest(BaseModel):
    """Carrier's price offer for a load."""
    call_id: str = Field(..., description="Unique call identifier")
    load_id: str = Field(..., description="Which load they're negotiating on")
    carrier_offer: float = Field(..., description="What the carrier is asking for in USD")
    round_number: int = Field(..., description="Which negotiation round (1-3)")


class NegotiationResponse(BaseModel):
    """Our response to the carrier's offer."""
    accepted: bool
    counter_offer: Optional[float] = None
    message: str
    round_number: int
    final_round: bool = False
    agreed_rate: Optional[float] = None


# Call logging

class CallLog(BaseModel):
    """Logged after every call via webhook."""
    call_id: str
    carrier_mc: Optional[str] = None
    carrier_name: Optional[str] = None
    load_id: Optional[str] = None
    outcome: CallOutcome
    sentiment: Sentiment = Sentiment.NEUTRAL
    agreed_rate: Optional[float] = None
    negotiation_rounds: int = 0
    initial_offer: Optional[float] = None
    final_offer: Optional[float] = None
    loadboard_rate: Optional[float] = None
    call_duration_seconds: Optional[int] = None
    transcript: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CallLogResponse(BaseModel):
    """Response after logging a call."""
    call_id: str
    status: str = "logged"


# Dashboard metrics

class DashboardMetrics(BaseModel):
    """Aggregated metrics for the dashboard."""
    total_calls: int
    calls_by_outcome: dict
    calls_by_sentiment: dict
    booking_rate: float
    avg_negotiation_rounds: float
    avg_discount_from_loadboard: float
    revenue_booked: float
    calls_over_time: List[dict]
    top_lanes: List[dict]
