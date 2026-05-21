export function EmptyState({ message, detail, cta }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '36px 24px', gap: 10,
      color: 'var(--ink-400)', textAlign: 'center',
    }}>
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 8v4M12 16h.01"/>
      </svg>
      <div style={{ fontSize: 13, color: 'var(--ink-500)', fontWeight: 500 }}>{message}</div>
      {detail && <div style={{ fontSize: 12, color: 'var(--ink-400)', maxWidth: 280 }}>{detail}</div>}
      {cta && <div style={{ marginTop: 4 }}>{cta}</div>}
    </div>
  );
}
