from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "工业设备预测性维护系统"
    version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    mysql_url: str = "mysql+pymysql://root:123123@127.0.0.1:3306/pdm"
    redis_url: str = "redis://127.0.0.1:6379/0"
    tsdb_url: str = "postgresql://pdm:123123@127.0.0.1:5432/pdm_tsdb"
    kafka_bootstrap_servers: str = "127.0.0.1:9092"
    kafka_api_version: str = "4.0"
    kafka_telemetry_raw_topic: str = "factory.telemetry.raw"
    kafka_telemetry_cleaned_topic: str = "factory.telemetry.cleaned"
    kafka_telemetry_invalid_topic: str = "factory.telemetry.invalid"
    kafka_features_windowed_topic: str = "factory.features.windowed"
    kafka_predictions_created_topic: str = "factory.predictions.created"
    kafka_warnings_created_topic: str = "factory.warnings.created"
    kafka_raw_group_id: str = "pdm-raw-telemetry-cleaner"
    kafka_cleaned_group_id: str = "pdm-cleaned-telemetry-writer"
    kafka_feature_group_id: str = "pdm-feature-window-builder"
    kafka_inference_group_id: str = "pdm-async-inference"
    feature_window_reading_limit: int = 120
    mqtt_broker_host: str = "127.0.0.1"
    mqtt_broker_port: int = 1883
    mqtt_telemetry_topic: str = "factory/+/workshop/+/line/+/machine/+/telemetry"
    mqtt_client_id: str = "pdm-mqtt-to-kafka"
    redis_online_ttl_seconds: int = 120
    redis_latest_snapshot_ttl_seconds: int = 300
    mqtt_to_kafka_enabled: bool = False
    raw_telemetry_consumer_enabled: bool = False
    cleaned_telemetry_consumer_enabled: bool = False
    feature_consumer_enabled: bool = False
    inference_consumer_enabled: bool = False
    warning_suppression_seconds: int = 60
    simulation_auto_start: bool = False
    simulation_control_api_enabled: bool = True
    simulation_model_bootstrap_enabled: bool = True
    simulation_model_dataset_path: str = "../ai4i2020.csv"
    simulation_device_count: int = 6
    simulation_mode: str = "degrading"
    simulation_interval_seconds: float = 1.0
    simulation_start_delay_seconds: float = 2.0
    auth_enabled: bool = False
    auth_admin_username: str = "admin"
    auth_admin_password: str = "admin123"
    auth_token_secret: str = "change-me-in-production"
    auth_token_ttl_seconds: int = 28800

    emqx_management_url: str = ""
    emqx_management_username: str = ""
    emqx_management_password: str = ""
    prometheus_url: str = ""
    grafana_url: str = ""
    backup_status_file: str = ""
    supervision_mode: str = ""
    ops_http_timeout_seconds: float = 3.0

    # Intelligence middle platform (Agent / RAG / inspection)
    intelligence_enabled: bool = True
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    # Legacy alias; provider prefers llm_chat_model when set.
    llm_model: str = "gpt-4o-mini"
    llm_chat_model: str = ""
    llm_embedding_model: str = "text-embedding-3-small"
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.2
    # Legacy alias; prefer ai4i_base_dataset_path when set.
    ai4i_dataset_path: str = "../ai4i2020.csv"
    ai4i_base_dataset_path: str = ""
    ai4i_archive_dir: str = "../archives/ai4i"
    intelligence_knowledge_batch_size: int = 100
    intelligence_rag_top_k: int = 5
    intelligence_max_tool_rounds: int = 3
    intelligence_history_limit: int = 20
    inspection_enabled: bool = False
    inspection_minute: int = 0
    inspection_device_limit: int = 50
    inspection_poll_seconds: float = 15.0

    def resolved_llm_chat_model(self) -> str:
        chat = (self.llm_chat_model or "").strip()
        if chat:
            return chat
        return (self.llm_model or "gpt-4o-mini").strip() or "gpt-4o-mini"

    def resolved_ai4i_dataset_path(self) -> str:
        base = (self.ai4i_base_dataset_path or "").strip()
        if base:
            return base
        return (self.ai4i_dataset_path or "../ai4i2020.csv").strip()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
