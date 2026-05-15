import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { api } from '../../lib/apiClient';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

const ETAPA_TITULO = {
  'Orden de Compra':     'Orden de Compra registrada',
  'Entregada':           'Entrega completada',
  'Facturada':           'Facturación registrada',
  'Complemento de Pago': 'Complemento de pago',
  'Pagada':              'Pago registrado',
};

const TIPO_COLOR = {
  creacion: 'var(--accent)',
  oc:       'var(--warn)',
  compra:   'var(--ink-400)',
  factura_venta: 'var(--primary)',
  entrega:  'var(--accent)',
  pago:     'var(--accent)',
  otro:     'var(--ink-300)',
};

function buildTimeline({ cot, etapas, compras, facturas }) {
  const ev = [];

  if (cot.fecha) {
    ev.push({ fecha: cot.fecha, tipo: 'creacion', titulo: 'Cotización enviada', detalle: cot.folio });
  }

  const etapaToTipo = {
    'Orden de Compra':     'oc',
    'Entregada':           'entrega',
    'Facturada':           'otro',
    'Complemento de Pago': 'otro',
    'Pagada':              'pago',
  };

  Object.entries(etapas).forEach(([etapa, dato]) => {
    if (dato?.completada && dato?.fecha_etapa) {
      let detalle = dato.referencia || '';
      if (etapa === 'Orden de Compra' && cot.orden_compra) detalle = cot.orden_compra;
      if (etapa === 'Pagada' && cot.monto_pagado != null) detalle = MXN.format(cot.monto_pagado);
      ev.push({
        fecha:  dato.fecha_etapa,
        tipo:   etapaToTipo[etapa] ?? 'otro',
        titulo: ETAPA_TITULO[etapa] ?? etapa,
        detalle: detalle || null,
      });
    }
  });

  compras.forEach((c) => {
    if (c.fecha) {
      ev.push({
        fecha:  c.fecha,
        tipo:   'compra',
        titulo: 'Compra registrada',
        detalle: c.compra_folio || c.folio_factura || `#${c.id}`,
        linkPath: `/compras/${c.id}`,
      });
    }
  });

  facturas.forEach((f) => {
    if (f.fecha) {
      ev.push({
        fecha:  f.fecha,
        tipo:   'factura_venta',
        titulo: 'Factura de venta',
        detalle: `${f.serie || ''}${f.folio_factura}`,
      });
    }
  });

  ev.sort((a, b) => (a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0));
  return ev;
}

