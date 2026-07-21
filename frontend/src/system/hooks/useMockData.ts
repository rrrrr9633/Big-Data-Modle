// Mock data generator — drives all dashboard pages when backend is unreachable.
// Data is seeded so it's deterministic per "tick" but looks live on each update.
import { useState, useEffect } from 'react';
import { api } from '../api/client';
import type { RealtimeDeviceSnapshot } from '../api/client';

// ─── Types ──────────────────────────────────────────────────────────────────
export interface SensorReading {
  sensor_code: string;
  sensor_name: string;
  value: number;
  unit: string;
  quality: number;
  status?: string;
  trend: number[]; // last 20 samples
}

export interface DeviceState {
  device_code: string;
  device_name: string;
  device_type: string;
  status: 'online' | 'warning' | 'fault' | 'offline';
  health_score: number;
  failure_probability: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  anomaly_score: number;
  rul_hours: number;
  last_seen: string;
  sensors: SensorReading[];
}

export interface PredictionRecord {
  id: number;
  device_code: string;
  device_name: string;
  failure_probability: number;
  health_score: number;
  risk_level: string;
  anomaly_score: number;
  rul_hours: number;
  created_at: string;
}

export interface WarningRecord {
  id: number;
  device_code: string;
  device_name: string;
  risk_level: string;
  title: string;
  detail: string;
  status: 'new' | 'acknowledged' | 'processing' | 'resolved' | 'ignored';
  created_at: string;
  suggested_action: string;
}

export interface DashboardSummary {
  total_devices: number;
  online_devices: number;
  high_risk_count: number;
  warning_count: number;
  avg_health_score: number;
  prediction_count: number;
}

export interface InspectionTask {
  id: number;
  device_code: string;
  device_name: string;
  task_type: string;
  priority: 'urgent' | 'high' | 'normal' | 'low';
  status: 'pending' | 'in_progress' | 'completed' | 'skipped';
  assigned_to: string;
  due_at: string;
  note: string;
}

// ─── Seeded RNG ──────────────────────────────────────────────────────────────
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

// ─── Device catalogue ────────────────────────────────────────────────────────
interface DeviceMeta { name: string; type: string; seed: number; degraded: boolean; critical: boolean }
const DEVICES: Record<string, DeviceMeta> = {
  'CNC-001': { name: '数控加工中心 #01', type: 'CNC', seed: 42,   degraded: false, critical: false },
  'CNC-002': { name: '数控加工中心 #02', type: 'CNC', seed: 137,  degraded: false, critical: false },
  'CNC-003': { name: '数控加工中心 #03', type: 'CNC', seed: 256,  degraded: false, critical: false },
  'CNC-004': { name: '激光切割机 #01',   type: 'LZC', seed: 991,  degraded: true,  critical: false },
  'CNC-005': { name: '激光切割机 #02',   type: 'LZC', seed: 777,  degraded: false, critical: false },
  'CNC-006': { name: '打磨抛光机 #01',   type: 'GND', seed: 1234, degraded: true,  critical: true  },
};
export const DEVICE_IDS = Object.keys(DEVICES);

interface SensorMeta { code: string; name: string; unit: string; lo: number; hi: number }
const SENSORS: SensorMeta[] = [
  { code: 'spindle_temperature', name: '主轴温度',   unit: '°C',    lo: 42,  hi: 88  },
  { code: 'vibration_rms',       name: '振动有效值', unit: 'mm/s',  lo: 0.4, hi: 4.8 },
  { code: 'cutting_force',       name: '切削力',     unit: 'N',     lo: 180, hi: 820 },
  { code: 'coolant_flow',        name: '冷却液流量', unit: 'L/min', lo: 7,   hi: 16  },
  { code: 'power_consumption',   name: '功率消耗',   unit: 'kW',    lo: 3.2, hi: 13  },
];

function trend(base: number, spread: number, seed: number): number[] {
  const r = rng(seed);
  return Array.from({ length: 20 }, (_, i) => {
    const drift = (i / 20) * spread * 0.25;
    return Math.max(0, base + drift + (r() - 0.5) * spread);
  });
}

