// API client — falls back gracefully when backend is unreachable.
// The config's api.base is proxied via Vite (/api/v1).

const BASE = '/api/v1';
const TIMEOUT = 8000;
const AI_TIMEOUT = 45000;

async function request<T>(
  path: string,
  options?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const { timeoutMs = TIMEOUT, ...init } = options ?? {};
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: controller.signal });
    clearTimeout(tid);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const body = await res.json() as { detail?: unknown; message?: unknown; reason?: unknown };
        if (typeof body.detail === 'string') detail = body.detail;
        else if (typeof body.message === 'string') detail = body.message;
        else if (typeof body.reason === 'string') detail = body.reason;
      } catch {
        // ignore non-JSON error bodies
      }
      throw new Error(detail);
    }
    return res.json() as Promise<T>;
  } catch (e) {
    clearTimeout(tid);
    throw e;
  }
}

type AnyRecord = Record<string, unknown>;

export type SimulationMode = 'normal' | 'degrading' | 'sudden_fault' | 'sensor_stuck' | 'sensor_drift';

export type SimulationTransport = 'local' | 'mqtt';

export interface SimulationState {
  running: boolean;
  cycle: number;
  mode: SimulationMode;
  transport: SimulationTransport;
  pipeline: string;
  device_count: number;
  interval_seconds: number;
  gateway_id: string;
  devices: string[];
  scenario_devices: string[];
  accepted_events: number;
  failed_cycles: number;
  last_published_at: string | null;
  last_error: string | null;
}

export interface RealtimePoint {
  point_code: string;
  value: number;
  unit: string | null;
  quality: number;
  status: string;
  ts: string;
}

export interface RealtimeDeviceSnapshot {
  device_code: string;
  point_code: string;
  value: number;
  unit: string | null;
  quality: number;
  ts: string;
  online: boolean;
  points?: Record<string, RealtimePoint>;
}

export interface RealtimeOverview {
  devices: RealtimeDeviceSnapshot[];
  online_total: number;
  device_total: number;
  warning_total: number;
  prediction_total: number;
}

// ── Intelligence middle-platform (aligned with backend /api/v1/intelligence/*) ─

export interface IntelligenceProviderStatus {
  configured: boolean;
  provider: string;
  base_url?: string;
  model?: string;
  reason?: string | null;
}

export interface IntelligenceInspectionConfig {
  enabled?: boolean;
  minute_of_hour?: number;
  schedule?: IntelligenceScheduleRecord | null;
}

export interface IntelligenceSchedulerRuntime {
  started?: boolean;
  thread_alive?: boolean;
  running_job?: boolean;
  enabled?: boolean;
  minute_of_hour?: number;
  last_hour_slot?: string | null;
  last_error?: string | null;
}

export interface IntelligenceKnowledgeStatus {
  document_total?: number;
  chunk_total?: number;
  mode?: string;
  cursors?: {
    prediction?: { last_source_id?: number | string; last_synced_at?: string | null; total_synced?: number } | null;
    warning?: { last_source_id?: number | string; last_synced_at?: string | null; total_synced?: number } | null;
  };
  // planned / optional top-level archive fields
  document_count?: number;
  chunk_count?: number;
  archive_count?: number;
  last_synced_at?: string | null;
  last_archive_at?: string | null;
  sources?: string[];
  summary?: string | null;
}

/** GET /intelligence/status — current + planned optional top-level fields */
export interface IntelligenceStatus {
  enabled?: boolean;
  provider?: IntelligenceProviderStatus | string | null;
  rag_mode?: string;
  inspection?: IntelligenceInspectionConfig | null;
  ai4i_dataset_path?: string;
  scheduler?: IntelligenceSchedulerRuntime | null;
  // planned / optional compatibility fields
  available?: boolean;
  ready?: boolean;
  llm_configured?: boolean;
  llm_ready?: boolean;
  model?: string | null;
  simulation_running?: boolean | null;
  degraded?: boolean;
  reason?: string | null;
  message?: string | null;
  knowledge?: IntelligenceKnowledgeStatus | null;
  last_error?: string | null;
}

export interface IntelligenceQueryRequest {
  question: string;
  session_key?: string | null;
  user_id?: string | null;
  use_llm?: boolean;
}

export interface IntelligenceCitation {
  document_id?: number;
  chunk_id?: number;
  source_type?: string;
  source_id?: string;
  title?: string;
  content?: string;
  score?: number;
  // loose compatibility
  source?: string;
  snippet?: string;
  device_code?: string | null;
}

