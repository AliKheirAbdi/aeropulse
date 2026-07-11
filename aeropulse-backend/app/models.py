from sqlalchemy import (
    Column, Integer, BigInteger, String, Numeric, ForeignKey, TIMESTAMP, text
)
from sqlalchemy.orm import relationship
from .database import Base


class AircraftProfile(Base):
    __tablename__ = "aircraft_profiles"
    aircraft_id = Column(Integer, primary_key=True)
    tail_number = Column(String(10), unique=True, nullable=False)
    model = Column(String(50), nullable=False)
    capacity = Column(Integer, nullable=False)
    age_years = Column(Numeric(4, 1))
    fuel_burn_rate_per_hr = Column(Numeric(10, 2))

    flights = relationship("FlightRegistry", back_populates="aircraft")


class FlightRegistry(Base):
    __tablename__ = "flight_registry"
    flight_id = Column(Integer, primary_key=True)
    flight_number = Column(String(10), nullable=False)
    aircraft_id = Column(Integer, ForeignKey("aircraft_profiles.aircraft_id"))
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    scheduled_dep = Column(TIMESTAMP(timezone=True), nullable=False)
    scheduled_arr = Column(TIMESTAMP(timezone=True), nullable=False)
    actual_dep = Column(TIMESTAMP(timezone=True))
    actual_arr = Column(TIMESTAMP(timezone=True))
    status = Column(String(20), nullable=False, server_default="SCHEDULED")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    aircraft = relationship("AircraftProfile", back_populates="flights")
    links = relationship("PassengerFlightLink", back_populates="flight")


class Passenger(Base):
    __tablename__ = "passengers"
    passenger_id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(160), unique=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class PassengerFlightLink(Base):
    __tablename__ = "passenger_flight_link"
    link_id = Column(Integer, primary_key=True)
    flight_id = Column(Integer, ForeignKey("flight_registry.flight_id"), nullable=False)
    passenger_id = Column(Integer, ForeignKey("passengers.passenger_id"), nullable=False)
    pnr = Column(String(10))
    seat = Column(String(5))
    verified_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))

    flight = relationship("FlightRegistry", back_populates="links")


class OperationalKPI(Base):
    __tablename__ = "operational_kpis"
    kpi_id = Column(BigInteger, primary_key=True)
    flight_id = Column(Integer, ForeignKey("flight_registry.flight_id"))
    on_time_variance_min = Column(Integer)
    turnaround_min = Column(Integer)
    load_factor = Column(Numeric(5, 2))
    recorded_at = Column(TIMESTAMP(timezone=True), primary_key=True, server_default=text("now()"))


class FlightProfitability(Base):
    __tablename__ = "flight_profitability"
    flight_id = Column(Integer, ForeignKey("flight_registry.flight_id"), primary_key=True)
    fuel_cost = Column(Numeric(12, 2), default=0)
    crew_cost = Column(Numeric(12, 2), default=0)
    maintenance_allocation = Column(Numeric(12, 2), default=0)
    catering_cost = Column(Numeric(12, 2), default=0)
    ancillary_revenue = Column(Numeric(12, 2), default=0)
    ticket_revenue = Column(Numeric(12, 2), default=0)
    # net_margin is DB-generated (STORED), not writable from the ORM


class PassengerFeedback(Base):
    __tablename__ = "passenger_feedback"
    feedback_id = Column(Integer, primary_key=True)
    passenger_id = Column(Integer, ForeignKey("passengers.passenger_id"))
    flight_id = Column(Integer, ForeignKey("flight_registry.flight_id"))
    nps_score = Column(Integer)
    comment = Column(String)
    submitted_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))


class ResolutionSLATracking(Base):
    __tablename__ = "resolution_sla_tracking"
    incident_id = Column(Integer, primary_key=True)
    flight_id = Column(Integer, ForeignKey("flight_registry.flight_id"))
    passenger_id = Column(Integer, ForeignKey("passengers.passenger_id"))
    incident_type = Column(String(30), nullable=False)
    opened_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    sla_deadline = Column(TIMESTAMP(timezone=True), nullable=False)
    resolved_at = Column(TIMESTAMP(timezone=True))
    status = Column(String(20), nullable=False, server_default="OPEN")
    rating = Column(String(10))


class AutomatedCouponLog(Base):
    __tablename__ = "automated_coupon_logs"
    coupon_id = Column(Integer, primary_key=True)
    passenger_id = Column(Integer, ForeignKey("passengers.passenger_id"))
    incident_id = Column(Integer, ForeignKey("resolution_sla_tracking.incident_id"))
    coupon_type = Column(String(30), nullable=False)
    value = Column(Numeric(10, 2))
    code = Column(String(30), unique=True)
    issued_at = Column(TIMESTAMP(timezone=True), server_default=text("now()"))
    redeemed_at = Column(TIMESTAMP(timezone=True))
