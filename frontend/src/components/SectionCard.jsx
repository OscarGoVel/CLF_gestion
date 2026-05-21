export function SectionCard({ title, action, children, style }) {
  return (
    <div className="section-card" style={style}>
      {(title || action) && (
        <div className="section-card-header">
          {title && <h3 className="section-card-title">{title}</h3>}
          {action && <div className="section-card-action">{action}</div>}
        </div>
      )}
      <div className="section-card-body">{children}</div>
    </div>
  );
}
