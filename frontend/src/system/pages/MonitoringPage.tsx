import { useEffect, useState } from 'react';
import { HealthGauge, LineChart } from '../components/Charts';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

const RISK_COLOR: Record<string, string> = {
  critical: 'var(--sys-danger)', high: 'var(--sys-warning)',
  medium: '#facc15', low: 'var(--sys-success)',
};

const SENSOR_STATUS_LABEL: Record<string, string> = {
  sensor_stuck: '传感器卡死',
  sensor_drift: '传感器漂移',
  sudden_fault: '突发故障',
  fault_emerging: '故障演变中',
};

export function MonitoringPage({ mock }: Props) {
  const { devices } = mock;
  const [selected, setSelected] = useState(devices[0]?.device_code ?? '');
  const device = devices.find(d => d.device_code === selected) ?? devices[0];

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">实时监测</h1>
      <p className="sys-page-sub">设备传感器实时数据 · 每3秒刷新</p>

      <div className="sys-grid-1-2">
        {/* Device list */}
        <div className="sys-panel">
          <div className="sys-panel-head">
            <h2 className="sys-panel-title">设备列表</h2>
          </div>
          <div className="monitoring-device-list" style={{ padding: '6px 0' }}>
            {devices.map(d => (
              <button
                key={d.device_code}
                onClick={() => setSelected(d.device_code)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, width: '100%',
                  padding: '10px 16px', border: 0, borderBottom: '1px solid var(--sys-border)',
                  background: selected === d.device_code ? 'rgba(61,130,255,0.1)' : 'transparent',
                  color: 'var(--sys-text)', cursor: 'pointer', textAlign: 'left',
                  borderLeft: selected === d.device_code ? '3px solid var(--sys-accent)' : '3px solid transparent',
                  transition: 'all .15s ease',
                }}
              >
                <HealthGauge score={d.health_score} size={50} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>{d.device_name}</div>
                  <div style={{ fontSize: 12, color: 'var(--sys-muted)' }}>{d.device_code}</div>
                  {d.sensors.filter(s => s.status && s.status !== 'good').map(s => (
                    <span key={s.sensor_code} className="sys-badge sys-badge-fault" style={{ marginTop: 4 }}>
                      {SENSOR_STATUS_LABEL[s.status ?? ''] ?? '质量异常'} · {s.sensor_name}
                    </span>
                  ))}
                </div>
                <span className={`sys-badge sys-badge-${d.status}`}>
                  {d.status === 'online' ? '在线' : d.status === 'warning' ? '预警' : d.status === 'fault' ? '故障' : '离线'}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Detail */}
        {device && (
          <div className="sys-stack">
            <div className="sys-panel">
              <div className="sys-panel-head">
                <div>
                  <h2 className="sys-panel-title">{device.device_name}</h2>
                  <p className="sys-panel-sub">{device.device_code} · 上次更新 {new Date(device.last_seen).toLocaleTimeString('zh-CN')}</p>
                </div>
                <span className={`sys-badge sys-badge-${device.risk_level}`}>{device.risk_level}</span>
              </div>
              <div className="sys-panel-body">
                <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 20, alignItems: 'center' }}>
                  <div style={{ textAlign: 'center' }}>
                    <HealthGauge score={device.health_score} size={110} />
                    <div style={{ fontSize: 12, color: 'var(--sys-muted)', marginTop: 4 }}>综合健康评分</div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    {[
                      { label: '故障概率', value: `${(device.failure_probability * 100).toFixed(1)}%`, color: RISK_COLOR[device.risk_level] },
                      { label: '异常评分', value: device.anomaly_score.toFixed(3) },
                      { label: '剩余寿命', value: `${device.rul_hours}h` },
                      { label: '风险等级', value: device.risk_level.toUpperCase(), color: RISK_COLOR[device.risk_level] },
                    ].map(kv => (
                      <div key={kv.label} style={{ background: 'var(--sys-surface)', borderRadius: 6, padding: '10px 12px', border: '1px solid var(--sys-border)' }}>
                        <div style={{ fontSize: 11, color: 'var(--sys-muted)', marginBottom: 4 }}>{kv.label}</div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: kv.color ?? 'var(--sys-text)' }}>{kv.value}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Sensor readings */}
            <div className="sys-panel">
              <div className="sys-panel-head">
                <h2 className="sys-panel-title">传感器实时读数</h2>
              </div>
              <div className="sys-panel-body">
                <div className="sys-sensor-list monitoring-sensor-list">
                  {device.sensors.map(s => {
                    const pct = Math.min(100, (s.value / (s.value * 1.5)) * 100);
                    const tone = s.quality < 0.7 ? 'danger' : s.quality < 0.85 ? 'warn' : '';
                    return (
                      <div key={s.sensor_code}>
                        <div className="sys-sensor-row">
                          <span className="sys-sensor-name">{s.sensor_name}</span>
                          {s.status && s.status !== 'good' && (
                            <span className="sys-badge sys-badge-fault" style={{ marginLeft: 8 }}>
                              {SENSOR_STATUS_LABEL[s.status] ?? '质量异常'}
                            </span>
                          )}
                          <span className="sys-sensor-val">{s.value} {s.unit} <small style={{ color: s.quality < 0.7 ? 'var(--sys-danger)' : 'var(--sys-muted)' }}>质量 {(s.quality * 100).toFixed(0)}%</small></span>
                          <div className="sys-sensor-bar">
                            <div className={`sys-sensor-fill${tone ? ' ' + tone : ''}`} style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                        <div style={{ marginBottom: 6 }}>
                          <LineChart data={s.trend} color="var(--sys-accent)" height={42} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}