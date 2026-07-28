import { Factory } from '@phosphor-icons/react';
import { useRouter } from '../router';

const PAGE_LABELS: Record<string, string> = {
  overview: '运行总览', monitoring: '实时监测', prediction: '故障预测',
  health: '健康评估', inspection: '智能巡检', warnings: '预警处置',
  model: '模型训练', settings: '系统设置',
};

interface StatusItem { label: string; tone: 'ok' | 'warn' | 'err' | 'idle'; value: string }

interface Props {
  statusItems: StatusItem[];
  onExit: () => void;
}

export function TopBar({ statusItems, onExit }: Props) {
  const { page } = useRouter();
  const now = new Date().toLocaleString('zh-CN', { hour12: false });

  return (
    <header className="sys-topbar">
      <div className="sys-topbar-brand">
        <Factory size={22} weight="duotone" color="var(--sys-accent)" />
        <div>
          <strong>PDM 工业监控平台</strong>
          <div><span>设备健康评估系统</span></div>
        </div>
      </div>

      <div className="sys-topbar-center">
        <span className="sys-breadcrumb">
          <span>系统工作台</span>
          <span className="sys-breadcrumb-sep">/</span>
          <span>{PAGE_LABELS[page] ?? page}</span>
        </span>
      </div>

      <div className="sys-topbar-right">
        {statusItems.map(s => (
          <div key={s.label} className={`sys-pill ${s.tone}`}>
            <span className="sys-pill-dot" />
            {s.label}
            <span style={{ color: 'var(--sys-text)', marginLeft: 3, fontWeight: 700 }}>{s.value}</span>
          </div>
        ))}
        <span style={{ fontSize: 12, color: 'var(--sys-muted)', marginLeft: 4 }}>{now}</span>
        <button className="sys-exit-btn" onClick={onExit} style={{ marginLeft: 4 }}>
          退出
        </button>
      </div>
    </header>
  );
}