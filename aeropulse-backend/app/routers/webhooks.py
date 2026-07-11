from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..redis_bus import publish

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/flight-status")
async def flight_status_webhook(payload: schemas.FlightStatusWebhook, db: Session = Depends(get_db)):
    """
    Entry point for a flight-status push from a provider like AeroDataBox.

    Point the provider's webhook (or a polling adapter, if the provider is
    poll-only) at this endpoint. Updating `status` to DELAYED here is what
    fires the DB trigger in 002_schema.sql, which fans out one
    resolution_sla_tracking row per verified passenger automatically —
    nothing else in the app needs to know about that fan-out.
    """
    flight = (
        db.query(models.FlightRegistry)
        .filter(models.FlightRegistry.flight_number == payload.flight_number)
        .order_by(models.FlightRegistry.scheduled_dep.desc())
        .first()
    )
    if not flight:
        raise HTTPException(404, f"No flight found for {payload.flight_number}")

    flight.status = payload.status.upper()
    if payload.actual_dep:
        flight.actual_dep = payload.actual_dep
    if payload.actual_arr:
        flight.actual_arr = payload.actual_arr
    db.commit()
    db.refresh(flight)

    await publish("flight.telemetry", {
        "flight_id": flight.flight_id,
        "flight_number": flight.flight_number,
        "status": flight.status,
    })

    return {"ok": True, "flight_id": flight.flight_id, "status": flight.status}
