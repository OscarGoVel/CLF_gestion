export function KpiCard({ label, value, foot, warn, color }) {
  return (
    <div className="card kpi" style={color ? { borderLeft: `4px solid ${color}` } : undefined}>
      <div className="k-label">{label}</div>
      <div className="k-value" style={{ color: color ?? (warn ? 'var(--danger)' : undefined) }}>
        {value ?? '—'}
      </div>
      {foot && <div className="k-foot">{foot}</div>}
    </div>
  );
}

export function KpiGrid({ cards }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${cards.length}, 1fr)`,
      gap: 12,
      marginBottom: 28,
    }}>
      {cards.map((card, i) => <KpiCard key={i} {...card} />)}
    </div>
  );
}
