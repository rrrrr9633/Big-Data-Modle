import { useRef, useEffect, useState } from 'react';
import gsap from 'gsap';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { useRouter, type SystemPage } from './router';
import { useMockData } from './hooks/useMockData';
import { OverviewPage }    from './pages/OverviewPage';
import { MonitoringPage }  from './pages/MonitoringPage';
import { PredictionPage }  from './pages/PredictionPage';
import { HealthPage }      from './pages/HealthPage';
import { InspectionPage }  from './pages/InspectionPage';
import { WarningsPage }    from './pages/WarningsPage';
import { ModelPage }       from './pages/ModelPage';
import { SettingsPage }    from './pages/SettingsPage';

interface Props { onExit: () => void }

export function SystemShell({ onExit }: Props) {
  const { page } = useRouter();
  const mock = useMockData();
  const mainRef = useRef<HTMLElement>(null);
  // Two-phase state lets us fade the old page out before swapping content,
  // then fade the new page in — a true crossfade instead of a hard cut.
  const [displayPage, setDisplayPage] = useState<SystemPage>(page);

  useEffect(() => {
    if (page === displayPage || !mainRef.current) { setDisplayPage(page); return; }
    const el = mainRef.current;
    gsap.timeline()
      .to(el, { opacity: 0, y: -8, scale: 0.99, duration: 0.16, ease: 'power1.in' })
      .call(() => setDisplayPage(page))
      .fromTo(el, { opacity: 0, y: 10, scale: 0.99 }, { opacity: 1, y: 0, scale: 1, duration: 0.32, ease: 'power2.out' });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const newWarnings = mock.warnings.filter(w => w.status === 'new').length;

  const statusItems = [
    { label: '在线设备', tone: 'ok'   as const, value: `${mock.dashboard.online_devices}/${mock.dashboard.total_devices}` },
    { label: '高风险',   tone: mock.dashboard.high_risk_count > 0 ? 'warn' as const : 'ok' as const, value: `${mock.dashboard.high_risk_count}` },
    { label: '活跃预警', tone: newWarnings > 0 ? 'err' as const : 'ok' as const, value: `${newWarnings}` },
  ];

  const PAGE_MAP: Record<SystemPage, React.ReactNode> = {
    overview:   <OverviewPage   mock={mock} />,
    monitoring: <MonitoringPage mock={mock} />,
    prediction: <PredictionPage mock={mock} />,
    health:     <HealthPage     mock={mock} />,
    inspection: <InspectionPage mock={mock} />,
    warnings:   <WarningsPage   mock={mock} />,
    model:      <ModelPage />,
    settings:   <SettingsPage   mock={mock} />,
  };

  return (
    <div className="sys-root">
      <TopBar statusItems={statusItems} onExit={onExit} />
      <Sidebar warningCount={newWarnings} onExit={onExit} />
      <main className="sys-main" ref={mainRef}>
        {PAGE_MAP[displayPage]}
      </main>
    </div>
  );
}