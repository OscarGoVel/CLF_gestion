import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const SEGMENTO_META = {
  Champions:  { color: '#10b981', desc: 'Compran frecuente y reciente — fidelizar y hacer upsell' },
  Loyal:      { color: '#3b82f6', desc: 'Historial sólido — cross-sell y programa de lealtad' },
  'At Risk':  { color: '#f59e0b', desc: 'Recencia 90–180 días — reactivar antes de perderlos' },
  Lost:       { color: '#ef4444', desc: 'Sin compras > 6 meses — campaña de recuperación' },
  Prospect:   { color: '#8b5cf6', desc: 'Sin compras o una sola cotización — nutrir y educar' },
};

export default function RfmView() {
  const navigate  = useNavigate();
  const { data, loading, refetch } = useFetch('/api/crm/rfm');
  const clientes      = data?.clientes      ?? [];
  const distribucion  = data?.distribucion  ?? {};
  const [filtro,  setFiltro]  = useState('');
  const [recalc,  setRecalc]  = useState(false);

  async function handleRecalcular() {
    setRecalc(true);
    try {
      await api.post('/api/crm/rfm/recalcular', {});
      await refetch();
      toast.success('RFM recalculado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRecalc(false);
    }
  }

  const filtrados = filtro
    ? clientes.filter(c => c.segmento_rfm === filtro)
    : clientes;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>RFM</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Segmentación RFM</div>
          <div className="page-sub">Recencia · Frecuencia · Monto — basado en últimos 12 meses</div>
        </div>
        <button className="btn btn-primary" onClick={handleRecalcular} disabled={recalc}>
          {recalc ? 'Calculando…' : 'Recalcular RFM'}
        </button>
      </div>

      {/* Distribución */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12, marginBottom: 24 }}>
        {Object.entries(SEGMENTO_META).map(([seg, meta]) => (
          <div
            key={seg}
            className="card"
            style={{
              padding: '14px 16px', cursor: 'pointer',
              borderLeft: `4px solid ${meta.color}`,
              background: filtro === seg ? `${meta.color}10` : undefined,
            }}
            onClick={() => setFiltro(filtro === seg ? '' : seg)}
          >
            <div style={{ fontSize: 22, fontWeight: 800, color: meta.color }}>
              {distribucion[seg] ?? 0}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{seg}</div>
            <div style={{ fontSize: 11, color: 'var(--ink-400)', lineHeight: 1.4 }}>{meta.desc}</div>
          </div>
        ))}
      </div>

      {filtro && (
        <div style={{ marginBottom: 12, fontSize: 13 }}>
          Mostrando: <strong>{filtro}</strong>
          <button className="btn" style={{ marginLeft: 8, padding: '1px 8px', fontSize: 12 }}
            onClick={() => setFiltro('')}>Ver todos</button>
        </div>
      )}

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              {['Cliente','Segmento','Recencia (días)','Compras 12m','Monto 12m'].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 12,
                                    fontWeight: 600, color: 'var(--ink-400)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && filtrados.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>
                {clientes.length === 0 ? 'Sin datos — ejecuta "Recalcular RFM"' : 'Sin clientes en este segmento'}
              </td></tr>
            )}
            {filtrados.map(c => {
              const meta = SEGMENTO_META[c.segmento_rfm] ?? { color: '#6b7280' };
              return (
                <tr key={c.cliente_id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 500, fontSize: 13 }}>
                    {c.nombre_comercial}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      background: `${meta.color}20`, color: meta.color,
                      padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                    }}>
                      {c.segmento_rfm}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>
                    {c.recencia_dias >= 9999 ? 'Nunca' : `${c.recencia_dias}d`}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.frecuencia}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>
                    {MXN.format(c.monto_total)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
