import { useEffect, useRef } from 'react';
import { Robot, X } from '@phosphor-icons/react';
import { IntelligencePage } from '../pages/IntelligencePage';
import type { useMockData } from '../hooks/useMockData';

type Props = {
  mock: ReturnType<typeof useMockData>;
  onClose: () => void;
};

export function IntelligenceModal({ mock, onClose }: Props) {
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    panelRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  return (
    <div
      className="intelligence-modal-backdrop"
      role="presentation"
      onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}
    >
      <section
        ref={panelRef}
        className="intelligence-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="intelligence-modal-title"
        tabIndex={-1}
      >
        <header className="intelligence-modal-head">
          <div className="intelligence-modal-title">
            <span className="intelligence-modal-mark"><Robot size={18} weight="duotone" /></span>
            <div>
              <strong id="intelligence-modal-title">智能中台</strong>
              <span>保留当前业务页作为实时上下文</span>
            </div>
          </div>
          <button type="button" className="intelligence-modal-close" onClick={onClose} aria-label="关闭智能中台">
            <X size={18} />
          </button>
        </header>
        <div className="intelligence-modal-content">
          <IntelligencePage mock={mock} />
        </div>
      </section>
    </div>
  );
}
