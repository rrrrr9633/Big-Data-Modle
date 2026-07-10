# 工业设备预测性维护系统

## 本地依赖检查结果

- Python：已安装 `3.13.13`
- Node.js：已安装 `v26.4.0`
- npm：已安装 `11.17.0`
- MySQL：已安装 `9.3.0`，但当前未连接到运行中的本地服务
- Redis：已安装 `8.6.1`，但当前未连接到运行中的本地服务
- Java Runtime：未安装，后续运行 Spark/PySpark 需要补 Java

## 启动基础设施

```bash
chmod +x scripts/start-infra.sh scripts/stop-infra.sh
./scripts/start-infra.sh
```

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