-- ============================================================
-- AeroPulse core schema
-- ============================================================

CREATE TABLE aircraft_profiles (
    aircraft_id            SERIAL PRIMARY KEY,
    tail_number             VARCHAR(10) UNIQUE NOT NULL,
    model                   VARCHAR(50) NOT NULL,
    capacity                INT NOT NULL,
    age_years               NUMERIC(4,1),
    fuel_burn_rate_per_hr   NUMERIC(10,2)
);

CREATE TABLE flight_registry (
    flight_id       SERIAL PRIMARY KEY,
    flight_number   VARCHAR(10) NOT NULL,
    aircraft_id     INT REFERENCES aircraft_profiles(aircraft_id),
    origin          VARCHAR(3) NOT NULL,
    destination     VARCHAR(3) NOT NULL,
    scheduled_dep   TIMESTAMPTZ NOT NULL,
    scheduled_arr   TIMESTAMPTZ NOT NULL,
    actual_dep      TIMESTAMPTZ,
    actual_arr      TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED'
        CHECK (status IN ('SCHEDULED','BOARDING','DEPARTED','AIRBORNE','LANDED','DELAYED','CANCELLED')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_flight_registry_number ON flight_registry(flight_number);
CREATE INDEX idx_flight_registry_status ON flight_registry(status);

CREATE TABLE passengers (
    passenger_id    SERIAL PRIMARY KEY,
    full_name       VARCHAR(120) NOT NULL,
    email           VARCHAR(160) UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Links a passenger to a flight once their ticket has been verified (OCR match or PNR/CRM sync)
CREATE TABLE passenger_flight_link (
    link_id         SERIAL PRIMARY KEY,
    flight_id       INT NOT NULL REFERENCES flight_registry(flight_id),
    passenger_id    INT NOT NULL REFERENCES passengers(passenger_id),
    pnr             VARCHAR(10),
    seat            VARCHAR(5),
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(flight_id, passenger_id)
);

-- Time-series operational telemetry (becomes a Timescale hypertable in 003_hypertables.sql)
CREATE TABLE operational_kpis (
    kpi_id                  BIGSERIAL,
    flight_id               INT REFERENCES flight_registry(flight_id),
    on_time_variance_min    INT,
    turnaround_min          INT,
    load_factor             NUMERIC(5,2),
    recorded_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (kpi_id, recorded_at)
);

CREATE TABLE flight_profitability (
    flight_id               INT PRIMARY KEY REFERENCES flight_registry(flight_id),
    fuel_cost               NUMERIC(12,2) NOT NULL DEFAULT 0,
    crew_cost               NUMERIC(12,2) NOT NULL DEFAULT 0,
    maintenance_allocation  NUMERIC(12,2) NOT NULL DEFAULT 0,
    catering_cost           NUMERIC(12,2) NOT NULL DEFAULT 0,
    ancillary_revenue       NUMERIC(12,2) NOT NULL DEFAULT 0,
    ticket_revenue          NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_margin              NUMERIC(12,2) GENERATED ALWAYS AS (
        (ancillary_revenue + ticket_revenue)
        - (fuel_cost + crew_cost + maintenance_allocation + catering_cost)
    ) STORED,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE passenger_feedback (
    feedback_id     SERIAL PRIMARY KEY,
    passenger_id    INT REFERENCES passengers(passenger_id),
    flight_id       INT REFERENCES flight_registry(flight_id),
    nps_score       INT CHECK (nps_score BETWEEN 0 AND 10),
    comment         TEXT,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE resolution_sla_tracking (
    incident_id     SERIAL PRIMARY KEY,
    flight_id       INT REFERENCES flight_registry(flight_id),
    passenger_id    INT REFERENCES passengers(passenger_id),
    incident_type   VARCHAR(30) NOT NULL CHECK (incident_type IN ('delay','baggage','service','rebooking')),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    sla_deadline    TIMESTAMPTZ NOT NULL,
    resolved_at     TIMESTAMPTZ,
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED','BREACHED','CLOSED')),
    rating          VARCHAR(10)
);
CREATE INDEX idx_sla_status ON resolution_sla_tracking(status);

CREATE TABLE automated_coupon_logs (
    coupon_id       SERIAL PRIMARY KEY,
    passenger_id    INT REFERENCES passengers(passenger_id),
    incident_id     INT REFERENCES resolution_sla_tracking(incident_id),
    coupon_type     VARCHAR(30) NOT NULL,
    value           NUMERIC(10,2),
    code            VARCHAR(30) UNIQUE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    redeemed_at     TIMESTAMPTZ
);

-- ============================================================
-- Relational logic: a flight moving to DELAYED auto-opens an
-- incident + resolution timer for every verified passenger on it.
-- This is enforced at the DB layer so it can never be skipped by
-- a buggy or bypassed API call.
-- ============================================================
CREATE OR REPLACE FUNCTION fn_handle_flight_delay() RETURNS TRIGGER AS $$
DECLARE
    sla_minutes INT := 240; -- delay-compensation SLA policy
BEGIN
    IF NEW.status = 'DELAYED' AND (OLD.status IS DISTINCT FROM 'DELAYED') THEN
        INSERT INTO resolution_sla_tracking (flight_id, passenger_id, incident_type, opened_at, sla_deadline, status)
        SELECT NEW.flight_id, pfl.passenger_id, 'delay', now(), now() + (sla_minutes || ' minutes')::interval, 'OPEN'
        FROM passenger_flight_link pfl
        WHERE pfl.flight_id = NEW.flight_id
          AND NOT EXISTS (
              SELECT 1 FROM resolution_sla_tracking r
              WHERE r.flight_id = NEW.flight_id
                AND r.passenger_id = pfl.passenger_id
                AND r.incident_type = 'delay'
                AND r.status = 'OPEN'
          );
        PERFORM pg_notify('flight_events', json_build_object(
            'event', 'flight.delayed', 'flight_id', NEW.flight_id, 'flight_number', NEW.flight_number
        )::text);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_flight_delay
AFTER UPDATE ON flight_registry
FOR EACH ROW EXECUTE FUNCTION fn_handle_flight_delay();
