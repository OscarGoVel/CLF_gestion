import { useState, useEffect } from 'react';
import { toastSignal } from '../lib/toast';

function ToastItem({ toast, onRemove }) {
  const icon = toast.type === 'success' ? '✓' : toast.type === 'error' ? '✕' : '⚠';
  return (
    <div className={`toast ${toast.type}`} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
      <span style={{ fontWeight: 700, flexShrink: 0 }}>{icon}</span>
      <span style={{ flex: 1 }}>{toast.message}</span>
      <button
        onClick={() => onRemove(toast.id)}
        style={{ background: 'none', border: 'none', cursor: 'pointer', opacity: 0.6,
                 fontSize: 14, lineHeight: 1, padding: '0 0 0 4px', flexShrink: 0 }}
      >×</button>
    </div>
  );
}

export function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    toastSignal.dispatch = (t) => {
      setToasts((prev) => [...prev, t]);
      setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== t.id)), 3500);
    };
    return () => { toastSignal.dispatch = null; };
  }, []);

  const remove = (id) => setToasts((prev) => prev.filter((x) => x.id !== id));

  if (!toasts.length) return null;
  return (
    <div className="toast-wrap">
      {toasts.map((t) => <ToastItem key={t.id} toast={t} onRemove={remove} />)}
    </div>
  );
}
