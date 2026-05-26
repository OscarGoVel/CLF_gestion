const TONE_COLOR = {
  success: 'var(--color-success)',
  info:    'var(--color-info)',
  warning: 'var(--color-warning)',
  danger:  'var(--color-danger)',
  neutral: 'var(--color-neutral)',
};

export function KpiCard({ label, value, foot, warn, color, tone, delta }) {
  const borderColor = color ?? (tone ? TONE_COLOR[tone] : undefined) ?? (warn ? 'var(--color-danger)' : undefined);
  return (
    <div className="card kpi" style={borderColor ? { borderLeft: `4px solid ${borderColor}` } : undefined}>
      <div className="k-label">{label}</div>
      <div className="k-value">
        {value ?? '—'}
      </div>
      {delta && <div className="k-foot k-delta">{delta}</div>}
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
