import {
  ChartBarHorizontal, ChartLine, Cpu, Gear, Heartbeat,
  Lightning, Robot, ShieldWarning, SquaresFour, Wrench, ArrowLeft,
} from '@phosphor-icons/react';
import { useRouter, type SystemPage } from '../router';

interface Props { warningCount: number; onExit: () => void }

const NAV: Array<{ page: SystemPage; label: string; icon: typeof SquaresFour; group: string }> = [
  { page: 'overview',   label: '运行总览',   icon: SquaresFour,         group: '监控中心' },
  { page: 'monitoring', label: '实时监测',   icon: Heartbeat,           group: '监控中心' },
  { page: 'prediction', label: '故障预测',   icon: ChartLine,           group: '分析决策' },
  { page: 'health',     label: '健康评估',   icon: Cpu,                 group: '分析决策' },
  { page: 'inspection', label: '智能巡检',   icon: Wrench,              group: '维护管理' },
  { page: 'warnings',   label: '预警处置',   icon: ShieldWarning,       group: '维护管理' },
  { page: 'model',      label: '模型训练',   icon: ChartBarHorizontal,  group: '系统管理' },
  { page: 'settings',   label: '系统设置',   icon: Gear,                group: '系统管理' },
];

const GROUPS = [...new Set(NAV.map(n => n.group))];

export function Sidebar({ warningCount, onExit }: Props) {
  const { page, navigate } = useRouter();

  return (
    <aside className="sys-sidebar">
      {GROUPS.map(group => (
        <div className="sys-sidebar-section" key={group}>
          <div className="sys-sidebar-label">{group}</div>
          {NAV.filter(n => n.group === group).map(item => {
            const Icon = item.icon;
            const isWarn = item.page === 'warnings';
            return (
              <button
                key={item.page}
                className={`sys-nav-btn${page === item.page ? ' active' : ''}`}
                onClick={() => navigate(item.page)}
              >
                <Icon size={16} weight={page === item.page ? 'fill' : 'regular'} />
                {item.label}
                {isWarn && warningCount > 0 && (
                  <span className="sys-nav-badge">{warningCount}</span>
                )}
              </button>
            );
          })}
        </div>
      ))}

      <div className="sys-sidebar-footer">
        <button
          className={`sys-ai-btn${page === 'intelligence' ? ' active' : ''}`}
          title="智能中台"
          onClick={() => navigate('intelligence')}
        >
          <Robot size={16} />
          智能中台
          <Lightning size={12} style={{ marginLeft: 'auto', opacity: 0.85 }} weight="fill" />
        </button>
        <button
          className="sys-nav-btn"
          style={{ marginTop: 8 }}
          onClick={onExit}
        >
          <ArrowLeft size={15} />
          返回入口
        </button>
      </div>
    </aside>
  );
}