export function KpiCard({ label, value, foot, warn }) {
  return (
    <div className="kpi">
      <div className="k-label">{label}</div>
      <div className="k-value" style={warn ? { color: 'var(--danger)' } : undefined}>{value ?? '—'}</div>
      {foot && <div className="k-foot">{foot}</div>}
    </div>
  );
}

export function KpiGrid({ cards }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cards.length}, 1fr)`,
      gap: 0,
      border: '1px solid var(--ink-200)',
      borderRadius: 6,
      marginBottom: 28,
    }}>
      {cards.map((card, i) => (
        <div key={i} style={{ borderRight: i < cards.length - 1 ? '1px solid var(--ink-200)' : 'none' }}>
          <KpiCard {...card} />
        </div>
      ))}
    </div>
  );
}
