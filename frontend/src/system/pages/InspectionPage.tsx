import { useState } from 'react';
import { CheckCircle, Clock, PlayCircle, XCircle } from '@phosphor-icons/react';
import { useMockData } from '../hooks/useMockData';
import type { InspectionTask } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };

const STATUS_LABEL: Record<InspectionTask['status'], string> = {
  pending: '待执行', in_progress: '进行中', completed: '已完成', skipped: '已跳过',
};
const STATUS_ICON: Record<InspectionTask['status'], typeof Clock> = {
  pending: Clock, in_progress: PlayCircle, completed: CheckCircle, skipped: XCircle,
};
const PRIORITY_LABEL: Record<InspectionTask['priority'], string> = {
  urgent: '紧急', high: '高', normal: '中', low: '低',
};

export function InspectionPage({ mock }: Props) {
  const [statusFilter, setStatusFilter] = useState<'all' | InspectionTask['status']>('all');
  const [expandedTaskId, setExpandedTaskId] = useState<number | null>(null);
  const { inspections } = mock;

  const filtered = statusFilter === 'all' ? inspections : inspections.filter(t => t.status === statusFilter);
  const counts = {
    pending: inspections.filter(t => t.status === 'pending').length,
    in_progress: inspections.filter(t => t.status === 'in_progress').length,
    completed: inspections.filter(t => t.status === 'completed').length,
  };

  return (
    <div className="sys-page">
      <h1 className="sys-page-title">智能巡检</h1>
      <p className="sys-page-sub">设备巡检任务调度与执行跟踪</p>

      <div className="sys-metrics" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
        <div className="sys-metric">
          <span className="sys-metric-label">待执行任务</span>
          <strong className="sys-metric-value">{counts.pending}</strong>
        </div>
        <div className="sys-metric cyan">
          <span className="sys-metric-label">进行中</span>
          <strong className="sys-metric-value">{counts.in_progress}</strong>
        </div>
        <div className="sys-metric ok">
          <span className="sys-metric-label">今日已完成</span>
          <strong className="sys-metric-value">{counts.completed}</strong>
        </div>
      </div>

      <div className="sys-panel">
        <div className="sys-panel-head">
          <h2 className="sys-panel-title">巡检任务</h2>
          <div className="sys-form-row">
            {(['all', 'pending', 'in_progress', 'completed'] as const).map(s => (
              <button
                key={s}
                className={`sys-btn sys-btn-sm${statusFilter === s ? ' sys-btn-primary' : ''}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === 'all' ? '全部' : STATUS_LABEL[s]}
              </button>
            ))}
          </div>
        </div>
        <div className="sys-panel-body">
          <div className="sys-insp-list inspection-list">
            {filtered.length === 0 ? (
              <div className="sys-empty">暂无匹配的巡检任务</div>
            ) : filtered.map(task => {
              const Icon = STATUS_ICON[task.status];
              return (
                <article className={`sys-insp-task${expandedTaskId === task.id ? ' expanded' : ''}`} key={task.id}>
                  <div className="sys-insp-row">
                    <div className={`sys-insp-pri ${task.priority}`} />
                    <div>
                      <div className="sys-insp-name">
                        {task.task_type} · {task.device_name}
                        {task.note && <span style={{ marginLeft: 8, color: 'var(--sys-danger)', fontSize: 12 }}>{task.note}</span>}
                      </div>
                      <div className="sys-insp-meta">
                        {task.device_code} · 负责人 {task.assigned_to} · 截止 {new Date(task.due_at).toLocaleDateString('zh-CN')} · 优先级 {PRIORITY_LABEL[task.priority]}
                      </div>
                    </div>
                    <span className={`sys-badge sys-badge-${task.status === 'completed' ? 'ok' : task.status === 'in_progress' ? 'processing' : 'offline'}`}>
                      <Icon size={12} style={{ marginRight: 3 }} />
                      {STATUS_LABEL[task.status]}
                    </span>
                    <button
                      type="button"
                      className="sys-btn sys-btn-sm"
                      aria-expanded={expandedTaskId === task.id}
                      aria-controls={`inspection-detail-${task.id}`}
                      onClick={() => setExpandedTaskId(current => current === task.id ? null : task.id)}
                    >
                      {expandedTaskId === task.id ? '收起' : '详情'}
                    </button>
                  </div>
                  {expandedTaskId === task.id && (
                    <div className="sys-insp-detail" id={`inspection-detail-${task.id}`}>
                      <dl>
                        <div><dt>巡检设备</dt><dd>{task.device_name}（{task.device_code}）</dd></div>
                        <div><dt>任务类型</dt><dd>{task.task_type}</dd></div>
                        <div><dt>执行人员</dt><dd>{task.assigned_to}</dd></div>
                        <div><dt>截止时间</dt><dd>{new Date(task.due_at).toLocaleString('zh-CN')}</dd></div>
                        <div><dt>优先级</dt><dd>{PRIORITY_LABEL[task.priority]}</dd></div>
                        <div><dt>当前状态</dt><dd>{STATUS_LABEL[task.status]}</dd></div>
                      </dl>
                      <div className="sys-insp-note">
                        <span>任务备注</span>
                        <strong>{task.note || '暂无补充说明，按标准巡检规程执行。'}</strong>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}