export interface IntelligenceAgentAnswer {
  mode?: string;
  status?: string;
  answer: string;
  facts?: Record<string, unknown>;
  citations?: IntelligenceCitation[];
  tool_results?: Array<Record<string, unknown>>;
  session_id?: number | string | null;
  session_key?: string | null;
  degraded?: boolean;
  reason?: string | null;
}

export type IntelligenceQueryResponse = IntelligenceAgentAnswer;

export interface IntelligenceChatRequest {
  message: string;
  session_key?: string | null;
  user_id?: string | null;
  title?: string | null;
}

export type IntelligenceChatResponse = IntelligenceAgentAnswer;

export interface IntelligenceSessionRecord {
  id?: number | string;
  session_key?: string;
  title?: string | null;
  user_id?: string | null;
  status?: string;
  metadata_json?: unknown;
  created_at?: string;
  updated_at?: string;
}

export interface IntelligenceStoredMessage {
  id?: number | string;
  session_id?: number | string;
  role: 'user' | 'assistant' | 'system' | string;
  content: string;
  mode?: string | null;
  status?: string | null;
  facts_json?: unknown;
  citations_json?: unknown;
  tool_calls_json?: unknown;
  created_at?: string;
}

export interface IntelligenceSessionByKeyResponse {
  session: IntelligenceSessionRecord;
  messages: IntelligenceStoredMessage[];
}

export interface IntelligenceSessionListResponse {
  items: IntelligenceSessionRecord[];
  total: number;
}

export interface IntelligenceKnowledgeSyncRequest {
  batch_size?: number | null;
}

export interface IntelligenceKnowledgeSyncResult {
  synced_predictions?: number;
  synced_warnings?: number;
  prediction_cursor?: number;
  warning_cursor?: number;
  document_total?: number;
  chunk_total?: number;
  message?: string;
  ok?: boolean;
  reason?: string | null;
}

export interface IntelligenceScheduleRecord {
  id?: number | string;
  schedule_key?: string;
  enabled: boolean;
  minute_of_hour: number;
  device_limit: number;
  last_triggered_at?: string | null;
  last_run_id?: number | string | null;
  updated_at?: string;
  created_at?: string;
}

export interface IntelligenceScheduleUpdate {
  enabled: boolean;
  minute_of_hour: number;
  device_limit: number;
}

export interface IntelligenceScheduleResponse {
  schedule: IntelligenceScheduleRecord;
  runtime?: IntelligenceSchedulerRuntime;
  config?: {
    inspection_enabled?: boolean;
    inspection_minute?: number;
    inspection_device_limit?: number;
  };
  note?: string;
}

export interface IntelligenceInspectionRunResult {
  accepted?: boolean;
  run_id?: number | string | null;
  status?: string;
  device_total?: number;
  issue_total?: number;
  summary?: string;
  error_message?: string | null;
  reason?: string | null;
}

export interface IntelligenceInspectionRun {
  id: number | string;
  trigger_type?: string;
  status?: string;
  summary?: string | null;
  device_total?: number | null;
  issue_total?: number | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at?: string | null;
}

export interface IntelligenceInspectionFinding {
  severity?: string;
  title?: string;
  detail?: string;
  device_code?: string;
}

export interface IntelligenceInspectionReport {
  id: number | string;
  run_id?: number | string;
  device_code?: string | null;
  severity?: string;
  title?: string;
  detail?: string;
  findings_json?: IntelligenceInspectionFinding[] | string | null;
  findings?: IntelligenceInspectionFinding[];
  created_at?: string;
}

export interface IntelligenceInspectionReportsResponse {
  runs: IntelligenceInspectionRun[];
  reports: IntelligenceInspectionReport[];
}

export interface ModelRetrainResponse {
  status: string;
  job_id: number | string;
  version?: string;
}

export type ModelTrainingJobStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | string;

export interface ModelTrainingJob {
  id: number | string;
  status: ModelTrainingJobStatus;
  version?: string | null;
  trained_rows?: number | null;
  error_message?: string | null;
  metrics_json?: unknown;
  detail_json?: unknown;
  created_by?: string | null;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
}

function jsonBody(payload: unknown): RequestInit {
  return {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  };
}

