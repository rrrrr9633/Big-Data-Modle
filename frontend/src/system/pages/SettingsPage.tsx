import { useEffect, useState } from 'react';
import { ModelPage } from './ModelPage';
import { api } from '../api/client';
import type { SimulationMode, SimulationState, SimulationTransport } from '../api/client';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

export function SettingsPage({ mock }: Props) {
  const [simMode, setSimMode] = useState<SimulationMode>('degrading');
  const [transport, setTransport] = useState<SimulationTransport>('local');
  const [deviceCount, setDeviceCount] = useState(6);
  const [running, setRunning] = useState(false);
  const [loadingState, setLoadingState] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('正在读取后端仿真状态…');
  const [stateError, setStateError] = useState(false);

  const syncSimulationState = (state: SimulationState) => {
    setSimMode(state.mode);
    setTransport(state.transport);
    setDeviceCount(state.device_count);
    setRunning(state.running);
  };

  useEffect(() => {
    let active = true;
    api.simulationState()
      .then(state => {
        if (!active) return;
        syncSimulationState(state);
        setFeedback(state.running ? `仿真运行中 · 已发布 ${state.accepted_events} 条事件` : '仿真当前已停止');
        setStateError(false);
      })
      .catch(error => {
        if (!active) return;
        setFeedback(`无法读取后端仿真状态：${String(error)}`);
        setStateError(true);
      })
      .finally(() => {
        if (active) setLoadingState(false);
      });
    return () => { active = false; };
  }, []);

  const applySimulation = async () => {
    setSaving(true);
    setFeedback('正在应用配置并启动仿真…');
    setStateError(false);
    try {
      const state = await api.startSimulation({ mode: simMode, device_count: deviceCount, transport });
      syncSimulationState(state);
      mock.markSimulationStarted();
      setFeedback(`配置已由后端确认 · ${state.pipeline} · ${state.device_count} 台设备`);
    } catch (error) {
      setFeedback(`配置未生效：${String(error)}`);
      setStateError(true);
    } finally {
      setSaving(false);
    }
  };

  const stopSimulation = async () => {
    setSaving(true);
    setFeedback('正在停止仿真…');
    setStateError(false);
    try {
      const state = await api.stopSimulation();
      syncSimulationState(state);
      mock.markSimulationStopped();
      setFeedback('仿真已由后端停止，当前配置已保留');
    } catch (error) {
      setFeedback(`停止失败：${String(error)}`);
      setStateError(true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">系统设置</h1>
      <p className="sys-page-sub">仿真数据源配置、模型管理与 AI 接口预留</p>

      <div className="sys-grid-2">
        <div className="sys-panel">
          <div className="sys-panel-head"><h2 className="sys-panel-title">仿真数据源</h2></div>
          <div className="sys-panel-body sys-stack">
            <div className="sys-form-row">
              <span className="sys-label">运行链路</span>
              <select
                className="sys-select"
                value={transport}
                disabled={loadingState || saving}
                onChange={e => setTransport(e.target.value as SimulationTransport)}
              >
                <option value="local">本地设备流（无需 MQTT）</option>
                <option value="mqtt">完整链路（MQTT / Kafka）</option>
              </select>
            </div>
            <div className="simulation-transport-note">
              {transport === 'local'
                ? '设备数据直接进入后端进程内快照，MQTT、Kafka、Redis、TSDB 不可用时仍可运行。'
                : '设备数据经 MQTT、Kafka 和后端消费者处理；启动前会校验完整链路配置。'}
            </div>
            <div className="sys-form-row">
              <span className="sys-label">仿真模式</span>
              <select
                className="sys-select"
                value={simMode}
                disabled={loadingState || saving}
                onChange={e => setSimMode(e.target.value as SimulationMode)}
              >
                <option value="normal">正常运行</option>
                <option value="degrading">渐进退化</option>
                <option value="sudden_fault">突发故障</option>
                <option value="sensor_stuck">传感器卡死</option>
                <option value="sensor_drift">传感器漂移</option>
              </select>
            </div>
            <div className="sys-form-row">
              <span className="sys-label">设备数量</span>
              <input
                className="sys-input"
                type="number"
                min={1}
                max={24}
                value={deviceCount}
                disabled={loadingState || saving}
                onChange={e => setDeviceCount(Math.min(24, Math.max(1, Number(e.target.value) || 1)))}
                style={{ width: 80 }}
              />
            </div>
            <div className="sys-form-row simulation-actions">
              <button
                type="button"
                className="sys-btn sys-btn-primary"
                disabled={loadingState || saving || stateError}
                onClick={applySimulation}
              >
                {saving ? '处理中…' : running ? '应用配置并重启' : '应用配置并启动'}
              </button>
              {running && (
                <button
                  type="button"
                  className="sys-btn sys-btn-danger"
                  disabled={saving}
                  onClick={stopSimulation}
                >
                  停止仿真
                </button>
              )}
            </div>
            <div className={`simulation-feedback${stateError ? ' error' : ''}`} role="status">
              <strong>{stateError ? '后端未确认' : running ? '后端运行中' : '后端已停止'}</strong>
              <span>{feedback}</span>
            </div>
            <div className="simulation-source-note">
              当前链路：{transport === 'local'
                ? 'AI4I 2020 特征分布 → 本地设备流 → 后端进程内快照'
                : 'AI4I 2020 特征分布 → 本地设备流 → MQTT → Kafka → 后端处理链路'}
            </div>
          </div>
        </div>

        <div className="sys-panel">
          <div className="sys-panel-head"><h2 className="sys-panel-title">AI 智能助手接口（预留）</h2></div>
          <div className="sys-panel-body sys-stack">
            <div style={{ fontSize: 13, color: 'var(--sys-muted)', lineHeight: 1.7 }}>
              系统已预留 AI 对话接口 <code style={{ color: 'var(--sys-cyan)' }}>POST /api/v1/ai/chat</code>，
              后续接入大模型后即可在侧边栏「AI 智能助手」按钮启用，
              用于自然语言查询设备状态、生成巡检建议、解释预测结果。
            </div>
            <div className="sys-form-row">
              <span className="sys-label">接口状态</span>
              <span className="sys-badge sys-badge-offline">未接入</span>
            </div>
            <div className="sys-form-row">
              <span className="sys-label">预留能力</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--sys-muted)', lineHeight: 1.8 }}>
              <li>自然语言设备状态查询</li>
              <li>预测结果智能解释（对接 SHAP 特征归因）</li>
              <li>巡检 / 维护建议生成</li>
              <li>预警自动分级与处置推荐</li>
            </ul>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 14 }}>
        <ModelPage />
      </div>
    </div>
  );
}