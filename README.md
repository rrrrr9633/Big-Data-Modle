# 工业设备预测性维护系统

## 本地依赖检查结果

- Python：已安装 `3.13.13`
- Node.js：已安装 `v26.4.0`
- npm：已安装 `11.17.0`
- MySQL：已安装 `9.3.0`，但当前未连接到运行中的本地服务
- Redis：已安装 `8.6.1`，但当前未连接到运行中的本地服务
- Java Runtime：未安装，后续运行 Spark/PySpark 需要补 Java

## 本地开发（推荐）

本项目默认按本机开发与答辩演示使用，不要求 Docker。前端工作台带有确定性的本地演示数据，入口页与工作台通过 `#/overview` 路由连接，单独启动前端即可验证完整界面流程。

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

如果需要真实后端接口，再单独启动 MySQL、Redis 和后端；Kafka、EMQX、TimescaleDB 只属于完整实时流处理链路，不是查看界面或演示导航的前置条件。

## 可选：完整实时链路

只有需要演示 MQTT → Kafka → TSDB → Redis → 推理的完整数据链路时，才使用 Docker Compose：

```bash
docker compose up --build
```

这条路径会启动 MySQL、Redis、TimescaleDB、Kafka、EMQX、后端和前端，启动时间和资源占用都明显高于本地前端模式。停止完整链路：

```bash
docker compose down
```

不需要实时链路时，不要启动 Kafka、EMQX 和 TimescaleDB；已有容器可手动停止，避免它们继续占用端口与内存。

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 边缘网关与工业模拟

边缘运行器使用 SQLite 本地出站队列：遥测事件先持久化，发布成功后才确认删除。
现场部署必须将 `EDGE_SPOOL_PATH` 指向边缘主机的持久化磁盘，而不是容器临时目录：

```bash
cd backend
export EDGE_SPOOL_PATH=/var/lib/pdm-edge/gateway-cnc-001.sqlite
./.venv/bin/python -m app.edge.runner /etc/pdm-edge/gateway-cnc-001.json
```

其中 `gateway-cnc-001.json` 可由 `/api/v1/ingress/edge-configs` 导出。网络恢复后，运行器按原始采集顺序补发未确认事件；重复的 `event_id` 由平台既有幂等键拦截。

本地设备流量模拟器可基于 AI4I 样本生成正常、劣化和故障设备：

```bash
cd backend
./.venv/bin/python scripts/simulate_devices.py --devices 20 --cycles 10 --dry-run
```

`IndustrialDeviceSimulator` 还提供确定性的 CNC 工况曲线，包含主轴温度、负载、振动、刀具磨损、传感器卡死和传感器漂移，用于边缘链路与告警演练。真实 CNC 协议需注册已授权的厂商驱动；未安装 FANUC、SINUMERIK、Mitsubishi、Haas 或华中数控 SDK 时会明确返回 `driver_unavailable`。

## 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

健康检查：`http://127.0.0.1:8000/api/v1/health`

## 边缘网关与工业模拟

边缘运行器使用 SQLite 本地出站队列：遥测事件先持久化，发布成功后才确认删除。
现场部署必须将 `EDGE_SPOOL_PATH` 指向边缘主机的持久化磁盘，而不是容器临时目录：

```bash
cd backend
export EDGE_SPOOL_PATH=/var/lib/pdm-edge/gateway-cnc-001.sqlite
./.venv/bin/python -m app.edge.runner /etc/pdm-edge/gateway-cnc-001.json
```

其中 `gateway-cnc-001.json` 可由 `/api/v1/ingress/edge-configs` 导出。网络恢复后，运行器按原始采集顺序补发未确认事件；重复的 `event_id` 由平台既有幂等键拦截。

本地设备流量模拟器可基于 AI4I 样本生成正常、劣化和故障设备：

```bash
cd backend
./.venv/bin/python scripts/simulate_devices.py --devices 20 --cycles 10 --dry-run
```

`IndustrialDeviceSimulator` 还提供确定性的 CNC 工况曲线，包含主轴温度、负载、振动、刀具磨损、传感器卡死和传感器漂移，用于边缘链路与告警演练。真实 CNC 协议需注册已授权的厂商驱动；未安装 FANUC、SINUMERIK、Mitsubishi、Haas 或华中数控 SDK 时会明确返回 `driver_unavailable`。

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端地址：`http://127.0.0.1:5173`

## 架构原则

- 数据接入只负责拿到数据，不做模型判断。
- 数据治理只负责数据质量和窗口化，不关心页面展示。
- 大数据计算只产出特征和统计结果，不直接生成业务建议。
- 模型分析只输出概率、分数、标签、RUL 等模型结果。
- 业务服务负责把模型结果转换为风险等级、预警和维护建议。
- 展示层只消费 API，不直接处理模型和清洗逻辑。
