import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';

function fmt(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

export default function PreInvList() {
  const navigate = useNavigate();
  const { data, loading } = useFetch('/api/preinventario/sesiones');

  const sesiones = data?.sesiones ?? [];
  const kpis     = data?.kpis     ?? {};

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Pre-inventario</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Pre-inventario</div>
          <div className="page-sub">Sesiones de conteo físico</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/preinventario/nueva')}>
          Nueva sesión
        </button>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Sesiones abiertas</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{kpis.abiertas ?? 0}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Pendientes aprobación</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: (kpis.pendientes_aprobacion ?? 0) > 0 ? 'var(--orange-600, #ea580c)' : '' }}>
            {kpis.pendientes_aprobacion ?? 0}
          </div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Aprobadas este mes</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{kpis.aprobadas_mes ?? 0}</div>
        </div>
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Nombre</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Tipo</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Creado por</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Fecha</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Ítems</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && sesiones.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin sesiones registradas</td></tr>
            )}
            {sesiones.map(s => (
              <tr
                key={s.id}
                onClick={() => navigate(`/preinventario/${s.id}`)}
                style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--ink-50)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}
              >
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>{s.nombre}</td>
                <td style={{ padding: '10px 12px' }}><Pill label={s.estado} /></td>
                <td style={{ padding: '10px 12px', fontSize: 13, color: 'var(--ink-500)' }}>{s.tipo}</td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{s.creado_por}</td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{fmt(s.fecha_creacion)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{s.total_items ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
