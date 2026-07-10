CREATE DATABASE IF NOT EXISTS pdm CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE pdm;

CREATE TABLE IF NOT EXISTS devices (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_code VARCHAR(64) NOT NULL UNIQUE,
  device_name VARCHAR(128) NOT NULL,
  device_type VARCHAR(64) NOT NULL,
  factory VARCHAR(128) NOT NULL DEFAULT '默认工厂',
  workshop VARCHAR(128) NOT NULL DEFAULT '默认车间',
  production_line VARCHAR(128) NOT NULL DEFAULT '默认产线',
  status VARCHAR(32) NOT NULL DEFAULT 'normal',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_points (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  sensor_code VARCHAR(64) NOT NULL,
  sensor_name VARCHAR(128) NOT NULL,
  device_code VARCHAR(64) NOT NULL,
  unit VARCHAR(32) NULL,
  sampling_frequency VARCHAR(64) NOT NULL DEFAULT 'realtime',
  min_value DOUBLE NULL,
  max_value DOUBLE NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_sensor_device_code (device_code, sensor_code),
  INDEX idx_sensor_point_device (device_code),
  CONSTRAINT fk_sensor_point_device FOREIGN KEY (device_code) REFERENCES devices(device_code)
);

CREATE TABLE IF NOT EXISTS data_import_batches (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_name VARCHAR(128) NOT NULL,
  row_count INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensor_readings (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_code VARCHAR(64) NOT NULL,
  sensor_code VARCHAR(64) NOT NULL,
  recorded_at DATETIME NOT NULL,
  value DOUBLE NOT NULL,
  unit VARCHAR(32),
  batch_id BIGINT NULL,
  INDEX idx_device_time (device_code, recorded_at),
  INDEX idx_sensor_time (sensor_code, recorded_at),
  CONSTRAINT fk_sensor_batch FOREIGN KEY (batch_id) REFERENCES data_import_batches(id)
);

CREATE TABLE IF NOT EXISTS feature_windows (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_code VARCHAR(64) NOT NULL,
  start_time DATETIME NOT NULL,
  end_time DATETIME NOT NULL,
  mean_value DOUBLE NOT NULL,
  std_value DOUBLE NOT NULL,
  max_value DOUBLE NOT NULL,
  min_value DOUBLE NOT NULL,
  trend_value DOUBLE NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_feature_device_time (device_code, end_time)
);

CREATE TABLE IF NOT EXISTS prediction_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_code VARCHAR(64) NOT NULL,
  feature_window_id BIGINT NULL,
  model_version VARCHAR(64) NULL,
  failure_probability DOUBLE NOT NULL,
  health_score DOUBLE NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  anomaly_score DOUBLE NOT NULL DEFAULT 0,
  anomaly_reasons JSON NULL,
  trend_factor DOUBLE NOT NULL DEFAULT 0,
  quality_score DOUBLE NOT NULL DEFAULT 1,
  rul_hours DOUBLE NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_prediction_device_time (device_code, created_at),
  INDEX idx_prediction_risk (risk_level),
  INDEX idx_prediction_window (feature_window_id)
);

CREATE TABLE IF NOT EXISTS prediction_explanations (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  prediction_id BIGINT NOT NULL,
  device_code VARCHAR(64) NOT NULL,
  feature_name VARCHAR(128) NOT NULL,
  feature_value DOUBLE NOT NULL,
  contribution DOUBLE NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_explanation_prediction (prediction_id),
  INDEX idx_explanation_device_time (device_code, created_at),
  CONSTRAINT fk_explanation_prediction FOREIGN KEY (prediction_id) REFERENCES prediction_logs(id)
);

CREATE TABLE IF NOT EXISTS warning_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  prediction_id BIGINT NULL,
  feature_window_id BIGINT NULL,
  model_version VARCHAR(64) NULL,
  failure_probability DOUBLE NULL,
  health_score DOUBLE NULL,
  warning_explanation JSON NULL,
  device_code VARCHAR(64) NOT NULL,
  risk_level VARCHAR(32) NOT NULL,
  title VARCHAR(128) NOT NULL,
  detail TEXT NOT NULL,
  suggested_action TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'new',
  acknowledged_at TIMESTAMP NULL,
  resolved_at TIMESTAMP NULL,
  latest_action TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_warning_status_time (status, created_at),
  INDEX idx_warning_device_time (device_code, created_at),
  INDEX idx_warning_prediction (prediction_id),
  INDEX idx_warning_window (feature_window_id)
);

CREATE TABLE IF NOT EXISTS warning_action_logs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  warning_id BIGINT NOT NULL,
  from_status VARCHAR(32) NOT NULL,
  to_status VARCHAR(32) NOT NULL,
  operator VARCHAR(64) NOT NULL,
  note TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_warning_action_warning_time (warning_id, created_at),
  CONSTRAINT fk_warning_action_event FOREIGN KEY (warning_id) REFERENCES warning_events(id)
);

CREATE TABLE IF NOT EXISTS maintenance_records (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  device_code VARCHAR(64) NOT NULL,
  maintenance_type VARCHAR(64) NOT NULL,
  description TEXT NOT NULL,
  operator_name VARCHAR(64) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_maintenance_device_time (device_code, created_at)
);

CREATE TABLE IF NOT EXISTS model_versions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  model_name VARCHAR(128) NOT NULL,
  model_type VARCHAR(64) NOT NULL,
  version VARCHAR(64) NOT NULL,
  metric_name VARCHAR(64) NOT NULL,
  metric_value DOUBLE NOT NULL,
  artifact_path VARCHAR(255) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_model_version_metric (model_name, version, metric_name)
);