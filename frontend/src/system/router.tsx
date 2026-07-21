import { createContext, useContext, useState, useEffect } from 'react';

export type SystemPage =
  | 'overview'
  | 'monitoring'
  | 'prediction'
  | 'health'
  | 'inspection'
  | 'warnings'
  | 'model'
  | 'settings';

interface RouterCtx {
  page: SystemPage;
  navigate: (p: SystemPage) => void;
}

const RouterContext = createContext<RouterCtx>({ page: 'overview', navigate: () => {} });

const ALL_PAGES: SystemPage[] = [
  'overview', 'monitoring', 'prediction', 'health',
  'inspection', 'warnings', 'model', 'settings',
];

function parsePage(raw: string): SystemPage {
  const s = raw.replace(/^#?\//, '');
  return ALL_PAGES.includes(s as SystemPage) ? (s as SystemPage) : 'overview';
}

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState<SystemPage>(() =>
    parsePage(window.location.hash),
  );

  const navigate = (p: SystemPage) => {
    window.location.hash = `/${p}`;
    setPage(p);
  };

  useEffect(() => {
    const handler = () => setPage(parsePage(window.location.hash));
    window.addEventListener('hashchange', handler);
    return () => window.removeEventListener('hashchange', handler);
  }, []);

  return (
    <RouterContext.Provider value={{ page, navigate }}>
      {children}
    </RouterContext.Provider>
  );
}

export const useRouter = () => useContext(RouterContext);