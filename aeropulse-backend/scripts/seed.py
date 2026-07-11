"""
Seeds a handful of aircraft, flights, and a demo passenger so the API
returns something meaningful right after `docker compose up`.

Run with:  docker compose exec api python -m scripts.seed
"""
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)  # no-op if init-db SQL already ran


def run():
    db = SessionLocal()
    try:
        if db.query(models.AircraftProfile).count() > 0:
            print("Already seeded, skipping.")
            return

        aircraft = [
            models.AircraftProfile(tail_number="N88AA", model="B738", capacity=166, age_years=8.2, fuel_burn_rate_per_hr=2600),
            models.AircraftProfile(tail_number="N21DL", model="A321", capacity=190, age_years=5.1, fuel_burn_rate_per_hr=2450),
            models.AircraftProfile(tail_number="N45UA", model="A320", capacity=150, age_years=11.4, fuel_burn_rate_per_hr=2500),
        ]
        db.add_all(aircraft)
        db.commit()
        for a in aircraft:
            db.refresh(a)

        now = datetime.now(timezone.utc)
        flights = [
            models.FlightRegistry(
                flight_number="AA204", aircraft_id=aircraft[0].aircraft_id,
                origin="JFK", destination="LHR",
                scheduled_dep=now + timedelta(hours=2), scheduled_arr=now + timedelta(hours=9),
                status="SCHEDULED",
            ),
            models.FlightRegistry(
                flight_number="AA118", aircraft_id=aircraft[1].aircraft_id,
                origin="ORD", destination="LAX",
                scheduled_dep=now + timedelta(hours=1), scheduled_arr=now + timedelta(hours=4),
                status="SCHEDULED",
            ),
            models.FlightRegistry(
                flight_number="AA552", aircraft_id=aircraft[2].aircraft_id,
                origin="MIA", destination="GRU",
                scheduled_dep=now + timedelta(minutes=30), scheduled_arr=now + timedelta(hours=8),
                status="BOARDING",
            ),
        ]
        db.add_all(flights)
        db.commit()

        passenger = models.Passenger(full_name="Jordan Diaz", email="jordan.diaz@example.com")
        db.add(passenger)
        db.commit()
        db.refresh(passenger)

        db.add(models.PassengerFlightLink(
            flight_id=flights[0].flight_id, passenger_id=passenger.passenger_id, seat="14C"
        ))
        db.commit()
        print(f"Seeded {len(aircraft)} aircraft, {len(flights)} flights, 1 passenger.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
