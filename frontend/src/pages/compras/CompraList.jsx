import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function CompraList() {
  const navigate = useNavigate();
  const [q, setQ]       = useState('');
  const [pagina, setPag] = useState(1);
  const [sel, setSel]   = useState(null);

  const params = new URLSearchParams({ pagina });
  if (q) params.set('q', q);

  const { data, loading }   = useFetch(`/api/compras?${params}`);
  const { data: detData }   = useFetch(sel ? `/api/compras/${sel}` : null);

  const compras    = data?.compras    ?? [];
  const total      = data?.total      ?? 0;
  const totalPags  = data?.total_pags ?? 1;
  const compra     = detData?.compra  ?? null;
  const lineas     = detData?.lineas  ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Compras</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Compras</div>
          <div className="page-sub">{total} registros</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/compras/nueva')}>
          Nueva compra
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <input className="input" style={{ maxWidth: 280 }}
          placeholder="Buscar folio, proveedor, ticket…"
          value={q} onChange={(e) => { setQ(e.target.value); setPag(1); }} />
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: sel ? '1fr 380px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 120 }}>Folio</th>
                <th style={{ width: 100 }}>Fecha</th>
                <th>Proveedor</th>
                <th style={{ width: 60 }}>Líneas</th>
                <th style={{ width: 70 }}>Cots.</th>
                <th className="num" style={{ width: 120 }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : compras.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
              ) : compras.map((c) => (
                <tr key={c.id} className={sel === c.id ? 'sel' : ''} style={{ cursor: 'pointer' }}
                    onClick={() => setSel(sel === c.id ? null : c.id)}>
                  <td className="folio">{c.folio}</td>
                  <td style={{ color: 'var(--ink-500)', fontSize: 12 }}>{c.fecha_compra}</td>
                  <td>{c.proveedor}</td>
                  <td style={{ textAlign: 'center', color: 'var(--ink-500)' }}>{c.num_lineas}</td>
                  <td style={{ textAlign: 'center', color: 'var(--ink-500)' }}>{c.num_cotizaciones}</td>
                  <td className="num" style={{ fontWeight: 500 }}>{c.total != null ? MXN.format(c.total) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)',
            fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between' }}>
            <span>{compras.length} de {total}</span>
            <span style={{ display: 'flex', gap: 12 }}>
              {pagina > 1 && <a className="linkish" onClick={() => setPag(p => p - 1)}>← anterior</a>}
              {pagina < totalPags && <a className="linkish" onClick={() => setPag(p => p + 1)}>siguiente →</a>}
            </span>
          </div>
        </div>

        {sel && (
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '70vh' }}>
            {!compra ? (
              <div style={{ color: 'var(--ink-400)', fontSize: 12 }}>Cargando detalle…</div>
            ) : (
              <>
                <div className="note">COMPRA</div>
                <div style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 600, marginTop: 4 }}>{compra.folio}</div>
                <div style={{ fontSize: 12, color: 'var(--ink-500)', marginTop: 2 }}>
                  {compra.proveedor} · {compra.fecha_compra}
                </div>
                {compra.proveedor_rfc && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>
                    {compra.proveedor_rfc}
                  </div>
                )}
                {compra.folio_factura && (
                  <div style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-600)' }}>
                    Factura: {compra.serie}{compra.folio_factura}
                    {compra.uuid && (
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-400)', display: 'block', marginTop: 2 }}>
                        {compra.uuid}
                      </span>
                    )}
                  </div>
                )}
                {compra.ticket_referencia && (
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-600)' }}>
                    Ticket: {compra.ticket_referencia}
                  </div>
                )}

                <div style={{ marginTop: 16 }}>
                  <div style={{ fontFamily: 'var(--serif)', fontSize: 24, letterSpacing: '-0.02em' }}>
                    {compra.total != null ? MXN.format(compra.total) : '—'}
                  </div>
                  <div className="note" style={{ marginTop: 2 }}>TOTAL</div>
                </div>

                <div className="eyebrow" style={{ marginTop: 16 }}>Líneas ({lineas.length})</div>
                <table className="tbl" style={{ marginTop: 6, fontSize: 11.5 }}>
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th className="num" style={{ width: 55 }}>Cant.</th>
                      <th className="num" style={{ width: 90 }}>Costo unit.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {lineas.map((l, i) => (
                      <tr key={i}>
                        <td>
                          <div>{l.nombre}</div>
                          {l.cotizaciones !== '—' && (
                            <div style={{ fontSize: 10, color: 'var(--ink-500)', marginTop: 1 }}>
                              → {l.cotizaciones}
                            </div>
                          )}
                        </td>
                        <td className="num">{l.cantidad}</td>
                        <td className="num">{l.costo_unitario != null ? MXN.format(l.costo_unitario) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div style={{ marginTop: 14, display: 'flex', gap: 6 }}>
                  <button className="btn btn-sm" onClick={() => navigate(`/compras/${sel}`)}>Abrir</button>
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