export function getProviderFromStatus(status: IntelligenceStatus | null): IntelligenceProviderStatus | null {
  if (!status) return null;
  if (status.provider && typeof status.provider === 'object') return status.provider;
  if (typeof status.llm_configured === 'boolean') {
    return {
      configured: status.llm_configured,
      provider: typeof status.provider === 'string' ? status.provider : 'unknown',
      model: status.model ?? undefined,
      reason: status.reason,
    };
  }
  if (typeof status.provider === 'string') {
    return { configured: Boolean(status.llm_configured), provider: status.provider, model: status.model ?? undefined };
  }
  return null;
}

export function isLlmConfigured(status: IntelligenceStatus | null): boolean {
  const provider = getProviderFromStatus(status);
  if (provider) return Boolean(provider.configured);
  if (typeof status?.llm_configured === 'boolean') return status.llm_configured;
  if (typeof status?.llm_ready === 'boolean') return status.llm_ready;
  return false;
}

export const api = {
  dashboard: () => request<AnyRecord>('/dashboard/summary'),
  devices: () => request<AnyRecord[]>('/devices'),
  predictions: (limit = 50) => request<AnyRecord[]>(`/predictions?limit=${limit}`),
  warnings: (limit = 50) => request<AnyRecord[]>(`/warnings?limit=${limit}`),
  realtimeOverview: () => request<RealtimeOverview>('/realtime/overview'),
  simulationState: () => request<SimulationState>('/simulation/state'),
  startSimulation: (payload: { device_count: number; mode: SimulationMode; transport: SimulationTransport }) =>
    request<SimulationState>('/simulation/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  stopSimulation: () => request<SimulationState>('/simulation/stop', { method: 'POST' }),
  activeModel: () => request<AnyRecord>('/models/active'),
  updateWarning: (id: number, payload: object) =>
    request<AnyRecord>(`/warnings/${id}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  trainModel: (formData: FormData) =>
    request<AnyRecord>('/ingestion/ai4i', { method: 'POST', body: formData }),
  modelRetrain: () =>
    request<ModelRetrainResponse>('/models/retrain', {
      method: 'POST',
      timeoutMs: AI_TIMEOUT,
    }),
  modelTrainingJobs: (limit = 20) =>
    request<ModelTrainingJob[]>(`/models/training-jobs?limit=${limit}`),

  // Intelligence middle-platform
  intelligenceStatus: () =>
    request<IntelligenceStatus>('/intelligence/status'),
  intelligenceQuery: (payload: IntelligenceQueryRequest) =>
    request<IntelligenceQueryResponse>('/intelligence/query', {
      ...jsonBody(payload),
      timeoutMs: AI_TIMEOUT,
    }),
  intelligenceChat: (payload: IntelligenceChatRequest) =>
    request<IntelligenceChatResponse>('/intelligence/chat', {
      ...jsonBody(payload),
      timeoutMs: AI_TIMEOUT,
    }),
  intelligenceSessions: (limit = 50) =>
    request<IntelligenceSessionListResponse>(`/intelligence/sessions?limit=${limit}`),
  intelligenceSessionByKey: (sessionKey: string) =>
    request<IntelligenceSessionByKeyResponse>(
      `/intelligence/sessions/by-key/${encodeURIComponent(sessionKey)}`,
    ),
  intelligenceKnowledgeStatus: () =>
    request<IntelligenceKnowledgeStatus>('/intelligence/knowledge/status'),
  intelligenceKnowledgeSync: (payload?: IntelligenceKnowledgeSyncRequest) =>
    request<IntelligenceKnowledgeSyncResult>('/intelligence/knowledge/sync', {
      ...(payload ? jsonBody(payload) : { method: 'POST' }),
      timeoutMs: AI_TIMEOUT,
    }),
  intelligenceInspectionSchedule: () =>
    request<IntelligenceScheduleResponse>('/intelligence/inspection/schedule'),
  intelligenceUpdateInspectionSchedule: (payload: IntelligenceScheduleUpdate) =>
    request<IntelligenceScheduleResponse>('/intelligence/inspection/schedule', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  intelligenceInspectionRun: () =>
    request<IntelligenceInspectionRunResult>('/intelligence/inspection/run', {
      method: 'POST',
      timeoutMs: AI_TIMEOUT,
    }),
  intelligenceInspectionReports: (limit = 50) =>
    request<IntelligenceInspectionReportsResponse>(
      `/intelligence/inspection/reports?limit=${limit}`,
    ),
};
