from app.core.config import settings
from app.ingestion.http_adapter import publish_payload_to_raw_topic
from app.ingestion.http_schemas import (
    TelemetryPayloadIn,
    error_message_from_payload,
    parse_telemetry_payload,
)
from app.ingestion.mqtt_simulator import publish_payload_to_mqtt
from app.security.auth import require_admin, verify_access_token
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.post("/readings", status_code=202, dependencies=[Depends(require_admin)])
def ingest_realtime_readings(payload: TelemetryPayloadIn) -> dict[str, object]:
    try:
        return publish_payload_to_raw_topic(payload, protocol="http")
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"遥测事件写入 Kafka raw 失败：{exc}") from exc


@router.post("/mqtt/simulate", status_code=202, dependencies=[Depends(require_admin)])
def simulate_mqtt_realtime_readings(payload: TelemetryPayloadIn) -> dict[str, object]:
    try:
        return publish_payload_to_mqtt(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"遥测事件发布到 EMQX 失败：{exc}") from exc


@router.websocket("/ws/readings")
async def ingest_realtime_readings_ws(websocket: WebSocket) -> None:
    if settings.auth_enabled:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=1008, reason="missing token")
            return
        try:
            verify_access_token(token)
        except Exception:
            await websocket.close(code=1008, reason="invalid token")
            return
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            try:
                payload = parse_telemetry_payload(message)
                result = publish_payload_to_raw_topic(payload, protocol="websocket")
                await websocket.send_json({"ok": True, "data": result})
            except Exception as exc:
                await websocket.send_json({"ok": False, "detail": error_message_from_payload(exc)})
    except WebSocketDisconnect:
        return
