import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';

function fmt(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

export default function AdminAuditoria() {
  const navigate = useNavigate();
  const { data, loading } = useFetch('/api/ajustes/audit');
  const eventos = data?.eventos ?? data ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Administración</span>
        <span className="sep">/</span>
        <span>Auditoría</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Auditoría</div>
          <div className="page-sub">Registro de acciones del sistema</div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Fecha</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Usuario</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Evento</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Detalle</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>IP</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && Array.isArray(eventos) && eventos.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin eventos registrados</td></tr>
            )}
            {Array.isArray(eventos) && eventos.map((ev, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)', whiteSpace: 'nowrap' }}>
                  {fmt(ev.ts || ev.fecha || ev.timestamp || ev.created_at)}
                </td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{ev.username || ev.usuario || '—'}</td>
                <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>{ev.evento || ev.accion || ev.tipo || '—'}</td>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-500)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {ev.detalle || ev.descripcion || '—'}
                </td>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)', fontFamily: 'monospace' }}>
                  {ev.ip || '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
