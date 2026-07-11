from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class FlightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    flight_id: int
    flight_number: str
    origin: str
    destination: str
    scheduled_dep: datetime
    scheduled_arr: datetime
    status: str


class FlightStatusWebhook(BaseModel):
    """Shape of an inbound flight-status webhook (e.g. from AeroDataBox)."""
    flight_number: str
    status: str  # SCHEDULED | BOARDING | DEPARTED | AIRBORNE | LANDED | DELAYED | CANCELLED
    actual_dep: Optional[datetime] = None
    actual_arr: Optional[datetime] = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    incident_id: int
    flight_id: int
    passenger_id: int
    incident_type: str
    opened_at: datetime
    sla_deadline: datetime
    resolved_at: Optional[datetime] = None
    status: str
    rating: Optional[str] = None


class IncidentCreate(BaseModel):
    flight_id: int
    passenger_id: int
    incident_type: str  # delay | baggage | service | rebooking


class IncidentRate(BaseModel):
    rating: str  # poor | fair | great


class TicketVerifyResult(BaseModel):
    matched: bool
    flight: Optional[FlightOut] = None
    detected_flight_number: Optional[str] = None
    passenger_id: Optional[int] = None
    message: str


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    coupon_id: int
    passenger_id: int
    coupon_type: str
    value: Optional[float] = None
    code: str
    issued_at: datetime
