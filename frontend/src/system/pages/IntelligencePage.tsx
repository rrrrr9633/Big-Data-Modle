import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowsClockwise, ChatCircleDots, Lightning, MagnifyingGlass,
  Path, PlayCircle, Robot, Stack, WarningCircle,
} from '@phosphor-icons/react';
import {
  api,
  getProviderFromStatus,
  isLlmConfigured,
  type IntelligenceAgentAnswer,
  type IntelligenceCitation,
  type IntelligenceInspectionReport,
  type IntelligenceInspectionRun,
  type IntelligenceKnowledgeStatus,
  type IntelligenceScheduleRecord,
  type IntelligenceSchedulerRuntime,
  type IntelligenceSessionRecord,
  type IntelligenceStatus,
  type IntelligenceStoredMessage,
  type ModelTrainingJob,
} from '../api/client';
import { useMockData } from '../hooks/useMockData';

type Props = { mock: ReturnType<typeof useMockData> };
type TabKey = 'query' | 'chat' | 'patrol' | 'knowledge';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'query', label: '总查询' },
  { key: 'chat', label: '主动问答' },
  { key: 'patrol', label: 'AI巡检' },
  { key: 'knowledge', label: '知识与训练' },
];

const WORKSPACE_STORAGE_KEY = 'pdm.intelligence.workspace.v1';

type PersistedWorkspace = {
  tab?: TabKey;
  question?: string;
  useLlm?: boolean;
  queryDevice?: string;
  queryResult?: IntelligenceAgentAnswer | null;
  querySessionKey?: string | null;
  sessionKey?: string | null;
  sessionId?: number | string | null;
  chatInput?: string;
  messages?: UiMessage[];
};

function readWorkspace(): PersistedWorkspace {
  try {
    const raw = window.localStorage.getItem(WORKSPACE_STORAGE_KEY);
    return raw ? JSON.parse(raw) as PersistedWorkspace : {};
  } catch {
    return {};
  }
}

function writeWorkspace(workspace: PersistedWorkspace): void {
  try {
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(workspace));
  } catch {
    // 浏览器禁用存储或达到容量上限时，数据库会话仍是最终事实源。
  }
}

type UiMessage = {
  role: 'user' | 'assistant' | 'system' | string;
  content: string;
  created_at?: string;
  degraded?: boolean;
  reason?: string | null;
  status?: string | null;
  citations?: IntelligenceCitation[];
  facts?: Record<string, unknown> | null;
};

function errText(error: unknown): string {
  if (error instanceof Error) return error.message || '请求失败';
  return String(error);
}

function isAbortOrNetwork(error: unknown): boolean {
  const msg = errText(error).toLowerCase();
  return (
    error instanceof TypeError
    || msg.includes('failed to fetch')
    || msg.includes('network')
    || msg.includes('abort')
    || msg.includes('http 502')
    || msg.includes('http 503')
    || msg.includes('http 504')
  );
}

function formatTs(value?: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('zh-CN', { hour12: false });
}

function parseFindings(report: IntelligenceInspectionReport): Array<{ severity?: string; title?: string; detail?: string }> {
  if (Array.isArray(report.findings) && report.findings.length) return report.findings;
  const raw = report.findings_json;
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  if (typeof raw === 'string') {
    try {
      const parsed = JSON.parse(raw) as unknown;
      return Array.isArray(parsed) ? parsed as Array<{ severity?: string; title?: string; detail?: string }> : [];
    } catch {
      return [];
    }
  }
  return [];
}

function parseJsonField<T>(value: unknown): T | null {
  if (value == null) return null;
  if (typeof value === 'object') return value as T;
  if (typeof value === 'string') {
    try {
      return JSON.parse(value) as T;
    } catch {
      return null;
    }
  }
  return null;
}

function storedToUi(messages: IntelligenceStoredMessage[]): UiMessage[] {
  return messages.map(m => ({
    role: m.role,
    content: m.content,
    created_at: m.created_at,
    status: m.status,
    degraded: m.status === 'degraded' || m.status === 'facts_only' || m.status === 'disabled',
    citations: parseJsonField<IntelligenceCitation[]>(m.citations_json) ?? undefined,
    facts: parseJsonField<Record<string, unknown>>(m.facts_json),
  }));
}