export default function CotExpediente() {
  const { id }     = useParams();
  const navigate   = useNavigate();
  const { data, loading, error } = useFetch(`/api/cotizaciones/${id}`);

  const handlePdf = () => api.download(`/api/cotizaciones/${id}/pdf`, `Cotizacion_${id}.pdf`);
  const handleNota = () => api.download(`/api/cotizaciones/${id}/nota-remision/pdf`, `NotaRemision_${id}.pdf`);

  if (loading) return <div className="page"><div className="page-state">Cargando…</div></div>;
  if (error)   return <div className="page"><div className="page-state page-state--error">Error: {error}</div></div>;
  if (!data)   return null;

  const cot      = data.cotizacion;
  const partidas = data.partidas ?? [];
  const etapas   = data.etapas ?? {};
  const facturas = data.facturas_vinculadas ?? [];
  const compras  = data.compras_vinculadas ?? [];

  const timeline = buildTimeline({ cot, etapas, compras, facturas });

  const infoRows = [
    ['Cliente',    cot.cliente],
    ['RFC',        cot.cliente_rfc],
    ['Tipo',       cot.tipo_cliente],
    ['Comprador',  cot.comprador_nombre],
    ['OC',         cot.orden_compra],
    ['Fecha',      cot.fecha],
    ['F. entrega', cot.fecha_entrega],
    ['F. pago',    cot.fecha_pago],
    ['Factura',    cot.numero_factura],
    ['Notas',      cot.notas],
  ].filter(([, v]) => v);

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <a onClick={() => navigate(`/cotizaciones/${id}`)}>{cot.folio}</a>
        <span className="sep">/</span>
        <span>Expediente</span>
      </div>

      <div className="page-header">
        <div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)', display: 'flex', gap: 8, alignItems: 'center' }}>
            {cot.folio} · <Pill status={cot.estado} />
          </div>
          <div className="page-title" style={{ marginTop: 4 }}>Expediente Digital</div>
          <div className="page-sub">
            {cot.cliente}
            {cot.total != null && ` · ${MXN.format(cot.total)}`}
            {` · ${partidas.length} partidas`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={handlePdf}>PDF</button>
          <button className="btn" onClick={handleNota}>Nota de Remisión</button>
          <button className="btn" onClick={() => window.print()}>Imprimir</button>
          <button className="btn" onClick={() => navigate(`/cotizaciones/${id}`)}>← Volver</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>

        {/* ── Columna izquierda ── */}
        <div>

          {/* Partidas */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h"><h3>Partidas</h3></div>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 28 }}>#</th>
                  <th>Descripción</th>
                  <th className="num" style={{ width: 80 }}>Cant.</th>
                  <th className="num" style={{ width: 100 }}>Precio unit.</th>
                  <th className="num" style={{ width: 110 }}>Total</th>
                </tr>
              </thead>
              <tbody>
                {partidas.map((p, i) => (
                  <tr key={i}>
                    <td style={{ color: 'var(--ink-400)' }}>{i + 1}</td>
                    <td>
                      <div>{p.nombre}</div>
                      {p.codigo && (
                        <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)', marginTop: 1 }}>
                          {p.codigo}
                        </div>
                      )}
                    </td>
                    <td className="num">{p.cantidad}{p.unidad_medida ? ` ${p.unidad_medida}` : ''}</td>
                    <td className="num">{p.precio_unitario != null ? MXN.format(p.precio_unitario) : '—'}</td>
                    <td className="num" style={{ fontWeight: 500 }}>
                      {p.total != null ? MXN.format(p.total) : '—'}
                    </td>
                  </tr>
                ))}
                <tr style={{ background: 'var(--ink-50)' }}>
                  <td colSpan={4} style={{ textAlign: 'right', fontSize: 11.5, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Subtotal</td>
                  <td className="num">{cot.subtotal != null ? MXN.format(cot.subtotal) : '—'}</td>
                </tr>
                {cot.aplica_iva && (
                  <tr style={{ background: 'var(--ink-50)' }}>
                    <td colSpan={4} style={{ textAlign: 'right', fontSize: 11.5, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>IVA 16%</td>
                    <td className="num">{cot.iva != null ? MXN.format(cot.iva) : '—'}</td>
                  </tr>
                )}
                <tr style={{ background: 'var(--ink-100)' }}>
                  <td colSpan={4} style={{ textAlign: 'right', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Total MXN</td>
                  <td className="num" style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-0.015em' }}>
                    {cot.total != null ? MXN.format(cot.total) : '—'}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Compras vinculadas */}
          {compras.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-h"><h3>Compras vinculadas</h3></div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Proveedor</th>
                    <th>Fecha</th>
                    <th className="num" style={{ width: 110 }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {compras.map((c, i) => (
                    <tr key={i} style={{ cursor: 'pointer' }} onClick={() => navigate(`/compras/${c.id}`)}>
                      <td className="folio">{c.compra_folio || `#${c.id}`}</td>
                      <td style={{ fontSize: 12 }}>{c.proveedor}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{c.fecha}</td>
                      <td className="num">{c.total != null ? MXN.format(c.total) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Facturas */}
          {facturas.length > 0 && (
            <div className="card">
              <div className="card-h"><h3>Facturas de venta</h3></div>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Folio</th>
                    <th>Receptor</th>
                    <th>Fecha</th>
                    <th className="num" style={{ width: 110 }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {facturas.map((f, i) => (
                    <tr key={i}>
                      <td className="folio">{f.serie}{f.folio_factura}</td>
                      <td style={{ fontSize: 12 }}>{f.nombre_receptor}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{f.fecha}</td>
                      <td className="num">{f.total != null ? MXN.format(f.total) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* ── Columna derecha ── */}
        <div>

          {/* Datos generales */}
          <div className="eyebrow">Datos</div>
          <div className="card" style={{ marginBottom: 14, padding: 0 }}>
            {infoRows.map(([k, v], i) => (
              <div key={k} style={{
                padding: '8px 14px',
                borderBottom: i < infoRows.length - 1 ? '1px solid var(--ink-100)' : 'none',
                display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline',
              }}>
                <span style={{ fontSize: 10.5, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>
                  {k}
                </span>
                <span style={{ fontSize: 12, textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </div>

          {/* Historial de eventos */}
          <div className="eyebrow">Historial</div>
          <div className="card" style={{ marginBottom: 14, padding: 0 }}>
            {timeline.length === 0 ? (
              <div style={{ padding: '12px 14px', fontSize: 12, color: 'var(--ink-400)' }}>Sin eventos registrados</div>
            ) : timeline.map((ev, i) => (
              <div key={i} style={{
                padding: '10px 14px',
                borderBottom: i < timeline.length - 1 ? '1px solid var(--ink-100)' : 'none',
                display: 'flex', gap: 10, alignItems: 'flex-start',
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0, marginTop: 4,
                  background: TIPO_COLOR[ev.tipo] ?? 'var(--ink-300)',
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 500 }}>{ev.titulo}</div>
                  {ev.detalle && (
                    <div style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 1, wordBreak: 'break-all' }}>
                      {ev.linkPath ? (
                        <a style={{ color: 'var(--primary)', cursor: 'pointer' }}
                           onClick={() => navigate(ev.linkPath)}>
                          {ev.detalle}
                        </a>
                      ) : ev.detalle}
                    </div>
                  )}
                  <div style={{ fontSize: 10.5, color: 'var(--ink-400)', marginTop: 2 }}>{ev.fecha}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Documentos */}
          <div className="eyebrow">Documentos</div>
          <div className="card" style={{ padding: 0 }}>
            {[
              { label: 'Cotización PDF', action: handlePdf },
              { label: 'Nota de Remisión', action: handleNota },
            ].map((doc, i, arr) => (
              <div key={i} style={{
                padding: '8px 14px',
                borderBottom: (i < arr.length - 1 || compras.length > 0) ? '1px solid var(--ink-100)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{ fontSize: 12 }}>{doc.label}</span>
                <button className="btn btn-sm" onClick={doc.action} style={{ fontSize: 11 }}>
                  ↓ PDF
                </button>
              </div>
            ))}
            {compras.map((c, i) => (
              <div key={i} style={{
                padding: '8px 14px',
                borderBottom: i < compras.length - 1 ? '1px solid var(--ink-100)' : 'none',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{ fontSize: 12 }}>
                  Presupuesto {c.compra_folio || `#${c.id}`}
                </span>
                <button className="btn btn-sm"
                  onClick={() => api.download(`/api/compras/${c.id}/pdf`, `Presupuesto_${c.id}.pdf`)}
                  style={{ fontSize: 11 }}>
                  ↓ PDF
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
