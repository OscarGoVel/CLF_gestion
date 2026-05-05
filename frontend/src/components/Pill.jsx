const STATUS_CLASS = {
  'Borrador':   's-borrador',
  'Pendiente':  's-pendiente',
  'Programada': 's-programada',
  'Entregada':  's-entregada',
  'Facturada':  's-facturada',
  'Pagada':     's-pagada',
  'Rechazada':  's-rechazada',
  'Parcial':    's-programada',
};

export function Pill({ status, children }) {
  const cls = STATUS_CLASS[status] ?? '';
  return (
    <span className={`pill ${cls}`}>
      {children ?? status}
    </span>
  );
}
