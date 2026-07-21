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
  protocol VARCHAR(64) NULL,
  source_address VARCHAR(255) NULL,
  protocol_options JSON NULL,
  feature_name VARCHAR(128) NULL,
  quality_rule VARCHAR(255) NULL,
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

CREATE TABLE IF NOT EXISTS master_data_change_requests (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  entity_type VARCHAR(32) NOT NULL,
  operation VARCHAR(32) NOT NULL,
  device_code VARCHAR(64) NOT NULL,
  sensor_code VARCHAR(64) NULL,
  payload_json JSON NOT NULL,
  impact_json JSON NULL,
  reason TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  requested_by VARCHAR(64) NOT NULL,
  requested_role VARCHAR(32) NOT NULL,
  approved_by VARCHAR(64) NULL,
  approved_role VARCHAR(32) NULL,
  decision_comment TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_at TIMESTAMP NULL,
  INDEX idx_master_data_change_status_time (status, created_at),
  INDEX idx_master_data_change_resource (device_code, sensor_code)
);

CREATE TABLE IF NOT EXISTS master_data_versions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  change_request_id BIGINT NOT NULL,
  entity_type VARCHAR(32) NOT NULL,
  device_code VARCHAR(64) NOT NULL,
  sensor_code VARCHAR(64) NULL,
  snapshot_json JSON NOT NULL,
  published_by VARCHAR(64) NOT NULL,
  published_role VARCHAR(32) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_master_data_version_resource_time (device_code, sensor_code, created_at),
  CONSTRAINT fk_master_data_version_change
    FOREIGN KEY (change_request_id) REFERENCES master_data_change_requests(id)
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

CREATE TABLE IF NOT EXISTS model_feature_dependencies (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  model_name VARCHAR(128) NOT NULL,
  version VARCHAR(64) NOT NULL,
  feature_name VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_model_feature_dependency (model_name, version, feature_name),
  INDEX idx_model_feature_active (feature_name, status)
);

CREATE TABLE IF NOT EXISTS model_training_jobs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  version VARCHAR(64) NULL,
  trained_rows INT NULL,
  error_message TEXT NULL,
  metrics_json JSON NULL,
  detail_json JSON NULL,
  created_by VARCHAR(64) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP NULL,
  finished_at TIMESTAMP NULL,
  INDEX idx_model_training_jobs_status_time (status, created_at)
);

CREATE TABLE IF NOT EXISTS agent_sessions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_key VARCHAR(64) NOT NULL UNIQUE,
  title VARCHAR(255) NOT NULL DEFAULT '新会话',
  user_id VARCHAR(64) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  metadata_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_agent_session_user_time (user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS agent_messages (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id BIGINT NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  mode VARCHAR(32) NOT NULL DEFAULT 'chat',
  status VARCHAR(32) NOT NULL DEFAULT 'ok',
  facts_json JSON NULL,
  citations_json JSON NULL,
  tool_calls_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_agent_message_session_time (session_id, created_at),
  CONSTRAINT fk_agent_message_session FOREIGN KEY (session_id) REFERENCES agent_sessions(id)
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_type VARCHAR(64) NOT NULL,
  source_id VARCHAR(128) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  metadata_json JSON NULL,
  content_hash VARCHAR(64) NOT NULL,
  synced_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_knowledge_source (source_type, source_id),
  INDEX idx_knowledge_synced (synced_at)
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  document_id BIGINT NOT NULL,
  chunk_index INT NOT NULL DEFAULT 0,
  content TEXT NOT NULL,
  keywords VARCHAR(512) NULL,
  metadata_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_knowledge_chunk (document_id, chunk_index),
  INDEX idx_knowledge_chunk_keywords (keywords),
  CONSTRAINT fk_knowledge_chunk_document FOREIGN KEY (document_id) REFERENCES knowledge_documents(id)
);

CREATE TABLE IF NOT EXISTS knowledge_sync_cursors (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_type VARCHAR(64) NOT NULL UNIQUE,
  last_source_id BIGINT NOT NULL DEFAULT 0,
  last_synced_at TIMESTAMP NULL,
  total_synced INT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspection_schedules (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  schedule_key VARCHAR(64) NOT NULL UNIQUE DEFAULT 'default',
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  minute_of_hour TINYINT NOT NULL DEFAULT 0,
  device_limit INT NOT NULL DEFAULT 50,
  last_triggered_at TIMESTAMP NULL,
  last_run_id BIGINT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inspection_runs (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  trigger_type VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  summary TEXT NULL,
  device_total INT NOT NULL DEFAULT 0,
  issue_total INT NOT NULL DEFAULT 0,
  error_message TEXT NULL,
  started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TIMESTAMP NULL,
  INDEX idx_inspection_run_status_time (status, started_at)
);

CREATE TABLE IF NOT EXISTS inspection_reports (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  run_id BIGINT NOT NULL,
  device_code VARCHAR(64) NULL,
  severity VARCHAR(32) NOT NULL DEFAULT 'info',
  title VARCHAR(255) NOT NULL,
  detail TEXT NOT NULL,
  findings_json JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_inspection_report_run (run_id),
  INDEX idx_inspection_report_device (device_code),
  CONSTRAINT fk_inspection_report_run FOREIGN KEY (run_id) REFERENCES inspection_runs(id)
);
