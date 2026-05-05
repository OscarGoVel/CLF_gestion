import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const TIPO_COLOR = {
  Empresa:  { bg: '#eff6ff', color: '#1d4ed8' },
  Gobierno: { bg: '#f5f3ff', color: '#6d28d9' },
  Persona:  { bg: '#f0fdf4', color: '#166534' },
};

export default function ClienteList() {
  const navigate = useNavigate();
  const [q, setQ]       = useState('');
  const [tipo, setTipo] = useState('');
  const [sel, setSel]   = useState(null);

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (tipo) params.set('tipo', tipo);

  const { data, loading } = useFetch(`/api/catalogos/clientes?${params}`);
  const clientes = data?.clientes ?? [];
  const tipos    = data?.tipos    ?? [];
  const selected = sel != null ? clientes.find((c) => c.id === sel) : null;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Clientes</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Clientes</div>
          <div className="page-sub">{clientes.length} registros</div>
        </div>
        <button className="btn btn-primary">Nuevo cliente</button>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <input
          className="input" style={{ maxWidth: 280 }}
          placeholder="Buscar nombre, RFC, contacto…"
          value={q} onChange={(e) => setQ(e.target.value)}
        />
        <span className={`chip${tipo === '' ? ' active' : ''}`} onClick={() => setTipo('')}>Todos</span>
        {tipos.map((t) => (
          <span key={t} className={`chip${tipo === t ? ' active' : ''}`} onClick={() => setTipo(t)}>
            {t}
          </span>
        ))}
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: selected ? '1fr 360px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Nombre comercial</th>
                <th style={{ width: 90 }}>Tipo</th>
                <th style={{ width: 130 }}>RFC</th>
                <th style={{ width: 160 }}>Contacto</th>
                <th className="num" style={{ width: 80 }}>Cots.</th>
                <th className="num" style={{ width: 120 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : clientes.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
              ) : clientes.map((c) => (
                <tr key={c.id} className={sel === c.id ? 'sel' : ''} style={{ cursor: 'pointer' }}
                    onClick={() => setSel(sel === c.id ? null : c.id)}>
                  <td style={{ fontWeight: 500 }}>{c.nombre_comercial}</td>
                  <td>
                    {c.tipo && (
                      <span style={{
                        fontSize: 11, padding: '2px 7px', borderRadius: 3,
                        background: TIPO_COLOR[c.tipo]?.bg ?? '#f3f4f6',
                        color: TIPO_COLOR[c.tipo]?.color ?? '#374151',
                      }}>{c.tipo}</span>
                    )}
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>{c.rfc ?? '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--ink-600)' }}>{c.contacto ?? '—'}</td>
                  <td className="num">{c.num_cotizaciones}</td>
                  <td className="num">{c.monto_total ? MXN.format(c.monto_total) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)', fontSize: 11.5, color: 'var(--ink-500)' }}>
            {clientes.length} clientes
          </div>
        </div>

        {selected && (
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '70vh' }}>
            <div className="note">CLIENTE</div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.015em', marginTop: 4 }}>
              {selected.nombre_comercial}
            </div>
            {selected.razon_social && (
              <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 2 }}>{selected.razon_social}</div>
            )}

            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0,
              border: '1px solid var(--ink-200)', borderRadius: 4 }}>
              {[
                ['RFC', selected.rfc],
                ['Tipo', selected.tipo],
                ['Teléfono', selected.telefono],
                ['Email', selected.email],
                ['Cotizaciones', selected.num_cotizaciones],
                ['Última cot.', selected.ultima_cotizacion],
              ].map(([k, v], i) => (
                <div key={i} style={{
                  padding: '10px 12px',
                  borderBottom: i < 4 ? '1px solid var(--ink-100)' : 'none',
                  borderRight: i % 2 === 0 ? '1px solid var(--ink-100)' : 'none',
                }}>
                  <div className="note">{k.toUpperCase()}</div>
                  <div style={{ fontSize: 12, marginTop: 2 }}>{v ?? '—'}</div>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 14 }}>
              <div className="note">TOTAL VENDIDO</div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em' }}>
                {selected.monto_total ? MXN.format(selected.monto_total) : '—'}
              </div>
            </div>

            {selected.direccion && (
              <div style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-600)' }}>
                <div className="note">DIRECCIÓN</div>
                <div style={{ marginTop: 2 }}>{selected.direccion}</div>
              </div>
            )}

            <div style={{ marginTop: 16, display: 'flex', gap: 6 }}>
              <button className="btn btn-sm btn-primary"
                onClick={() => navigate(`/cotizaciones?cliente=${selected.id}`)}>
                Ver cotizaciones
              </button>
              <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
