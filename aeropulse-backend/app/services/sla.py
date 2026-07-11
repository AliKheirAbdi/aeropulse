from datetime import datetime, timedelta, timezone

# Minutes-to-resolve policy per incident type — mirrors the trigger in
# 002_schema.sql for the auto-created 'delay' incidents, and is reused
# here for incidents raised directly through the API.
SLA_POLICY_MINUTES = {
    "delay": 240,
    "baggage": 240,
    "service": 120,
    "rebooking": 360,
}


def compute_deadline(incident_type: str, opened_at: datetime | None = None) -> datetime:
    opened_at = opened_at or datetime.now(timezone.utc)
    minutes = SLA_POLICY_MINUTES.get(incident_type, 240)
    return opened_at + timedelta(minutes=minutes)
