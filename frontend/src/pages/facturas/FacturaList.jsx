import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

const TIPO_COLOR = {
  I: { bg: '#dcfce7', color: '#166534' },
  E: { bg: '#fee2e2', color: '#991b1b' },
  P: { bg: '#e0f2fe', color: '#075985' },
  N: { bg: '#f3f4f6', color: '#374151' },
  T: { bg: '#fef9c3', color: '#854d0e' },
};

export default function FacturaList() {
  const navigate = useNavigate();
  const [q, setQ]       = useState('');
  const [tipo, setTipo] = useState('');
  const [pagina, setPag] = useState(1);
  const [sel, setSel]   = useState(null);

  const params = new URLSearchParams({ pagina });
  if (q) params.set('q', q);
  if (tipo) params.set('tipo', tipo);

  const { data, loading } = useFetch(`/api/facturas?${params}`);
  const { data: detData } = useFetch(sel ? `/api/facturas/${sel}` : null);

  const facturas   = data?.facturas   ?? [];
  const total      = data?.total      ?? 0;
  const totalPags  = data?.total_pags ?? 1;
  const tipos      = data?.tipos      ?? [];

  const factura    = detData?.factura    ?? null;
  const conceptos  = detData?.conceptos  ?? [];
  const cotizaciones = detData?.cotizaciones ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Facturas</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Facturas CFDI</div>
          <div className="page-sub">{total} facturas importadas</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/facturas/importar')}>
          Importar XML
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
        <input className="input" style={{ maxWidth: 300 }}
          placeholder="Buscar folio, RFC, nombre, UUID…"
          value={q} onChange={(e) => { setQ(e.target.value); setPag(1); }} />
        <span className={`chip${tipo === '' ? ' active' : ''}`} onClick={() => { setTipo(''); setPag(1); }}>Todos</span>
        {tipos.map((t) => (
          <span key={t.value} className={`chip${tipo === t.value ? ' active' : ''}`}
            onClick={() => { setTipo(t.value); setPag(1); }}>
            {t.label}
          </span>
        ))}
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: sel ? '1fr 380px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 40 }}>Tipo</th>
                <th style={{ width: 90 }}>Folio</th>
                <th style={{ width: 95 }}>Fecha</th>
                <th>Emisor / Receptor</th>
                <th className="num" style={{ width: 120 }}>Total</th>
                <th style={{ width: 55 }}>Cots.</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : facturas.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
              ) : facturas.map((f) => (
                <tr key={f.id} className={sel === f.id ? 'sel' : ''} style={{ cursor: 'pointer' }}
                    onClick={() => setSel(sel === f.id ? null : f.id)}>
                  <td>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '2px 5px', borderRadius: 3,
                      background: TIPO_COLOR[f.tipo]?.bg ?? '#f3f4f6',
                      color: TIPO_COLOR[f.tipo]?.color ?? '#374151',
                    }}>{f.tipo_label}</span>
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>{f.folio || '—'}</td>
                  <td style={{ fontSize: 12, color: 'var(--ink-500)' }}>{f.fecha ?? f.fecha_timbrado ?? '—'}</td>
                  <td>
                    <div style={{ fontSize: 12.5 }}>{f.nombre_receptor ?? f.nombre_emisor ?? '—'}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)' }}>
                      {f.rfc_receptor ?? f.rfc_emisor ?? ''}
                    </div>
                  </td>
                  <td className="num" style={{ fontWeight: 500 }}>{f.total != null ? MXN.format(f.total) : '—'}</td>
                  <td style={{ textAlign: 'center', color: f.num_cotizaciones > 0 ? 'var(--accent)' : 'var(--ink-300)' }}>
                    {f.num_cotizaciones}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)',
            fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between' }}>
            <span>{facturas.length} de {total}</span>
            <span style={{ display: 'flex', gap: 12 }}>
              {pagina > 1 && <a className="linkish" onClick={() => setPag(p => p - 1)}>← anterior</a>}
              {pagina < totalPags && <a className="linkish" onClick={() => setPag(p => p + 1)}>siguiente →</a>}
            </span>
          </div>
        </div>

        {sel && (
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '75vh' }}>
            {!factura ? (
              <div style={{ color: 'var(--ink-400)', fontSize: 12 }}>Cargando…</div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4,
                    background: TIPO_COLOR[factura.tipo]?.bg ?? '#f3f4f6',
                    color: TIPO_COLOR[factura.tipo]?.color ?? '#374151',
                  }}>{factura.tipo_label}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600 }}>
                    {factura.serie}{factura.folio_factura}
                  </span>
                </div>

                <div style={{ marginTop: 8 }}>
                  <div className="note">EMISOR</div>
                  <div style={{ fontSize: 13, marginTop: 2 }}>{factura.nombre_emisor ?? '—'}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)' }}>
                    {factura.rfc_emisor}
                  </div>
                </div>
                <div style={{ marginTop: 8 }}>
                  <div className="note">RECEPTOR</div>
                  <div style={{ fontSize: 13, marginTop: 2 }}>{factura.nombre_receptor ?? '—'}</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)' }}>
                    {factura.rfc_receptor}
                  </div>
                </div>

                <div style={{ marginTop: 12, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0,
                  border: '1px solid var(--ink-200)', borderRadius: 4 }}>
                  {[
                    ['Subtotal', factura.subtotal != null ? MXN.format(factura.subtotal) : '—'],
                    ['IVA', factura.iva != null ? MXN.format(factura.iva) : '—'],
                    ['Total', factura.total != null ? MXN.format(factura.total) : '—'],
                    ['Fecha', factura.fecha ?? '—'],
                  ].map(([k, v], i) => (
                    <div key={i} style={{
                      padding: '10px 12px',
                      borderBottom: i < 2 ? '1px solid var(--ink-100)' : 'none',
                      borderRight: i % 2 === 0 ? '1px solid var(--ink-100)' : 'none',
                    }}>
                      <div className="note">{k.toUpperCase()}</div>
                      <div style={{ fontSize: 12, marginTop: 2, fontWeight: k === 'Total' ? 600 : 400 }}>{v}</div>
                    </div>
                  ))}
                </div>

                {factura.uuid && (
                  <div style={{ marginTop: 10, fontFamily: 'var(--mono)', fontSize: 9.5,
                    color: 'var(--ink-400)', wordBreak: 'break-all' }}>
                    UUID: {factura.uuid}
                  </div>
                )}

                {conceptos.length > 0 && (
                  <>
                    <div className="eyebrow" style={{ marginTop: 14 }}>Conceptos ({conceptos.length})</div>
                    {conceptos.map((c, i) => (
                      <div key={i} style={{ fontSize: 11.5, padding: '6px 0', borderBottom: '1px solid var(--ink-100)' }}>
                        <div>{c.descripcion}</div>
                        <div style={{ color: 'var(--ink-500)', fontSize: 11 }}>
                          {c.cantidad} {c.unidad} × {c.valor_unitario != null ? MXN.format(c.valor_unitario) : '—'}
                        </div>
                      </div>
                    ))}
                  </>
                )}

                {cotizaciones.length > 0 && (
                  <>
                    <div className="eyebrow" style={{ marginTop: 14 }}>Cotizaciones vinculadas</div>
                    {cotizaciones.map((c, i) => (
                      <div key={i} style={{ display: 'flex', justifyContent: 'space-between',
                        padding: '6px 0', borderBottom: '1px solid var(--ink-100)', fontSize: 12 }}>
                        <div>
                          <span className="folio">{c.folio}</span>
                          <span style={{ color: 'var(--ink-500)', marginLeft: 8 }}>{c.cliente}</span>
                        </div>
                        <a className="linkish" style={{ fontSize: 11 }}
                          onClick={() => navigate(`/cotizaciones/${c.id}`)}>Abrir →</a>
                      </div>
                    ))}
                  </>
                )}

                <div style={{ marginTop: 14, display: 'flex', gap: 6 }}>
                  <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
