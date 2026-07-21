import { useRef } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  ChartLineUp, Database, Factory, GitBranch, Pulse, ShieldWarning, Waveform,
} from '@phosphor-icons/react';

gsap.registerPlugin(ScrollTrigger);

interface Props { onEnter: () => void }

const pipeline = ['机床传感器','EMQX MQTT','Kafka Raw','清洗治理','TSDB / Redis','特征窗口','模型推理','预测预警'];

const capabilities = [
  { title:'工业数据接入', text:'生产主入口是 MQTT。现场 Modbus、OPC UA、S7 等协议由工业网关适配，统一转换为 TelemetryEvent 后发布到 EMQX。', icon:Waveform, image:'industrial-sensors-floor', className:'card-xl' },
  { title:'流式数据治理', text:'原始遥测进入 Kafka 后完成结构解析、幂等控制、质量校验、单位保留与异常消息隔离，避免脏数据直接进入推理链路。', icon:GitBranch, image:'stream-processing-control-room', className:'card-sm' },
  { title:'时序与在线状态', text:'清洗后的点位写入 TimescaleDB；Redis 保存设备最新快照、在线态与最近上报时间，支撑实时监测页面低延迟读取。', icon:Database, image:'time-series-database-rack', className:'card-sm' },
  { title:'模型推理闭环', text:'特征窗口驱动故障概率、健康评分、异常评分、RUL 与风险等级计算，预测结果进入 MySQL 形成可追溯记录。', icon:ChartLineUp, image:'machine-learning-manufacturing', className:'card-sm' },
  { title:'预警与处置记录', text:'高风险设备自动生成预警事件，保留预测记录、特征窗口、模型版本和状态流转，为运维人员提供明确处置入口。', icon:ShieldWarning, image:'industrial-alert-panel', className:'card-sm' },
];

const systemLayers = [
  { title:'采集接入层', signal:'Modbus / OPC UA / S7 → TelemetryEvent', output:'MQTT 标准遥测事件' },
  { title:'流式总线层', signal:'raw → cleaned → features', output:'可回放事件流' },
  { title:'数据资产层', signal:'TSDB / Redis / MySQL', output:'在线状态与可追溯记录' },
  { title:'评估决策层', signal:'failure_probability / health_score / RUL', output:'风险等级与预警处置' },
];

const operationLoop = [
  { title:'设备接入', detail:'真实设备主入口是 MQTT；HTTP 与 WebSocket 只作为调试和联调旁路。' },
  { title:'数据治理', detail:'完成幂等、清洗、质量校验、异常隔离和在线快照更新。' },
  { title:'模型推理', detail:'基于窗口特征生成故障概率、健康评分、异常评分和 RUL。' },
  { title:'预警闭环', detail:'高风险设备进入预警中心，保留模型版本、窗口和处置状态。' },
];

const riskQueues = [
  { name:'在线设备', value:'持续监测', tone:'steady' },
  { name:'风险上升', value:'进入关注队列', tone:'warning' },
  { name:'高风险设备', value:'生成预警事件', tone:'danger' },
];

const responsibilityStats = [
  ['接入','MQTT / HTTP / WebSocket'], ['治理','清洗、校验、幂等'],
  ['计算','特征窗口与异步推理'],     ['闭环','预测、预警、状态流转'],
];

const gatewayFlow = [
  { title:'现场协议采集', detail:'CNC、PLC 与传感器不要求直接调用后端 API，由工业网关读取 Modbus、OPC UA、S7、EtherNet/IP 等点位。', tag:'EDGE' },
  { title:'点位语义标准化', detail:'网关统一设备编号、点位编码、单位、质量分数、采集时间和 event_id，避免后端绑定具体厂商协议。', tag:'NORMALIZE' },
  { title:'MQTT 发布到 EMQX', detail:'topic 使用 factory/{factory}/workshop/{workshop}/line/{line}/machine/{device_code}/telemetry。', tag:'MQTT' },
  { title:'后端流式闭环', detail:'mqtt_to_kafka 订阅工厂遥测主题，写入 Kafka raw，再进入清洗、TSDB、Redis、特征窗口、推理和预警。', tag:'BACKEND' },
];

const telemetryFields = [
  ['event_id','网关生成的事件唯一 ID，用于幂等'],
  ['device_code','设备编号，必须和设备台账一致'],
  ['point_code','点位编码，例如 spindle_temperature'],
  ['value / unit','数值与单位，例如 72.6 C'],
  ['quality','0 到 1 的质量分数，坏点不能伪装成 1'],
  ['ts / gateway_id','采集时间与来源网关'],
];

