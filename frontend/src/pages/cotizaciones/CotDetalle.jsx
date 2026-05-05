import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { Stepper, buildSteps } from '../../components/Stepper';
import { NextRibbon, buildNextAction } from '../../components/NextRibbon';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function CotDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error } = useFetch(`/api/cotizaciones/${id}`);

  if (loading) return <div className="page" style={{ paddingTop: 60, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>;
  if (error)   return <div className="page" style={{ paddingTop: 60, color: 'var(--danger)' }}>Error: {error}</div>;
  if (!data)   return null;

  const cot      = data.cotizacion;
  const partidas = data.partidas ?? [];
  const etapas   = data.etapas ?? {};
  const facturas = data.facturas_vinculadas ?? [];
  const compras  = data.compras_vinculadas ?? [];

  const steps     = buildSteps(cot);
  const nextAction = buildNextAction(cot, {
    onGenerarOC: () => navigate(`/compras/nueva?cot=${cot.id}`),
    onFacturar:  () => navigate(`/facturas/nueva?cot=${cot.id}`),
  });

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <span>{cot.folio}</span>
      </div>

      <div className="page-header">
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)', display: 'flex', gap: 8, alignItems: 'center' }}>
            {cot.folio} · <Pill status={cot.estado} />
            {cot.fecha && <span>· {cot.fecha}</span>}
          </div>
          <div className="page-title" style={{ marginTop: 4 }}>{cot.cliente}</div>
          <div className="page-sub">
            {partidas.length} partidas
            {cot.total != null && ` · ${MXN.format(cot.total)}`}
            {cot.orden_compra && ` · OC: ${cot.orden_compra}`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <a className="btn" href={`/cotizaciones/${id}/pdf`} target="_blank" rel="noreferrer">PDF</a>
          <button className="btn" onClick={() => navigate(`/cotizaciones/${id}/editar`)}>Editar</button>
        </div>
      </div>

      {/* Stepper */}
      <div style={{ marginBottom: 20 }}>
        <Stepper steps={steps} />
      </div>

      {/* Next action ribbon */}
      {nextAction && (
        <div style={{ marginBottom: 20 }}>
          <NextRibbon action={nextAction} warn={cot.stock_ok === false} />
        </div>
      )}

      {/* Two-column layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>
        <div>
          {/* Condiciones */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h"><h3>Datos generales</h3></div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)' }}>
              {[
                ['Cliente',   cot.cliente],
                ['Tipo',      cot.tipo_cliente],
                ['Comprador', cot.comprador_nombre],
                ['Fecha',     cot.fecha],
                ['RFC',       cot.cliente_rfc],
                ['Contacto',  cot.cliente_contacto],
                ['Email',     cot.cliente_email],
                ['Teléfono',  cot.cliente_tel],
                ['OC',        cot.orden_compra],
                ['Factura',   cot.numero_factura],
                ['F. entrega',cot.fecha_entrega],
                ['F. pago',   cot.fecha_pago],
              ].map(([k, v], i) => (
                <div key={i} style={{
                  padding: '10px 14px',
                  borderRight: (i % 4 !== 3) ? '1px solid var(--ink-100)' : 'none',
                  borderTop: i >= 4 ? '1px solid var(--ink-100)' : 'none',
                }}>
                  <div className="note">{k.toUpperCase()}</div>
                  <div style={{ fontSize: 12, marginTop: 3 }}>{v ?? '—'}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Partidas */}
          <div className="card">
            <div className="card-h">
              <h3>Partidas ({partidas.length})</h3>
            </div>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 28 }}>#</th>
                  <th>Descripción</th>
                  <th className="num" style={{ width: 70 }}>Cant.</th>
                  <th className="num" style={{ width: 90 }}>Unit.</th>
                  <th className="num" style={{ width: 100 }}>Importe</th>
                  <th style={{ width: 90 }}>Stock</th>
                </tr>
              </thead>
              <tbody>
                {partidas.map((p, i) => {
                  const stockFalta = p.producto_id && !p.stock_ok;
                  return (
                    <tr key={i}>
                      <td style={{ color: 'var(--ink-400)' }}>{i + 1}</td>
                      <td>
                        {p.nombre}
                        {p.pendiente_catalogo && (
                          <span className="qb-tag" style={{ marginLeft: 4, color: 'var(--warn)' }}>libre</span>
                        )}
                      </td>
                      <td className="num">{p.cantidad}</td>
                      <td className="num">{p.precio_unitario != null ? MXN.format(p.precio_unitario) : '—'}</td>
                      <td className="num" style={{ fontWeight: 500 }}>
                        {p.total != null ? MXN.format(p.total) : '—'}
                      </td>
                      <td style={{ fontSize: 11.5, color: stockFalta ? 'var(--danger)' : 'var(--ink-500)' }}>
                        {p.producto_id ? (
                          <>
                            {p.stock_actual ?? 0} / {p.cantidad}
                            {stockFalta && <span className="qb-tag" style={{ marginLeft: 4 }}>Falta</span>}
                          </>
                        ) : (
                          <span style={{ color: 'var(--ink-400)' }}>—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
                <tr style={{ background: 'var(--ink-50)' }}>
                  <td colSpan={4} style={{ textAlign: 'right', fontSize: 11.5, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Subtotal</td>
                  <td className="num">{cot.subtotal != null ? MXN.format(cot.subtotal) : '—'}</td>
                  <td></td>
                </tr>
                {cot.aplica_iva ? (
                  <tr style={{ background: 'var(--ink-50)' }}>
                    <td colSpan={4} style={{ textAlign: 'right', fontSize: 11.5, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>IVA 16%</td>
                    <td className="num">{cot.iva != null ? MXN.format(cot.iva) : '—'}</td>
                    <td></td>
                  </tr>
                ) : null}
                <tr style={{ background: 'var(--ink-100)' }}>
                  <td colSpan={4} style={{ textAlign: 'right', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Total MXN</td>
                  <td className="num" style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-0.015em' }}>
                    {cot.total != null ? MXN.format(cot.total) : '—'}
                  </td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Sidebar */}
        <div>
          {/* Flujos vinculados */}
          <div className="eyebrow">Flujos vinculados</div>
          <div className="card" style={{ marginBottom: 14 }}>
            <div style={{ padding: '10px 14px', borderBottom: '1px solid var(--ink-100)' }}>
              <div className="note">COMPRAS</div>
              {compras.length === 0 ? (
                <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ink-400)' }}>Sin compra vinculada</div>
              ) : compras.map((c, i) => (
                <div key={i} style={{ fontSize: 12, marginTop: 4 }}>
                  {c.compra_folio ?? c.folio_factura ?? `Compra #${c.id}`}
                  {c.total != null && ` · ${MXN.format(c.total)}`}
                </div>
              ))}
            </div>
            <div style={{ padding: '10px 14px' }}>
              <div className="note">FACTURAS DE VENTA</div>
              {facturas.length === 0 ? (
                <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ink-400)' }}>Sin factura vinculada</div>
              ) : facturas.map((f, i) => (
                <div key={i} style={{ fontSize: 12, marginTop: 4 }}>
                  {f.serie}{f.folio_factura}
                  {f.total != null && ` · ${MXN.format(f.total)}`}
                </div>
              ))}
            </div>
          </div>

          {/* Seguimiento de etapas */}
          <div className="eyebrow">Seguimiento</div>
          <div className="card" style={{ marginBottom: 14, padding: 0 }}>
            {['Orden de Compra','Entregada','Facturada','Complemento de Pago','Pagada'].map((e) => {
              const dato = etapas[e];
              return (
                <div key={e} style={{
                  padding: '10px 14px',
                  borderBottom: '1px solid var(--ink-100)',
                  display: 'flex', alignItems: 'center', gap: 10,
                }}>
                  <div style={{
                    width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                    background: dato?.completada ? 'var(--accent)' : 'var(--ink-200)',
                  }} />
                  <div>
                    <div style={{ fontSize: 12, fontWeight: dato?.completada ? 500 : 400 }}>{e}</div>
                    {dato?.fecha_etapa && (
                      <div style={{ fontSize: 11, color: 'var(--ink-500)' }}>{dato.fecha_etapa}</div>
                    )}
                    {dato?.referencia && (
                      <div style={{ fontSize: 11, color: 'var(--ink-500)' }}>{dato.referencia}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Notas */}
          {cot.notas && (
            <>
              <div className="eyebrow">Notas</div>
              <div className="card" style={{ fontSize: 12, color: 'var(--ink-700)', marginBottom: 14 }}>
                <div style={{ padding: '10px 14px' }}>{cot.notas}</div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