// ─── Device state ────────────────────────────────────────────────────────────
export function generateDeviceState(id: string, tick: number): DeviceState {
  const meta = DEVICES[id]!;
  const r = rng(meta.seed + tick * 7);

  const baseHealth = meta.critical ? 28 + r() * 22
    : meta.degraded ? 52 + r() * 22
    : 68 + r() * 28;
  const health_score = +(Math.min(99, Math.max(8, baseHealth + Math.sin(tick * 0.08) * 4)).toFixed(1));
  const failure_probability = +(Math.max(0.01, ((100 - health_score) / 100) * 1.35).toFixed(3));
  const risk_level =
    failure_probability > 0.52 ? 'critical'
    : failure_probability > 0.32 ? 'high'
    : failure_probability > 0.16 ? 'medium' : 'low';
  const status =
    risk_level === 'critical' ? 'fault'
    : risk_level === 'high'   ? 'warning' : 'online';

  const factor = meta.critical ? 1.65 : meta.degraded ? 1.28 : 1 + r() * 0.12;
  const sensors = SENSORS.map(s => {
    const base = s.lo + (s.hi - s.lo) * (0.3 + r() * 0.7);
    return {
      sensor_code: s.code,
      sensor_name: s.name,
      value: +(base * factor + (r() - 0.5) * base * 0.06).toFixed(2),
      unit: s.unit,
      quality: meta.critical ? +(0.55 + r() * 0.28).toFixed(2) : +(0.86 + r() * 0.13).toFixed(2),
      trend: trend(base * factor, base * 0.08, meta.seed + s.code.charCodeAt(0) + tick),
    };
  });

  return {
    device_code: id, device_name: meta.name, device_type: meta.type,
    status, health_score, failure_probability, risk_level,
    anomaly_score: +(r() * (meta.critical ? 0.88 : meta.degraded ? 0.52 : 0.22)).toFixed(3),
    rul_hours: +((health_score / 100) * 2000 + r() * 180).toFixed(0),
    last_seen: new Date().toISOString(),
    sensors,
  };
}

// ─── Predictions ─────────────────────────────────────────────────────────────
export function generatePredictions(tick: number): PredictionRecord[] {
  return DEVICE_IDS.flatMap((id, di) => {
    const d = generateDeviceState(id, tick);
    return Array.from({ length: 3 }, (_, i) => ({
      id: di * 100 + i + 1,
      device_code: id, device_name: d.device_name,
      failure_probability: +(d.failure_probability * (0.92 + i * 0.04)).toFixed(3),
      health_score: +(d.health_score - i * 1.8).toFixed(1),
      risk_level: d.risk_level,
      anomaly_score: +(d.anomaly_score * (1 + i * 0.08)).toFixed(3),
      rul_hours: d.rul_hours - i * 18,
      created_at: new Date(Date.now() - (2 - i) * 300_000).toISOString(),
    }));
  }).sort((a, b) => b.failure_probability - a.failure_probability);
}

// ─── Warnings ────────────────────────────────────────────────────────────────
const WARN_TPL = [
  { title: '主轴温度异常升高',   detail: '主轴温度超过预警阈值，冷却系统可能存在故障', action: '停机检修冷却系统' },
  { title: '振动幅度持续超标',   detail: '振动有效值持续上升，主轴轴承可能存在磨损', action: '检查并更换主轴轴承' },
  { title: '健康评分急剧下降',   detail: '综合健康评分持续下降，预计剩余寿命不足200小时', action: '安排预防性维护计划' },
  { title: '切削力异常波动',     detail: '切削力波动超过25%，刀具可能存在崩刃', action: '检查并更换切削刀具' },
  { title: '冷却液流量不足',     detail: '冷却液流量低于设定阈值，存在热损伤风险', action: '检查冷却液管路和泵' },
];
const WARN_STATUSES: WarningRecord['status'][] = ['new', 'acknowledged', 'processing', 'resolved'];

export function generateWarnings(tick: number): WarningRecord[] {
  const results: WarningRecord[] = [];
  let id = 1;
  const seeds: Array<[string, string, number]> = [
    ['CNC-006', 'critical', 3], ['CNC-004', 'high', 2], ['CNC-002', 'medium', 1],
  ];
  seeds.forEach(
    ([device, risk, count]) => {
      const d = generateDeviceState(device, tick);
      for (let i = 0; i < count; i++) {
        results.push({
          id: id++,
          device_code: device, device_name: d.device_name, risk_level: risk,
          title: WARN_TPL[i % WARN_TPL.length]!.title,
          detail: WARN_TPL[i % WARN_TPL.length]!.detail,
          status: WARN_STATUSES[Math.min(i, WARN_STATUSES.length - 1)]!,
          created_at: new Date(Date.now() - (i + 1) * 3_600_000).toISOString(),
          suggested_action: WARN_TPL[i % WARN_TPL.length]!.action,
        });
      }
    }
  );
  return results;
}

// ─── Inspections ─────────────────────────────────────────────────────────────
const INSPECTION_TYPES = ['润滑油检查', '轴承间隙检测', '刀具磨损测量', '冷却系统检查', '电气系统检查', '传动系统检查'];
const ASSIGNEES = ['张工', '李工', '王工', '赵工'];
const PRIORITY: InspectionTask['priority'][] = ['urgent', 'high', 'normal', 'low'];
const ISTATUS: InspectionTask['status'][] = ['pending', 'in_progress', 'completed', 'pending'];

