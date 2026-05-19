import { useParams, useNavigate, Link } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { api } from '../../lib/apiClient';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

function fmt(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

function AgeBar({ value, total }) {
  if (!total) return null;
  const pct = Math.round((value / total) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--ink-100)', borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--primary)', borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color: 'var(--ink-400)', minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

export default function EstadoCuentaDetalle() {
  const { cliente_id } = useParams();
  const navigate       = useNavigate();

  const { data, loading } = useFetch(`/api/estado-cuenta/${cliente_id}`);

  const cliente     = data?.cliente     ?? {};
  const kpis        = data?.kpis        ?? {};
  const aging       = data?.aging       ?? {};
  const cotizaciones = data?.cotizaciones ?? [];

  const pendienteTotal = kpis.pendiente ?? 0;

  async function handlePdf() {
    try {
      await api.download(`/api/estado-cuenta/pdf`, `EstadoCuenta_${cliente.nombre_comercial}.pdf`);
    } catch (e) {
      alert(e.message);
    }
  }

  if (loading) {
    return <div className="page"><div className="card" style={{ padding: 24 }}>Cargando…</div></div>;
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/estado-cuenta')}>Estado de Cuenta</a>
        <span className="sep">/</span>
        <span>{cliente.nombre_comercial}</span>
      </div>

      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">{cliente.nombre_comercial}</div>
          <div className="page-sub" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            {cliente.rfc && <span>RFC: {cliente.rfc}</span>}
            {cliente.tipo && <Pill label={cliente.tipo} />}
            {cliente.corporativo && <span style={{ color: 'var(--ink-400)' }}>{cliente.corporativo}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={handlePdf}>Exportar PDF</button>
        </div>
      </div>

      {/* Contacto */}
      {(cliente.contacto || cliente.telefono || cliente.email) && (
        <div className="card" style={{ padding: '12px 16px', marginBottom: 20, fontSize: 13, display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {cliente.contacto && <span>👤 {cliente.contacto}</span>}
          {cliente.telefono && <span>📞 {cliente.telefono}</span>}
          {cliente.email    && <span>✉️ {cliente.email}</span>}
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cartera</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{MXN.format(kpis.cartera ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cobrado</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{MXN.format(kpis.cobrado ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Pendiente</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: pendienteTotal > 0 ? 'var(--red-600, #dc2626)' : '' }}>
            {MXN.format(pendienteTotal)}
          </div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>DSO (días cobro)</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {kpis.dso != null ? `${kpis.dso} días` : '—'}
          </div>
        </div>
      </div>

      {/* Aging */}
      {pendienteTotal > 0 && (
        <div className="card" style={{ padding: 20, marginBottom: 24 }}>
          <div style={{ fontWeight: 600, marginBottom: 16, fontSize: 14 }}>Antigüedad del saldo pendiente</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {[
              { label: '0 – 30 días',  key: 'dias_0_30',   color: '#16a34a' },
              { label: '30 – 60 días', key: 'dias_30_60',  color: '#ca8a04' },
              { label: '60 – 90 días', key: 'dias_60_90',  color: '#ea580c' },
              { label: '+90 días',     key: 'dias_mas_90', color: '#dc2626' },
            ].map(({ label, key, color }) => (
              <div key={key}>
                <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color, marginBottom: 6 }}>
                  {MXN.format(aging[key] ?? 0)}
                </div>
                <AgeBar value={aging[key] ?? 0} total={pendienteTotal} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cotizaciones */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <div style={{ padding: '12px 16px', fontWeight: 600, fontSize: 14, borderBottom: '1px solid var(--ink-100)' }}>
          Cotizaciones
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Folio</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Entrega</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Total</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pagado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pendiente</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Días</th>
            </tr>
          </thead>
          <tbody>
            {cotizaciones.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin cotizaciones activas</td></tr>
            )}
            {cotizaciones.map(c => (
              <tr
                key={c.id}
                style={{ borderBottom: '1px solid var(--ink-100)' }}
              >
                <td style={{ padding: '10px 12px' }}>
                  <Link to={`/cotizaciones/${c.id}`} style={{ fontWeight: 500 }}>{c.folio}</Link>
                </td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{fmt(c.fecha_entrega)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{MXN.format(c.total ?? 0)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{MXN.format(c.pagado ?? 0)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13,
                             color: (c.pendiente ?? 0) > 0.01 ? 'var(--red-600, #dc2626)' : '' }}>
                  {MXN.format(c.pendiente ?? 0)}
                </td>
                <td style={{ padding: '10px 12px' }}><Pill label={c.estado} /></td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                  {c.dias_desde_entrega != null ? `${Math.round(c.dias_desde_entrega)}d` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
