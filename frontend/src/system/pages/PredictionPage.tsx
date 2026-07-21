import { BarChart } from '../components/Charts';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

const RISK_COLOR: Record<string, string> = {
  critical: 'var(--sys-danger)', high: 'var(--sys-warning)',
  medium: '#facc15', low: 'var(--sys-success)',
};

function fmt(d: string) {
  return new Date(d).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}

export function PredictionPage({ mock }: Props) {
  const { predictions, devices } = mock;

  const barData = devices.map(d => ({
    label: d.device_code.replace('CNC-',''),
    value: d.failure_probability * 100,
    color: RISK_COLOR[d.risk_level],
  }));

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">故障预测</h1>
      <p className="sys-page-sub">基于 AI4I 数据集训练的模型推理结果</p>

      <div className="sys-grid-2-1 prediction-layout" style={{ marginBottom: 14 }}>
        {/* Prediction table */}
        <div className="sys-panel prediction-panel">
          <div className="sys-panel-head">
            <div><h2 className="sys-panel-title">预测记录</h2><p className="sys-panel-sub">最近 {predictions.length} 条 · 表格可独立滚动</p></div>
          </div>
          <div className="sys-table-wrap prediction-table-wrap">
            <table className="sys-table">
              <thead>
                <tr>
                  <th>设备</th><th>故障概率</th><th>健康评分</th>
                  <th>风险等级</th><th>剩余寿命</th><th>时间</th>
                </tr>
              </thead>
              <tbody>
                {predictions.slice(0, 18).map(p => (
                  <tr key={p.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{p.device_code}</div>
                      <div style={{ fontSize: 12, color: 'var(--sys-muted)' }}>{p.device_name}</div>
                    </td>
                    <td className="sys-num" style={{ color: RISK_COLOR[p.risk_level] }}>
                      {(p.failure_probability * 100).toFixed(1)}%
                    </td>
                    <td className="sys-num">{p.health_score.toFixed(1)}</td>
                    <td><span className={`sys-badge sys-badge-${p.risk_level}`}>{p.risk_level}</span></td>
                    <td className="sys-num">{p.rul_hours}h</td>
                    <td style={{ fontSize: 12, color: 'var(--sys-muted)' }}>{fmt(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Failure probability chart */}
        <div className="sys-stack prediction-side">
          <div className="sys-panel prediction-chart-panel">
            <div className="sys-panel-head">
              <h2 className="sys-panel-title">故障概率对比</h2>
            </div>
            <div className="sys-panel-body">
              <BarChart data={barData} height={140} />
              <div className="prediction-risk-list">
                {devices.map(d => (
                  <div key={d.device_code} className="prediction-risk-row">
                    <div className="prediction-risk-dot" style={{ background: RISK_COLOR[d.risk_level] }} />
                    <span>{d.device_name}</span>
                    <strong style={{ color: RISK_COLOR[d.risk_level] }}>
                      {(d.failure_probability * 100).toFixed(1)}%
                    </strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="sys-panel">
            <div className="sys-panel-head"><h2 className="sys-panel-title">预测统计</h2></div>
            <div className="sys-panel-body">
              {[
                { label: '总预测次数', value: predictions.length },
                { label: '高风险设备数', value: devices.filter(d => ['high','critical'].includes(d.risk_level)).length },
                { label: '平均故障概率', value: `${(devices.reduce((s,d)=>s+d.failure_probability,0)/devices.length*100).toFixed(1)}%` },
                { label: '最高故障概率', value: `${(Math.max(...devices.map(d=>d.failure_probability))*100).toFixed(1)}%` },
              ].map(kv => (
                <div key={kv.label} style={{ display:'flex', justifyContent:'space-between', padding:'8px 0', borderBottom:'1px solid var(--sys-border)', fontSize:13 }}>
                  <span style={{ color:'var(--sys-muted)' }}>{kv.label}</span>
                  <strong>{kv.value}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}