export function generateInspections(tick: number): InspectionTask[] {
  return DEVICE_IDS.flatMap((id, di) => {
    const d = generateDeviceState(id, tick);
    return INSPECTION_TYPES.slice(0, di < 2 ? 3 : 2).map((type, ti) => ({
      id: di * 10 + ti + 1,
      device_code: id, device_name: d.device_name,
      task_type: type,
      priority: PRIORITY[Math.min(ti, PRIORITY.length - 1)]!,
      status: ISTATUS[Math.min(ti, ISTATUS.length - 1)]!,
      assigned_to: ASSIGNEES[di % ASSIGNEES.length]!,
      due_at: new Date(Date.now() + (ti + 1) * 86_400_000).toISOString(),
      note: d.risk_level === 'critical' ? '⚠ 高风险设备，优先处理' : '',
    }));
  });
}

// ─── Dashboard summary ───────────────────────────────────────────────────────
export function generateDashboard(tick: number): DashboardSummary {
  const devs = DEVICE_IDS.map(id => generateDeviceState(id, tick));
  return {
    total_devices: devs.length,
    online_devices: devs.filter(d => d.status !== 'offline').length,
    high_risk_count: devs.filter(d => ['high', 'critical'].includes(d.risk_level)).length,
    warning_count: generateWarnings(tick).filter(w => w.status === 'new').length,
    avg_health_score: +(devs.reduce((s, d) => s + d.health_score, 0) / devs.length).toFixed(1),
    prediction_count: devs.length * 3,
  };
}

function liveDeviceState(
  snapshot: RealtimeDeviceSnapshot,
  previous: DeviceState | undefined,
): DeviceState {
  const points = Object.values(snapshot.points ?? {});
  const previousSensors = new Map((previous?.sensors ?? []).map(sensor => [sensor.sensor_code, sensor]));
  const sensors = points.map(point => ({
    sensor_code: point.point_code,
    sensor_name: SENSOR_NAMES[point.point_code] ?? point.point_code,
    value: point.value,
    unit: point.unit ?? '',
    quality: point.quality,
    status: point.status,
    trend: [...(previousSensors.get(point.point_code)?.trend ?? []), point.value].slice(-20),
  }));
  const values = new Map(sensors.map(sensor => [sensor.sensor_code, sensor.value]));
  const rawAnomaly = (
    Math.max(0, ((values.get('spindle_temperature') ?? 42) - 65) / 30) * 0.35
    + Math.max(0, ((values.get('vibration_rms') ?? 1.4) - 3) / 8) * 0.3
    + Math.max(0, ((values.get('tool_wear') ?? 18) - 75) / 150) * 0.2
    + Math.max(0, ((values.get('spindle_load') ?? 46) - 70) / 30) * 0.15
  );
  const averageQuality = sensors.length > 0
    ? sensors.reduce((sum, sensor) => sum + sensor.quality, 0) / sensors.length
    : 1;
  const faultStatuses = sensors.map(sensor => sensor.status).filter(status => status && status !== 'good');
  const faultPenalty = faultStatuses.some(value => value === 'sudden_fault')
    ? 0.35
    : faultStatuses.some(value => ['sensor_stuck', 'sensor_drift'].includes(value)) ? 0.25
    : faultStatuses.length > 0 ? 0.12 : 0;
  const anomaly_score = Math.min(1, rawAnomaly + (1 - averageQuality) * 0.65 + faultPenalty);
  const health_score = +(Math.max(8, 100 - anomaly_score * 100)).toFixed(1);
  const failure_probability = +Math.max(0.01, ((100 - health_score) / 100) * 1.35).toFixed(3);
  const risk_level: DeviceState['risk_level'] = failure_probability > 0.52
    ? 'critical' : failure_probability > 0.32 ? 'high' : failure_probability > 0.16 ? 'medium' : 'low';
  const status: DeviceState['status'] = snapshot.online
    ? faultStatuses.some(value => ['sensor_stuck', 'sensor_drift', 'sudden_fault'].includes(value))
      ? 'fault'
      : faultStatuses.length > 0 || sensors.some(sensor => sensor.quality < 0.85) ? 'warning' : 'online'
    : 'offline';

  return {
    device_code: snapshot.device_code,
    device_name: `数控机床 ${snapshot.device_code}`,
    device_type: 'CNC',
    status,
    health_score,
    failure_probability,
    risk_level,
    anomaly_score: +anomaly_score.toFixed(3),
    rul_hours: +((health_score / 100) * 2000).toFixed(0),
    last_seen: snapshot.ts,
    sensors,
  };
}

const SENSOR_NAMES: Record<string, string> = {
  air_temperature: '环境温度', process_temperature: '工艺温度', rotational_speed: '主轴转速',
  torque: '扭矩', tool_wear: '刀具磨损', spindle_temperature: '主轴温度',
  spindle_load: '主轴负载', vibration_rms: '振动 RMS',
};

