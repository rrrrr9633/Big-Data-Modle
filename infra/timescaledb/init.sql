CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry_readings (
  time TIMESTAMPTZ NOT NULL,
  device_code TEXT NOT NULL,
  point_code TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  unit TEXT,
  quality DOUBLE PRECISION,
  event_id TEXT,
  gateway_id TEXT,
  source_topic TEXT,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (time, device_code, point_code, event_id)
);

SELECT create_hypertable('telemetry_readings', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time
  ON telemetry_readings (device_code, time DESC);

CREATE INDEX IF NOT EXISTS idx_telemetry_point_time
  ON telemetry_readings (point_code, time DESC);

CREATE TABLE IF NOT EXISTS feature_window_events (
  time TIMESTAMPTZ NOT NULL,
  event_id TEXT NOT NULL,
  device_code TEXT NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  feature_values JSONB NOT NULL,
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (time, event_id)
);

SELECT create_hypertable('feature_window_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_feature_window_device_time
  ON feature_window_events (device_code, time DESC);

CREATE TABLE IF NOT EXISTS prediction_metrics (
  time TIMESTAMPTZ NOT NULL,
  prediction_id BIGINT,
  feature_window_id BIGINT,
  device_code TEXT NOT NULL,
  model_version TEXT,
  failure_probability DOUBLE PRECISION NOT NULL,
  health_score DOUBLE PRECISION NOT NULL,
  risk_level TEXT NOT NULL,
  anomaly_score DOUBLE PRECISION NOT NULL,
  trend_factor DOUBLE PRECISION NOT NULL,
  quality_score DOUBLE PRECISION NOT NULL,
  rul_hours DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (time, device_code, prediction_id)
);

SELECT create_hypertable('prediction_metrics', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_prediction_metrics_device_time
  ON prediction_metrics (device_code, time DESC);

CREATE INDEX IF NOT EXISTS idx_prediction_metrics_risk_time
  ON prediction_metrics (risk_level, time DESC);

CREATE TABLE IF NOT EXISTS device_status_events (
  time TIMESTAMPTZ NOT NULL,
  device_code TEXT NOT NULL,
  status TEXT NOT NULL,
  reason TEXT,
  source TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (time, device_code, status)
);

SELECT create_hypertable('device_status_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_device_status_device_time
  ON device_status_events (device_code, time DESC);