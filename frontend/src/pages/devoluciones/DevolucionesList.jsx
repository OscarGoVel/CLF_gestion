import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { FilterChips } from '../../components/FilterChips';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const ESTADOS = ['Abierta', 'Cerrada'];

export default function DevolucionesList() {
  const navigate = useNavigate();
  const { activeRS } = useRazonSocial();
  const [q, setQ]         = useState('');
  const [estado, setEst]  = useState('');
  const [pagina, setPag]  = useState(1);

  const params = new URLSearchParams({ pagina });
  if (q) params.set('q', q);
  if (estado) params.set('estado', estado);
  if (activeRS != null) params.set('razon_social_id', activeRS);

  const { data, loading } = useFetch(`/api/devoluciones?${params}`);

  const rows   = data?.devoluciones ?? [];
  const total  = data?.total ?? 0;
  const totalPags = data?.total_pags ?? 1;
  const conteo = data?.conteo ?? {};

  const chips = ESTADOS.map((e) => ({ key: e, label: e, count: conteo[e] ?? 0 }));

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Devoluciones</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Devoluciones</div>
          <div className="page-sub">{total} registros</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/comercial/devoluciones/nueva')}>
          + Nueva devolución
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
        <input className="input" style={{ maxWidth: 280 }}
          placeholder="Buscar folio, cliente…"
          value={q} onChange={(e) => { setQ(e.target.value); setPag(1); }} />
        <FilterChips
          chips={chips}
          active={estado}
          onSelect={(v) => { setEst(estado === v ? '' : v); setPag(1); }}
        />
      </div>

      <div className="card" style={{ padding: 0 }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Folio</th>
              <th style={{ width: 95 }}>Fecha</th>
              <th>Cliente</th>
              <th>Cotización</th>
              <th>Motivo</th>
              <th className="num" style={{ width: 110 }}>Total</th>
              <th style={{ width: 90 }}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
            ) : rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <Link to={`/comercial/devoluciones/${r.id}`} style={{ fontFamily: 'var(--mono)', fontWeight: 500 }}>
                    {r.folio}
                  </Link>
                </td>
                <td style={{ fontSize: 12, color: 'var(--ink-500)' }}>{r.fecha}</td>
                <td style={{ fontSize: 13 }}>{r.cliente}</td>
                <td style={{ fontSize: 12 }}>
                  {r.cot_folio
                    ? <Link to={`/comercial/cotizaciones/${r.cotizacion_id}`} style={{ fontFamily: 'var(--mono)' }}>{r.cot_folio}</Link>
                    : <span style={{ color: 'var(--ink-400)' }}>—</span>}
                </td>
                <td style={{ fontSize: 12, color: 'var(--ink-600)' }}>{r.motivo ?? '—'}</td>
                <td className="num" style={{ fontWeight: 500 }}>{r.total != null ? MXN.format(r.total) : '—'}</td>
                <td>
                  <span style={{
                    fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 600,
                    background: r.estado === 'Cerrada' ? '#f3f4f6' : '#dcfce7',
                    color: r.estado === 'Cerrada' ? '#374151' : '#166534',
                  }}>{r.estado}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)',
          fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between' }}>
          <span>{rows.length} de {total}</span>
          <span style={{ display: 'flex', gap: 12 }}>
            {pagina > 1 && <a className="linkish" onClick={() => setPag(p => p - 1)}>← anterior</a>}
            {pagina < totalPags && <a className="linkish" onClick={() => setPag(p => p + 1)}>siguiente →</a>}
          </span>
        </div>
      </div>
    </div>
  );
}
