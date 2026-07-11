-- Turn the telemetry table into a Timescale hypertable partitioned by time
SELECT create_hypertable('operational_kpis', 'recorded_at', if_not_exists => TRUE);

-- Continuous aggregate powering the admin dashboard's rolling KPI cards
-- (refreshes on a schedule instead of scanning raw rows on every dashboard load)
CREATE MATERIALIZED VIEW operational_kpis_hourly
WITH (timescaledb.continuous) AS
SELECT
    flight_id,
    time_bucket('1 hour', recorded_at) AS bucket,
    avg(on_time_variance_min)  AS avg_variance_min,
    avg(turnaround_min)        AS avg_turnaround_min,
    avg(load_factor)           AS avg_load_factor
FROM operational_kpis
GROUP BY flight_id, bucket;

SELECT add_continuous_aggregate_policy('operational_kpis_hourly',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);