export function LandingPage({ onEnter }: Props) {
  const root = useRef<HTMLElement | null>(null);

  useGSAP(() => {
    gsap.from('.nav-shell', { y: -28, opacity: 0, duration: 0.9, ease: 'power3.out' });
    gsap.from('.hero-copy > *', { y: 44, opacity: 0, duration: 1, stagger: 0.08, ease: 'power4.out' });
    gsap.utils.toArray<HTMLElement>('.media-reveal').forEach((item) => {
      gsap.fromTo(item,
        { scale: 0.94, opacity: 0.72, filter: 'grayscale(0.8) contrast(1.1) brightness(0.78)' },
        { scale: 1, opacity: 1, filter: 'grayscale(0.28) contrast(1.16) brightness(0.92)',
          ease: 'power2.out',
          scrollTrigger: { trigger: item, start: 'top 84%', end: 'bottom 45%', scrub: true } }
      );
    });
  }, { scope: root });

  return (
    <main ref={root} className="landing-shell">
      <nav className="nav-shell">
        <a className="brand-mark" href="#top"><Factory size={24} weight="duotone" /><span>设备健康评估系统</span></a>
        <div className="nav-links">
          <a href="#architecture">架构</a>
          <a href="#capability">能力</a>
          <a href="#ingress">接入</a>
          <button onClick={onEnter}>进入系统</button>
        </div>
      </nav>

      <section className="hero-section">
        <div className="hero-bg media-reveal" />
        <div className="hero-wash" />
        <div className="hero-grid">
          <div className="hero-copy">
            <p className="kicker">Industrial IoT Predictive Maintenance</p>
            <h1>面向真实工厂的设备故障预测与健康评估系统</h1>
            <p className="hero-lead">系统围绕工业网关、EMQX、Kafka、时序库、Redis、模型推理和预警闭环构建，不直接绑定具体厂商设备协议，而是在网关侧完成协议采集与标准遥测转换。</p>
            <div className="hero-actions">
              <button className="primary-action" onClick={onEnter}>进入系统工作台</button>
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
              {pipeline.map((item, i) => (
                <div className="flow-node" key={item}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
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
                <div className="card-media" style={{ backgroundImage: `url(https://picsum.photos/seed/${item.image}/1200/820)` }} />
                <div className="card-content"><Icon size={30} weight="duotone" /><h3>{item.title}</h3><p>{item.text}</p></div>
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
            <p>本系统不直接绑定具体厂商设备协议，而是在工业网关侧完成协议采集，并统一转换为 TelemetryEvent 标准遥测事件，通过 MQTT 发布到 EMQX。</p>
          </div>
          <div className="architecture-flow">
            <div className="point-packet">
              <span>POINT EVENT</span>
              <strong>SIM-0007 / vibration_rms</strong>
              <small>value 1.82 mm/s · quality 0.98</small>
            </div>
            <div className="flow-track">
              {systemLayers.map((layer, i) => (
                <article className="flow-stage" key={layer.title}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
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
        </div>
        <div className="gateway-grid media-reveal">
          <div className="gateway-flow-card">
            {gatewayFlow.map((item) => (
              <article className="gateway-step" key={item.title}>
                <span>{item.tag}</span><h3>{item.title}</h3><p>{item.detail}</p>
              </article>
            ))}
          </div>
          <div className="telemetry-contract">
            <div className="contract-head"><span>TelemetryEvent JSON</span><strong>单点位标准事件</strong></div>
            <pre>{`{\n  "event_id": "gw-line1-CNC-001-spindle_temp-20260710153000",\n  "device_code": "CNC-001",\n  "point_code": "spindle_temperature",\n  "value": 72.6, "unit": "C", "quality": 0.98,\n  "ts": "2026-07-10T15:30:00.123Z",\n  "gateway_id": "gateway-line-1"\n}`}</pre>
            <div className="field-grid">
              {telemetryFields.map(([f, d]) => <div key={f}><strong>{f}</strong><span>{d}</span></div>)}
            </div>
          </div>
        </div>
      </section>

      <section className="truth-section section-spacious">
        <div className="truth-layout">
          <div className="truth-panel">
            <p className="kicker">Runtime Responsibility</p>
            <h2>后端不是接口集合，而是工厂设备运行态的计算底座。</h2>
            <p>它承担接入、训练、治理、存储、推理、预警与查询职责。</p>
            <div className="responsibility-meter">
              {responsibilityStats.map(([l, v]) => <div key={l}><span>{l}</span><strong>{v}</strong></div>)}
            </div>
          </div>
          <div className="operation-board">
            <div className="operation-board-head"><span>工业运行闭环</span><strong>从读数进入到预警处置</strong></div>
            <div className="operation-loop">
              {operationLoop.map((item, i) => (
                <article className="operation-step" key={item.title}>
                  <span>{String(i + 1).padStart(2, '0')}</span>
                  <div><h3>{item.title}</h3><p>{item.detail}</p></div>
                </article>
              ))}
            </div>
            <div className="risk-queue">
              {riskQueues.map((item) => (
                <article className={`risk-chip ${item.tone}`} key={item.name}>
                  <span>{item.name}</span><strong>{item.value}</strong>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="action-section">
        <div>
          <p className="kicker">Next Workspace</p>
          <h2>入口已准备好。下一步进入正式系统工作台。</h2>
          <p>主系统将围绕实时监测、设备台账、故障预测、预警处置、模型管理和数据接入重建。</p>
        </div>
        <button className="primary-action light" onClick={onEnter}>进入系统</button>
      </section>

      <footer className="footer">
        <strong>Predictive Fault Health Evaluation System</strong>
        <span>Industrial Internet of Things · Big Data · Equipment Reliability</span>
      </footer>
    </main>
  );
}