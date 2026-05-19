import { useFetch } from '../../hooks/useFetch';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { useState } from 'react';
import { KpiCard } from '../../components/KpiCard';

const SEGMENTO_COLOR = {
  Champions: '#10b981',
  Loyal:     '#3b82f6',
  'At Risk': '#f59e0b',
  Lost:      '#ef4444',
  Prospect:  '#8b5cf6',
};

export default function CrmDashboard() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/crm/dashboard');
  const [recalculating, setRecalculating] = useState(false);

  const metricas   = data?.metricas_30d    ?? {};
  const campanas   = data?.campanas         ?? {};
  const contactos  = data?.contactos        ?? {};
  const rfm        = data?.distribucion_rfm ?? {};
  const recientes  = data?.campanas_recientes ?? [];

  async function handleRecalcularRfm() {
    setRecalculating(true);
    try {
      await api.post('/api/crm/rfm/recalcular', {});
      await refetch();
      toast.success('RFM recalculado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRecalculating(false);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>CRM</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">CRM — Marketing</div>
          <div className="page-sub">Campañas, contactos y métricas últimos 30 días</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/crm/campanas/nueva')}>
            Nueva campaña
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/crm/campanas')}>
            Ver campañas
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>
          Cargando…
        </div>
      )}

      {!loading && (
        <>
          {/* KPIs principales */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
            <KpiCard label="Envíos (30d)"  value={metricas.total_envios ?? 0}  color="#6b7280" />
            <KpiCard label="Entregados"    value={metricas.enviados ?? 0}       color="#10b981" />
            <KpiCard
              label="Tasa apertura"
              value={`${metricas.tasa_apertura ?? 0}%`}
              color={metricas.tasa_apertura >= 25 ? '#10b981' : '#f59e0b'}
            />
            <KpiCard
              label="Tasa clics"
              value={`${metricas.tasa_clics ?? 0}%`}
              color={metricas.tasa_clics >= 3 ? '#10b981' : '#f59e0b'}
            />
            <KpiCard label="Rebotes"    value={metricas.rebotes ?? 0}    color="#ef4444" />
            <KpiCard label="Contactos"  value={contactos.total ?? 0}     color="#3b82f6" />
            <KpiCard label="Opt-outs"   value={contactos.opt_outs ?? 0}  color="#f59e0b" />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
            {/* Estado de campañas */}
            <div className="card" style={{ padding: 20 }}>
              <div style={{ fontWeight: 600, marginBottom: 14, fontSize: 14 }}>Estado de campañas</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  ['Borradores', campanas.borradores ?? 0, '#6b7280'],
                  ['Aprobadas',  campanas.aprobadas  ?? 0, '#3b82f6'],
                  ['Enviando',   campanas.enviando   ?? 0, '#f59e0b'],
                  ['Completadas',campanas.completadas ?? 0, '#10b981'],
                ].map(([label, val, color]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                    <span style={{ color: 'var(--ink-500)' }}>{label}</span>
                    <span style={{ fontWeight: 700, color }}>{val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Distribución RFM */}
            <div className="card" style={{ padding: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Segmentación RFM</div>
                <button
                  className="btn"
                  style={{ padding: '2px 10px', fontSize: 12 }}
                  onClick={handleRecalcularRfm}
                  disabled={recalculating}
                >
                  {recalculating ? 'Calculando…' : 'Recalcular'}
                </button>
              </div>
              {Object.keys(rfm).length === 0 ? (
                <div style={{ color: 'var(--ink-400)', fontSize: 13 }}>
                  Sin datos — ejecuta "Recalcular"
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(rfm).map(([seg, total]) => (
                    <div key={seg} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                      <span style={{ color: SEGMENTO_COLOR[seg] ?? 'var(--ink-500)', fontWeight: 500 }}>
                        {seg}
                      </span>
                      <span style={{ fontWeight: 700 }}>{total}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Campañas recientes */}
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <div style={{ padding: '14px 16px', fontWeight: 600, fontSize: 14, borderBottom: '1px solid var(--ink-100)' }}>
              Campañas recientes
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
                  {['Campaña','Estado','Programada','Envíos','Aperturas','Clics'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: 'var(--ink-400)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {recientes.length === 0 && (
                  <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)', fontSize: 13 }}>
                    Sin campañas recientes
                  </td></tr>
                )}
                {recientes.map(c => (
                  <tr
                    key={c.id}
                    style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer' }}
                    onClick={() => navigate(`/crm/campanas/${c.id}`)}
                  >
                    <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>{c.nombre}</td>
                    <td style={{ padding: '10px 12px' }}><EstadoPill estado={c.estado} /></td>
                    <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>
                      {c.fecha_programada ? new Date(c.fecha_programada).toLocaleDateString('es-MX') : '—'}
                    </td>
                    <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.envios}</td>
                    <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.aperturas}</td>
                    <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.clics}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Accesos rápidos */}
          <div style={{ display: 'flex', gap: 10, marginTop: 20, flexWrap: 'wrap' }}>
            {[
              ['Contactos',  '/crm/contactos'],
              ['Plantillas', '/crm/plantillas'],
              ['Secuencias', '/crm/secuencias'],
              ['Segmentos',  '/crm/segmentos'],
              ['RFM',        '/crm/rfm'],
            ].map(([label, path]) => (
              <button key={path} className="btn" onClick={() => navigate(path)}>
                {label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function EstadoPill({ estado }) {
  const map = {
    borrador:   { bg: '#f3f4f6', color: '#374151' },
    revision:   { bg: '#fef3c7', color: '#92400e' },
    aprobada:   { bg: '#dbeafe', color: '#1e40af' },
    enviando:   { bg: '#fef9c3', color: '#713f12' },
    completada: { bg: '#d1fae5', color: '#065f46' },
  };
  const s = map[estado] ?? { bg: '#f3f4f6', color: '#374151' };
  return (
    <span style={{
      background: s.bg, color: s.color,
      padding: '2px 8px', borderRadius: 10,
      fontSize: 11, fontWeight: 600,
    }}>
      {estado}
    </span>
  );
}
