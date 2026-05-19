export function ConfirmModal({
  open, onClose, onConfirm,
  title, description,
  confirmLabel = 'Confirmar',
  loading = false,
  danger = false,
}) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="card" style={{ width: 400, padding: 28 }}>
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 10 }}>{title}</div>
        {description && (
          <div style={{ fontSize: 13, color: 'var(--ink-600)', marginBottom: 20, lineHeight: 1.55 }}>
            {description}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose} disabled={loading}>Cancelar</button>
          <button
            className="btn"
            disabled={loading}
            onClick={onConfirm}
            style={danger ? {
              background: 'var(--danger)', borderColor: 'var(--danger)',
              color: '#fff', cursor: loading ? 'not-allowed' : 'pointer',
            } : { cursor: loading ? 'not-allowed' : 'pointer' }}
          >
            {loading ? 'Procesando…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
