import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/StatusBadge';
import { exportCSV } from '../../lib/exportCSV';
import { api } from '../../lib/apiClient';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const TIPOS = ['Empresa', 'Gobierno', 'Persona'];

export default function EstadoCuentaList() {
  const navigate = useNavigate();
  const { activeRS } = useRazonSocial();

  const [corporativoId, setCorporativoId] = useState('');
  const [tipo, setTipo]                   = useState('');
  const [desde, setDesde]                 = useState('');
  const [hasta, setHasta]                 = useState('');
  const [exportando, setExportando]       = useState(false);

  const params = new URLSearchParams();
  if (corporativoId) params.set('corporativo_id', corporativoId);
  if (tipo)          params.set('tipo', tipo);
  if (desde)         params.set('desde', desde);
  if (hasta)         params.set('hasta', hasta);
  if (activeRS != null) params.set('razon_social_id', activeRS);

  const { data, loading } = useFetch(`/api/finanzas/cobranza?${params}`);
  const { data: corpsData } = useFetch('/api/finanzas/cobranza/corporativos');

  const clientes     = data?.clientes ?? [];
  const kpis         = data?.kpis     ?? {};
  const corporativos = corpsData?.corporativos ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Estado de Cuenta</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Estado de Cuenta</div>
          <div className="page-sub">Cartera activa de clientes</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" disabled={clientes.length === 0}
            onClick={() => exportCSV(
              ['nombre', 'tipo', 'rfc', 'corporativo', 'cartera', 'cobrado', 'pendiente', 'dso'],
              clientes,
              'estado_cuenta'
            )}>
            Exportar CSV
          </button>
          <button className="btn" disabled={clientes.length === 0 || exportando}
            onClick={async () => {
              setExportando(true);
              try {
                const q = new URLSearchParams();
                if (corporativoId) q.set('corporativo_id', corporativoId);
                if (tipo)          q.set('tipo', tipo);
                if (desde)         q.set('desde', desde);
                if (hasta)         q.set('hasta', hasta);
                await api.download(
                  `/api/finanzas/cobranza/export-pdf?${q}`,
                  'aging_cartera.pdf'
                );
              } catch (e) {
                alert(e.message);
              } finally {
                setExportando(false);
              }
            }}>
            {exportando ? 'Generando…' : 'Exportar PDF'}
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 160, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cartera total</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{MXN.format(kpis.cartera_total ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cobrado</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{MXN.format(kpis.cobrado_total ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Pendiente</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--red-600, #dc2626)' }}>
            {MXN.format(kpis.pendiente_total ?? 0)}
          </div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 160, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>DSO promedio</div>
          <div style={{ fontSize: 22, fontWeight: 700 }}>
            {kpis.dso_global != null ? `${kpis.dso_global} días` : '—'}
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        {corporativos.length > 0 && (
          <select
            className="input"
            style={{ maxWidth: 200 }}
            value={corporativoId}
            onChange={e => setCorporativoId(e.target.value)}
          >
            <option value="">Todos los corporativos</option>
            {corporativos.map(c => (
              <option key={c.id} value={c.id}>{c.nombre}</option>
            ))}
          </select>
        )}
        <select
          className="input"
          style={{ maxWidth: 160 }}
          value={tipo}
          onChange={e => setTipo(e.target.value)}
        >
          <option value="">Todos los tipos</option>
          {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          type="date"
          className="input"
          style={{ maxWidth: 160 }}
          value={desde}
          onChange={e => setDesde(e.target.value)}
          title="Entrega desde"
        />
        <input
          type="date"
          className="input"
          style={{ maxWidth: 160 }}
          value={hasta}
          onChange={e => setHasta(e.target.value)}
          title="Entrega hasta"
        />
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Cliente</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Tipo</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Cartera</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Cobrado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pendiente</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>DSO</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && clientes.length === 0 && (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin cartera activa</td></tr>
            )}
            {clientes.map(cl => (
              <tr
                key={cl.cliente_id}
                onClick={() => navigate(`/finanzas/cobranza/${cl.cliente_id}`)}
                style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--ink-50)'}
                onMouseLeave={e => e.currentTarget.style.background = ''}
              >
                <td style={{ padding: '10px 12px' }}>
                  <div style={{ fontWeight: 500 }}>{cl.nombre}</div>
                  {cl.corporativo && (
                    <div style={{ fontSize: 11, color: 'var(--ink-400)' }}>{cl.corporativo}</div>
                  )}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <StatusBadge status={cl.tipo} />
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                  {MXN.format(cl.cartera ?? 0)}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                  {MXN.format(cl.cobrado ?? 0)}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13,
                             color: (cl.pendiente ?? 0) > 0 ? 'var(--red-600, #dc2626)' : '' }}>
                  {MXN.format(cl.pendiente ?? 0)}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                  {cl.dso != null ? `${Math.round(cl.dso)} días` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