function livePredictions(devices: DeviceState[]): PredictionRecord[] {
  return devices.flatMap((device, deviceIndex) => Array.from({ length: 3 }, (_, index) => ({
    id: deviceIndex * 100 + index + 1,
    device_code: device.device_code,
    device_name: device.device_name,
    failure_probability: +(device.failure_probability * (0.92 + index * 0.04)).toFixed(3),
    health_score: +(device.health_score - index * 1.8).toFixed(1),
    risk_level: device.risk_level,
    anomaly_score: +(device.anomaly_score * (1 + index * 0.08)).toFixed(3),
    rul_hours: device.rul_hours - index * 18,
    created_at: device.last_seen,
  })) ).sort((a, b) => b.failure_probability - a.failure_probability);
}

function liveWarnings(devices: DeviceState[]): WarningRecord[] {
  return devices
    .filter(device => ['medium', 'high', 'critical'].includes(device.risk_level))
    .map((device, index) => ({
      id: index + 1,
      device_code: device.device_code,
      device_name: device.device_name,
      risk_level: device.risk_level,
      title: device.risk_level === 'critical' ? '设备传感器异常' : '设备健康风险升高',
      detail: `当前异常评分 ${device.anomaly_score.toFixed(3)}，请检查实时传感器读数`,
      status: 'new' as const,
      created_at: device.last_seen,
      suggested_action: '安排设备巡检',
    }));
}

export function useMockData() {
  const [tick, setTick] = useState(0);
  const [liveSnapshots, setLiveSnapshots] = useState<RealtimeDeviceSnapshot[]>([]);
  const [liveBackendAvailable, setLiveBackendAvailable] = useState(false);
  const [simulationRunning, setSimulationRunning] = useState<boolean | null>(null);
  const [liveHistory, setLiveHistory] = useState<DeviceState[]>([]);

  useEffect(() => {
    let active = true;
    api.simulationState()
      .then(state => {
        if (!active) return;
        setLiveBackendAvailable(true);
        setSimulationRunning(state.running);
        if (!state.running) setLiveSnapshots([]);
      })
      .catch(() => {
        if (!active) return;
        setLiveBackendAvailable(false);
        setSimulationRunning(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!simulationRunning) return;
    let active = true;
    const refresh = async () => {
      try {
        const overview = await api.realtimeOverview();
        if (!active) return;
        setLiveBackendAvailable(true);
        setLiveSnapshots(overview.devices);
      } catch {
        if (active) setLiveBackendAvailable(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => {
      setTick(value => value + 1);
      void refresh();
    }, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [simulationRunning]);

  const generatedDevices = DEVICE_IDS.map(id => generateDeviceState(id, tick));
  const liveDevices = liveSnapshots.map(snapshot => liveDeviceState(
    snapshot,
    liveHistory.find(device => device.device_code === snapshot.device_code),
  ));
  const devices = liveBackendAvailable ? liveDevices : generatedDevices;
  const predictions = liveBackendAvailable ? livePredictions(devices) : generatePredictions(tick);
  const warnings = liveBackendAvailable ? liveWarnings(devices) : generateWarnings(tick);
  const dashboard = liveBackendAvailable
    ? {
        total_devices: devices.length,
        online_devices: devices.filter(device => device.status !== 'offline').length,
        high_risk_count: devices.filter(device => ['high', 'critical'].includes(device.risk_level)).length,
        warning_count: warnings.filter(warning => warning.status === 'new').length,
        avg_health_score: devices.length > 0
          ? +(devices.reduce((sum, device) => sum + device.health_score, 0) / devices.length).toFixed(1)
          : 0,
        prediction_count: predictions.length,
      }
    : generateDashboard(tick);

  useEffect(() => {
    if (liveDevices.length > 0) setLiveHistory(liveDevices);
  }, [liveSnapshots]);

  const markSimulationStarted = () => {
    setLiveBackendAvailable(true);
    setSimulationRunning(true);
  };

  const markSimulationStopped = () => {
    setLiveBackendAvailable(true);
    setSimulationRunning(false);
    setLiveSnapshots([]);
  };

  return {
    tick,
    devices,
    predictions,
    warnings,
    inspections: liveBackendAvailable
      ? devices.length > 0
        ? generateInspections(tick).map((task, index) => ({
            ...task,
            device_code: devices[index % devices.length]?.device_code ?? task.device_code,
            device_name: devices[index % devices.length]?.device_name ?? task.device_name,
          }))
        : []
      : generateInspections(tick),
    dashboard,
    deviceIds: devices.map(device => device.device_code),
    markSimulationStarted,
    markSimulationStopped,
  };
}