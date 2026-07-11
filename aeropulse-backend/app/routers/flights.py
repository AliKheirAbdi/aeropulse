from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=list[schemas.FlightOut])
def list_flights(db: Session = Depends(get_db)):
    return db.query(models.FlightRegistry).order_by(models.FlightRegistry.scheduled_dep).all()


@router.get("/{flight_id}", response_model=schemas.FlightOut)
def get_flight(flight_id: int, db: Session = Depends(get_db)):
    flight = db.get(models.FlightRegistry, flight_id)
    if not flight:
        raise HTTPException(404, "Flight not found")
    return flight


@router.get("/{flight_id}/passenger-count")
def passenger_count(flight_id: int, db: Session = Depends(get_db)):
    count = (
        db.query(func.count(models.PassengerFlightLink.link_id))
        .filter(models.PassengerFlightLink.flight_id == flight_id)
        .scalar()
    )
    return {"flight_id": flight_id, "passenger_count": count}


@router.get("/kpis/summary")
def kpi_summary(db: Session = Depends(get_db)):
    """Powers the admin dashboard's top KPI row (on-time %, open incidents, etc.)."""
    total = db.query(func.count(models.FlightRegistry.flight_id)).scalar() or 0
    delayed = (
        db.query(func.count(models.FlightRegistry.flight_id))
        .filter(models.FlightRegistry.status == "DELAYED")
        .scalar()
        or 0
    )
    on_time_pct = round(((total - delayed) / total) * 100, 1) if total else 100.0
    open_incidents = (
        db.query(func.count(models.ResolutionSLATracking.incident_id))
        .filter(models.ResolutionSLATracking.status == "OPEN")
        .scalar()
        or 0
    )
    verified_passengers = db.query(func.count(models.PassengerFlightLink.link_id)).scalar() or 0
    return {
        "on_time_pct": on_time_pct,
        "open_incidents": open_incidents,
        "verified_passengers": verified_passengers,
        "total_flights": total,
    }
