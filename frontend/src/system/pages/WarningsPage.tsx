import { useState } from 'react';
import { useMockData } from '../hooks/useMockData';
import type { WarningRecord } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

const STATUS_LABEL: Record<WarningRecord['status'], string> = {
  new: '新预警', acknowledged: '已确认', processing: '处理中', resolved: '已解决', ignored: '已忽略',
};

// Mirrors backend ALLOWED_TRANSITIONS in warnings.py
const ALLOWED_TRANSITIONS: Record<WarningRecord['status'], WarningRecord['status'][]> = {
  new: ['acknowledged', 'ignored'],
  acknowledged: ['processing', 'resolved', 'ignored'],
  processing: ['resolved', 'ignored'],
  resolved: [],
  ignored: [],
};

export function WarningsPage({ mock }: Props) {
  const [localWarnings, setLocalWarnings] = useState<WarningRecord[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const warnings = localWarnings ?? mock.warnings;
  const active = warnings.find(w => w.id === selected) ?? warnings[0];

  const transition = (id: number, to: WarningRecord['status']) => {
    setLocalWarnings((warnings ?? []).map(w => (w.id === id ? { ...w, status: to } : w)));
  };

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">预警处置</h1>
      <p className="sys-page-sub">设备预警事件管理与状态流转</p>

      <div className="sys-grid-2-1">
        <div className="sys-panel">
          <div className="sys-panel-head">
            <h2 className="sys-panel-title">预警列表</h2>
            <span className="sys-badge sys-badge-new">{warnings.filter(w => w.status === 'new').length} 待处理</span>
          </div>
          <div className="sys-table-wrap warnings-table-wrap">
            <table className="sys-table">
              <thead>
                <tr><th>设备</th><th>预警内容</th><th>风险</th><th>状态</th><th>时间</th></tr>
              </thead>
              <tbody>
                {warnings.map(w => (
                  <tr key={w.id} onClick={() => setSelected(w.id)} style={{ cursor: 'pointer', background: active?.id === w.id ? 'rgba(56,130,255,0.08)' : undefined }}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{w.device_code}</div>
                      <div style={{ fontSize: 12, color: 'var(--sys-muted)' }}>{w.device_name}</div>
                    </td>
                    <td>{w.title}</td>
                    <td><span className={`sys-badge sys-badge-${w.risk_level}`}>{w.risk_level}</span></td>
                    <td><span className={`sys-badge sys-badge-${w.status}`}>{STATUS_LABEL[w.status]}</span></td>
                    <td style={{ fontSize: 12, color: 'var(--sys-muted)' }}>
                      {new Date(w.created_at).toLocaleString('zh-CN', { month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {active && (
          <div className="sys-panel">
            <div className="sys-panel-head">
              <div><h2 className="sys-panel-title">处置详情</h2><p className="sys-panel-sub">{active.device_name}</p></div>
              <span className={`sys-badge sys-badge-${active.risk_level}`}>{active.risk_level}</span>
            </div>
            <div className="sys-panel-body">
              <p className="sys-warn-title">{active.title}</p>
              <p className="sys-warn-detail">{active.detail}</p>
              <div className="sys-warn-action">建议动作：{active.suggested_action}</div>

              <div style={{ marginTop: 16 }}>
                <div className="sys-label" style={{ marginBottom: 8 }}>当前状态：{STATUS_LABEL[active.status]}</div>
                <div className="sys-form-row">
                  {ALLOWED_TRANSITIONS[active.status].map(to => (
                    <button
                      key={to}
                      className={`sys-btn sys-btn-sm ${to === 'ignored' ? 'sys-btn-danger' : 'sys-btn-primary'}`}
                      onClick={() => transition(active.id, to)}
                    >
                      转为 {STATUS_LABEL[to]}
                    </button>
                  ))}
                  {ALLOWED_TRANSITIONS[active.status].length === 0 && (
                    <span style={{ fontSize: 12, color: 'var(--sys-muted)' }}>该预警已进入终态，无法继续流转</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}