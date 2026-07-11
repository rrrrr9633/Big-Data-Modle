import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  ChartLineUp,
  Database,
  Factory,
  GitBranch,
  Pulse,
  ShieldWarning,
  Waveform,
} from '@phosphor-icons/react';

gsap.registerPlugin(ScrollTrigger);

const pipeline = [
  '机床传感器',
  'EMQX MQTT',
  'Kafka Raw',
  '清洗治理',
  'TSDB / Redis',
  '特征窗口',
  '模型推理',
  '预测预警',
];

const capabilities = [
  {
    title: '工业数据接入',
    text: '生产主入口是 MQTT。现场 Modbus、OPC UA、S7 等协议由工业网关适配，统一转换为 TelemetryEvent 后发布到 EMQX。',
    icon: Waveform,
    image: 'industrial-sensors-floor',
    className: 'card-xl',
  },
  {
    title: '流式数据治理',
    text: '原始遥测进入 Kafka 后完成结构解析、幂等控制、质量校验、单位保留与异常消息隔离，避免脏数据直接进入推理链路。',
    icon: GitBranch,
    image: 'stream-processing-control-room',
    className: 'card-sm',
  },
  {
    title: '时序与在线状态',
    text: '清洗后的点位写入 TimescaleDB；Redis 保存设备最新快照、在线态与最近上报时间，支撑实时监测页面低延迟读取。',
    icon: Database,
    image: 'time-series-database-rack',
    className: 'card-sm',
  },
  {
    title: '模型推理闭环',
    text: '特征窗口驱动故障概率、健康评分、异常评分、RUL 与风险等级计算，预测结果进入 MySQL 形成可追溯记录。',
    icon: ChartLineUp,
    image: 'machine-learning-manufacturing',
    className: 'card-sm',
  },
  {
    title: '预警与处置记录',
    text: '高风险设备自动生成预警事件，保留预测记录、特征窗口、模型版本和状态流转，为运维人员提供明确处置入口。',
    icon: ShieldWarning,
    image: 'industrial-alert-panel',
    className: 'card-sm',
  },
];

const systemLayers = [
  {
    title: '采集接入层',
    detail: '工业网关或边缘采集服务把 PLC / CNC / 传感器点位标准化为单点位事件。',
    signal: 'Modbus / OPC UA / S7 → TelemetryEvent',
    output: 'MQTT 标准遥测事件',
  },
  {
    title: '流式总线层',
    detail: 'Kafka 承接 raw、cleaned、features、predictions 与 warnings topic，解耦采集、清洗、窗口与推理。',
    signal: 'raw → cleaned → features',
    output: '可回放事件流',
  },
  {
    title: '数据资产层',
    detail: 'TimescaleDB 保存高频点位，Redis 保存在线快照，MySQL 保存设备、预测、预警和模型资产。',
    signal: 'TSDB / Redis / MySQL',
    output: '在线状态与可追溯记录',
  },
  {
    title: '评估决策层',
    detail: '根据窗口特征形成故障概率、健康评分、RUL、异常原因与维护建议。',
    signal: 'failure_probability / health_score / RUL',
    output: '风险等级与预警处置',
  },
];

const backendCapabilities = [
  {
    group: '接入层',
    title: 'FastAPI REST 与 WebSocket 接入',
    detail: '提供健康检查、业务查询、实时读数接入和长连接读数入口，统一挂载在 /api/v1。',
  },
  {
    group: '训练层',
    title: 'AI4I CSV 训练与模型产物管理',
    detail: '导入历史样本，训练 active 模型，保存模型版本、指标、产物路径和可追溯批次。',
  },
  {
    group: '流式层',
    title: 'MQTT 到 Kafka 后台消费者',
    detail: '订阅 EMQX 机床遥测主题，将标准点位事件写入 Kafka raw topic。',
  },
  {
    group: '治理层',
    title: 'Raw 遥测清洗、校验与幂等',
    detail: '解析原始消息，完成质量校验、事件幂等、异常隔离和 cleaned topic 发布。',
  },
  {
    group: '数据层',
    title: 'TSDB 点位写入与 Redis 快照',
    detail: 'TimescaleDB 保存高频时序点位，Redis 保存设备最新读数、在线状态和最近上报。',
  },
  {
    group: '推理层',
    title: '窗口特征构建与异步推理',
    detail: '基于设备最近点位构建特征窗口，异步计算故障概率、健康评分、RUL 和风险等级。',
  },
  {
    group: '预警层',
    title: '预测日志、预警事件与状态流转',
    detail: '记录预测结果、模型版本和解释字段，高风险设备生成预警并支持确认、处理、关闭。',
  },
  {
    group: '查询层',
    title: '设备台账、模型版本与全厂总览 API',
    detail: '向前端提供设备资产、预测记录、预警列表、模型状态和全厂健康统计。',
  },
];

const operationLoop = [
  {
    title: '设备接入',
    detail: '真实设备主入口是 MQTT；HTTP 与 WebSocket 只作为调试和联调旁路。',
  },
  {
    title: '数据治理',
    detail: '完成幂等、清洗、质量校验、异常隔离和在线快照更新。',
  },
  {
    title: '模型推理',
    detail: '基于窗口特征生成故障概率、健康评分、异常评分和 RUL。',
  },
  {
    title: '预警闭环',
    detail: '高风险设备进入预警中心，保留模型版本、窗口和处置状态。',
  },
];

const riskQueues = [
  { name: '在线设备', value: '持续监测', tone: 'steady' },
  { name: '风险上升', value: '进入关注队列', tone: 'warning' },
  { name: '高风险设备', value: '生成预警事件', tone: 'danger' },
];

const responsibilityStats = [
  ['接入', 'MQTT / HTTP / WebSocket'],
  ['治理', '清洗、校验、幂等'],
  ['计算', '特征窗口与异步推理'],
  ['闭环', '预测、预警、状态流转'],
];

const gatewayFlow = [
  {
    title: '现场协议采集',
    detail: 'CNC、PLC 与传感器不要求直接调用后端 API，由工业网关读取 Modbus、OPC UA、S7、EtherNet/IP 等点位。',
    tag: 'EDGE',
  },
  {
    title: '点位语义标准化',
    detail: '网关统一设备编号、点位编码、单位、质量分数、采集时间和 event_id，避免后端绑定具体厂商协议。',
    tag: 'NORMALIZE',
  },
  {
    title: 'MQTT 发布到 EMQX',
    detail: 'topic 使用 factory/{factory}/workshop/{workshop}/line/{line}/machine/{device_code}/telemetry。',
    tag: 'MQTT',
  },
  {
    title: '后端流式闭环',
    detail: 'mqtt_to_kafka 订阅工厂遥测主题，写入 Kafka raw，再进入清洗、TSDB、Redis、特征窗口、推理和预警。',
    tag: 'BACKEND',
  },
];

const telemetryFields = [
  ['event_id', '网关生成的事件唯一 ID，用于幂等'],
  ['device_code', '设备编号，必须和设备台账一致'],
  ['point_code', '点位编码，例如 spindle_temperature'],
  ['value / unit', '数值与单位，例如 72.6 C'],
  ['quality', '0 到 1 的质量分数，坏点不能伪装成 1'],
  ['ts / gateway_id', '采集时间与来源网关'],
];

const productionReadiness = [
  {
    state: '已具备',
    title: '后端实时计算链路',
    detail: 'MQTT → Kafka raw → 清洗 → TSDB/Redis → 特征窗口 → 推理 → 预测/预警已按后台消费者拆分。',
  },
  {
    state: '已具备',
    title: '标准遥测事件模型',
    detail: 'TelemetryEvent 明确 event_id、device_code、point_code、value、unit、quality、ts、gateway_id。',
  },
  {
    state: '需现场补齐',
    title: '边缘采集适配器',
    detail: '需要工业网关或边缘程序完成 PLC/CNC 协议读取、点位映射、质量判断和 MQTT JSON 发布。',
  },
  {
    state: '需治理',
    title: '设备与点位主数据',
    detail: '需要确定设备编号规则、点位编码规则、单位、采样频率、质量规则和模型特征映射。',
  },
  {
    state: '需运维',
    title: '生产运行保障',
    detail: '需要 EMQX、Kafka、Redis、TSDB、MySQL 的监控、备份、权限、告警和消费者进程守护。',
  },
  {
    state: '需验证',
    title: '模型现场校准',
    detail: 'AI4I 训练链路可用，但真实工厂需要现场历史数据、阈值标定、漂移监测和误报复核。',
  },
];

const SYSTEM_ENTERED_STORAGE_KEY = 'industrial-pdm-system-entered';
const AUTH_TOKEN_STORAGE_KEY = 'industrial-pdm-auth-token';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';

function apiUrl(path: string) {
  return path.startsWith('http') ? path : `${API_BASE_URL}${path}`;
}

