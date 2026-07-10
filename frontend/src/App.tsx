import { useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  ActivityIcon,
  ChartLineUp,
  Database,
  Factory,
  Gauge,
  GitBranch,
  HardDrives,
  Pulse,
  ShieldWarning,
  Stack,
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
  },
  {
    title: '流式数据治理',
    text: '原始遥测进入 Kafka 后完成结构解析、幂等控制、质量校验、单位保留与异常消息隔离，避免脏数据直接进入推理链路。',
    icon: GitBranch,
  },
  {
    title: '时序与在线状态',
    text: '清洗后的点位写入 TimescaleDB；Redis 保存设备最新快照、在线态与最近上报时间，支撑实时监测页面低延迟读取。',
    icon: Database,
  },
  {
    title: '模型推理闭环',
    text: '特征窗口驱动故障概率、健康评分、异常评分、RUL 与风险等级计算，预测结果进入 MySQL 形成可追溯记录。',
    icon: ChartLineUp,
  },
  {
    title: '预警与处置记录',
    text: '高风险设备自动生成预警事件，保留预测记录、特征窗口、模型版本和状态流转，为运维人员提供明确处置入口。',
    icon: ShieldWarning,
  },
];

const systemLayers = [
  { title: '采集接入层', detail: '机床、网关或模拟设备源发布标准点位事件；生产环境主路径为 MQTT 到 EMQX。' },
  { title: '流式总线层', detail: 'Kafka 承接 raw、cleaned、features、predictions 与 warnings topic，解耦采集、清洗、窗口与推理。' },
  { title: '数据资产层', detail: 'TimescaleDB 保存高频点位，Redis 保存在线快照，MySQL 保存设备、预测、预警和模型资产。' },
  { title: '评估决策层', detail: '根据窗口特征形成故障概率、健康评分、RUL、异常原因与维护建议。' },
];

const backendCapabilities = [
  ['接入层', 'FastAPI REST 与 WebSocket 接入'],
  ['训练层', 'AI4I CSV 训练与模型产物管理'],
  ['流式层', 'MQTT 到 Kafka 后台消费者'],
  ['治理层', 'Raw 遥测清洗、校验与幂等'],
  ['数据层', 'TSDB 点位写入与 Redis 快照'],
  ['推理层', '窗口特征构建与异步推理'],
  ['预警层', '预测日志、预警事件与状态流转'],
  ['查询层', '设备台账、模型版本与全厂总览 API'],
];

export function App() {
  const root = useRef<HTMLElement | null>(null);
  const [entered, setEntered] = useState(false);

  useGSAP(
    () => {
      gsap.from('.nav-shell', { y: -28, opacity: 0, duration: 0.8, ease: 'power3.out' });
      gsap.from('.hero-copy > *', { y: 36, opacity: 0, duration: 0.9, stagger: 0.07, ease: 'power4.out' });
      gsap.utils.toArray<HTMLElement>('.media-reveal').forEach((item) => {
        gsap.fromTo(
          item,
          { opacity: 0.65, y: 22 },
          {
            opacity: 1,
            y: 0,
            duration: 0.7,
            ease: 'power2.out',
            scrollTrigger: { trigger: item, start: 'top 86%' },
          },
        );
      });
    },
    { scope: root },
  );

  if (entered) {
    return <SystemPlaceholder onBack={() => setEntered(false)} />;
  }

  return (
    <main ref={root} className="landing-shell">
      <Navigation onEnter={() => setEntered(true)} />

      <section className="hero-section">
        <div className="hero-bg media-reveal" />
        <div className="hero-wash" />
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="kicker">Industrial IoT Predictive Maintenance</p>
            <h1>面向真实工厂的设备故障预测与健康评估系统</h1>
            <p className="hero-lead">
              系统围绕机床传感器、EMQX、Kafka、时序库、Redis、模型推理和预警闭环构建，服务对象是设备运维、产线管理和工厂数据平台，而不是接口演示页面。
            </p>
            <div className="hero-actions">
              <button className="primary-action" onClick={() => setEntered(true)}>进入系统工作台</button>
              <a className="secondary-action" href="#architecture">查看落地架构</a>
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
              <article className="bento-card media-reveal" key={item.title}>
                <Icon size={30} weight="duotone" />
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section id="architecture" className="chapter section-spacious">
        <div className="chapter-heading">
          <p className="kicker">Operational Architecture</p>
          <h2>从一条点位读数，到一次可处理的设备风险。</h2>
        </div>
        <div className="layer-rail">
          {systemLayers.map((layer, index) => (
            <article className="layer-card media-reveal" key={layer.title}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <h3>{layer.title}</h3>
              <p>{layer.detail}</p>
            </article>
          ))}
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
          </div>
          <div className="operation-board">
            {backendCapabilities.map(([group, title], index) => (
              <article key={title}>
                <span>{String(index + 1).padStart(2, '0')} · {group}</span>
                <strong>{title}</strong>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="action-section">
        <div>
          <p className="kicker">Next Workspace</p>
          <h2>入口已准备好。下一步进入正式系统工作台。</h2>
          <p>主系统将围绕实时监测、设备台账、故障预测、预警处置、模型管理和数据接入重建，不保留旧页面的调试式结构。</p>
        </div>
        <button className="primary-action light" onClick={() => setEntered(true)}>进入系统</button>
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

function SystemPlaceholder({ onBack }: { onBack: () => void }) {
  return (
    <main className="placeholder-shell">
      <section className="placeholder-panel">
        <Stack size={48} weight="duotone" />
        <p className="kicker">Workspace reserved</p>
        <h1>主系统工作台将在下一步重建。</h1>
        <p>这里将接入真实后端 API：健康检查、总览、实时监测、设备台账、预测记录、预警处置、模型版本和数据接入。</p>
        <div className="placeholder-grid">
          <span><Gauge size={22} /> 实时监测</span>
          <span><HardDrives size={22} /> 设备台账</span>
          <span><ActivityIcon size={22} /> 故障预测</span>
        </div>
        <button className="secondary-action dark" onClick={onBack}>返回入口</button>
      </section>
    </main>
  );
}
