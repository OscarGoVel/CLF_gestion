/**
 * Next-action ribbon — contextual "qué hacer ahora" based on cotizacion state.
 * action: { message, detail, buttons: [{ label, onClick, primary }] }
 */
export function NextRibbon({ action, warn }) {
  if (!action) return null;
  return (
    <div className={`next-ribbon${warn ? ' warn' : ''}`}>
      <div>
        <strong>{action.message}</strong>
        {action.detail && (
          <>
            <br />
            <span style={{ fontSize: 11.5 }}>{action.detail}</span>
          </>
        )}
      </div>
      {action.buttons && (
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          {action.buttons.map((b, i) => (
            <button
              key={i}
              className={`btn btn-sm${b.primary ? ' btn-primary' : ''}`}
              onClick={b.onClick}
            >
              {b.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Derives the next action from a cotizacion object.
 * Returns null when no action is needed (e.g. Pagada).
 */
export function buildNextAction(cot, handlers = {}) {
  if (!cot) return null;
  const { estado, stock_ok, faltantes, orden_compra, folio_factura } = cot;

  if (estado === 'Pagada') return null;

  if (estado === 'Borrador') {
    return {
      message: 'Cotización en borrador.',
      detail: 'Completa las partidas y envía al cliente para continuar.',
      buttons: [{ label: 'Enviar al cliente →', onClick: handlers.onEnviar, primary: true }],
    };
  }

  if (estado === 'Pendiente') {
    return {
      message: 'Esperando orden de compra del cliente.',
      detail: orden_compra ? null : 'Sin OC registrada aún.',
      buttons: [{ label: 'Registrar OC', onClick: handlers.onRegistrarOC, primary: false }],
    };
  }

  if (estado === 'Programada' && stock_ok === false) {
    return {
      message: 'Esta cotización no se puede entregar todavía.',
      detail: `${faltantes ?? '?'} productos requieren compra al proveedor.`,
      buttons: [
        { label: 'Sustituir productos', onClick: handlers.onSustituir },
        { label: 'Generar OC →', onClick: handlers.onGenerarOC, primary: true },
      ],
    };
  }

  if (estado === 'Programada' && stock_ok !== false) {
    return {
      message: 'Stock completo. Lista para entregar.',
      detail: 'Programa la entrega con el cliente.',
      buttons: [
        { label: 'Nota remision', onClick: handlers.onNotaRemision, primary: true },
        { label: 'Marcar entregada', onClick: handlers.onEntregar },
      ].filter((b) => b.onClick),
    };
  }

  if (estado === 'Parcialmente Entregada') {
    return {
      message: 'Entrega parcial registrada.',
      detail: 'Emite la nota de remision con las cantidades entregadas.',
      buttons: [
        { label: 'Nota remision', onClick: handlers.onNotaRemision, primary: true },
      ].filter((b) => b.onClick),
    };
  }

  if (estado === 'Entregada' && !folio_factura) {
    return {
      message: 'Entregada. Pendiente de facturar.',
      detail: 'Genera el CFDI para cerrar el ciclo.',
      buttons: [{ label: 'Facturar ahora →', onClick: handlers.onFacturar, primary: true }],
    };
  }

  if (estado === 'Facturada') {
    return {
      message: 'Facturada. Pendiente de pago.',
      detail: cot.fecha_vencimiento ? `Vence ${cot.fecha_vencimiento}` : null,
      buttons: [{ label: 'Registrar pago', onClick: handlers.onPago, primary: true }],
    };
  }

  return null;
}
