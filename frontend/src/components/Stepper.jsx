/**
 * Stepper de proceso para cotizaciones.
 * steps: [{ label, value, state }]  state: 'done' | 'current' | 'todo'
 */
export function Stepper({ steps }) {
  return (
    <div className="stepper">
      {steps.map((s, i) => (
        <div key={i} className={`step ${s.state}`}>
          <div className="s-label">{s.label}</div>
          <div className="s-val">{s.value ?? '—'}</div>
        </div>
      ))}
    </div>
  );
}

/**
 * Builds stepper steps from a cotizacion object.
 * cotizacion: { estado, fecha_cotizacion, orden_compra, stock_ok, fecha_entrega, factura_id, pago_recibido }
 */
export function buildSteps(cot) {
  const estado = cot?.estado ?? '';
  const ordered = ['Pendiente', 'Programada', 'Entregada', 'Facturada', 'Pagada'];
  const idx = ordered.indexOf(estado);

  const steps = [
    {
      label: 'Cotizada',
      value: cot?.fecha_cotizacion ?? '—',
      state: 'done',
    },
    {
      label: 'OC recibida',
      value: cot?.orden_compra ?? '—',
      state: cot?.orden_compra ? 'done' : idx >= 1 ? 'current' : 'todo',
    },
    {
      label: 'Stock',
      value: cot?.stock_ok === false
        ? `${cot?.faltantes ?? '?'} faltantes`
        : cot?.stock_ok
          ? 'Completo'
          : '—',
      state: cot?.stock_ok === true
        ? 'done'
        : cot?.stock_ok === false
          ? 'current'
          : idx >= 2 ? 'done' : 'todo',
    },
    {
      label: 'Entrega',
      value: cot?.fecha_entrega ?? (estado === 'Entregada' ? 'Entregada' : '—'),
      state: estado === 'Entregada' || estado === 'Facturada' || estado === 'Pagada'
        ? 'done'
        : idx === 2 ? 'current' : 'todo',
    },
    {
      label: 'Factura',
      value: cot?.folio_factura ?? (estado === 'Facturada' || estado === 'Pagada' ? '✓' : '—'),
      state: estado === 'Facturada' || estado === 'Pagada' ? 'done' : idx === 3 ? 'current' : 'todo',
    },
    {
      label: 'Pago',
      value: estado === 'Pagada' ? '✓' : '—',
      state: estado === 'Pagada' ? 'done' : idx === 4 ? 'current' : 'todo',
    },
  ];

  return steps;
}