function Citations({ items }: { items?: IntelligenceCitation[] }) {
  if (!items?.length) return null;
  return (
    <div className="intel-citations intelligence-citations">
      <span className="sys-label">引用</span>
      <ul>
        {items.map((c, i) => (
          <li key={`${c.chunk_id ?? c.source_id ?? c.source ?? i}-${i}`}>
            <strong>{c.title || c.source_type || c.source || '知识片段'}</strong>
            {(c.source_type || c.source_id) && (
              <span className="intel-cite-meta">
                {[c.source_type, c.source_id].filter(Boolean).join(' · ')}
              </span>
            )}
            {typeof c.score === 'number' && (
              <span className="intel-cite-meta">score {c.score.toFixed(1)}</span>
            )}
            {(c.content || c.snippet) && <p>{c.content || c.snippet}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FactsPanel({ facts }: { facts?: Record<string, unknown> | null }) {
  if (!facts || Object.keys(facts).length === 0) return null;
  const tools = Array.isArray(facts.tools) ? facts.tools : null;
  const overview = (facts['realtime.overview'] ?? facts.realtime_overview ?? facts.overview) as
    | Record<string, unknown>
    | undefined;
  const entries = Object.entries(facts).filter(([k]) => k !== 'tools');

  return (
    <div className="intelligence-structured">
      <div className="sys-form-row" style={{ marginBottom: 8 }}>
        <span className="sys-label">本地事实 facts</span>
      </div>
      {overview && typeof overview === 'object' && (
        <div className="intelligence-metric-grid">
          {['device_total', 'online_total', 'warning_total', 'prediction_total'].map(key => (
            overview[key] != null ? (
              <div key={key} className="intelligence-metric-card">
                <span>{key}</span>
                <strong>{String(overview[key])}</strong>
              </div>
            ) : null
          ))}
        </div>
      )}
      <div className="sys-table-wrap intelligence-table-wrap">
        <table className="sys-table">
          <thead>
            <tr><th>键</th><th>值摘要</th></tr>
          </thead>
          <tbody>
            {entries.slice(0, 12).map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td className="sys-num" style={{ maxWidth: 420, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {typeof value === 'string' ? value : JSON.stringify(value)?.slice(0, 180)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tools && tools.length > 0 && (
        <p className="intelligence-structured-summary" style={{ marginTop: 8 }}>
          工具结果 {tools.length} 条
        </p>
      )}
    </div>
  );
}

type GateKind = 'loading' | 'backend' | 'no_key' | 'sim_stopped' | 'degraded' | 'ready' | 'disabled';

function resolveGate(
  status: IntelligenceStatus | null,
  statusError: string | null,
  loading: boolean,
  simulationRunning: boolean | null,
): { kind: GateKind; title: string; detail: string } {
  if (loading) {
    return { kind: 'loading', title: '正在连接智能中台', detail: '读取 /api/v1/intelligence/status …' };
  }
  if (statusError || !status) {
    return {
      kind: 'backend',
      title: '后端不可用',
      detail: statusError || '无法读取智能中台状态。',
    };
  }

  const provider = getProviderFromStatus(status);
  const llmOk = isLlmConfigured(status);
  const reasonBlob = `${provider?.reason ?? ''} ${status.reason ?? ''} ${status.message ?? ''} ${status.last_error ?? ''}`.toLowerCase();
  const enabled = status.enabled !== false;

  const simRunning = status.simulation_running ?? simulationRunning;
  const simStopped = simRunning === false;

  if (!enabled) {
    return {
      kind: 'disabled',
      title: '智能中台已关闭',
      detail: 'INTELLIGENCE_ENABLED=false 时仍可返回本地事实，不会调用大模型。',
    };
  }
  if (!llmOk) {
    return {
      kind: 'no_key',
      title: '未配置模型密钥',
      detail: provider?.reason
        || status.message
        || '总查询/问答可走本地事实（degraded）；巡检为本地规则，可运行。不会伪造 LLM 成功。',
    };
  }
  if (simStopped) {
    return {
      kind: 'sim_stopped',
      title: '仿真已停止',
      detail: '智能中台可连接，但实时上下文可能不完整。可在系统设置启动仿真。',
    };
  }
  if (status.degraded) {
    return {
      kind: 'degraded',
      title: '降级运行',
      detail: status.message || status.reason || reasonBlob || '部分能力降级。',
    };
  }
  return {
    kind: 'ready',
    title: '智能中台就绪',
    detail: [
      provider?.provider && `提供商 ${provider.provider}`,
      provider?.model && `模型 ${provider.model}`,
      status.rag_mode && `RAG ${status.rag_mode}`,
      status.message,
    ].filter(Boolean).join(' · ') || '查询、问答、巡检与知识训练可用。',
  };
}

export function IntelligencePage({ mock }: Props) {
  const { devices, simulationRunning } = mock;
  const initialWorkspace = useMemo(readWorkspace, []);
  const initialTab = TABS.some(item => item.key === initialWorkspace.tab)
    ? initialWorkspace.tab as TabKey
    : 'query';
  const [tab, setTab] = useState<TabKey>(initialTab);

  const [status, setStatus] = useState<IntelligenceStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [knowledge, setKnowledge] = useState<IntelligenceKnowledgeStatus | null>(null);

  // Query
  const [question, setQuestion] = useState(initialWorkspace.question ?? '当前高风险设备有哪些？');
  const [useLlm, setUseLlm] = useState(initialWorkspace.useLlm ?? true);
  const [queryDevice, setQueryDevice] = useState(initialWorkspace.queryDevice ?? '');
  const [queryBusy, setQueryBusy] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [queryResult, setQueryResult] = useState<IntelligenceAgentAnswer | null>(initialWorkspace.queryResult ?? null);
  const [querySessionKey, setQuerySessionKey] = useState<string | null>(initialWorkspace.querySessionKey ?? null);

  // Chat
  const [sessionKey, setSessionKey] = useState<string | null>(initialWorkspace.sessionKey ?? null);
  const [sessionId, setSessionId] = useState<number | string | null>(initialWorkspace.sessionId ?? null);
  const [chatInput, setChatInput] = useState(initialWorkspace.chatInput ?? '');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>(initialWorkspace.messages ?? []);
  const [sessions, setSessions] = useState<IntelligenceSessionRecord[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const restoredSessionRef = useRef<string | null>(null);

  // Inspection
  const [schedule, setSchedule] = useState<IntelligenceScheduleRecord>({
    enabled: false,
    minute_of_hour: 0,
    device_limit: 50,
  });
  const [runtime, setRuntime] = useState<IntelligenceSchedulerRuntime | null>(null);
  const [scheduleBusy, setScheduleBusy] = useState(false);
  const [patrolBusy, setPatrolBusy] = useState(false);
  const [patrolFeedback, setPatrolFeedback] = useState<string | null>(null);
  const [patrolError, setPatrolError] = useState<string | null>(null);
  const [runs, setRuns] = useState<IntelligenceInspectionRun[]>([]);
  const [reports, setReports] = useState<IntelligenceInspectionReport[]>([]);

  // Knowledge / training
  const [syncBusy, setSyncBusy] = useState(false);
  const [retrainBusy, setRetrainBusy] = useState(false);
  const [knowledgeFeedback, setKnowledgeFeedback] = useState<string | null>(null);
  const [knowledgeError, setKnowledgeError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<ModelTrainingJob[]>([]);

  const gate = useMemo(
    () => resolveGate(status, statusError, statusLoading, simulationRunning),
    [status, statusError, statusLoading, simulationRunning],
  );

  // Only block when backend is unreachable / still loading.
  // No-key must NOT block query/chat; inspection is local-rule based.
  const backendBlocked = gate.kind === 'backend' || gate.kind === 'loading';
  const llmOk = isLlmConfigured(status);
  const provider = getProviderFromStatus(status);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const next = await api.intelligenceStatus();
      setStatus(next);
      if (next.knowledge) setKnowledge(next.knowledge);
      const sched = next.inspection?.schedule;
      if (sched && typeof sched === 'object') {
        setSchedule({
          enabled: Boolean(sched.enabled),
          minute_of_hour: Number(sched.minute_of_hour) % 60,
          device_limit: Number(sched.device_limit) || 50,
          last_triggered_at: sched.last_triggered_at,
          last_run_id: sched.last_run_id,
          schedule_key: sched.schedule_key,
          id: sched.id,
        });
      }
      if (next.scheduler) setRuntime(next.scheduler);
    } catch (error) {
      setStatus(null);
      setStatusError(
        isAbortOrNetwork(error)
          ? `后端不可用：${errText(error)}`
          : errText(error),
      );
    } finally {
      setStatusLoading(false);
    }
  }, []);

  const loadSchedule = useCallback(async () => {
    try {
      const res = await api.intelligenceInspectionSchedule();
      if (res.schedule) {
        setSchedule({
          enabled: Boolean(res.schedule.enabled),
          minute_of_hour: Number(res.schedule.minute_of_hour) % 60,
          device_limit: Number(res.schedule.device_limit) || 50,
          last_triggered_at: res.schedule.last_triggered_at,
          last_run_id: res.schedule.last_run_id,
          schedule_key: res.schedule.schedule_key,
          id: res.schedule.id,
        });
      }
      if (res.runtime) setRuntime(res.runtime);
      setPatrolError(null);
    } catch (error) {
      if (!isAbortOrNetwork(error)) setPatrolError(errText(error));
    }
  }, []);

  const loadReports = useCallback(async () => {
    try {
      const data = await api.intelligenceInspectionReports(50);
      setRuns(Array.isArray(data.runs) ? data.runs : []);
      setReports(Array.isArray(data.reports) ? data.reports : []);
      setPatrolError(null);
    } catch (error) {
      setRuns([]);
      setReports([]);
      if (!isAbortOrNetwork(error)) setPatrolError(errText(error));
    }
  }, []);

  const loadKnowledge = useCallback(async () => {
    try {
      const ks = await api.intelligenceKnowledgeStatus();
      setKnowledge(ks);
    } catch {
      // optional; status.knowledge may already cover it
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const data = await api.modelTrainingJobs(20);
      setJobs(Array.isArray(data) ? data : []);
      setKnowledgeError(null);
    } catch (error) {
      setJobs([]);
      if (!isAbortOrNetwork(error)) setKnowledgeError(errText(error));
    }
  }, []);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const data = await api.intelligenceSessions(50);
      setSessions(Array.isArray(data.items) ? data.items : []);
    } catch (error) {
      if (!isAbortOrNetwork(error)) setChatError(`历史会话加载失败：${errText(error)}`);
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  const loadSessionByKey = useCallback(async (key: string) => {
    setChatBusy(true);
    setChatError(null);
    try {
      const res = await api.intelligenceSessionByKey(key);
      setMessages(storedToUi(res.messages ?? []));
      setSessionKey(res.session?.session_key || key);
      setSessionId(res.session?.id ?? null);
      restoredSessionRef.current = res.session?.session_key || key;
    } catch (error) {
      setChatError(`会话加载失败：${errText(error)}`);
    } finally {
      setChatBusy(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (backendBlocked) return;
    if (tab === 'chat') {
      void loadSessions();
      if (sessionKey && restoredSessionRef.current !== sessionKey) {
        void loadSessionByKey(sessionKey);
      }
    }
    if (tab === 'patrol') {
      void loadSchedule();
      void loadReports();
    }
    if (tab === 'knowledge') {
      void loadKnowledge();
      void loadJobs();
    }
  }, [tab, backendBlocked, sessionKey, loadSessions, loadSessionByKey, loadSchedule, loadReports, loadKnowledge, loadJobs]);

  useEffect(() => {
    writeWorkspace({
      tab,
      question,
      useLlm,
      queryDevice,
      queryResult,
      querySessionKey,
      sessionKey,
      sessionId,
      chatInput,
      messages: messages.slice(-40),
    });
  }, [tab, question, useLlm, queryDevice, queryResult, querySessionKey, sessionKey, sessionId, chatInput, messages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages, chatBusy]);

  const runQuery = async () => {
    const q = question.trim();
    if (!q || queryBusy || backendBlocked) return;
    const finalQuestion = queryDevice
      ? `【设备 ${queryDevice}】${q}`
      : q;
    setQueryBusy(true);
    setQueryError(null);
    setQueryResult(null);
    try {
      const result = await api.intelligenceQuery({
        question: finalQuestion,
        session_key: querySessionKey,
        use_llm: useLlm,
      });
      setQueryResult(result);
      if (result.session_key) setQuerySessionKey(result.session_key);
    } catch (error) {
      setQueryError(
        isAbortOrNetwork(error)
          ? `查询失败（后端不可用）：${errText(error)}`
          : `查询失败：${errText(error)}`,
      );
    } finally {
      setQueryBusy(false);
    }
  };

  const sendChat = async () => {
    const text = chatInput.trim();
    if (!text || chatBusy || backendBlocked) return;
    setMessages(prev => [
      ...prev,
      { role: 'user', content: text, created_at: new Date().toISOString() },
    ]);
    setChatInput('');
    setChatBusy(true);
    setChatError(null);
    try {
      const res = await api.intelligenceChat({
        message: text,
        session_key: sessionKey,
      });
      if (res.session_key) setSessionKey(res.session_key);
      if (res.session_id != null) setSessionId(res.session_id);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          created_at: new Date().toISOString(),
          citations: res.citations,
          degraded: Boolean(res.degraded),
          reason: res.reason,
          status: res.status,
          facts: res.facts ?? null,
        },
      ]);
      void loadSessions();
    } catch (error) {
      setChatError(
        isAbortOrNetwork(error)
          ? `问答失败（后端不可用）：${errText(error)}`
          : `问答失败：${errText(error)}`,
      );
    } finally {
      setChatBusy(false);
    }
  };

  const newSession = () => {
    restoredSessionRef.current = null;
    setSessionKey(null);
    setSessionId(null);
    setMessages([]);
    setChatInput('');
    setChatError(null);
  };

  const reloadSession = async () => {
    if (!sessionKey) return;
    await loadSessionByKey(sessionKey);
  };

  const saveSchedule = async () => {
    if (backendBlocked || scheduleBusy) return;
    setScheduleBusy(true);
    setPatrolError(null);
    setPatrolFeedback(null);
    try {
      const minute = Math.max(0, Math.min(59, Number(schedule.minute_of_hour) || 0));
      const limit = Math.max(1, Math.min(500, Number(schedule.device_limit) || 50));
      const res = await api.intelligenceUpdateInspectionSchedule({
        enabled: Boolean(schedule.enabled),
        minute_of_hour: minute,
        device_limit: limit,
      });
      if (res.schedule) {
        setSchedule({
          enabled: Boolean(res.schedule.enabled),
          minute_of_hour: Number(res.schedule.minute_of_hour) % 60,
          device_limit: Number(res.schedule.device_limit) || limit,
          last_triggered_at: res.schedule.last_triggered_at,
          last_run_id: res.schedule.last_run_id,
        });
      }
      if (res.runtime) setRuntime(res.runtime);
      setPatrolFeedback(
        res.note
        || (res.schedule?.enabled
          ? `计划已保存：每小时第 ${res.schedule.minute_of_hour} 分钟执行，设备上限 ${res.schedule.device_limit}`
          : '巡检计划已关闭（手工 run 仍可用）'),
      );
      void loadStatus();
    } catch (error) {
      setPatrolError(`计划更新失败：${errText(error)}`);
    } finally {
      setScheduleBusy(false);
    }
  };

  const manualRun = async () => {
    if (backendBlocked || patrolBusy) return;
    setPatrolBusy(true);
    setPatrolError(null);
    setPatrolFeedback(null);
    try {
      const res = await api.intelligenceInspectionRun();
      if (res.status === 'busy' || res.accepted === false) {
        setPatrolError(res.reason || res.error_message || '巡检进行中，请稍后');
      } else if (res.status === 'failed') {
        setPatrolError(res.error_message || res.summary || '巡检失败');
        setPatrolFeedback(res.summary || null);
      } else {
        setPatrolFeedback(
          res.summary
          || `巡检完成 · run #${res.run_id ?? '—'} · 设备 ${res.device_total ?? '—'} · 问题 ${res.issue_total ?? '—'}`,
        );
      }
      await loadReports();
      void loadStatus();
    } catch (error) {
      setPatrolError(`手动巡检失败：${errText(error)}`);
    } finally {
      setPatrolBusy(false);
    }
  };

  const syncKnowledge = async () => {
    if (backendBlocked || syncBusy) return;
    setSyncBusy(true);
    setKnowledgeError(null);
    setKnowledgeFeedback(null);
    try {
      const res = await api.intelligenceKnowledgeSync();
      setKnowledgeFeedback(
        `同步完成 · 预测 ${res.synced_predictions ?? 0} · 预警 ${res.synced_warnings ?? 0}`
        + ` · 文档 ${res.document_total ?? '—'} · 分块 ${res.chunk_total ?? '—'}`,
      );
      void loadKnowledge();
      void loadStatus();
    } catch (error) {
      setKnowledgeError(`知识同步失败：${errText(error)}`);
    } finally {
      setSyncBusy(false);
    }
  };

  const startRetrain = async () => {
    if (backendBlocked || retrainBusy) return;
    setRetrainBusy(true);
    setKnowledgeError(null);
    setKnowledgeFeedback(null);
    try {
      const res = await api.modelRetrain();
      setKnowledgeFeedback(
        `二次训练已受理 · job ${res.job_id}${res.version ? ` · ${res.version}` : ''} · ${res.status}`,
      );
      void loadJobs();
    } catch (error) {
      setKnowledgeError(`二次训练失败：${errText(error)}`);
    } finally {
      setRetrainBusy(false);
    }
  };

  const archive = knowledge ?? status?.knowledge ?? null;
  const reportsByRun = useMemo(() => {
    const map = new Map<string, IntelligenceInspectionReport[]>();
    for (const r of reports) {
      const key = String(r.run_id ?? 'unknown');
      const list = map.get(key) ?? [];
      list.push(r);
      map.set(key, list);
    }
    return map;
  }, [reports]);

  return (
    <div className="sys-page intelligence-page">
      <div className="intelligence-header">
        <div>
          <h1 className="sys-page-title">智能中台</h1>
          <p className="sys-page-sub">总查询 · 主动问答 · 本地规则巡检 · 知识同步与模型二次训练</p>
        </div>
        <button type="button" className="sys-btn sys-btn-sm" onClick={() => void loadStatus()} disabled={statusLoading}>
          <ArrowsClockwise size={14} />
          刷新状态
        </button>
      </div>

      <div className={`intelligence-status gate-${gate.kind}`} role="status">
        <div className="intelligence-status-main">
          {gate.kind === 'ready' ? <Lightning size={16} weight="fill" /> : <WarningCircle size={16} weight="fill" />}
          <div>
            <strong>{gate.title}</strong>
            <span>{gate.detail}</span>
          </div>
        </div>
        <div className="intelligence-status-meta">
          <span className="sys-pill">
            <span className="sys-pill-dot" />
            中台
            <strong>{status?.enabled === false ? '关闭' : statusLoading ? '…' : '开启'}</strong>
          </span>
          <span className="sys-pill">
            <span className="sys-pill-dot" />
            密钥
            <strong>{llmOk ? '已配置' : statusLoading ? '…' : '未配置'}</strong>
          </span>
          <span className="sys-pill">
            <span className="sys-pill-dot" />
            仿真
            <strong>
              {(status?.simulation_running ?? simulationRunning) === true
                ? '运行中'
                : (status?.simulation_running ?? simulationRunning) === false
                  ? '已停止'
                  : '未知'}
            </strong>
          </span>
          {provider?.provider ? (
            <span className="sys-pill">
              <span className="sys-pill-dot" />
              {provider.provider}
              {provider.model ? <strong>{provider.model}</strong> : null}
            </span>
          ) : null}
        </div>
      </div>

      <div className="intelligence-tabs" role="tablist" aria-label="智能中台分区">
        {TABS.map(item => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            className={`intelligence-tab${tab === item.key ? ' active' : ''}`}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="intelligence-body" role="tabpanel">
        {tab === 'query' && (
          <div className="intelligence-pane">
            <div className="sys-panel intelligence-panel">
              <div className="sys-panel-head">
                <div>
                  <h2 className="sys-panel-title">
                    <MagnifyingGlass size={15} style={{ marginRight: 6, verticalAlign: -2 }} />
                    总查询
                  </h2>
                  <p className="sys-panel-sub">
                    POST /intelligence/query · question / session_key / use_llm · 无密钥时仍返回本地 facts
                  </p>
                </div>
              </div>
              <div className="sys-panel-body sys-stack intelligence-panel-body">
                <div className="sys-form-row intelligence-filters">
                  <label className="sys-label">设备上下文</label>
                  <select
                    className="sys-select"
                    value={queryDevice}
                    onChange={e => setQueryDevice(e.target.value)}
                  >
                    <option value="">不限定（写入 question 前缀）</option>
                    {devices.map(d => (
                      <option key={d.device_code} value={d.device_code}>
                        {d.device_code} · {d.device_name}
                      </option>
                    ))}
                  </select>
                  <label className="sys-label">use_llm</label>
                  <button
                    type="button"
                    className={`sys-btn sys-btn-sm${useLlm ? ' sys-btn-primary' : ''}`}
                    onClick={() => setUseLlm(v => !v)}
                    title={!llmOk ? '无密钥时后端会忽略 LLM，返回 facts_only' : undefined}
                  >
                    {useLlm ? '尝试 LLM' : '仅事实'}
                  </button>
                  {querySessionKey && (
                    <span className="sys-badge sys-badge-offline">session {querySessionKey}</span>
                  )}
                </div>
                {!llmOk && !backendBlocked && (
                  <div className="intelligence-feedback warn">
                    未配置 API Key：总查询仍可用，后端将返回本地实时事实（degraded / facts_only），不会伪造成功生成。
                  </div>
                )}
                <div className="sys-form-row intelligence-query-row">
                  <input
                    className="sys-input intelligence-input"
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') void runQuery(); }}
                    placeholder="例如：当前有多少高风险设备？"
                    disabled={queryBusy || backendBlocked}
                  />
                  <button
                    type="button"
                    className="sys-btn sys-btn-primary"
                    disabled={queryBusy || backendBlocked || !question.trim()}
                    onClick={() => void runQuery()}
                  >
                    {queryBusy ? '查询中…' : '执行查询'}
                  </button>
                </div>
                {queryError && <div className="intelligence-feedback error">{queryError}</div>}
                <div className="intelligence-scroll">
                  {!queryResult && !queryError && (
                    <div className="sys-empty">提交后展示 answer / facts / citations；失败仅显示错误，不伪造结果。</div>
                  )}
                  {queryResult && (
                    <div className="intelligence-result sys-stack">
                      <div className="sys-form-row" style={{ gap: 6 }}>
                        {queryResult.status && (
                          <span className={`sys-badge ${
                            queryResult.degraded || queryResult.status === 'facts_only' || queryResult.status === 'degraded'
                              ? 'sys-badge-warning'
                              : queryResult.status === 'ok'
                                ? 'sys-badge-ok'
                                : 'sys-badge-offline'
                          }`}
                          >
                            {queryResult.status}
                          </span>
                        )}
                        {queryResult.degraded && <span className="sys-badge sys-badge-warning">degraded</span>}
                        {queryResult.mode && <span className="sys-badge sys-badge-processing">{queryResult.mode}</span>}
                      </div>
                      {queryResult.reason && (
                        <div className="intelligence-feedback warn">{queryResult.reason}</div>
                      )}
                      <div className="intelligence-answer">{queryResult.answer}</div>
                      <FactsPanel facts={queryResult.facts} />
                      <Citations items={queryResult.citations} />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'chat' && (
          <div className="intelligence-pane">
            <div className="sys-panel intelligence-panel intelligence-chat-panel">
              <div className="sys-panel-head">
                <div>
                  <h2 className="sys-panel-title">
                    <ChatCircleDots size={15} style={{ marginRight: 6, verticalAlign: -2 }} />
                    主动问答
                  </h2>
                  <p className="sys-panel-sub">
                    POST /intelligence/chat · message / session_key
                    {sessionKey ? ` · key ${sessionKey}` : ' · 新会话'}
                    {sessionId != null ? ` · id ${sessionId}` : ''}
                  </p>
                </div>
                <div className="sys-form-row">
                  <button type="button" className="sys-btn sys-btn-sm" onClick={newSession}>新会话</button>
                  <button
                    type="button"
                    className="sys-btn sys-btn-sm"
                    disabled={!sessionKey || chatBusy}
                    onClick={() => void reloadSession()}
                  >
                    重载会话
                  </button>
                </div>
              </div>
              <div className="sys-panel-body intelligence-chat-body">
                {!llmOk && !backendBlocked && (
                  <div className="intelligence-feedback warn">
                    无 API Key 时仍可发送；后端返回 degraded 事实答复，不会伪造 LLM 成功。
                  </div>
                )}
                <div className="intelligence-session-history" aria-label="历史对话">
                  <div className="intelligence-session-history-head">
                    <span className="sys-label">历史对话</span>
                    <button
                      type="button"
                      className="sys-btn sys-btn-sm"
                      disabled={sessionsLoading || backendBlocked}
                      onClick={() => void loadSessions()}
                    >
                      {sessionsLoading ? '读取中…' : '刷新'}
                    </button>
                  </div>
                  <div className="intelligence-session-list">
                    {!sessionsLoading && sessions.length === 0 && (
                      <span className="intelligence-session-empty">暂无已保存会话</span>
                    )}
                    {sessions.map(item => {
                      const key = item.session_key || '';
                      const active = Boolean(key && key === sessionKey);
                      return (
                        <button
                          type="button"
                          key={String(item.id ?? key)}
                          className={`intelligence-session-item${active ? ' active' : ''}`}
                          disabled={!key || chatBusy}
                          title={`${item.title || '未命名会话'} · ${formatTs(item.updated_at)}`}
                          onClick={() => { if (key) void loadSessionByKey(key); }}
                        >
                          <strong>{item.title || '未命名会话'}</strong>
                          <span>{formatTs(item.updated_at)}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="intelligence-chat-scroll">
                  {messages.length === 0 && (
                    <div className="sys-empty">输入问题开始多轮对话。会话通过 session_key 续接。</div>
                  )}
                  {messages.map((m, idx) => (
                    <div key={`${m.role}-${idx}-${m.created_at ?? idx}`} className={`intelligence-msg ${m.role}`}>
                      <div className="intelligence-msg-role">
                        {m.role === 'user' ? '操作员' : m.role === 'assistant' ? '智能中台' : '系统'}
                        {m.degraded ? <span className="sys-badge sys-badge-warning">降级</span> : null}
                        {m.status ? <span className="sys-badge sys-badge-offline">{m.status}</span> : null}
                      </div>
                      <div className="intelligence-msg-content">{m.content}</div>
                      {m.reason ? <div className="intelligence-msg-reason">{m.reason}</div> : null}
                      {m.facts ? <FactsPanel facts={m.facts} /> : null}
                      <Citations items={m.citations} />
                    </div>
                  ))}
                  {chatBusy && <div className="intelligence-msg assistant pending">处理中…</div>}
                  <div ref={chatEndRef} />
                </div>
                {chatError && <div className="intelligence-feedback error">{chatError}</div>}
                <div className="sys-form-row intelligence-chat-input">
                  <input
                    className="sys-input intelligence-input"
                    value={chatInput}
                    onChange={e => setChatInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendChat(); } }}
                    placeholder={backendBlocked ? '后端不可用' : '描述设备现象或处置问题…'}
                    disabled={chatBusy || backendBlocked}
                  />
                  <button
                    type="button"
                    className="sys-btn sys-btn-primary"
                    disabled={chatBusy || backendBlocked || !chatInput.trim()}
                    onClick={() => void sendChat()}
                  >
                    发送
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'patrol' && (
          <div className="intelligence-pane intelligence-split">
            <div className="sys-panel intelligence-panel">
              <div className="sys-panel-head">
                <div>
                  <h2 className="sys-panel-title">
                    <Path size={15} style={{ marginRight: 6, verticalAlign: -2 }} />
                    AI 巡检计划
                  </h2>
                  <p className="sys-panel-sub">
                    /intelligence/inspection/schedule · 每小时第 N 分钟（0–59）· 本地规则，不依赖 LLM
                  </p>
                </div>
              </div>
              <div className="sys-panel-body sys-stack">
                <div className="sys-form-row">
                  <span className="sys-label">计划启用</span>
                  <button
                    type="button"
                    className={`sys-btn sys-btn-sm${schedule.enabled ? ' sys-btn-primary' : ''}`}
                    disabled={backendBlocked || scheduleBusy}
                    onClick={() => setSchedule(s => ({ ...s, enabled: !s.enabled }))}
                  >
                    {schedule.enabled ? '已开启' : '已关闭'}
                  </button>
                </div>
                <div className="sys-form-row">
                  <span className="sys-label">执行分钟（0–59）</span>
                  <input
                    className="sys-input"
                    type="number"
                    min={0}
                    max={59}
                    style={{ width: 96 }}
                    value={schedule.minute_of_hour}
                    disabled={backendBlocked || scheduleBusy}
                    onChange={e => setSchedule(s => ({
                      ...s,
                      minute_of_hour: Math.max(0, Math.min(59, Number(e.target.value) || 0)),
                    }))}
                  />
                  <span className="sys-label">设备上限</span>
                  <input
                    className="sys-input"
                    type="number"
                    min={1}
                    max={500}
                    style={{ width: 96 }}
                    value={schedule.device_limit}
                    disabled={backendBlocked || scheduleBusy}
                    onChange={e => setSchedule(s => ({
                      ...s,
                      device_limit: Math.max(1, Math.min(500, Number(e.target.value) || 1)),
                    }))}
                  />
                </div>
                <div className="sys-form-row simulation-actions">
                  <button
                    type="button"
                    className="sys-btn sys-btn-primary"
                    disabled={backendBlocked || scheduleBusy}
                    onClick={() => void saveSchedule()}
                  >
                    {scheduleBusy ? '保存中…' : '保存计划'}
                  </button>
                  <button
                    type="button"
                    className="sys-btn"
                    disabled={backendBlocked || patrolBusy}
                    onClick={() => void manualRun()}
                  >
                    <PlayCircle size={14} />
                    {patrolBusy ? '执行中…' : '手动巡检'}
                  </button>
                </div>
                <div className="intelligence-kv">
                  <div><span>上次触发</span><strong>{formatTs(schedule.last_triggered_at)}</strong></div>
                  <div><span>上次 run</span><strong>{schedule.last_run_id ?? '—'}</strong></div>
                  <div><span>调度线程</span><strong>{runtime?.thread_alive ? '存活' : runtime?.started ? '已启动' : '未启动'}</strong></div>
                  <div><span>环境分钟</span><strong>{runtime?.minute_of_hour ?? status?.inspection?.minute_of_hour ?? '—'}</strong></div>
                </div>
                {runtime?.last_error && (
                  <div className="intelligence-feedback error">runtime: {runtime.last_error}</div>
                )}
                {patrolFeedback && <div className="intelligence-feedback">{patrolFeedback}</div>}
                {patrolError && <div className="intelligence-feedback error">{patrolError}</div>}
              </div>
            </div>

            <div className="sys-panel intelligence-panel">
              <div className="sys-panel-head">
                <h2 className="sys-panel-title">巡检 runs / reports</h2>
                <button type="button" className="sys-btn sys-btn-sm" onClick={() => void loadReports()} disabled={backendBlocked}>
                  刷新
                </button>
              </div>
              <div className="sys-panel-body intelligence-panel-body">
                <div className="intelligence-scroll intelligence-report-list">
                  {runs.length === 0 && reports.length === 0 ? (
                    <div className="sys-empty">暂无巡检记录</div>
                  ) : (
                    (runs.length > 0 ? runs : [{ id: 'orphan', status: '—', summary: '未归类报告' } as IntelligenceInspectionRun]).map(run => {
                      const runReports = reportsByRun.get(String(run.id))
                        ?? (run.id === 'orphan'
                          ? reports.filter(r => r.run_id == null)
                          : []);
                      return (
                        <article key={String(run.id)} className="intelligence-report-card">
                          <div className="sys-form-row" style={{ justifyContent: 'space-between' }}>
                            <strong>Run #{run.id}</strong>
                            {run.status && (
                              <span className={`sys-badge sys-badge-${
                                run.status === 'completed' ? 'ok'
                                  : run.status === 'failed' ? 'critical'
                                    : run.status === 'running' ? 'processing'
                                      : 'offline'
                              }`}
                              >
                                {run.status}
                              </span>
                            )}
                          </div>
                          <div className="intelligence-report-meta">
                            {[run.trigger_type, formatTs(run.started_at || run.created_at), run.finished_at ? `完成 ${formatTs(run.finished_at)}` : null]
                              .filter(Boolean)
                              .join(' · ')}
                          </div>
                          {run.summary && <p>{run.summary}</p>}
                          <div className="intelligence-kv" style={{ marginTop: 8 }}>
                            <div><span>扫描设备</span><strong>{run.device_total ?? '—'}</strong></div>
                            <div><span>问题项</span><strong>{run.issue_total ?? runReports.length}</strong></div>
                          </div>
                          {run.error_message && (
                            <div className="intelligence-feedback error" style={{ marginTop: 8 }}>{run.error_message}</div>
                          )}
                          {runReports.length > 0 && (
                            <ul className="intelligence-finding-list">
                              {runReports.slice(0, 12).map(r => {
                                const findings = parseFindings(r);
                                return (
                                  <li key={String(r.id)}>
                                    {r.device_code ? <code>{r.device_code}</code> : null}
                                    {r.severity ? <span className={`sys-badge sys-badge-${r.severity}`}>{r.severity}</span> : null}
                                    <span>{r.title || r.detail}</span>
                                    {findings.length > 1 && (
                                      <span className="intelligence-report-meta">+{findings.length - 1} findings</span>
                                    )}
                                  </li>
                                );
                              })}
                            </ul>
                          )}
                        </article>
                      );
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'knowledge' && (
          <div className="intelligence-pane intelligence-split">
            <div className="sys-panel intelligence-panel">
              <div className="sys-panel-head">
                <div>
                  <h2 className="sys-panel-title">
                    <Stack size={15} style={{ marginRight: 6, verticalAlign: -2 }} />
                    知识同步与二次训练
                  </h2>
                  <p className="sys-panel-sub">
                    knowledge/sync · POST /models/retrain · GET /models/training-jobs
                  </p>
                </div>
              </div>
              <div className="sys-panel-body sys-stack">
                {archive ? (
                  <div className="intelligence-kv">
                    <div>
                      <span>文档数</span>
                      <strong>{archive.document_total ?? archive.document_count ?? '—'}</strong>
                    </div>
                    <div>
                      <span>分块数</span>
                      <strong>{archive.chunk_total ?? archive.chunk_count ?? '—'}</strong>
                    </div>
                    <div>
                      <span>模式</span>
                      <strong>{archive.mode ?? status?.rag_mode ?? '—'}</strong>
                    </div>
                    <div>
                      <span>预测游标</span>
                      <strong>
                        {archive.cursors?.prediction?.last_source_id != null
                          ? String(archive.cursors.prediction.last_source_id)
                          : '—'}
                      </strong>
                    </div>
                    <div>
                      <span>预警游标</span>
                      <strong>
                        {archive.cursors?.warning?.last_source_id != null
                          ? String(archive.cursors.warning.last_source_id)
                          : '—'}
                      </strong>
                    </div>
                    {(archive.archive_count != null || archive.last_synced_at) && (
                      <>
                        <div><span>归档数</span><strong>{archive.archive_count ?? '—'}</strong></div>
                        <div><span>最近同步</span><strong>{formatTs(archive.last_synced_at)}</strong></div>
                      </>
                    )}
                  </div>
                ) : (
                  <div className="sys-empty" style={{ padding: 16 }}>
                    暂无知识库概览（可点同步后刷新）
                  </div>
                )}
                {archive?.summary && <p className="intelligence-structured-summary">{archive.summary}</p>}
                <div className="sys-form-row simulation-actions">
                  <button
                    type="button"
                    className="sys-btn"
                    disabled={backendBlocked || syncBusy}
                    onClick={() => void syncKnowledge()}
                  >
                    <ArrowsClockwise size={14} />
                    {syncBusy ? '同步中…' : '同步知识库'}
                  </button>
                  <button
                    type="button"
                    className="sys-btn sys-btn-primary"
                    disabled={backendBlocked || retrainBusy}
                    onClick={() => void startRetrain()}
                  >
                    <Robot size={14} />
                    {retrainBusy ? '提交中…' : '发起二次训练'}
                  </button>
                </div>
                {knowledgeFeedback && <div className="intelligence-feedback">{knowledgeFeedback}</div>}
                {knowledgeError && <div className="intelligence-feedback error">{knowledgeError}</div>}
              </div>
            </div>

            <div className="sys-panel intelligence-panel">
              <div className="sys-panel-head">
                <h2 className="sys-panel-title">训练任务</h2>
                <button type="button" className="sys-btn sys-btn-sm" onClick={() => void loadJobs()} disabled={backendBlocked}>
                  刷新
                </button>
              </div>
              <div className="sys-panel-body intelligence-panel-body">
                <div className="intelligence-scroll">
                  {jobs.length === 0 ? (
                    <div className="sys-empty">暂无训练任务</div>
                  ) : (
                    <div className="sys-table-wrap intelligence-table-wrap">
                      <table className="sys-table">
                        <thead>
                          <tr>
                            <th>ID</th>
                            <th>状态</th>
                            <th>版本</th>
                            <th>样本</th>
                            <th>创建人</th>
                            <th>创建时间</th>
                            <th>错误</th>
                          </tr>
                        </thead>
                        <tbody>
                          {jobs.map(job => (
                            <tr key={String(job.id)}>
                              <td className="sys-num">{job.id}</td>
                              <td>
                                <span className={`sys-badge sys-badge-${
                                  job.status === 'succeeded' ? 'ok'
                                    : job.status === 'failed' ? 'critical'
                                      : job.status === 'running' ? 'processing'
                                        : 'offline'
                                }`}
                                >
                                  {job.status}
                                </span>
                              </td>
                              <td>{job.version || '—'}</td>
                              <td className="sys-num">{job.trained_rows ?? '—'}</td>
                              <td>{job.created_by || '—'}</td>
                              <td>{formatTs(job.created_at)}</td>
                              <td>{job.error_message || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
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
