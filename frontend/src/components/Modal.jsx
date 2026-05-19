export function Modal({ open, onClose, title, children, width = 480 }) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="card" style={{ width, padding: 28, maxHeight: '90vh', overflowY: 'auto' }}>
        {title && <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 20 }}>{title}</div>}
        {children}
      </div>
    </div>
  );
}
