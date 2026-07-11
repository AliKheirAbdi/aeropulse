from datetime import datetime, timezone
import random
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..services.sla import compute_deadline
from ..redis_bus import publish

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _gen_coupon_code() -> str:
    return "AP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


@router.get("", response_model=list[schemas.IncidentOut])
def list_incidents(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(models.ResolutionSLATracking)
    if status:
        q = q.filter(models.ResolutionSLATracking.status == status.upper())
    return q.order_by(models.ResolutionSLATracking.opened_at.desc()).all()


@router.post("", response_model=schemas.IncidentOut)
async def raise_incident(payload: schemas.IncidentCreate, db: Session = Depends(get_db)):
    flight = db.get(models.FlightRegistry, payload.flight_id)
    if not flight:
        raise HTTPException(404, "Flight not found")

    opened_at = datetime.now(timezone.utc)
    incident = models.ResolutionSLATracking(
        flight_id=payload.flight_id,
        passenger_id=payload.passenger_id,
        incident_type=payload.incident_type,
        opened_at=opened_at,
        sla_deadline=compute_deadline(payload.incident_type, opened_at),
        status="OPEN",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)

    await publish("incident.raised", {
        "incident_id": incident.incident_id,
        "flight_id": incident.flight_id,
        "passenger_id": incident.passenger_id,
        "incident_type": incident.incident_type,
        "sla_deadline": incident.sla_deadline.isoformat(),
    })
    return incident


@router.post("/{incident_id}/resolve", response_model=schemas.IncidentOut)
async def resolve_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.get(models.ResolutionSLATracking, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    incident.status = "RESOLVED"
    incident.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(incident)

    await publish("incident.resolved", {"incident_id": incident.incident_id, "flight_id": incident.flight_id})
    return incident


@router.post("/{incident_id}/rate", response_model=schemas.IncidentOut)
async def rate_incident(incident_id: int, payload: schemas.IncidentRate, db: Session = Depends(get_db)):
    incident = db.get(models.ResolutionSLATracking, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    incident.rating = payload.rating
    incident.status = "CLOSED"
    db.commit()
    db.refresh(incident)
    return incident


async def sweep_breached_incidents(db: Session):
    """Run periodically (see main.py startup task): auto-marks any OPEN
    incident past its SLA deadline as BREACHED and auto-issues a
    recovery coupon — the automated compensation rule from the schema."""
    now = datetime.now(timezone.utc)
    breached = (
        db.query(models.ResolutionSLATracking)
        .filter(models.ResolutionSLATracking.status == "OPEN")
        .filter(models.ResolutionSLATracking.sla_deadline < now)
        .all()
    )
    for incident in breached:
        incident.status = "BREACHED"
        coupon = models.AutomatedCouponLog(
            passenger_id=incident.passenger_id,
            incident_id=incident.incident_id,
            coupon_type="auto_recovery_voucher",
            value=75.00,
            code=_gen_coupon_code(),
        )
        db.add(coupon)
        db.commit()
        await publish("incident.breached", {"incident_id": incident.incident_id})
        await publish("coupon.issued", {
            "passenger_id": incident.passenger_id,
            "code": coupon.code,
            "coupon_type": coupon.coupon_type,
        })
