import { useState, useEffect } from 'react';
import { LandingPage } from './entrance/LandingPage';
import { SystemShell } from './system/SystemShell';
import { RouterProvider } from './system/router';
import './styles.css';
import './system.css';

const SYSTEM_HASH = /^#\/(overview|monitoring|prediction|health|inspection|warnings|model|settings)$/;

export function App() {
  const [inSystem, setInSystem] = useState(() => SYSTEM_HASH.test(window.location.hash));

  useEffect(() => {
    const syncRoute = () => setInSystem(SYSTEM_HASH.test(window.location.hash));
    window.addEventListener('hashchange', syncRoute);
    return () => window.removeEventListener('hashchange', syncRoute);
  }, []);

  // 路由先落地，动画不再承担状态切换职责；刷新和深链因此保持一致。
  const enterSystem = () => {
    window.location.hash = '/overview';
    setInSystem(true);
  };

  const exitSystem = () => {
    window.location.hash = '';
    setInSystem(false);
  };

  return inSystem ? (
    <RouterProvider>
      <SystemShell onExit={exitSystem} />
    </RouterProvider>
  ) : (
    <LandingPage onEnter={enterSystem} />
  );
}