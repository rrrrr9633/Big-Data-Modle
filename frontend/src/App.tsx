import { useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
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
    text: '支持机床点位以 MQTT 主题进入 EMQX，后端消费者写入 Kafka raw topic；未接物理设备时，模拟设备源也走同一协议链路。',
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
    detail: '机床、网关或模拟设备源发布标准点位事件；生产环境主路径为 MQTT 到 EMQX。',
    signal: 'vibration_rms / spindle_temperature / motor_current',
    output: '标准点位事件',
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
    detail: 'MQTT、HTTP 与 WebSocket 入口统一转换为标准点位事件。',
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

const SYSTEM_ENTERED_STORAGE_KEY = 'industrial-pdm-system-entered';
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

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
              系统围绕机床传感器、EMQX、Kafka、时序库、Redis、模型推理和预警闭环构建，服务对象是设备运维、产线管理和工厂数据平台，而不是接口演示页面。
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
              系统不是把接口结果摆到页面上，而是把设备点位变成可追溯的生产判断：读数进入流式总线，治理后沉淀到时序与业务库，再由模型形成风险、健康评分和处置入口。
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
  sensor_points?: Array<{ sensor_code?: string; sensor_name?: string; unit?: string; enabled?: boolean }>;
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

type SystemData = {
  health?: { status?: string; service?: string };
  realtime?: RealtimeOverview;
  warnings?: WarningRecord[];
  predictions?: PredictionRecord[];
  devices?: DeviceRecord[];
  activeModel?: ActiveModelState;
  models?: ModelMetric[];
};

type ViewKey = 'ops' | 'realtime' | 'warnings' | 'predictions' | 'devices' | 'models';

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
  realtime: '设备实时监测',
  warnings: '预警处置中心',
  predictions: '预测与健康评估',
  devices: '设备资产',
  models: '模型与数据接入',
};

const menuItems: Array<{ key: ViewKey; label: string; desc: string }> = [
  { key: 'ops', label: '实时运行工作台', desc: '全局态势 / 高风险队列' },
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

  async function request<T>(path: string): Promise<T> {
    const response = await fetch(apiUrl(path));
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `${response.status} ${response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  const loadData = async (mode: 'initial' | 'refresh' = 'refresh') => {
    setApiState((current) => ({ ...current, loading: mode === 'initial', refreshing: mode === 'refresh', error: null }));
    try {
      const [health, realtime, warnings, predictions, devices, activeModel, models] = await Promise.allSettled([
        request<{ status?: string; service?: string }>('/api/v1/health'),
        request<RealtimeOverview>('/api/v1/realtime/overview'),
        request<WarningRecord[]>('/api/v1/warnings?limit=100'),
        request<PredictionRecord[]>('/api/v1/predictions?limit=100'),
        request<DeviceRecord[]>('/api/v1/devices'),
        request<ActiveModelState>('/api/v1/models/active'),
        request<ModelMetric[]>('/api/v1/models'),
      ]);

      setData((current) => ({
        health: settledValue(health) ?? current.health,
        realtime: settledValue(realtime) ?? current.realtime,
        warnings: settledValue(warnings) ?? current.warnings,
        predictions: settledValue(predictions) ?? current.predictions,
        devices: settledValue(devices) ?? current.devices,
        activeModel: settledValue(activeModel) ?? current.activeModel,
        models: settledValue(models) ?? current.models,
      }));

      const endpointResults = [
        { label: '健康检查', path: '/api/v1/health', result: health },
        { label: '实时总览', path: '/api/v1/realtime/overview', result: realtime },
        { label: '预警列表', path: '/api/v1/warnings?limit=100', result: warnings },
        { label: '预测记录', path: '/api/v1/predictions?limit=100', result: predictions },
        { label: '设备台账', path: '/api/v1/devices', result: devices },
        { label: 'active 模型状态', path: '/api/v1/models/active', result: activeModel },
        { label: '模型指标', path: '/api/v1/models', result: models },
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

  useEffect(() => {
    void loadData('initial');
    const realtimeTimer = window.setInterval(() => void loadData('refresh'), 3000);
    return () => window.clearInterval(realtimeTimer);
  }, []);

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
        headers: { 'Content-Type': 'application/json' },
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

          {activeView === 'ops' && <RealtimeOpsView summary={summary} devices={devices} warnings={warnings} predictions={predictions} apiState={apiState} onOpenDevice={(code) => { setSelectedDevice(code); setActiveView('realtime'); }} />}
          {activeView === 'realtime' && <RealtimeDevicesView devices={devices} selectedDevice={selectedRealtimeDevice} onSelect={setSelectedDevice} />}
          {activeView === 'warnings' && <WarningCenterView warnings={warnings} operator={operator} note={note} actionMessage={actionMessage} onOperatorChange={setOperator} onNoteChange={setNote} onTransition={transitionWarning} />}
          {activeView === 'predictions' && <PredictionsView predictions={predictions} activeModel={data.activeModel} />}
          {activeView === 'devices' && <DevicesView devices={assets} onOpenRealtime={(code) => { setSelectedDevice(code); setActiveView('realtime'); }} />}
          {activeView === 'models' && (
            <ModelDataView
              activeModel={data.activeModel}
              models={models}
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

function RealtimeOpsView({ summary, devices, warnings, predictions, apiState, onOpenDevice }: { summary: { onlineTotal: number; deviceTotal: number; warningTotal: number; predictionTotal: number; criticalTotal: number }; devices: RealtimeDevice[]; warnings: WarningRecord[]; predictions: PredictionRecord[]; apiState: ApiState; onOpenDevice: (code: string) => void }) {
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

function DevicesView({ devices, onOpenRealtime }: { devices: DeviceRecord[]; onOpenRealtime: (code: string) => void }) {
  return (
    <div className="console-page">
      <Panel title="设备资产" subtitle="资产页只展示设备基础信息，实时判断以实时监测页为准">
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
                <td>{device.sensor_points?.map((point) => point.sensor_code).join('、') || '-'}</td>
                <td><button className="table-action" onClick={() => onOpenRealtime(device.device_code ?? '')}>实时详情</button></td>
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
  busy,
  actionMessage,
  onTrain,
  onReset,
}: {
  activeModel?: ActiveModelState;
  models: ModelMetric[];
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
