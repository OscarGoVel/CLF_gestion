export function Stepper({ steps }) {
  return (
    <div className="stepper">
      {steps.map((s, i) => {
        const leftDone  = i > 0 && steps[i - 1].state === 'done';
        const rightDone = s.state === 'done';
        return (
          <div key={i} className="stepper-step">
            <div className="stepper-track">
              <div className={`stepper-line ${i === 0 ? 'hidden' : leftDone ? 'done' : ''}`} />
              <div className={`stepper-node ${s.state}`}>
                {s.state === 'done'
                  ? '✓'
                  : s.state === 'warn'
                  ? '⚠'
                  : i + 1}
              </div>
              <div className={`stepper-line ${i === steps.length - 1 ? 'hidden' : rightDone ? 'done' : ''}`} />
            </div>
            <div className="stepper-meta">
              <span className={`stepper-label ${s.state === 'todo' ? 'muted' : ''}`}>{s.label}</span>
              {s.value && <span className="stepper-val">{s.value}</span>}
              {s.badge && (
                <span className={`stepper-badge ${s.badgeType ?? 'neutral'}`}>{s.badge}</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function buildSteps(cot) {
  const estado  = cot?.estado ?? '';
  const ordered = ['Pendiente', 'Programada', 'Entregada', 'Facturada', 'Pagada'];
  const idx     = ordered.indexOf(estado);

  return [
    {
      label: 'Cotizada',
      value: cot?.fecha_cotizacion ?? null,
      state: 'done',
    },
    {
      label: 'OC recibida',
      value: cot?.orden_compra ?? null,
      state: cot?.orden_compra ? 'done' : idx >= 1 ? 'current' : 'todo',
    },
    {
      label: 'Stock',
      value: cot?.stock_ok === true ? 'Completo' : null,
      state: cot?.stock_ok === true
        ? 'done'
        : cot?.stock_ok === false
          ? 'warn'
          : idx >= 2 ? 'done' : 'todo',
      badge:     cot?.stock_ok === false ? `⚠ ${cot?.faltantes ?? '?'} faltantes` : null,
      badgeType: 'warn',
    },
    {
      label: 'Entrega',
      value: cot?.fecha_entrega ?? null,
      state: estado === 'Entregada' || estado === 'Facturada' || estado === 'Pagada'
        ? 'done'
        : idx === 2 ? 'current' : 'todo',
    },
    {
      label: 'Factura',
      value: cot?.folio_factura ?? null,
      state: estado === 'Facturada' || estado === 'Pagada' ? 'done' : idx === 3 ? 'current' : 'todo',
      badge:     (estado !== 'Facturada' && estado !== 'Pagada' && idx === 3) ? 'Pendiente' : null,
      badgeType: 'info',
    },
    {
      label: 'Pago',
      value: estado === 'Pagada' ? cot?.fecha_pago ?? 'Pagada' : null,
      state: estado === 'Pagada' ? 'done' : idx === 4 ? 'current' : 'todo',
    },
  ];
}