export function App() {
  const root = useRef<HTMLElement | null>(null);
  const [entered, setEntered] = useState(() => window.sessionStorage.getItem(SYSTEM_ENTERED_STORAGE_KEY) === 'true');

  const enterSystem = () => {
    window.sessionStorage.setItem(SYSTEM_ENTERED_STORAGE_KEY, 'true');
    setEntered(true);
  };

  const exitSystem = () => {
    window.sessionStorage.removeItem(SYSTEM_ENTERED_STORAGE_KEY);
    setEntered(false);
  };

  useGSAP(
    () => {
      gsap.from('.nav-shell', {
        y: -28,
        opacity: 0,
        duration: 0.9,
        ease: 'power3.out',
      });

      gsap.from('.hero-copy > *', {
        y: 44,
        opacity: 0,
        duration: 1,
        stagger: 0.08,
        ease: 'power4.out',
      });

      gsap.utils.toArray<HTMLElement>('.media-reveal').forEach((item) => {
        gsap.fromTo(
          item,
          { scale: 0.94, opacity: 0.72, filter: 'grayscale(0.8) contrast(1.1) brightness(0.78)' },
          {
            scale: 1,
            opacity: 1,
            filter: 'grayscale(0.28) contrast(1.16) brightness(0.92)',
            ease: 'power2.out',
            scrollTrigger: {
              trigger: item,
              start: 'top 84%',
              end: 'bottom 45%',
              scrub: true,
            },
          },
        );
      });
    },
    { scope: root },
  );

  if (entered) {
    return <SystemConsole onBack={exitSystem} />;
  }

  return (
    <main ref={root} className="landing-shell">
      <Navigation onEnter={enterSystem} />

      <section className="hero-section">
        <div className="hero-bg media-reveal" />
        <div className="hero-wash" />
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="kicker">Industrial IoT Predictive Maintenance</p>
            <h1>
              面向真实工厂的设备故障预测与健康评估系统
              <span
                className="inline-image"
                aria-hidden="true"
                style={{ backgroundImage: 'url(https://picsum.photos/seed/cnc-spindle-sensor/420/220)' }}
              />
            </h1>
            <p className="hero-lead">
              系统围绕工业网关、EMQX、Kafka、时序库、Redis、模型推理和预警闭环构建。它不直接绑定具体厂商设备协议，而是在网关侧完成协议采集与标准遥测转换。
            </p>
            <div className="hero-actions">
              <button className="primary-action" onClick={enterSystem}>
                进入系统工作台
              </button>
              <a className="secondary-action" href="#architecture">
                查看落地架构
              </a>
            </div>
          </div>

          <div className="hero-instrument" aria-label="系统运行链路概览">
            <div className="instrument-head">
              <span>实时链路状态</span>
              <strong>在线推理链路</strong>
              <small>MQTT / Kafka / TSDB / Redis</small>
            </div>
            <div className="instrument-flow">
              {pipeline.map((item, index) => (
                <div className="flow-node" key={item}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{item}</strong>
                </div>
              ))}
            </div>
            <div className="instrument-footer">
              <Pulse size={26} weight="duotone" />
              <span>设备上报后自动形成特征窗口，持续更新健康评分、故障概率、RUL 与预警事件。</span>
            </div>
          </div>
        </div>
      </section>

      <section id="capability" className="chapter section-spacious">
        <div className="chapter-heading">
          <p className="kicker">System Scope</p>
          <h2>不是监控大屏皮肤，而是一条能跑通的工业数据链路。</h2>
        </div>
        <div className="bento-grid">
          {capabilities.map((item) => {
            const Icon = item.icon;
            return (
              <article className={`bento-card ${item.className} media-reveal`} key={item.title}>
                <div
                  className="card-media"
                  style={{ backgroundImage: `url(https://picsum.photos/seed/${item.image}/1200/820)` }}
                />
                <div className="card-content">
                  <Icon size={30} weight="duotone" />
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section id="architecture" className="chapter section-spacious">
        <div className="architecture-spread media-reveal">
          <div className="architecture-copy">
            <p className="kicker">Operational Architecture</p>
            <h2>从一条点位读数，到一次可处理的设备风险。</h2>
            <p>
              本系统不直接绑定具体厂商设备协议，而是在工业网关侧完成 Modbus、OPC UA、S7 等协议采集，并统一转换为 TelemetryEvent 标准遥测事件，通过 MQTT 发布到 EMQX。后端 mqtt_to_kafka 消费器订阅工厂遥测主题，将设备点位写入 Kafka raw topic，后续由清洗、时序入库、Redis 实时快照、特征窗口和异步推理模块完成实时预测与预警闭环。
            </p>
          </div>
          <div className="architecture-flow" aria-label="点位读数到风险处置链路">
            <div className="point-packet">
              <span>POINT EVENT</span>
              <strong>SIM-0007 / vibration_rms</strong>
              <small>value 1.82 mm/s · quality 0.98</small>
            </div>
            <div className="flow-track">
              {systemLayers.map((layer, index) => (
                <article className="flow-stage" key={layer.title}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <h3>{layer.title}</h3>
                  <p>{layer.signal}</p>
                  <strong>{layer.output}</strong>
                </article>
              ))}
            </div>
            <div className="risk-ticket">
              <span>RISK TICKET</span>
              <strong>高风险设备进入预警中心</strong>
              <small>故障概率、健康评分、RUL、解释字段、建议动作同步记录。</small>
            </div>
          </div>
        </div>
      </section>

      <section id="ingress" className="chapter section-spacious">
        <div className="chapter-heading wide-heading">
          <p className="kicker">Production Ingress</p>
          <h2>真实设备不直接接后端 API，接入边界放在工业网关。</h2>
          <p>后端接收的是统一后的 TelemetryEvent，不负责直接适配所有 PLC、CNC、传感器和厂家私有协议。</p>
        </div>
        <div className="gateway-grid media-reveal">
          <div className="gateway-flow-card">
            {gatewayFlow.map((item) => (
              <article className="gateway-step" key={item.title}>
                <span>{item.tag}</span>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
          <div className="telemetry-contract">
            <div className="contract-head">
              <span>TelemetryEvent JSON</span>
              <strong>单点位标准事件</strong>
            </div>
            <pre>{`{
  "event_id": "gateway-line-1-CNC-001-spindle_temperature-20260710153000123",
  "device_code": "CNC-001",
  "point_code": "spindle_temperature",
  "value": 72.6,
  "unit": "C",
  "quality": 0.98,
  "ts": "2026-07-10T15:30:00.123Z",
  "gateway_id": "gateway-line-1"
}`}</pre>
            <div className="field-grid">
              {telemetryFields.map(([field, detail]) => (
                <div key={field}>
                  <strong>{field}</strong>
                  <span>{detail}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="truth-section section-spacious">
        <div className="truth-layout">
          <div className="truth-panel">
            <p className="kicker">Runtime Responsibility</p>
            <h2>后端不是接口集合，而是工厂设备运行态的计算底座。</h2>
            <p>
              它承担接入、训练、治理、存储、推理、预警与查询职责。实时链路的价值不是手动发送 JSON，而是持续识别在线设备、风险上升设备和需要进入预警中心的设备。
            </p>
            <div className="responsibility-meter">
              {responsibilityStats.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{value}</strong>
                </div>
              ))}
            </div>
          </div>

          <div className="operation-board" aria-label="工业运行闭环">
            <div className="operation-board-head">
              <span>工业运行闭环</span>
              <strong>从读数进入到预警处置</strong>
            </div>
            <div className="operation-loop">
              {operationLoop.map((item, index) => (
                <article className="operation-step" key={item.title}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.detail}</p>
                  </div>
                </article>
              ))}
            </div>
            <div className="risk-queue">
              {riskQueues.map((item) => (
                <article className={`risk-chip ${item.tone}`} key={item.name}>
                  <span>{item.name}</span>
                  <strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="chapter section-spacious">
        <div className="chapter-heading wide-heading">
          <p className="kicker">Backend Capability Map</p>
          <h2>后端能力按工业系统职责组织，前端只呈现真实能力。</h2>
          <p>这不是装饰图，而是前端重构时的页面边界：哪些能力能查、哪些能操作、哪些只作为链路状态展示。</p>
        </div>
        <div className="capability-map capability-map--lanes media-reveal">
          {['接入层', '治理层', '推理层', '业务层'].map((lane) => (
            <section className="capability-lane" key={lane}>
              <div className="lane-label">
                <span>{lane}</span>
              </div>
              {backendCapabilities
                .filter((item) => {
                  if (lane === '接入层') return ['接入层', '训练层', '流式层'].includes(item.group);
                  if (lane === '治理层') return ['治理层', '数据层'].includes(item.group);
                  if (lane === '推理层') return ['推理层'].includes(item.group);
                  return ['预警层', '查询层'].includes(item.group);
                })
                .map((item, index) => (
                  <article className="capability-card" key={item.title}>
                    <div className="capability-index">{String(index + 1).padStart(2, '0')}</div>
                    <div>
                      <span>{item.group}</span>
                      <h3>{item.title}</h3>
                      <p>{item.detail}</p>
                    </div>
                  </article>
                ))}
            </section>
          ))}
          <div className="capability-note">
            <Database size={24} weight="duotone" />
            <div>
              <strong>能力边界清晰</strong>
              <p>入口只说明后端已经具备的链路和接口，不把未实现的工单、报表、知识库或 Agent 功能包装成系统能力。</p>
            </div>
          </div>
        </div>
      </section>

      <section id="readiness" className="chapter section-spacious">
        <div className="readiness-board media-reveal">
          <div className="readiness-copy">
            <p className="kicker">Production Gap</p>
            <h2>距离真实工厂落地，差距不在“能不能发消息”，而在现场接入治理。</h2>
            <p>
              当前后端已经具备流式接入、清洗、存储、推理和预警主链路；真正投产前，需要把设备主数据、点位映射、边缘采集、运行保障和模型校准补齐。
            </p>
          </div>
          <div className="readiness-list">
            {productionReadiness.map((item) => (
              <article className="readiness-item" key={item.title}>
                <span>{item.state}</span>
                <h3>{item.title}</h3>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="marquee-section">
        <div className="marquee-row">
          {[...pipeline, ...pipeline].map((item, index) => (
            <span key={`${item}-${index}`}>{item}</span>
          ))}
        </div>
      </section>

      <section className="action-section">
        <div>
          <p className="kicker">Next Workspace</p>
          <h2>入口已准备好。下一步进入正式系统工作台。</h2>
          <p>主系统将围绕实时监测、设备台账、故障预测、预警处置、模型管理和数据接入重建，不保留旧页面的调试式结构。</p>
        </div>
        <button className="primary-action light" onClick={enterSystem}>
          进入系统
        </button>
      </section>

      <footer className="footer">
        <strong>Predictive Fault Health Evaluation System</strong>
        <span>Industrial Internet of Things · Big Data · Equipment Reliability</span>
      </footer>
    </main>
  );
}

function Navigation({ onEnter }: { onEnter: () => void }) {
  return (
    <nav className="nav-shell">
      <a className="brand-mark" href="#top" aria-label="系统入口">
        <Factory size={24} weight="duotone" />
        <span>设备健康评估系统</span>
      </a>
      <div className="nav-links">
        <a href="#architecture">架构</a>
        <a href="#capability">能力</a>
        <a href="#ingress">接入</a>
        <button onClick={onEnter}>进入系统</button>
      </div>
    </nav>
  );
}

type RiskLevel = 'low' | 'medium' | 'high' | 'critical' | string;
type WarningStatus = 'new' | 'acknowledged' | 'processing' | 'resolved' | 'ignored' | string;
type FreshnessState = 'fresh' | 'delayed' | 'stale' | 'expired' | 'unknown' | 'error';

type RealtimeDevice = {
  device_code?: string;
  point_code?: string;
  value?: number | string;
  unit?: string;
  quality?: number;
  ts?: string;
  online?: boolean;
  latest_prediction?: PredictionRecord | null;
  latest_warning?: WarningRecord | null;
};

type RealtimeOverview = {
  devices?: RealtimeDevice[];
  online_total?: number;
  device_total?: number;
  warning_total?: number;
  prediction_total?: number;
};

type WarningRecord = {
  id?: number;
  device_code?: string;
  risk_level?: RiskLevel;
  title?: string;
  detail?: string;
  suggested_action?: string;
  status?: WarningStatus;
  failure_probability?: number;
  health_score?: number;
  created_at?: string;
};

type PredictionRecord = {
  id?: number;
  device_code?: string;
  model_version?: string;
  failure_probability?: number;
  health_score?: number;
  risk_level?: RiskLevel;
  anomaly_score?: number;
  anomaly_reasons?: string;
  quality_score?: number;
  rul_hours?: number;
  created_at?: string;
};

type DeviceRecord = {
  device_code?: string;
  device_name?: string;
  device_type?: string;
  factory?: string;
  workshop?: string;
  production_line?: string;
  status?: string;
  health_score?: number;
  risk_level?: RiskLevel;
  sensor_points?: Array<{ sensor_code?: string; sensor_name?: string; unit?: string; sampling_frequency?: string; protocol?: string; source_address?: string; feature_name?: string; quality_rule?: string; enabled?: boolean; min_value?: number | null; max_value?: number | null }>;
};

type DeviceCatalogPayload = {
  device_code: string;
  device_name: string;
  device_type: string;
  factory: string;
  workshop: string;
  production_line: string;
  status: string;
};

type SensorPointPayload = {
  sensor_name: string;
  unit: string;
  sampling_frequency: string;
  protocol: string;
  source_address: string;
  feature_name: string;
  quality_rule: string;
  min_value: number | null;
  max_value: number | null;
  enabled: boolean;
};

type ActiveModelState = {
  available?: boolean;
  saved_at?: string;
  model_names?: string[];
  path?: string | null;
  manifest_path?: string | null;
};

type ModelMetric = {
  model_name?: string;
  model_type?: string;
  version?: string;
  metric_name?: string;
  metric_value?: number;
  status?: string;
  created_at?: string;
};

type RuntimeDiagnostics = {
  status?: 'ready' | 'degraded' | string;
  ingress?: {
    primary?: string;
    mqtt_topic?: string;
    raw_topic?: string;
    broker?: string;
  };
  dependencies?: Array<{ name?: string; status?: string; detail?: string }>;
  stream_consumers?: Array<{ name?: string; enabled?: boolean; source?: string; target?: string; group_id?: string; responsibility?: string }>;
  active_model?: { available?: boolean; saved_at?: string; model_names?: string[] };
  operations_readiness?: Array<{ area?: string; status?: string; items?: string[] }>;
  production_gaps?: string[];
};

type QualitySummary = {
  window_minutes?: number;
  invalid_topic?: string;
  invalid_trace_status?: string;
  invalid_trace_error?: string | null;
  quality_points?: Array<{
    device_code?: string;
    point_code?: string;
    reading_count?: number;
    average_quality?: number | null;
    min_quality?: number | null;
    last_seen?: string | null;
  }>;
  invalid_events?: Array<{ reason?: string; raw?: unknown; [key: string]: unknown }>;
};

type IngressCatalog = {
  primary_ingress?: string;
  mqtt_topic?: string;
  mqtt_example_topic?: string;
  edge_adapter_contract?: Record<string, string>;
  edge_gateway_mappings?: Array<{
    device_code?: string;
    mqtt_topic?: string;
    factory?: string;
    workshop?: string;
    production_line?: string;
    points?: Array<{
      point_code?: string;
      point_name?: string;
      unit?: string;
      sampling_frequency?: string;
      protocol?: string;
      enabled?: boolean;
      range?: { min?: number | null; max?: number | null };
      source_address?: string;
      feature_name?: string;
      quality_rule?: string;
      target_payload?: Record<string, unknown>;
    }>;
  }>;
  payload_schema?: string[];
  gateway_responsibility?: string[];
  devices?: DeviceRecord[];
  production_gaps?: string[];
};

type SystemData = {
  health?: { status?: string; service?: string };
  realtime?: RealtimeOverview;
  warnings?: WarningRecord[];
  predictions?: PredictionRecord[];
  devices?: DeviceRecord[];
  activeModel?: ActiveModelState;
  models?: ModelMetric[];
  runtimeDiagnostics?: RuntimeDiagnostics;
  ingressCatalog?: IngressCatalog;
  qualitySummary?: QualitySummary;
  simulation?: SimulationState;
};

type SimulationReading = { value?: number; quality?: number; status?: string };
type SimulationDevice = { device_code?: string; mode?: string; readings?: Record<string, SimulationReading> };
type SimulationState = { source?: string; running?: boolean; cycle?: number; mode?: string; devices?: SimulationDevice[] };

type AuthUser = {
  username?: string;
  role?: string;
  auth_disabled?: boolean;
};

type AuditLogRecord = {
  id?: number;
  actor?: string;
  role?: string;
  action?: string;
  resource?: string;
  detail_json?: unknown;
  created_at?: string;
};

type ViewKey = 'ops' | 'simulation' | 'realtime' | 'warnings' | 'predictions' | 'devices' | 'models';

type ApiState = {
  loading: boolean;
  refreshing: boolean;
  mutating: boolean;
  error: string | null;
  failedEndpoints: string[];
  updatedAt: Date | null;
};

const viewLabels: Record<ViewKey, string> = {
  ops: '实时运行工作台',
  simulation: '现场仿真场景',
  realtime: '设备实时监测',
  warnings: '预警处置中心',
  predictions: '预测与健康评估',
  devices: '设备资产',
  models: '模型与数据接入',
};

const menuItems: Array<{ key: ViewKey; label: string; desc: string }> = [
  { key: 'ops', label: '实时运行工作台', desc: '全局态势 / 高风险队列' },
  { key: 'simulation', label: '现场仿真场景', desc: '连续工况 / 质量故障演练' },
  { key: 'realtime', label: '设备实时监测', desc: 'Redis 快照 / TSDB 点位' },
  { key: 'warnings', label: '预警处置中心', desc: '确认 / 处理 / 关闭' },
  { key: 'predictions', label: '预测与健康评估', desc: '故障概率 / 健康评分' },
  { key: 'devices', label: '设备资产', desc: '台账 / 点位 / 状态' },
  { key: 'models', label: '模型与数据接入', desc: '训练 / 回放 / 链路验证' },
];

const warningTransitions: Record<string, Array<{ next: WarningStatus; label: string }>> = {
  new: [
    { next: 'acknowledged', label: '确认' },
    { next: 'ignored', label: '忽略' },
  ],
  acknowledged: [
    { next: 'processing', label: '开始处理' },
    { next: 'resolved', label: '标记解决' },
    { next: 'ignored', label: '忽略' },
  ],
  processing: [
    { next: 'resolved', label: '标记解决' },
    { next: 'ignored', label: '忽略' },
  ],
  resolved: [],
  ignored: [],
};

function SystemConsole({ onBack }: { onBack: () => void }) {
  const [activeView, setActiveView] = useState<ViewKey>('ops');
  const [data, setData] = useState<SystemData>({});
  const [apiState, setApiState] = useState<ApiState>({ loading: true, refreshing: false, mutating: false, error: null, failedEndpoints: [], updatedAt: null });
  const [selectedDevice, setSelectedDevice] = useState<string>('');
  const [operator, setOperator] = useState('系统操作员');
  const [note, setNote] = useState('');
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [authToken, setAuthToken] = useState(() => window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) ?? '');
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [loginForm, setLoginForm] = useState({ username: 'admin', password: '' });

  const authHeader: Record<string, string> = authToken ? { Authorization: `Bearer ${authToken}` } : {};

  async function request<T>(path: string): Promise<T> {
    const response = await fetch(apiUrl(path), { headers: authHeader });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  const loadData = async (mode: 'initial' | 'refresh' = 'refresh') => {
    setApiState((current) => ({ ...current, loading: mode === 'initial', refreshing: mode === 'refresh', error: null }));
    try {
      const [health, realtime, warnings, predictions, devices, activeModel, models, ingressCatalog, qualitySummary, simulation] = await Promise.allSettled([
        request<{ status?: string; service?: string }>('/api/v1/health'),
        request<RealtimeOverview>('/api/v1/realtime/overview'),
        request<WarningRecord[]>('/api/v1/warnings?limit=100'),
        request<PredictionRecord[]>('/api/v1/predictions?limit=100'),
        request<DeviceRecord[]>('/api/v1/devices'),
        request<ActiveModelState>('/api/v1/models/active'),
        request<ModelMetric[]>('/api/v1/models'),
        request<IngressCatalog>('/api/v1/ingress/catalog'),
        request<QualitySummary>('/api/v1/quality/summary'),
        request<SimulationState>('/api/v1/simulation/state'),
      ]);

      setData((current) => ({
        health: settledValue(health) ?? current.health,
        realtime: settledValue(realtime) ?? current.realtime,
        warnings: settledValue(warnings) ?? current.warnings,
        predictions: settledValue(predictions) ?? current.predictions,
        devices: settledValue(devices) ?? current.devices,
        activeModel: settledValue(activeModel) ?? current.activeModel,
        models: settledValue(models) ?? current.models,
        ingressCatalog: settledValue(ingressCatalog) ?? current.ingressCatalog,
        qualitySummary: settledValue(qualitySummary) ?? current.qualitySummary,
        simulation: settledValue(simulation) ?? current.simulation,
      }));

      const endpointResults = [
        { label: '健康检查', path: '/api/v1/health', result: health },
        { label: '实时总览', path: '/api/v1/realtime/overview', result: realtime },
        { label: '预警列表', path: '/api/v1/warnings?limit=100', result: warnings },
        { label: '预测记录', path: '/api/v1/predictions?limit=100', result: predictions },
        { label: '设备台账', path: '/api/v1/devices', result: devices },
        { label: 'active 模型状态', path: '/api/v1/models/active', result: activeModel },
        { label: '模型指标', path: '/api/v1/models', result: models },
        { label: '接入目录', path: '/api/v1/ingress/catalog', result: ingressCatalog },
        { label: '点位质量与异常追踪', path: '/api/v1/quality/summary', result: qualitySummary },
        { label: '现场仿真场景', path: '/api/v1/simulation/state', result: simulation },
      ];
      const failedEndpoints = endpointResults
        .filter((item) => item.result.status === 'rejected')
        .map((item) => `${item.label} ${item.path}`);
      setApiState({
        loading: false,
        refreshing: false,
        mutating: false,
        error: failedEndpoints.length > 0 ? `${failedEndpoints.length} 个后端接口未连通：${failedEndpoints.join('；')}。为保证生产数据保真，相关模块不展示任何模拟数据。` : null,
        failedEndpoints,
        updatedAt: new Date(),
      });
    } catch (error) {
      setApiState({
        loading: false,
        refreshing: false,
        mutating: false,
        error: error instanceof Error ? error.message : '系统数据加载失败',
        failedEndpoints: [],
        updatedAt: new Date(),
      });
    }
  };

  const loadDiagnostics = async () => {
    try {
      const diagnostics = await request<RuntimeDiagnostics>('/api/v1/runtime/diagnostics');
      setData((current) => ({ ...current, runtimeDiagnostics: diagnostics }));
    } catch (error) {
      setData((current) => ({
        ...current,
        runtimeDiagnostics: {
          status: 'error',
          production_gaps: [error instanceof Error ? error.message : '生产运行诊断接口不可用'],
        },
      }));
    }
  };

  const login = async () => {
    setActionMessage('正在登录生产工作台...');
    try {
      const response = await fetch(apiUrl('/api/v1/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json() as { access_token?: string; role?: string };
      const token = result.access_token ?? '';
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
      setAuthToken(token);
      setAuthUser({ username: loginForm.username, role: result.role ?? 'admin' });
      setActionMessage(`已登录：${loginForm.username}`);
      setLoginForm((current) => ({ ...current, password: '' }));
      await loadData('refresh');
    } catch (error) {
      setActionMessage(error instanceof Error ? `登录失败：${error.message}` : '登录失败');
    }
  };

  const logout = () => {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    setAuthToken('');
    setAuthUser(null);
    setActionMessage('已退出登录');
  };

  const loadCurrentUser = async () => {
    try {
      const user = await request<AuthUser>('/api/v1/auth/me');
      setAuthUser(user);
    } catch {
      if (authToken) {
        window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        setAuthToken('');
      }
      setAuthUser(null);
    }
  };

  const loadAuditLogs = async () => {
    if (!authToken) {
      setAuditLogs([]);
      return;
    }
    try {
      const logs = await request<AuditLogRecord[]>('/api/v1/auth/audit?limit=50');
      setAuditLogs(logs);
    } catch {
      setAuditLogs([]);
    }
  };

  useEffect(() => {
    void loadData('initial');
    void loadDiagnostics();
    void loadCurrentUser();
    void loadAuditLogs();
    const realtimeTimer = window.setInterval(() => void loadData('refresh'), 3000);
    const diagnosticsTimer = window.setInterval(() => void loadDiagnostics(), 15000);
    return () => {
      window.clearInterval(realtimeTimer);
      window.clearInterval(diagnosticsTimer);
    };
  }, []);

  useEffect(() => {
    void loadCurrentUser();
    void loadAuditLogs();
  }, [authToken]);

  const devices = data.realtime?.devices ?? [];
  const warnings = data.warnings ?? [];
  const predictions = data.predictions ?? [];
  const assets = data.devices ?? [];
  const models = data.models ?? [];
  const selectedRealtimeDevice = devices.find((device) => device.device_code === selectedDevice) ?? devices[0];
  const criticalWarnings = warnings.filter((warning) => ['critical', 'high'].includes(String(warning.risk_level)) && !['resolved', 'ignored'].includes(String(warning.status)));
  const worstFreshness = getWorstFreshness(devices);

  const summary = useMemo(
    () => ({
      onlineTotal: data.realtime?.online_total ?? devices.filter((device) => device.online).length,
      deviceTotal: data.realtime?.device_total ?? Math.max(devices.length, assets.length),
      warningTotal: data.realtime?.warning_total ?? warnings.length,
      predictionTotal: data.realtime?.prediction_total ?? predictions.length,
      criticalTotal: criticalWarnings.length,
    }),
    [assets.length, criticalWarnings.length, data.realtime, devices, predictions.length, warnings.length],
  );

  const transitionWarning = async (warning: WarningRecord, status: WarningStatus) => {
    if (!warning.id) return;
    setActionMessage(`正在提交预警 ${warning.id} 状态变更...`);
    try {
      const response = await fetch(apiUrl(`/api/v1/warnings/${warning.id}/status`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify({ status, operator, note }),
      });
      if (!response.ok) {
        throw new Error(response.status === 409 ? '当前预警状态已变化，操作不再允许，正在刷新。' : await response.text());
      }
      setActionMessage(`预警 ${warning.id} 已更新为 ${status}`);
      setNote('');
      void loadData('refresh');
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : '预警状态更新失败');
      void loadData('refresh');
    }
  };

  const trainAi4iModel = async (file: File, replayDemoData: boolean) => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    setActionMessage(`正在训练模型：${file.name}`);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('replay_demo_data', String(replayDemoData));
      const response = await fetch(apiUrl('/api/v1/ingestion/ai4i'), {
        method: 'POST',
        headers: authHeader,
        body: formData,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json() as {
        mode?: string;
        imported_rows?: number;
        trained_rows?: number;
        prediction_count?: number;
        warning_count?: number;
      };
      setActionMessage(
        `模型训练完成：训练 ${result.trained_rows ?? result.imported_rows ?? 0} 行，模式 ${result.mode ?? '-'}，预测 ${result.prediction_count ?? 0} 条，预警 ${result.warning_count ?? 0} 条。`,
      );
      await loadData('refresh');
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '模型训练失败' }));
      setActionMessage(error instanceof Error ? `模型训练失败：${error.message}` : '模型训练失败');
    }
  };

  const resetActiveModel = async () => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    setActionMessage('正在删除 active 模型与训练记录...');
    try {
      const response = await fetch(apiUrl('/api/v1/models/active'), {
        method: 'DELETE',
        headers: authHeader,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json() as {
        status?: string;
        artifact_deleted?: boolean;
        manifest_deleted?: boolean;
      };
      setActionMessage(
        `active 模型已删除：${result.status ?? 'reset'}，模型产物 ${result.artifact_deleted ? '已删除' : '无产物'}，manifest ${result.manifest_deleted ? '已删除' : '无 manifest'}。`,
      );
      await loadData('refresh');
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '删除 active 模型失败' }));
      setActionMessage(error instanceof Error ? `删除 active 模型失败：${error.message}` : '删除 active 模型失败');
    }
  };

  const controlSimulation = async (action: 'start' | 'tick' | 'stop', mode = 'degrading') => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    try {
      const response = await fetch(apiUrl(`/api/v1/simulation/${action}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: action === 'start' ? JSON.stringify({ device_count: 6, mode }) : undefined,
      });
      if (!response.ok) throw new Error(await response.text());
      const simulation = await response.json() as SimulationState;
      setData((current) => ({ ...current, simulation }));
      setActionMessage(`仿真场景${action === 'start' ? '已启动' : action === 'tick' ? '已推进一个采集周期' : '已停止'}。`);
      setApiState((current) => ({ ...current, mutating: false, updatedAt: new Date() }));
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '仿真控制失败' }));
    }
  };

  const saveDevice = async (payload: DeviceCatalogPayload) => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    setActionMessage(`正在保存设备台账：${payload.device_code}`);
    try {
      const response = await fetch(apiUrl('/api/v1/devices'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setActionMessage(`设备台账已保存：${payload.device_code}`);
      await loadData('refresh');
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '设备台账保存失败' }));
      setActionMessage(error instanceof Error ? `设备台账保存失败：${error.message}` : '设备台账保存失败');
    }
  };

  const saveSensorPoint = async (deviceCode: string, sensorCode: string, payload: SensorPointPayload) => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    setActionMessage(`正在保存点位：${deviceCode}/${sensorCode}`);
    try {
      const response = await fetch(apiUrl(`/api/v1/devices/${encodeURIComponent(deviceCode)}/points/${encodeURIComponent(sensorCode)}`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeader },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setActionMessage(`点位已保存：${deviceCode}/${sensorCode}`);
      await loadData('refresh');
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '点位保存失败' }));
      setActionMessage(error instanceof Error ? `点位保存失败：${error.message}` : '点位保存失败');
    }
  };

  const disableSensorPoint = async (deviceCode: string, sensorCode: string) => {
    setApiState((current) => ({ ...current, mutating: true, error: null }));
    setActionMessage(`正在停用点位：${deviceCode}/${sensorCode}`);
    try {
      const response = await fetch(apiUrl(`/api/v1/devices/${encodeURIComponent(deviceCode)}/points/${encodeURIComponent(sensorCode)}`), {
        method: 'DELETE',
        headers: authHeader,
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setActionMessage(`点位已停用：${deviceCode}/${sensorCode}`);
      await loadData('refresh');
    } catch (error) {
      setApiState((current) => ({ ...current, mutating: false, error: error instanceof Error ? error.message : '点位停用失败' }));
      setActionMessage(error instanceof Error ? `点位停用失败：${error.message}` : '点位停用失败');
    }
  };

  return (
    <main className="console-shell">
      <header className="console-topbar">
        <div className="console-brand">
          <Factory size={20} weight="duotone" />
          <div>
            <strong>设备故障预测与健康评估系统</strong>
            <span>Industrial IoT Realtime Console</span>
          </div>
        </div>
        <div className="topbar-status">
          <StatusPill label="后端" value={data.health?.status ?? 'unknown'} tone={data.health?.status === 'ok' ? 'ok' : 'warn'} />
          <StatusPill label="模型" value={data.activeModel?.available ? 'active' : '未训练'} tone={data.activeModel?.available ? 'ok' : 'warn'} />
          <StatusPill label="实时性" value={freshnessLabel(worstFreshness)} tone={freshnessTone(worstFreshness)} />
          <StatusPill label="刷新" value={apiState.updatedAt ? formatClock(apiState.updatedAt) : '--:--:--'} tone="neutral" />
        </div>
        <div className="auth-console">
          {authUser ? (
            <>
              <span>{authUser.auth_disabled ? '开发模式' : `${authUser.username ?? '-'} · ${authUser.role ?? '-'}`}</span>
              {!authUser.auth_disabled && <button onClick={logout}>退出</button>}
            </>
          ) : (
            <>
              <input value={loginForm.username} onChange={(event) => setLoginForm((current) => ({ ...current, username: event.target.value }))} placeholder="账号" />
              <input value={loginForm.password} onChange={(event) => setLoginForm((current) => ({ ...current, password: event.target.value }))} placeholder="密码" type="password" />
              <button disabled={!loginForm.username || !loginForm.password} onClick={() => void login()}>登录</button>
            </>
          )}
        </div>
        <button className="console-exit" onClick={onBack}>返回入口</button>
      </header>

      <div className="console-body">
        <aside className="console-sidebar">
          <div className="sidebar-section-title">系统菜单</div>
          {menuItems.map((item) => (
            <button className={`side-menu-item ${activeView === item.key ? 'active' : ''}`} key={item.key} onClick={() => setActiveView(item.key)}>
              <strong>{item.label}</strong>
              <span>{item.desc}</span>
            </button>
          ))}
          <div className="sidebar-runtime-card">
            <span>实时链路</span>
            <strong>MQTT → Kafka → TSDB/Redis → 推理</strong>
            <p>{apiState.error ?? '轮询运行中，异常预警会在顶部与首页突出。'}</p>
          </div>
        </aside>

        <section className="console-main">
          <div className="breadcrumb-bar">
            <span>首页</span>
            <span>/</span>
            <strong>{viewLabels[activeView]}</strong>
            <button onClick={() => void loadData('refresh')}>{apiState.refreshing ? '刷新中...' : '立即刷新'}</button>
          </div>

          {criticalWarnings.length > 0 && <CriticalAlertBanner warnings={criticalWarnings} onOpen={() => setActiveView('warnings')} />}

          {activeView === 'ops' && <RealtimeOpsView summary={summary} devices={devices} warnings={warnings} predictions={predictions} apiState={apiState} diagnostics={data.runtimeDiagnostics} qualitySummary={data.qualitySummary} auditLogs={auditLogs} onOpenDevice={(code) => { setSelectedDevice(code); setActiveView('realtime'); }} />}
          {activeView === 'simulation' && <SimulationView simulation={data.simulation} busy={apiState.mutating} onControl={controlSimulation} />}
          {activeView === 'realtime' && <RealtimeDevicesView devices={devices} selectedDevice={selectedRealtimeDevice} onSelect={setSelectedDevice} />}
          {activeView === 'warnings' && <WarningCenterView warnings={warnings} operator={operator} note={note} actionMessage={actionMessage} onOperatorChange={setOperator} onNoteChange={setNote} onTransition={transitionWarning} />}
          {activeView === 'predictions' && <PredictionsView predictions={predictions} activeModel={data.activeModel} />}
          {activeView === 'devices' && (
            <DevicesView
              devices={assets}
              busy={apiState.mutating || apiState.refreshing}
              actionMessage={actionMessage}
              onOpenRealtime={(code) => { setSelectedDevice(code); setActiveView('realtime'); }}
              onSaveDevice={saveDevice}
              onSaveSensorPoint={saveSensorPoint}
              onDisableSensorPoint={disableSensorPoint}
            />
          )}
          {activeView === 'models' && (
            <ModelDataView
              activeModel={data.activeModel}
              models={models}
              ingressCatalog={data.ingressCatalog}
              busy={apiState.mutating || apiState.refreshing}
              actionMessage={actionMessage}
              onTrain={trainAi4iModel}
              onReset={resetActiveModel}
            />
          )}
        </section>
      </div>
    </main>
  );
}

function RealtimeOpsView({ summary, devices, warnings, predictions, apiState, diagnostics, qualitySummary, auditLogs, onOpenDevice }: { summary: { onlineTotal: number; deviceTotal: number; warningTotal: number; predictionTotal: number; criticalTotal: number }; devices: RealtimeDevice[]; warnings: WarningRecord[]; predictions: PredictionRecord[]; apiState: ApiState; diagnostics?: RuntimeDiagnostics; qualitySummary?: QualitySummary; auditLogs: AuditLogRecord[]; onOpenDevice: (code: string) => void }) {
  const activeWarnings = warnings.filter((warning) => !['resolved', 'ignored'].includes(String(warning.status))).slice(0, 6);
  return (
    <div className="console-page">
      <section className="metric-row">
        <MetricBox label="在线设备" value={`${summary.onlineTotal}/${summary.deviceTotal}`} note="Redis 在线快照" tone="dark" />
        <MetricBox label="高优先级预警" value={summary.criticalTotal} note="critical / high 未关闭" tone={summary.criticalTotal > 0 ? 'danger' : 'dark'} />
        <MetricBox label="预警总数" value={summary.warningTotal} note="MySQL warning_events" tone="dark" />
        <MetricBox label="预测记录" value={summary.predictionTotal} note="MySQL prediction_logs" tone="dark" />
      </section>

      <section className="console-grid two-one">
        <Panel title="实时设备状态" subtitle="每 3 秒刷新，保留时间戳与新鲜度">
          <table className="console-table compact">
            <thead><tr><th>设备编号</th><th>最新点位</th><th>当前值</th><th>质量</th><th>新鲜度</th><th>风险</th><th>操作</th></tr></thead>
            <tbody>
              {devices.length === 0 && <EmptyTableRow colSpan={7} message="暂无后端实时设备数据。请确认 Redis/TSDB 实时链路已有真实快照。" />}
              {devices.map((device) => (
                <tr key={device.device_code}>
                  <td><strong>{device.device_code}</strong></td>
                  <td>{device.point_code ?? '-'}</td>
                  <td>{formatValue(device.value)} {device.unit}</td>
                  <td>{formatPercent(device.quality)}</td>
                  <td><FreshnessBadge ts={device.ts} /></td>
                  <td><RiskBadge level={device.latest_prediction?.risk_level ?? device.latest_warning?.risk_level ?? 'unknown'} /></td>
                  <td><button className="table-action" onClick={() => onOpenDevice(device.device_code ?? '')}>查看</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <Panel title="待处理预警" subtitle="预警不是历史列表，是当前处置队列">
          <div className="warning-list dense">
            {activeWarnings.length === 0 && <div className="empty-inline">暂无后端真实预警数据。</div>}
            {activeWarnings.map((warning) => <WarningMiniCard key={warning.id} warning={warning} />)}
          </div>
        </Panel>
      </section>

      <section className="console-grid ops-prediction-grid">
        <Panel title="最新预测风险" subtitle="用于解释设备为何进入关注队列">
          <PredictionTable predictions={predictions.slice(0, 6)} />
        </Panel>
        <RuntimeDiagnosticsPanel diagnostics={diagnostics} />
        <QualityTracePanel summary={qualitySummary} />
        <AuditLogPanel logs={auditLogs} />
        <Panel title="链路状态说明" subtitle="区分设备故障与实时链路故障">
          <div className="link-state-box">
            <p>实时工作台读取 `/realtime/overview`、`/warnings` 与 `/predictions`。接口失败时不展示模拟数据；没有后端真实返回的模块保持空态。</p>
            <p>{apiState.error ?? '当前未检测到接口错误。Kafka / Redis / TSDB 如未启动，实时数据可能为空。'}</p>
          </div>
        </Panel>
      </section>
    </div>
  );
}

function SimulationView({ simulation, busy, onControl }: { simulation?: SimulationState; busy: boolean; onControl: (action: 'start' | 'tick' | 'stop', mode?: string) => void }) {
  const devices = simulation?.devices ?? [];
  return (
    <div className="console-page simulation-page">
      <section className="simulation-header">
        <div>
          <span className="simulation-source">本地仿真源</span>
          <h1>现场工况演练</h1>
          <p>此页面运行连续 CNC 工况与传感器故障场景，不代表真实现场设备。启动后可逐周期观察点位、质量状态和劣化趋势。</p>
        </div>
        <div className="simulation-actions">
          <button disabled={busy} onClick={() => onControl('start', 'degrading')}>启动劣化场景</button>
          <button disabled={busy || !simulation?.running} onClick={() => onControl('tick')}>推进一个周期</button>
          <button disabled={busy || !simulation?.running} onClick={() => onControl('stop')}>停止场景</button>
        </div>
      </section>
      <section className="metric-row">
        <MetricBox label="运行状态" value={simulation?.running ? '运行中' : '未启动'} note="独立仿真运行时" tone={simulation?.running ? 'dark' : 'danger'} />
        <MetricBox label="采集周期" value={simulation?.cycle ?? 0} note="每次推进代表一轮采集" tone="dark" />
        <MetricBox label="设备数量" value={devices.length} note="SIM-CNC 虚拟设备" tone="dark" />
        <MetricBox label="当前场景" value={simulation?.mode ?? '未选择'} note="工况和质量故障模型" tone="dark" />
      </section>
      <section className="simulation-device-grid">
        {devices.length === 0 && <div className="simulation-empty">启动场景后将在这里显示连续传感器工况。</div>}
        {devices.map((device) => {
          const readings = device.readings ?? {};
          return <article className="simulation-device" key={device.device_code}>
            <header><strong>{device.device_code}</strong><span>{device.mode}</span></header>
            <dl>
              <div><dt>主轴温度</dt><dd>{formatValue(readings.spindle_temperature?.value)} C</dd></div>
              <div><dt>主轴负载</dt><dd>{formatValue(readings.spindle_load?.value)} %</dd></div>
              <div><dt>振动 RMS</dt><dd>{formatValue(readings.vibration_rms?.value)}</dd></div>
              <div><dt>刀具磨损</dt><dd>{formatValue(readings.tool_wear?.value)} min</dd></div>
            </dl>
            <footer>数据质量 {formatPercent(readings.spindle_temperature?.quality)} · {readings.spindle_temperature?.status ?? '等待采集'}</footer>
          </article>;
        })}
      </section>
    </div>
  );
}

function RuntimeDiagnosticsPanel({ diagnostics }: { diagnostics?: RuntimeDiagnostics }) {
  const dependencies = diagnostics?.dependencies ?? [];
  const consumers = diagnostics?.stream_consumers ?? [];
  const gaps = diagnostics?.production_gaps ?? [];
  const readiness = diagnostics?.operations_readiness ?? [];
  return (
    <Panel title="生产运行诊断" subtitle="每 15 秒检测依赖、消费者、模型与接入配置">
      <div className="runtime-diagnostics">
        <div className="runtime-summary">
          <StatusTag value={diagnostics?.status ?? 'unknown'} />
          <div>
            <strong>主入口：{diagnostics?.ingress?.primary?.toUpperCase() ?? '-'}</strong>
            <span>{diagnostics?.ingress?.broker ?? '-'} · {diagnostics?.ingress?.mqtt_topic ?? '-'}</span>
          </div>
        </div>
        <div className="runtime-check-grid">
          {dependencies.map((item) => (
            <div className="runtime-check" key={item.name}>
              <span>{item.name}</span>
              <StatusTag value={item.status ?? 'unknown'} />
              {item.detail && <small>{item.detail}</small>}
            </div>
          ))}
          {consumers.map((item) => (
            <div className="runtime-check" key={item.name}>
              <span>{item.name}</span>
              <StatusTag value={item.enabled ? 'enabled' : 'disabled'} />
              <small>{item.source ?? '-'} → {item.target ?? '-'}</small>
              {item.group_id && <small>group: {item.group_id}</small>}
              {item.responsibility && <small>{item.responsibility}</small>}
            </div>
          ))}
          <div className="runtime-check">
            <span>active-model</span>
            <StatusTag value={diagnostics?.active_model?.available ? 'available' : 'missing'} />
            {diagnostics?.active_model?.model_names?.length ? <small>{diagnostics.active_model.model_names.join(' / ')}</small> : null}
          </div>
        </div>
        <div className="runtime-gaps">
          {gaps.length === 0 && <div className="empty-inline">当前诊断未发现生产阻断项。</div>}
          {gaps.map((gap) => <p key={gap}>{gap}</p>)}
        </div>
        <div className="readiness-checks">
          {readiness.map((item) => (
            <article className="readiness-check" key={item.area}>
              <div>
                <strong>{item.area}</strong>
                <StatusTag value={item.status ?? 'unknown'} />
              </div>
              {(item.items ?? []).map((entry) => <p key={entry}>{entry}</p>)}
            </article>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function QualityTracePanel({ summary }: { summary?: QualitySummary }) {
  const qualityPoints = summary?.quality_points ?? [];
  const invalidEvents = summary?.invalid_events ?? [];
  return (
    <Panel title="点位质量与异常追踪" subtitle={`最近 ${summary?.window_minutes ?? 60} 分钟；异常来自 Kafka invalid topic`}>
      <div className="quality-trace">
        <div className="quality-head">
          <div>
            <strong>invalid topic</strong>
            <span>{summary?.invalid_topic ?? '-'}</span>
          </div>
          <StatusTag value={summary?.invalid_trace_status ?? 'unknown'} />
        </div>
        {summary?.invalid_trace_error && <div className="quality-error">{summary.invalid_trace_error}</div>}
        <table className="console-table compact">
          <thead><tr><th>设备</th><th>点位</th><th>读数</th><th>平均质量</th><th>最低质量</th><th>最后上报</th></tr></thead>
          <tbody>
            {qualityPoints.length === 0 && <EmptyTableRow colSpan={6} message="暂无 TSDB 点位质量统计。请确认 cleaned 消费者已写入 telemetry_readings。" />}
            {qualityPoints.slice(0, 8).map((point) => (
              <tr key={`${point.device_code}-${point.point_code}`}>
                <td><strong>{point.device_code}</strong></td>
                <td>{point.point_code}</td>
                <td>{point.reading_count ?? 0}</td>
                <td>{formatPercent(point.average_quality ?? undefined)}</td>
                <td>{formatPercent(point.min_quality ?? undefined)}</td>
                <td>{formatDateTime(point.last_seen ?? undefined)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="invalid-event-list">
          <strong>最近异常遥测</strong>
          {invalidEvents.length === 0 && <div className="empty-inline">暂无可读取异常事件。若 invalid topic 不可读，上方会显示 unavailable。</div>}
          {invalidEvents.slice(0, 5).map((event, index) => (
            <article className="invalid-event" key={`${event.reason}-${index}`}>
              <span>{event.reason ?? 'unknown invalid telemetry'}</span>
              <code>{stringifyCompact(event.raw ?? event)}</code>
            </article>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function AuditLogPanel({ logs }: { logs: AuditLogRecord[] }) {
  return (
    <Panel title="操作审计" subtitle="关键生产操作来自 audit_logs，开启鉴权后写操作必须留痕">
      <table className="console-table compact">
        <thead><tr><th>时间</th><th>操作者</th><th>角色</th><th>动作</th><th>资源</th></tr></thead>
        <tbody>
          {logs.length === 0 && <EmptyTableRow colSpan={5} message="暂无可读取审计日志。未登录或后端未开启鉴权时不会展示生产审计记录。" />}
          {logs.slice(0, 8).map((log, index) => (
            <tr key={`${log.id ?? index}-${log.action}`}>
              <td>{formatDateTime(log.created_at)}</td>
              <td><strong>{log.actor ?? '-'}</strong></td>
              <td>{log.role ?? '-'}</td>
              <td>{log.action ?? '-'}</td>
              <td>{log.resource ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

function RealtimeDevicesView({ devices, selectedDevice, onSelect }: { devices: RealtimeDevice[]; selectedDevice?: RealtimeDevice; onSelect: (code: string) => void }) {
  return (
    <div className="console-page">
      <Panel title="设备实时监测" subtitle="以 Redis 最新快照和 TSDB 最近点位为准，重点看时间戳是否过期">
        <table className="console-table">
          <thead><tr><th>设备编号</th><th>在线</th><th>点位</th><th>数值</th><th>质量分数</th><th>上报时间</th><th>新鲜度</th><th>最新风险</th></tr></thead>
          <tbody>
            {devices.length === 0 && <EmptyTableRow colSpan={8} message="暂无后端实时设备数据。请确认 Redis/TSDB 实时链路已有真实快照。" />}
            {devices.map((device) => (
              <tr className={selectedDevice?.device_code === device.device_code ? 'selected' : ''} key={device.device_code} onClick={() => onSelect(device.device_code ?? '')}>
                <td><strong>{device.device_code}</strong></td>
                <td>{device.online ? '在线' : '离线/未知'}</td>
                <td>{device.point_code ?? '-'}</td>
                <td>{formatValue(device.value)} {device.unit}</td>
                <td>{formatPercent(device.quality)}</td>
                <td>{formatDateTime(device.ts)}</td>
                <td><FreshnessBadge ts={device.ts} /></td>
                <td><RiskBadge level={device.latest_prediction?.risk_level ?? device.latest_warning?.risk_level ?? 'unknown'} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <section className="console-grid one-one">
        <Panel title="单设备实时详情" subtitle={selectedDevice?.device_code ?? '未选择设备'}>
          <dl className="detail-list">
            <div><dt>最新点位</dt><dd>{selectedDevice?.point_code ?? '-'}</dd></div>
            <div><dt>最新数值</dt><dd>{formatValue(selectedDevice?.value)} {selectedDevice?.unit}</dd></div>
            <div><dt>质量分数</dt><dd>{formatPercent(selectedDevice?.quality)}</dd></div>
            <div><dt>上报时间</dt><dd>{formatDateTime(selectedDevice?.ts)}</dd></div>
          </dl>
        </Panel>
        <Panel title="最新预测 / 预警" subtitle="定位风险来源">
          <dl className="detail-list">
            <div><dt>风险等级</dt><dd><RiskBadge level={selectedDevice?.latest_prediction?.risk_level ?? selectedDevice?.latest_warning?.risk_level ?? 'unknown'} /></dd></div>
            <div><dt>故障概率</dt><dd>{formatPercent(selectedDevice?.latest_prediction?.failure_probability)}</dd></div>
            <div><dt>健康评分</dt><dd>{selectedDevice?.latest_prediction?.health_score ?? '-'}</dd></div>
            <div><dt>最新预警</dt><dd>{selectedDevice?.latest_warning?.title ?? '暂无'}</dd></div>
          </dl>
        </Panel>
      </section>
    </div>
  );
}

function WarningCenterView({ warnings, operator, note, actionMessage, onOperatorChange, onNoteChange, onTransition }: { warnings: WarningRecord[]; operator: string; note: string; actionMessage: string | null; onOperatorChange: (value: string) => void; onNoteChange: (value: string) => void; onTransition: (warning: WarningRecord, status: WarningStatus) => void }) {
  return (
    <div className="console-page">
      <Panel title="预警处置中心" subtitle="只展示后端状态机允许的操作，不允许任意跳转">
        <div className="action-form-row">
          <label>操作人 <input value={operator} onChange={(event) => onOperatorChange(event.target.value)} /></label>
          <label>备注 <input value={note} onChange={(event) => onNoteChange(event.target.value)} placeholder="可选，最多 500 字" /></label>
          {actionMessage && <span className="action-message">{actionMessage}</span>}
        </div>
        <table className="console-table">
          <thead><tr><th>ID</th><th>设备</th><th>等级</th><th>状态</th><th>标题</th><th>故障概率</th><th>健康评分</th><th>建议动作</th><th>操作</th></tr></thead>
          <tbody>
            {warnings.length === 0 && <EmptyTableRow colSpan={9} message="暂无后端真实预警数据。" />}
            {warnings.map((warning) => (
              <tr key={warning.id}>
                <td>{warning.id}</td>
                <td><strong>{warning.device_code}</strong></td>
                <td><RiskBadge level={warning.risk_level ?? 'unknown'} /></td>
                <td><StatusTag value={warning.status ?? 'unknown'} /></td>
                <td>{warning.title}</td>
                <td>{formatPercent(warning.failure_probability)}</td>
                <td>{warning.health_score ?? '-'}</td>
                <td>{warning.suggested_action ?? '-'}</td>
                <td>
                  <div className="table-actions">
                    {(warningTransitions[String(warning.status)] ?? []).map((action) => <button className="table-action" key={action.next} onClick={() => onTransition(warning, action.next)}>{action.label}</button>)}
                    {(warningTransitions[String(warning.status)] ?? []).length === 0 && <span className="muted-cell">终态</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function PredictionsView({ predictions, activeModel }: { predictions: PredictionRecord[]; activeModel?: ActiveModelState }) {
  return (
    <div className="console-page">
      <Panel title="预测与健康评估" subtitle={activeModel?.available ? `active 模型：${activeModel.model_names?.join(' / ') ?? '已加载'}` : '尚未生成 active 模型'}>
        <PredictionTable predictions={predictions} />
      </Panel>
    </div>
  );
}

function DevicesView({
  devices,
  busy,
  actionMessage,
  onOpenRealtime,
  onSaveDevice,
  onSaveSensorPoint,
  onDisableSensorPoint,
}: {
  devices: DeviceRecord[];
  busy: boolean;
  actionMessage: string | null;
  onOpenRealtime: (code: string) => void;
  onSaveDevice: (payload: DeviceCatalogPayload) => Promise<void>;
  onSaveSensorPoint: (deviceCode: string, sensorCode: string, payload: SensorPointPayload) => Promise<void>;
  onDisableSensorPoint: (deviceCode: string, sensorCode: string) => Promise<void>;
}) {
  const [deviceForm, setDeviceForm] = useState<DeviceCatalogPayload>({
    device_code: '',
    device_name: '',
    device_type: 'CNC',
    factory: 'factory-a',
    workshop: 'machining',
    production_line: 'line-1',
    status: 'online',
  });
  const [pointDeviceCode, setPointDeviceCode] = useState(devices[0]?.device_code ?? '');
  const [sensorCode, setSensorCode] = useState('');
  const [pointForm, setPointForm] = useState({
    sensor_name: '',
    unit: '',
    sampling_frequency: '1s',
    protocol: 'opcua',
    source_address: '',
    feature_name: '',
    quality_rule: 'quality=1 when source status is good; quality=0 when bad',
    min_value: '',
    max_value: '',
    enabled: true,
  });

  useEffect(() => {
    if (!pointDeviceCode && devices[0]?.device_code) {
      setPointDeviceCode(devices[0].device_code);
    }
  }, [devices, pointDeviceCode]);

  const submitDevice = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!deviceForm.device_code.trim()) return;
    void onSaveDevice({
      ...deviceForm,
      device_code: deviceForm.device_code.trim(),
      device_name: deviceForm.device_name.trim() || deviceForm.device_code.trim(),
      device_type: deviceForm.device_type.trim() || 'industrial-machine',
      factory: deviceForm.factory.trim() || 'default',
      workshop: deviceForm.workshop.trim() || 'default',
      production_line: deviceForm.production_line.trim() || 'default',
      status: deviceForm.status.trim() || 'online',
    });
  };

  const submitPoint = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const deviceCode = pointDeviceCode.trim();
    const code = sensorCode.trim();
    if (!deviceCode || !code) return;
    void onSaveSensorPoint(deviceCode, code, {
      sensor_name: pointForm.sensor_name.trim() || code,
      unit: pointForm.unit.trim(),
      sampling_frequency: pointForm.sampling_frequency.trim() || '1s',
      protocol: pointForm.protocol.trim(),
      source_address: pointForm.source_address.trim(),
      feature_name: pointForm.feature_name.trim() || code,
      quality_rule: pointForm.quality_rule.trim(),
      min_value: parseOptionalNumber(pointForm.min_value),
      max_value: parseOptionalNumber(pointForm.max_value),
      enabled: pointForm.enabled,
    });
  };

  const loadDeviceToForm = (device: DeviceRecord) => {
    setDeviceForm({
      device_code: device.device_code ?? '',
      device_name: device.device_name ?? '',
      device_type: device.device_type ?? 'CNC',
      factory: device.factory ?? 'factory-a',
      workshop: device.workshop ?? 'machining',
      production_line: device.production_line ?? 'line-1',
      status: device.status ?? 'online',
    });
    setPointDeviceCode(device.device_code ?? '');
  };

  const loadPointToForm = (device: DeviceRecord, point: NonNullable<DeviceRecord['sensor_points']>[number]) => {
    setPointDeviceCode(device.device_code ?? '');
    setSensorCode(point.sensor_code ?? '');
    setPointForm({
      sensor_name: point.sensor_name ?? '',
      unit: point.unit ?? '',
      sampling_frequency: point.sampling_frequency ?? '1s',
      protocol: point.protocol ?? 'opcua',
      source_address: point.source_address ?? '',
      feature_name: point.feature_name ?? '',
      quality_rule: point.quality_rule ?? 'quality=1 when source status is good; quality=0 when bad',
      min_value: point.min_value == null ? '' : String(point.min_value),
      max_value: point.max_value == null ? '' : String(point.max_value),
      enabled: point.enabled ?? true,
    });
  };

  return (
    <div className="console-page">
      <section className="console-grid one-one">
        <Panel title="设备台账配置" subtitle="维护真实接入链路依赖的设备编号、工厂、车间与产线主数据">
          <form className="catalog-form" onSubmit={submitDevice}>
            <div className="catalog-form-grid">
              <label>设备编号<input value={deviceForm.device_code} onChange={(event) => setDeviceForm((current) => ({ ...current, device_code: event.target.value }))} placeholder="CNC-001" /></label>
              <label>设备名称<input value={deviceForm.device_name} onChange={(event) => setDeviceForm((current) => ({ ...current, device_name: event.target.value }))} placeholder="一号数控机床" /></label>
              <label>设备类型<input value={deviceForm.device_type} onChange={(event) => setDeviceForm((current) => ({ ...current, device_type: event.target.value }))} placeholder="CNC" /></label>
              <label>工厂<input value={deviceForm.factory} onChange={(event) => setDeviceForm((current) => ({ ...current, factory: event.target.value }))} placeholder="factory-a" /></label>
              <label>车间<input value={deviceForm.workshop} onChange={(event) => setDeviceForm((current) => ({ ...current, workshop: event.target.value }))} placeholder="machining" /></label>
              <label>产线<input value={deviceForm.production_line} onChange={(event) => setDeviceForm((current) => ({ ...current, production_line: event.target.value }))} placeholder="line-1" /></label>
              <label>状态<select value={deviceForm.status} onChange={(event) => setDeviceForm((current) => ({ ...current, status: event.target.value }))}><option value="online">online</option><option value="offline">offline</option><option value="maintenance">maintenance</option></select></label>
            </div>
            <div className="catalog-actions">
              <button className="console-primary-action" disabled={busy || !deviceForm.device_code.trim()} type="submit">{busy ? '处理中...' : '保存设备台账'}</button>
            </div>
          </form>
        </Panel>
        <Panel title="传感器点位配置" subtitle="raw 遥测会按设备、点位、单位和值域校验，不在目录内的数据会进入异常隔离">
          <form className="catalog-form" onSubmit={submitPoint}>
            <div className="catalog-form-grid">
              <label>所属设备<select value={pointDeviceCode} onChange={(event) => setPointDeviceCode(event.target.value)}><option value="">选择设备</option>{devices.map((device) => <option key={device.device_code} value={device.device_code}>{device.device_code}</option>)}</select></label>
              <label>点位编码<input value={sensorCode} onChange={(event) => setSensorCode(event.target.value)} placeholder="spindle_temperature" /></label>
              <label>点位名称<input value={pointForm.sensor_name} onChange={(event) => setPointForm((current) => ({ ...current, sensor_name: event.target.value }))} placeholder="主轴温度" /></label>
              <label>单位<input value={pointForm.unit} onChange={(event) => setPointForm((current) => ({ ...current, unit: event.target.value }))} placeholder="C / A / mm/s / rpm" /></label>
              <label>采样频率<input value={pointForm.sampling_frequency} onChange={(event) => setPointForm((current) => ({ ...current, sampling_frequency: event.target.value }))} placeholder="1s" /></label>
              <label>现场协议<select value={pointForm.protocol} onChange={(event) => setPointForm((current) => ({ ...current, protocol: event.target.value }))}><option value="opcua">OPC UA</option><option value="modbus-tcp">Modbus TCP</option><option value="s7">Siemens S7</option><option value="ethernet-ip">EtherNet/IP</option><option value="cnc-vendor">CNC Vendor</option></select></label>
              <label>协议源地址<input value={pointForm.source_address} onChange={(event) => setPointForm((current) => ({ ...current, source_address: event.target.value }))} placeholder="ns=2;s=CNC001.Spindle.Temp / 40001 / DB1.DBD0" /></label>
              <label>模型特征名<input value={pointForm.feature_name} onChange={(event) => setPointForm((current) => ({ ...current, feature_name: event.target.value }))} placeholder="spindle_temperature_mean" /></label>
              <label>质量规则<input value={pointForm.quality_rule} onChange={(event) => setPointForm((current) => ({ ...current, quality_rule: event.target.value }))} placeholder="source bad => quality=0" /></label>
              <label>最小值<input value={pointForm.min_value} onChange={(event) => setPointForm((current) => ({ ...current, min_value: event.target.value }))} inputMode="decimal" placeholder="0" /></label>
              <label>最大值<input value={pointForm.max_value} onChange={(event) => setPointForm((current) => ({ ...current, max_value: event.target.value }))} inputMode="decimal" placeholder="120" /></label>
              <label className="checkbox-row catalog-checkbox"><input checked={pointForm.enabled} type="checkbox" onChange={(event) => setPointForm((current) => ({ ...current, enabled: event.target.checked }))} />启用点位</label>
            </div>
            <div className="catalog-actions">
              <button className="console-primary-action" disabled={busy || !pointDeviceCode.trim() || !sensorCode.trim()} type="submit">{busy ? '处理中...' : '保存点位规则'}</button>
            </div>
          </form>
        </Panel>
      </section>
      {actionMessage && <div className="catalog-message">{actionMessage}</div>}
      <Panel title="设备资产" subtitle="设备台账与点位目录是 MQTT 生产接入、数据质量校验和模型特征映射的基础">
        <table className="console-table">
          <thead><tr><th>设备编号</th><th>设备名称</th><th>类型</th><th>工厂</th><th>车间/产线</th><th>状态</th><th>健康评分</th><th>风险</th><th>传感器点位</th><th>操作</th></tr></thead>
          <tbody>
            {devices.length === 0 && <EmptyTableRow colSpan={10} message="暂无后端真实设备资产数据。" />}
            {devices.map((device) => (
              <tr key={device.device_code}>
                <td><strong>{device.device_code}</strong></td>
                <td>{device.device_name ?? '-'}</td>
                <td>{device.device_type ?? '-'}</td>
                <td>{device.factory ?? '-'}</td>
                <td>{device.workshop ?? '-'} / {device.production_line ?? '-'}</td>
                <td>{device.status ?? '-'}</td>
                <td>{device.health_score ?? '-'}</td>
                <td><RiskBadge level={device.risk_level ?? 'unknown'} /></td>
                <td>
                  <div className="point-chip-list">
                    {(device.sensor_points ?? []).length === 0 && <span className="muted-cell">未配置</span>}
                    {(device.sensor_points ?? []).map((point) => (
                      <span className={`point-chip ${point.enabled === false ? 'disabled' : ''}`} key={`${device.device_code}-${point.sensor_code}`}>
                        <button type="button" onClick={() => loadPointToForm(device, point)}>{point.sensor_code}</button>
                        <small>{point.protocol || '-'} · {point.unit || '-'} · {formatRange(point.min_value, point.max_value)}</small>
                        <small>{point.source_address || '未配置源地址'}</small>
                        {point.enabled === false && <em>停用</em>}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  <div className="table-actions">
                    <button className="table-action" onClick={() => loadDeviceToForm(device)}>编辑台账</button>
                    <button className="table-action" onClick={() => onOpenRealtime(device.device_code ?? '')}>实时详情</button>
                    {(device.sensor_points ?? []).filter((point) => point.enabled !== false).map((point) => (
                      <button
                        className="table-action danger"
                        disabled={busy}
                        key={`${device.device_code}-${point.sensor_code}-disable`}
                        onClick={() => void onDisableSensorPoint(device.device_code ?? '', point.sensor_code ?? '')}
                      >
                        停用 {point.sensor_code}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function ModelDataView({
  activeModel,
  models,
  ingressCatalog,
  busy,
  actionMessage,
  onTrain,
  onReset,
}: {
  activeModel?: ActiveModelState;
  models: ModelMetric[];
  ingressCatalog?: IngressCatalog;
  busy: boolean;
  actionMessage: string | null;
  onTrain: (file: File, replayDemoData: boolean) => Promise<void>;
  onReset: () => Promise<void>;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [replayDemoData, setReplayDemoData] = useState(false);

  const submitTraining = () => {
    if (!selectedFile) return;
    void onTrain(selectedFile, replayDemoData);
  };

  return (
    <div className="console-page">
      <section className="console-grid one-one">
        <Panel title="active 模型状态" subtitle="预测和异步推理依赖 active 模型">
          <dl className="detail-list">
            <div><dt>可用状态</dt><dd>{activeModel?.available ? '可用' : '未初始化'}</dd></div>
            <div><dt>模型名称</dt><dd>{activeModel?.model_names?.join(' / ') ?? '-'}</dd></div>
            <div><dt>保存时间</dt><dd>{formatDateTime(activeModel?.saved_at)}</dd></div>
            <div><dt>模型产物</dt><dd>{activeModel?.path ?? '-'}</dd></div>
          </dl>
        </Panel>
        <Panel title="模型训练与数据接入" subtitle="上传 AI4I CSV 训练 active 模型，可选回放生成预测与预警">
          <div className="model-action-panel">
            <label className="file-drop">
              <span>训练数据 CSV</span>
              <input
                accept=".csv,text/csv"
                type="file"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <strong>{selectedFile?.name ?? '选择 AI4I CSV 文件'}</strong>
            </label>
            <label className="checkbox-row">
              <input checked={replayDemoData} type="checkbox" onChange={(event) => setReplayDemoData(event.target.checked)} />
              训练完成后回放样本数据，生成设备、预测与预警记录
            </label>
            <div className="model-action-buttons">
              <button className="console-primary-action" disabled={!selectedFile || busy} onClick={submitTraining}>
                {busy ? '处理中...' : '训练 active 模型'}
              </button>
              <button className="console-danger-action" disabled={!activeModel?.available || busy} onClick={() => void onReset()}>
                删除已训练模型
              </button>
            </div>
            {actionMessage && <p className="model-action-message">{actionMessage}</p>}
            <p className="model-action-hint">训练接口：POST /api/v1/ingestion/ai4i；删除接口：DELETE /api/v1/models/active。删除会清理训练记录、预测、预警和 active 模型产物。</p>
          </div>
        </Panel>
      </section>
      <section className="console-grid one-one">
        <Panel title="真实设备接入目录" subtitle="生产主入口为 MQTT，HTTP / WebSocket 仅作为联调旁路">
          <div className="ingress-catalog-panel">
            <dl className="detail-list">
              <div><dt>主入口</dt><dd>{ingressCatalog?.primary_ingress?.toUpperCase() ?? '-'}</dd></div>
              <div><dt>MQTT Topic</dt><dd>{ingressCatalog?.mqtt_topic ?? '-'}</dd></div>
              <div><dt>示例 Topic</dt><dd>{ingressCatalog?.mqtt_example_topic ?? '-'}</dd></div>
              <div><dt>字段契约</dt><dd>{ingressCatalog?.payload_schema?.join(' / ') ?? '-'}</dd></div>
              <div><dt>发布模式</dt><dd>{ingressCatalog?.edge_adapter_contract?.publish_mode ?? '-'}</dd></div>
              <div><dt>协议适配</dt><dd>{ingressCatalog?.edge_adapter_contract?.required_protocol_adapter ?? '-'}</dd></div>
            </dl>
            <div className="ingress-rule-list">
              {(ingressCatalog?.gateway_responsibility ?? []).map((item) => <p key={item}>{item}</p>)}
            </div>
          </div>
        </Panel>
        <Panel title="点位治理缺口" subtitle="这些问题会影响真实设备接入和模型特征一致性">
          <div className="runtime-gaps">
            {(ingressCatalog?.production_gaps ?? []).length === 0 && <div className="empty-inline">当前设备点位目录未发现生产阻断项。</div>}
            {(ingressCatalog?.production_gaps ?? []).map((gap) => <p key={gap}>{gap}</p>)}
          </div>
        </Panel>
      </section>
      <Panel title="边缘网关配置包" subtitle="交给网关工程师配置 Modbus / OPC UA / S7 采集映射，发布到对应 MQTT topic">
        <div className="edge-mapping-list">
          {(ingressCatalog?.edge_gateway_mappings ?? []).length === 0 && <div className="empty-inline">暂无边缘网关映射。请先在设备资产页配置设备和点位。</div>}
          {(ingressCatalog?.edge_gateway_mappings ?? []).map((mapping) => (
            <article className="edge-mapping-card" key={mapping.device_code}>
              <header>
                <div>
                  <strong>{mapping.device_code}</strong>
                  <span>{mapping.factory} / {mapping.workshop} / {mapping.production_line}</span>
                </div>
                <code>{mapping.mqtt_topic}</code>
              </header>
              <table className="console-table compact">
                <thead><tr><th>点位</th><th>协议地址</th><th>单位</th><th>频率</th><th>特征映射</th><th>质量规则</th><th>Payload 模板</th></tr></thead>
                <tbody>
                  {(mapping.points ?? []).length === 0 && <EmptyTableRow colSpan={7} message="该设备暂无可发布点位。" />}
                  {(mapping.points ?? []).map((point) => (
                    <tr key={`${mapping.device_code}-${point.point_code}`}>
                      <td><strong>{point.point_code}</strong><br />{point.point_name ?? '-'}</td>
                      <td>{point.protocol ?? '-'}<br /><code>{point.source_address ?? '-'}</code></td>
                      <td>{point.unit ?? '-'}</td>
                      <td>{point.sampling_frequency ?? '-'}</td>
                      <td>{point.feature_name ?? '-'}</td>
                      <td>{point.quality_rule ?? '-'}</td>
                      <td><code>{stringifyCompact(point.target_payload)}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          ))}
        </div>
      </Panel>
      <Panel title="设备点位目录" subtitle="来自设备台账 sensor_points，raw 遥测会按此目录校验设备、点位、单位和值域">
        <table className="console-table compact">
          <thead><tr><th>设备</th><th>点位</th><th>名称</th><th>单位</th><th>值域</th><th>启用</th></tr></thead>
          <tbody>
            {flattenSensorPoints(ingressCatalog?.devices).length === 0 && <EmptyTableRow colSpan={6} message="暂无设备点位目录。真实接入前需要先配置设备与点位主数据。" />}
            {flattenSensorPoints(ingressCatalog?.devices).map((point) => (
              <tr key={`${point.device_code}-${point.sensor_code}`}>
                <td><strong>{point.device_code}</strong></td>
                <td>{point.sensor_code}</td>
                <td>{point.sensor_name ?? '-'}</td>
                <td>{point.unit ?? '-'}</td>
                <td>{formatRange(point.min_value, point.max_value)}</td>
                <td>{point.enabled ? '启用' : '停用'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Panel title="模型指标" subtitle="来自 MySQL model_versions / metrics">
        <table className="console-table compact">
          <thead><tr><th>模型</th><th>类型</th><th>版本</th><th>指标</th><th>值</th><th>状态</th></tr></thead>
          <tbody>
        {models.length === 0 && <EmptyTableRow colSpan={6} message="暂无后端真实模型指标数据。" />}
        {models.map((model, index) => <tr key={`${model.model_name}-${index}`}><td>{model.model_name}</td><td>{model.model_type}</td><td>{model.version}</td><td>{model.metric_name}</td><td>{model.metric_value}</td><td>{model.status}</td></tr>)}
      </tbody>
        </table>
      </Panel>
    </div>
  );
}

function EmptyTableRow({ colSpan, message }: { colSpan: number; message: string }) {
  return (
    <tr>
      <td className="empty-table-cell" colSpan={colSpan}>{message}</td>
    </tr>
  );
}

function flattenSensorPoints(devices?: DeviceRecord[]) {
  return (devices ?? []).flatMap((device) =>
    (device.sensor_points ?? []).map((point) => ({
      ...point,
      device_code: device.device_code,
    })),
  );
}

function formatRange(minValue?: number | null, maxValue?: number | null) {
  if (minValue == null && maxValue == null) return '-';
  return `${minValue ?? '-'} ~ ${maxValue ?? '-'}`;
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function stringifyCompact(value: unknown) {
  if (typeof value === 'string') return value.length > 220 ? `${value.slice(0, 220)}...` : value;
  try {
    const text = JSON.stringify(value);
    return text.length > 220 ? `${text.slice(0, 220)}...` : text;
  } catch {
    return String(value);
  }
}

function PredictionTable({ predictions }: { predictions: PredictionRecord[] }) {
  return (
    <table className="console-table compact">
      <thead><tr><th>ID</th><th>设备</th><th>模型版本</th><th>风险</th><th>故障概率</th><th>健康评分</th><th>异常分数</th><th>数据质量</th><th>RUL</th><th>原因</th></tr></thead>
      <tbody>
        {predictions.length === 0 && <EmptyTableRow colSpan={10} message="暂无后端真实预测结果数据。" />}
        {predictions.map((prediction) => <tr key={prediction.id}><td>{prediction.id}</td><td><strong>{prediction.device_code}</strong></td><td>{prediction.model_version ?? '-'}</td><td><RiskBadge level={prediction.risk_level ?? 'unknown'} /></td><td>{formatPercent(prediction.failure_probability)}</td><td>{prediction.health_score ?? '-'}</td><td>{formatPercent(prediction.anomaly_score)}</td><td>{formatPercent(prediction.quality_score)}</td><td>{prediction.rul_hours ?? '-'} h</td><td>{prediction.anomaly_reasons ?? '-'}</td></tr>)}
      </tbody>
    </table>
  );
}

function CriticalAlertBanner({ warnings, onOpen }: { warnings: WarningRecord[]; onOpen: () => void }) {
  const top = warnings[0];
  return <button className="critical-banner" onClick={onOpen}><ShieldWarning size={20} weight="fill" /><strong>{warnings.length} 条高优先级预警</strong><span>{top?.device_code}：{top?.title}</span><em>进入处置</em></button>;
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return <section className="console-panel"><div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div></div>{children}</section>;
}

function MetricBox({ label, value, note, tone }: { label: string; value: string | number; note: string; tone: 'dark' | 'danger' }) {
  return <article className={`metric-box ${tone}`}><span>{label}</span><strong>{value}</strong><p>{note}</p></article>;
}

function RiskBadge({ level }: { level: RiskLevel }) {
  return <span className={`risk-badge risk-${String(level)}`}>{riskLabel(level)}</span>;
}

function FreshnessBadge({ ts }: { ts?: string }) {
  const state = getFreshness(ts);
  return <span className={`freshness-badge freshness-${state}`}>{freshnessLabel(state)}</span>;
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'warn' | 'neutral' }) {
  return <span className={`status-pill ${tone}`}><small>{label}</small><strong>{value}</strong></span>;
}

function StatusTag({ value }: { value: string }) {
  return <span className={`status-tag status-${value}`}>{warningStatusLabel(value)}</span>;
}

function WarningMiniCard({ warning }: { warning: WarningRecord }) {
  return <article className="warning-mini"><div><RiskBadge level={warning.risk_level ?? 'unknown'} /><StatusTag value={String(warning.status ?? 'unknown')} /></div><strong>{warning.device_code} · {warning.title}</strong><p>{warning.suggested_action ?? warning.detail ?? '等待处置'}</p></article>;
}

function settledValue<T>(result: PromiseSettledResult<T>, fallback?: T): T | undefined {
  return result.status === 'fulfilled' ? result.value : fallback;
}

function getFreshness(ts?: string): FreshnessState {
  if (!ts) return 'unknown';
  const time = new Date(ts).getTime();
  if (Number.isNaN(time)) return 'unknown';
  const diff = Date.now() - time;
  if (diff <= 10_000) return 'fresh';
  if (diff <= 30_000) return 'delayed';
  if (diff <= 120_000) return 'stale';
  return 'expired';
}

function getWorstFreshness(devices: RealtimeDevice[]): FreshnessState {
  if (!devices.length) return 'unknown';
  const rank: Record<FreshnessState, number> = { fresh: 1, delayed: 2, stale: 3, expired: 4, unknown: 5, error: 6 };
  return devices.map((device) => getFreshness(device.ts)).sort((a, b) => rank[b] - rank[a])[0] ?? 'unknown';
}

function freshnessLabel(state: FreshnessState): string {
  return { fresh: '实时正常', delayed: '链路延迟', stale: '实时性不足', expired: '数据过期', unknown: '暂无快照', error: '链路异常' }[state];
}

function freshnessTone(state: FreshnessState): 'ok' | 'warn' | 'neutral' {
  return state === 'fresh' ? 'ok' : state === 'unknown' ? 'neutral' : 'warn';
}

function riskLabel(level: RiskLevel): string {
  return { critical: '严重', high: '高风险', medium: '中风险', low: '低风险', unknown: '未知' }[String(level)] ?? String(level);
}

function warningStatusLabel(value: string): string {
  return { new: '新预警', acknowledged: '已确认', processing: '处理中', resolved: '已解决', ignored: '已忽略' }[value] ?? value;
}

function formatPercent(value?: number): string {
  if (typeof value !== 'number') return '-';
  return `${Math.round(value * 100)}%`;
}

function formatValue(value?: number | string): string {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return value ?? '-';
}

function formatDateTime(value?: string): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false });
}

function formatClock(value: Date): string {
  return value.toLocaleTimeString('zh-CN', { hour12: false });
}
