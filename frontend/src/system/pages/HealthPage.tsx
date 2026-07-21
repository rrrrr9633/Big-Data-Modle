import { HealthGauge, BarChart, DonutChart } from '../components/Charts';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

export function HealthPage({ mock }: Props) {
  const { devices } = mock;
  const sorted = [...devices].sort((a, b) => a.health_score - b.health_score);

  const buckets = [
    { label: '优秀 80+',  value: devices.filter(d => d.health_score >= 80).length, color: 'var(--sys-success)' },
    { label: '良好 60-80', value: devices.filter(d => d.health_score >= 60 && d.health_score < 80).length, color: '#facc15' },
    { label: '关注 40-60', value: devices.filter(d => d.health_score >= 40 && d.health_score < 60).length, color: 'var(--sys-warning)' },
    { label: '警戒 <40',  value: devices.filter(d => d.health_score < 40).length, color: 'var(--sys-danger)' },
  ].filter(b => b.value > 0);

  const barData = sorted.map(d => ({
    label: d.device_code.replace('CNC-', ''),
    value: d.health_score,
    color: d.health_score >= 70 ? 'var(--sys-success)' : d.health_score >= 45 ? 'var(--sys-warning)' : 'var(--sys-danger)',
  }));

  const avgAnomaly = devices.reduce((s, d) => s + d.anomaly_score, 0) / devices.length;

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">健康评估</h1>
      <p className="sys-page-sub">设备综合健康评分与异常检测</p>

      <div className="sys-grid-2" style={{ marginBottom: 14 }}>
        <div className="sys-panel">
          <div className="sys-panel-head"><h2 className="sys-panel-title">健康评分排名</h2></div>
          <div className="sys-panel-body">
            <BarChart data={barData} height={130} />
          </div>
        </div>
        <div className="sys-panel">
          <div className="sys-panel-head"><h2 className="sys-panel-title">健康分布</h2></div>
          <div className="sys-panel-body" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <DonutChart segments={buckets} size={110} thickness={20} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {buckets.map(b => (
                <div key={b.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 2, background: b.color, flexShrink: 0 }} />
                  <span style={{ color: 'var(--sys-muted)' }}>{b.label}</span>
                  <strong style={{ marginLeft: 'auto' }}>{b.value} 台</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="sys-panel">
        <div className="sys-panel-head">
          <div><h2 className="sys-panel-title">设备健康详情</h2><p className="sys-panel-sub">平均异常评分 {avgAnomaly.toFixed(3)}</p></div>
        </div>
        <div className="sys-panel-body">
          <div className="sys-device-grid health-device-grid">
            {sorted.map(d => (
              <div key={d.device_code} className={`sys-device-card ${d.risk_level === 'critical' ? 'critical' : d.risk_level === 'high' ? 'high' : ''}`}>
                <div className="sys-device-header">
                  <div>
                    <div className="sys-device-name">{d.device_name}</div>
                    <div className="sys-device-code">{d.device_type} · {d.device_code}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <HealthGauge score={d.health_score} size={78} />
                </div>
                <div className="sys-device-metrics">
                  <div className="sys-device-kv"><span>异常评分</span><strong>{d.anomaly_score.toFixed(3)}</strong></div>
                  <div className="sys-device-kv"><span>剩余寿命</span><strong>{d.rul_hours}h</strong></div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--sys-muted)' }}>
                  数据质量：{d.sensors.length > 0 ? `${(d.sensors.reduce((s,x)=>s+x.quality,0)/d.sensors.length*100).toFixed(0)}%` : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}