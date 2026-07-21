// API client — falls back gracefully when backend is unreachable.
// The config's api.base is proxied via Vite (/api/v1).

const BASE = '/api/v1';
const TIMEOUT = 8000;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const tid = setTimeout(() => controller.abort(), TIMEOUT);
  try {
    const res = await fetch(`${BASE}${path}`, { ...options, signal: controller.signal });
    clearTimeout(tid);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
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
  // Reserved AI endpoint — wired when backend is ready
  aiChat: (message: string) =>
    request<AnyRecord>('/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    }),
};