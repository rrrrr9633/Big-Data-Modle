# Industrial Predictive Maintenance Production Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the six requested production capability areas with explicit, testable boundaries between repository-owned software and site-owned industrial infrastructure.

**Architecture:** The FastAPI service remains the control plane and business API. A separately runnable edge process loads exported gateway configurations, reads supported industrial protocols, maps readings to `TelemetryEvent`, and publishes to MQTT. MySQL stores governance, security, and MLOps workflows; deployment compose assets provide observability, backup, process supervision, and alert delivery.

**Tech Stack:** FastAPI, SQLAlchemy/MySQL, Redis, Kafka, EMQX, TimescaleDB, React/Vite, Prometheus/Grafana, Docker Compose, pymodbus, asyncua, python-snap7.

---

### Task 1: Production Edge Runtime

**Files:**
- Create: `backend/app/edge/runner.py`, `backend/app/edge/adapters/parsing.py`
- Modify: `backend/app/edge/adapters/{modbus,opcua,s7,cnc}.py`, `backend/app/edge/contracts.py`, `backend/requirements.txt`
- Test: `backend/tests/test_edge_protocol_adapters.py`, `backend/tests/test_edge_runner.py`

- [ ] Write failing tests for a protocol binding that returns a numeric `RawPointValue`, converts a protocol failure to quality `0`, and publishes the configured MQTT topic.
- [ ] Run `./.venv/bin/python -m pytest -q tests/test_edge_protocol_adapters.py tests/test_edge_runner.py` and confirm the expected missing-runtime failure.
- [ ] Implement endpoint/session configuration, Modbus TCP/RTU decoding, OPC UA node reads, S7 DB reads, reconnect backoff, interval scheduling, local spool/replay, and MQTT publishing.
- [ ] Implement CNC vendor plugins. FANUC FOCAS is enabled only when an approved SDK is installed; unsupported vendors report `driver_unavailable` without simulated values.
- [ ] Re-run the focused tests and retain explicit integration-test requirements for endpoint, certificate, rack/slot, and vendor SDK parameters.

### Task 2: Master Data Governance

**Files:**
- Create: `backend/app/governance/{schemas,service}.py`, `backend/app/api/v1/governance.py`
- Modify: `infra/mysql/init.sql`, `backend/app/repositories/maintenance_repository.py`, `backend/app/api/routes.py`, `backend/app/api/v1/devices.py`
- Test: `backend/tests/test_governance_workflow.py`

- [ ] Write failing tests for submitting a point change, approval/rejection, immutable version history, and feature-map impact calculation against active models.
- [ ] Implement `master_data_changes`, `master_data_versions`, and approval actions; apply records only after approver action and write audit events.
- [ ] Expose pending, history, diff, approval, and impact endpoints; require submit versus approve permissions.

### Task 3: Security and User Management

**Files:**
- Create: `backend/app/security/{repository,passwords,tokens}.py`
- Modify: `infra/mysql/init.sql`, `backend/app/api/v1/auth.py`, `backend/app/security/{auth,policies}.py`, `backend/app/core/config.py`
- Test: `backend/tests/test_user_security.py`

- [ ] Write failing tests for a stored password hash, assigned role, failed-login lockout, refresh rotation, and revoked access token.
- [ ] Implement user/role/permission persistence, Argon2 password hashes, lockout counters, refresh-token rotation, revocation storage, and audit trails.
- [ ] Remove production dependence on `AUTH_ADMIN_PASSWORD`; preserve an explicit bootstrap-admin migration path.

### Task 4: Model Governance and Feedback

**Files:**
- Create: `backend/app/mlops/{datasets,calibration,drift,review,service}.py`, `backend/app/api/v1/mlops.py`
- Modify: `infra/mysql/init.sql`, `backend/app/api/routes.py`, `backend/app/api/v1/{ingestion,models,warnings}.py`
- Test: `backend/tests/test_mlops_workflow.py`

- [ ] Write failing tests for factory CSV validation, candidate-versus-active comparison, threshold calibration, drift detection, review feedback, and approval-gated activation.
- [ ] Implement dataset/version records, candidate artifacts, metric comparison, threshold profiles, PSI-style drift summaries, false-positive/false-negative review records, and retraining dataset export.
- [ ] Require model approval before activation and preserve rollback history.

### Task 5: Operations Deployment

**Files:**
- Create: `infra/prometheus/prometheus.yml`, `infra/alertmanager/alertmanager.yml`, `infra/grafana/`, `scripts/{backup,restore-verify}.sh`, `deploy/systemd/`, `deploy/supervisor/`
- Modify: `docker-compose.yml`, `backend/app/main.py`, `backend/app/ops/{observability,backup_status,supervision}.py`
- Test: `backend/tests/test_operations_deployment.py`

- [ ] Write failing tests for Prometheus metrics, backup status generation, and declared restart policy.
- [ ] Add service metrics, Prometheus/Grafana/Alertmanager services, backup scripts for MySQL/TimescaleDB/Redis metadata, restore verification, and restart policies for every long-running service.
- [ ] Configure email/webhook notification adapters from environment variables; do not hardcode recipient or secret values.

### Task 6: Workbench Completion

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/styles.css`
- Test: `frontend` build and browser interaction checks

- [ ] Add failing API/client tests for config export, runtime streams/EMQX/backups, governance approvals, model drift/reviews, and role-gated actions.
- [ ] Implement dense operational views that consume only real backend responses, download edge configuration JSON, and hide/disable unauthorized actions based on permission claims.
- [ ] Verify keyboard access, empty/error/loading states, desktop/mobile layouts, and no simulated presentation for unavailable external services.

### Task 7: Full Verification and Site Acceptance

**Files:**
- Create: `docs/site-acceptance.md`

- [ ] Run `./.venv/bin/python -m pytest -q`, `./.venv/bin/ruff check app tests`, and `npm run build`.
- [ ] Start compose infrastructure and validate health, metrics, backup status, and notification test route.
- [ ] Record required site values: PLC endpoint/RTU device, OPC UA trust chain, S7 rack/slot, CNC vendor SDK/license, MQTT credentials, TLS certificates, and alert recipients.
- [ ] Execute one approved physical-device read per configured protocol before declaring field connectivity complete.
