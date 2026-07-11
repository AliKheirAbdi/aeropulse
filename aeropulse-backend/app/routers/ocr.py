from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..services.ocr_service import extract_flight_and_pnr
from ..redis_bus import publish

router = APIRouter(prefix="/ocr", tags=["ocr"])

CONFIDENCE_THRESHOLD = 0.5


@router.post("/verify-ticket", response_model=schemas.TicketVerifyResult)
async def verify_ticket(
    passenger_name: str = Form(...),
    passenger_email: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Step 1-5 of the ingestion pipeline: OCR the uploaded photo, match the
    detected flight number against flight_registry, and — on a confident
    match — create/link the passenger so they show up live on the admin
    dashboard's passenger counts.
    """
    image_bytes = await file.read()
    result = extract_flight_and_pnr(image_bytes)

    if not result["flight_number"] or result["confidence"] < CONFIDENCE_THRESHOLD:
        return schemas.TicketVerifyResult(
            matched=False,
            detected_flight_number=result["flight_number"],
            message="Could not confidently read a flight number from this image. "
                    "Routed to manual review.",
        )

    flight = (
        db.query(models.FlightRegistry)
        .filter(models.FlightRegistry.flight_number == result["flight_number"])
        .order_by(models.FlightRegistry.scheduled_dep.desc())
        .first()
    )
    if not flight:
        return schemas.TicketVerifyResult(
            matched=False,
            detected_flight_number=result["flight_number"],
            message=f"Detected flight number {result['flight_number']} but no matching "
                    f"live flight was found.",
        )

    passenger = (
        db.query(models.Passenger)
        .filter(models.Passenger.full_name == passenger_name)
        .first()
    )
    if not passenger:
        passenger = models.Passenger(full_name=passenger_name, email=passenger_email)
        db.add(passenger)
        db.commit()
        db.refresh(passenger)

    existing_link = (
        db.query(models.PassengerFlightLink)
        .filter(
            models.PassengerFlightLink.flight_id == flight.flight_id,
            models.PassengerFlightLink.passenger_id == passenger.passenger_id,
        )
        .first()
    )
    if not existing_link:
        link = models.PassengerFlightLink(
            flight_id=flight.flight_id,
            passenger_id=passenger.passenger_id,
            pnr=result.get("pnr"),
        )
        db.add(link)
        db.commit()

    await publish("ticket.uploaded", {
        "flight_id": flight.flight_id,
        "flight_number": flight.flight_number,
        "passenger_id": passenger.passenger_id,
    })

    return schemas.TicketVerifyResult(
        matched=True,
        flight=flight,
        detected_flight_number=result["flight_number"],
        passenger_id=passenger.passenger_id,
        message=f"Matched to flight {flight.flight_number} ({flight.origin} → {flight.destination}).",
    )
