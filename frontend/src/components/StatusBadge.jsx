const TONE = {
  success: { bg: 'var(--color-success-bg)', text: 'var(--color-success)' },
  info:    { bg: 'var(--color-info-bg)',    text: 'var(--color-info)' },
  warning: { bg: 'var(--color-warning-bg)', text: 'var(--color-warning)' },
  danger:  { bg: 'var(--color-danger-bg)',  text: 'var(--color-danger)' },
  neutral: { bg: 'var(--color-neutral-bg)', text: 'var(--color-neutral)' },
};

const STATUS_TONE = {
  // Cotizaciones
  Borrador:               'neutral',
  Pendiente:              'warning',
  Programada:             'info',
  'Parcialmente Entregada': 'info',
  Entregada:              'success',
  Facturada:              'success',
  Pagada:                 'success',
  Cancelada:              'neutral',
  Vencida:                'danger',
  Rechazada:              'danger',
  // Compras
  Creada:                 'neutral',
  'Recibida Parcial':     'warning',
  'Recibida Completa':    'success',
  // Conteos / inventario
  abierto:                'info',
  cerrado:                'neutral',
  // Usuarios
  Activo:                 'success',
  Inactivo:               'neutral',
  // Roles
  admin:                  'info',
  operador:               'neutral',
  almacenista:            'neutral',
  lectura:                'neutral',
};

export function StatusBadge({ status, tone: toneProp }) {
  const t = toneProp ?? STATUS_TONE[status] ?? 'neutral';
  const colors = TONE[t] ?? TONE.neutral;
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 4,
      fontSize: 11,
      fontWeight: 500,
      background: colors.bg,
      color: colors.text,
      whiteSpace: 'nowrap',
    }}>
      {status}
    </span>
  );
}
