• 当前项目要改造成 机床传感器 → EMQX(MQTT) → Kafka → TSDB，不是小改一个接口，而
  是要把现在“后端直接吃实时读数并立即推理”的链路，改成“采集接入、消息缓冲、时序
  落库、再异步推理”的工业数据管道。

  当前项目现状

  - 现在 Docker 里有 Kafka，但 MQTT 用的是 eclipse-mosquitto，不是 EMQX，见
    docker-compose.yml:29。

  - 后端已经有 MQTT/Kafka 消费者雏形，见 backend/app/services/
    telemetry_consumers.py:49。

  - 但当前逻辑是：MQTT/Kafka/HTTP/WebSocket → ingest_telemetry_payload → MySQL
    sensor_readings → 特征窗口 → 模型推理 → prediction_logs/warning_events。

  - Kafka 和 MQTT 默认关闭，配置在 backend/app/core/config.py:16。
  - 高频传感器数据现在写 MySQL 的 sensor_readings，见 infra/mysql/init.sql:42。
    这不适合真实工厂长期高频数据。

  目标链路
  真实落地应该改成：

  机床 / PLC / 工业网关
    ↓ MQTT
  EMQX
    ↓ Rule Engine / MQTT Bridge
  Kafka: factory.telemetry.raw
    ↓ raw consumer
  数据校验 / 标准化 / 幂等 / 单位换算
    ↓
  Kafka: factory.telemetry.cleaned
    ↓ tsdb writer
  TSDB: sensor_readings
    ↓ feature consumer
  Kafka: factory.features.windowed
    ↓ inference consumer
  MySQL: prediction_logs / warning_events / device_status
  Redis: latest snapshot / online status / idempotency

  第一步：把 Mosquitto 换成 EMQX
  当前 docker-compose.yml 里是：

  mqtt:
    image: eclipse-mosquitto:2

  建议改成 EMQX：

  emqx:
    image: emqx/emqx:5
    container_name: pdm-emqx
    ports:
      - "1883:1883"
      - "8083:8083"
      - "18083:18083"
    environment:
      EMQX_DASHBOARD__DEFAULT_USERNAME: admin
      EMQX_DASHBOARD__DEFAULT_PASSWORD: public

  EMQX 的价值不是“能收 MQTT”这么简单，而是它能做规则引擎、认证、ACL、桥接、设备
  连接管理、订阅追踪。真实工厂里比 Mosquitto 更适合做接入层。

  第二步：明确 MQTT Topic 规范
  不要继续用现在的泛化 topic：

  factory/+/telemetry

  建议改成可定位工厂、车间、产线、设备的结构：

  factory/{factory_id}/workshop/{workshop_id}/line/{line_id}/machine/
  {device_code}/telemetry

  消息体建议统一成标准遥测事件：

  {
    "event_id": "uuid",
    "device_code": "CNC-001",
    "point_code": "spindle_temperature",
    "value": 62.4,
    "unit": "C",
    "quality": 1,
    "ts": "2026-07-09T09:30:00.000Z",
    "gateway_id": "GW-001"
  }

  当前项目的 TelemetryPayloadIn 是一台设备一次带多个 readings，见 backend/app/
  services/telemetry_ingestion.py:17。真实工厂更建议 Kafka raw 层按“点位事件”接
  收，后续再聚合成设备窗口。

  第三步：MQTT 不要直接推理，先写 Kafka
  现在 _start_mqtt_consumer() 收到 MQTT 后直接调用：

  process_protocol_message(message.payload, protocol="mqtt")

  这会立刻进入模型推理。目标链路里这里应该改成：

  MQTT consumer / EMQX bridge
    → Kafka producer
    → factory.telemetry.raw

  也就是说，telemetry_consumers.py 需要拆：

  - mqtt_to_kafka.py：只负责 MQTT 消息进入 Kafka raw topic。
  - raw_telemetry_consumer.py：从 Kafka raw 消费，做解析、校验、幂等。
  - cleaned_telemetry_consumer.py：写 TSDB，并维护 Redis 最新快照。
  - feature_consumer.py：从 TSDB 或 Kafka cleaned 聚合窗口。
  - inference_consumer.py：消费窗口特征，执行模型推理和预警落库。

  第四步：Kafka Topic 要拆，不要只有一个
  当前配置只有：

  kafka_telemetry_topic = "factory.telemetry.readings"

  建议改成这些：

  factory.telemetry.raw
  factory.telemetry.cleaned
  factory.telemetry.invalid
  factory.features.windowed
  factory.predictions.created
  factory.warnings.created

  含义：

  - factory.telemetry.raw：EMQX/MQTT 原始消息，尽量不丢。
  - factory.telemetry.cleaned：通过校验、单位统一、时间纠偏后的标准读数。
  - factory.telemetry.invalid：坏数据、未知点位、非法设备、格式错误。
  - factory.features.windowed：按设备和窗口生成的模型输入特征。
  - factory.predictions.created：推理结果事件。
  - factory.warnings.created：预警事件，可给前端、工单、通知服务消费。

  第五步：TSDB 接入位置
  当前高频读数写 MySQL：

  sensor_readings
  feature_windows

  真实落地建议：

  - MySQL 保留：设备、点位、模型版本、预测记录、预警、用户、权限、工单。
  - TSDB 存：原始传感器读数、清洗后的读数、按点位聚合指标。
  - MySQL 的 sensor_readings 可以保留为演示兼容，但真实链路不应主写它。

  推荐选型：

  - TimescaleDB：和 SQL 体系兼容，适合这个项目从 MySQL 迁移。
  - InfluxDB：时序写入和查询成熟，但查询模型和关系数据割裂更明显。
  - ClickHouse：高吞吐分析强，适合大规模历史分析。

  对当前项目，最务实是 TimescaleDB。新增表类似：

  CREATE TABLE telemetry_readings (
    time TIMESTAMPTZ NOT NULL,
    device_code TEXT NOT NULL,
    point_code TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    quality DOUBLE PRECISION,
    event_id TEXT,
    gateway_id TEXT
  );

  SELECT create_hypertable('telemetry_readings', 'time');

  第六步：Redis 应该插在实时状态层
  现在 Redis 没有实际使用。这个链路里 Redis 应该做这些：

  device:{device_code}:latest
  device:{device_code}:online
  idempotency:telemetry:{event_id}
  warning:suppress:{device_code}:{risk_type}
  feature:window:{device_code}:{window_size}

  用途很明确：

  - 防重复上报。
  - 判断设备在线/离线。
  - 前端实时监测页快速读最新状态。
  - 告警抑制，避免同一个设备一分钟刷几十条高风险预警。
  - 缓存短期窗口，减少 TSDB 查询压力。

  第七步：后端代码建议改造目录
  当前后端可以先保持模块化单体，不急着拆微服务。建议按边界重组：

  backend/app/
    ingestion/
      mqtt_to_kafka.py
      http_adapter.py
      schemas.py
      kafka_producer.py

    streams/
      raw_consumer.py
      cleaned_consumer.py
      feature_consumer.py
      inference_consumer.py

    quality/
      validator.py
      normalizer.py
      idempotency.py

    tsdb/
      client.py
      telemetry_repository.py

    features/
      window_builder.py
      feature_repository.py

    inference/
      predictor.py
      explainer.py

    rules/
      warning_policy.py
      risk_policy.py

    realtime/
      device_snapshot.py
      online_status.py

  当前 backend/app/services/prediction_pipeline.py:1 里把“写读数、取窗口、治理、
  特征、推理、预警”都串在一起。目标链路要把它拆成异步阶段。

  建议改造顺序

  1. 把 Docker 的 Mosquitto 换成 EMQX，并补 EMQX 管理端口。
  2. 增加 Kafka topic 配置：raw、cleaned、invalid、features、predictions、
     warnings。

  3. 新增 mqtt_to_kafka，让 MQTT 消息先进 Kafka raw，不直接推理。
  4. 新增 raw consumer：解析、校验、幂等、写 cleaned topic。
  5. 接入 TSDB，cleaned consumer 写 TSDB，不再把高频读数主写 MySQL。
  6. Redis 保存设备最新状态和在线状态。
  7. feature consumer 从 TSDB/cleaned topic 生成窗口特征。
  8. inference consumer 消费窗口特征，复用现有模型推理和预警逻辑。
  9. 前端实时监测页改读 Redis/MySQL 的设备快照和预警，而不是靠手动模拟流。

  结论
  当前项目有接入雏形，但还不是 机床传感器 → EMQX → Kafka → TSDB。它现在更像：

  HTTP/WebSocket/MQTT/Kafka
    → FastAPI 进程
    → MySQL
    → 同步推理
    → MySQL 预测和预警

  要朝真实工厂链路改，核心不是再加页面，而是把实时数据主链路改成：

  EMQX 接入
    → Kafka 缓冲与解耦
    → TSDB 承接高频数据
    → Redis 承接实时状态
    → MySQL 承接业务结果
    → 异步消费者完成特征与推理

  优先做 EMQX + Kafka raw topic + TSDB writer，这三件事做完，项目的数据底座才开
  始接近真实工厂。
