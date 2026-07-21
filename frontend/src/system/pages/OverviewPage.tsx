import { useRef, useEffect } from 'react';
import gsap from 'gsap';
import { HealthGauge, LineChart, DonutChart } from '../components/Charts';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

const RISK_COLOR: Record<string, string> = {
  critical: 'var(--sys-danger)', high: 'var(--sys-warning)',
  medium: '#facc15', low: 'var(--sys-success)',
};

export function OverviewPage({ mock }: Props) {
  const { dashboard, devices, warnings } = mock;
  const metricRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!metricRef.current) return;
    gsap.from(metricRef.current.children, {
      y: 20, opacity: 0, duration: 0.4, stagger: 0.07, ease: 'power2.out',
    });
  }, []);

  const recentWarnings = warnings.filter(w => w.status === 'new').slice(0, 5);

  const donutData = [
    { label: '低风险', value: devices.filter(d => d.risk_level === 'low').length,    color: 'var(--sys-success)' },
    { label: '中风险', value: devices.filter(d => d.risk_level === 'medium').length,  color: '#facc15' },
    { label: '高风险', value: devices.filter(d => d.risk_level === 'high').length,    color: 'var(--sys-warning)' },
    { label: '严重',   value: devices.filter(d => d.risk_level === 'critical').length, color: 'var(--sys-danger)' },
  ].filter(d => d.value > 0);

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">运行总览</h1>
      <p className="sys-page-sub">全厂设备实时健康状态 · 每3秒更新</p>

      {/* Metrics */}
      <div className="sys-metrics" ref={metricRef}>
        <div className="sys-metric cyan">
          <span className="sys-metric-label">在线设备</span>
          <strong className="sys-metric-value">{dashboard.online_devices}</strong>
          <span className="sys-metric-sub">共 {dashboard.total_devices} 台</span>
        </div>
        <div className={`sys-metric ${dashboard.high_risk_count > 0 ? 'warn' : 'ok'}`}>
          <span className="sys-metric-label">高风险设备</span>
          <strong className="sys-metric-value">{dashboard.high_risk_count}</strong>
          <span className="sys-metric-sub">需要重点关注</span>
        </div>
        <div className={`sys-metric ${dashboard.warning_count > 0 ? 'danger' : 'ok'}`}>
          <span className="sys-metric-label">待处理预警</span>
          <strong className="sys-metric-value">{dashboard.warning_count}</strong>
          <span className="sys-metric-sub">今日新增</span>
        </div>
        <div className="sys-metric">
          <span className="sys-metric-label">平均健康评分</span>
          <strong className="sys-metric-value">{dashboard.avg_health_score}</strong>
          <span className="sys-metric-sub">综合评估</span>
        </div>
      </div>

      <div className="sys-grid-2-1" style={{ marginBottom: 14 }}>
        {/* Device grid */}
        <div className="sys-panel">
          <div className="sys-panel-head">
            <div><h2 className="sys-panel-title">设备健康状态</h2><p className="sys-panel-sub">实时健康评分与风险等级</p></div>
          </div>
          <div className="sys-panel-body">
            <div className="sys-device-grid overview-device-grid">
              {devices.map(d => (
                <div key={d.device_code} className={`sys-device-card ${d.risk_level === 'critical' ? 'critical' : d.risk_level === 'high' ? 'high' : ''}`}>
                  <div className="sys-device-header">
                    <div>
                      <div className="sys-device-name">{d.device_name}</div>
                      <div className="sys-device-code">{d.device_code}</div>
                    </div>
                    <span className={`sys-badge sys-badge-${d.status}`}>
                      {d.status === 'online' ? '在线' : d.status === 'warning' ? '预警' : d.status === 'fault' ? '故障' : '离线'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <HealthGauge score={d.health_score} size={80} />
                  </div>
                  <div className="sys-device-metrics">
                    <div className="sys-device-kv">
                      <span>故障概率</span>
                      <strong style={{ color: RISK_COLOR[d.risk_level] }}>
                        {(d.failure_probability * 100).toFixed(1)}%
                      </strong>
                    </div>
                    <div className="sys-device-kv">
                      <span>剩余寿命</span>
                      <strong>{d.rul_hours}h</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="sys-stack">
          {/* Risk distribution donut */}
          <div className="sys-panel">
            <div className="sys-panel-head">
              <h2 className="sys-panel-title">风险分布</h2>
            </div>
            <div className="sys-panel-body" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <DonutChart segments={donutData} size={120} thickness={22} />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {donutData.map(d => (
                  <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 2, background: d.color, flexShrink: 0 }} />
                    <span style={{ color: 'var(--sys-muted)' }}>{d.label}</span>
                    <strong style={{ marginLeft: 'auto', color: 'var(--sys-text)' }}>{d.value} 台</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent warnings */}
          <div className="sys-panel" style={{ flex: 1 }}>
            <div className="sys-panel-head">
              <h2 className="sys-panel-title">最新预警</h2>
              <span className="sys-badge sys-badge-new">{recentWarnings.length}</span>
            </div>
            <div style={{ padding: '8px 0' }}>
              {recentWarnings.length === 0 ? (
                <div className="sys-empty">暂无待处理预警</div>
              ) : recentWarnings.map(w => (
                <div key={w.id} style={{ padding: '10px 16px', borderBottom: '1px solid var(--sys-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                    <span className="sys-warn-title" style={{ fontSize: 13 }}>{w.title}</span>
                    <span className={`sys-badge sys-badge-${w.risk_level}`}>{w.risk_level}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--sys-muted)' }}>{w.device_name}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Trend chart row */}
      <div className="sys-grid-3">
        {devices.slice(0, 3).map(d => (
          <div key={d.device_code} className="sys-panel">
            <div className="sys-panel-head">
              <div>
                <h2 className="sys-panel-title">{d.device_code} 主轴温度趋势</h2>
                <p className="sys-panel-sub">健康分 {d.health_score}</p>
              </div>
              <span className={`sys-badge sys-badge-${d.risk_level}`}>{d.risk_level}</span>
            </div>
            <div className="sys-panel-body" style={{ paddingTop: 8, paddingBottom: 8 }}>
              <LineChart
                data={d.sensors[0]?.trend ?? []}
                color={RISK_COLOR[d.risk_level] ?? 'var(--sys-cyan)'}
                height={60}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}