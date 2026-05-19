export function SidePreview({ children }) {
  return (
    <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: 'calc(100vh - 120px)' }}>
      {children}
    </div>
  );
}

export function FieldGrid({ fields, cols = 2 }) {
  return (
    <div style={{
      marginTop: 16,
      display: 'grid',
      gridTemplateColumns: `repeat(${cols}, 1fr)`,
      gap: 0,
      border: '1px solid var(--ink-200)',
      borderRadius: 4,
    }}>
      {fields.map(([k, v], i) => (
        <div key={i} style={{
          padding: '10px 12px',
          borderBottom: i < fields.length - cols ? '1px solid var(--ink-100)' : 'none',
          borderRight: i % cols < cols - 1 ? '1px solid var(--ink-100)' : 'none',
        }}>
          <div className="note">{k.toUpperCase()}</div>
          <div style={{ fontSize: 12, marginTop: 2 }}>{v ?? '—'}</div>
        </div>
      ))}
    </div>
  );
}
