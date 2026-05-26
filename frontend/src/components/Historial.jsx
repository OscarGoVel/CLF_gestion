import { useFetch } from '../hooks/useFetch';

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

export function Historial({ entidad, entidadId }) {
  const { data, loading } = useFetch(
    entidadId ? `/api/historial/${entidad}/${entidadId}` : null,
  );
  const eventos = data?.eventos ?? [];

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 10.5, fontFamily: 'var(--mono)', color: 'var(--ink-500)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        Historial
      </div>
      {loading && (
        <div style={{ color: 'var(--ink-400)', fontSize: 12 }}>Cargando…</div>
      )}
      {!loading && eventos.length === 0 && (
        <div style={{ color: 'var(--ink-400)', fontSize: 12 }}>Sin eventos registrados</div>
      )}
      {eventos.map((ev) => (
        <div key={ev.id} style={{ display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--ink-100)' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--accent)', flexShrink: 0, marginTop: 5 }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: 'var(--ink-800)' }}>{ev.accion}</div>
            {ev.detalle && (
              <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 1 }}>{ev.detalle}</div>
            )}
            <div style={{ fontSize: 10.5, color: 'var(--ink-400)', marginTop: 2 }}>{fmt(ev.ts)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
