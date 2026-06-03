import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/StatusBadge';
import { Stepper, buildSteps } from '../../components/Stepper';
import { NextRibbon, buildNextAction } from '../../components/NextRibbon';
import { Modal } from '../../components/Modal';
import { ConfirmModal } from '../../components/ConfirmModal';
import { VincularCfdiModal } from '../facturas/VincularCfdiModal';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function CotDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const ids = location.state?.ids ?? [];
  const currentIdx = ids.indexOf(Number(id));
  const prevId = currentIdx > 0 ? ids[currentIdx - 1] : null;
  const nextId = currentIdx < ids.length - 1 ? ids[currentIdx + 1] : null;

  const handlePdf = async () => {
    await api.download(`/api/comercial/cotizaciones/${id}/pdf`, `Cotizacion_${id}.pdf`);
  };

  const handleNotaRemision = async () => {
    await api.download(`/api/comercial/cotizaciones/${id}/nota-remision/pdf`, `NotaRemision_${id}.pdf`);
  };
  const { data, loading, error, refetch } = useFetch(`/api/comercial/cotizaciones/${id}`);
  const { data: trasladoData, refetch: refetchTraslado } = useFetch(`/api/comercial/cotizaciones/${id}/traslado`);

  const [resultado,      setResultado]      = useState(null);
  const [motivoPerdida,  setMotivoPerdida]  = useState('');
  const [guardandoRes,   setGuardandoRes]   = useState(false);

  const [modalOC,        setModalOC]        = useState(false);
  const [ocInput,        setOcInput]        = useState('');
  const [confirmEntregar, setConfirmEntregar] = useState(false);
  const [modalEntregar,  setModalEntregar]  = useState(false);
  const [fechaEntrega,   setFechaEntrega]   = useState('');
  const [modalPago,      setModalPago]      = useState(false);
  const [pagoMonto,      setPagoMonto]      = useState('');
  const [pagoFecha,      setPagoFecha]      = useState('');
  const [guardandoEst,   setGuardandoEst]   = useState(false);
  const [confirmCancelar, setConfirmCancelar] = useState(false);
  const [docsOpen,        setDocsOpen]        = useState(false);
  const [modalSinCfdi,   setModalSinCfdi]   = useState(false);
  const [nroFactura,     setNroFactura]     = useState('');
  const [fechaFactura,   setFechaFactura]   = useState('');
  const [modalTraslado,  setModalTraslado]  = useState(false);
  const [tOrigen,        setTOrigen]        = useState('');
  const [tDestino,       setTDestino]       = useState('');
  const [tTransportista, setTTransportista] = useState('');
  const [tPlacas,        setTPlacas]        = useState('');
  const [tFecha,         setTFecha]         = useState('');
  const [tNotas,         setTNotas]         = useState('');
  const [guardandoTras,  setGuardandoTras]  = useState(false);
  const [modalVincular,  setModalVincular]  = useState(false);
  const [creandoEstudio, setCreandoEstudio] = useState(false);

  const LABELS_ESTADO = {
    Programada: 'OC registrada — cotización programada',
    Entregada:  'Cotización marcada como Entregada',
    Pagada:     'Pago registrado',
  };

  const handleCambiarEstado = async (nuevoEstado, extras = {}) => {
    setGuardandoEst(true);
    try {
      await api.patch(`/api/comercial/cotizaciones/${id}/estado`, { nuevo_estado: nuevoEstado, ...extras });
      await refetch();
      toast.success(LABELS_ESTADO[nuevoEstado] ?? 'Estado actualizado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardandoEst(false);
    }
  };

  if (loading) return <div className="page"><div className="page-state">Cargando…</div></div>;
  if (error)   return <div className="page"><div className="page-state page-state--error">Error: {error}</div></div>;
  if (!data)   return null;

  const cot      = data.cotizacion;
  const partidas = data.partidas ?? [];
  const etapas   = data.etapas ?? {};
  const facturas = data.facturas_vinculadas ?? [];
  const compras  = data.compras_vinculadas ?? [];

  const estudios  = data.estudios ?? [];
  const traslado  = trasladoData?.traslado ?? null;

  const resActual = resultado ?? cot.resultado;
  const motivoActual = motivoPerdida || cot.motivo_perdida || '';

  const handleGuardarResultado = async () => {
    if (!resActual) return;
    setGuardandoRes(true);
    try {
      await api.patch(`/api/comercial/cotizaciones/${id}/resultado`, {
        resultado: resActual,
        motivo_perdida: resActual === 'perdida' ? motivoActual : null,
      });
      toast.success('Resultado guardado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardandoRes(false);
    }
  };

  const handleNuevoEstudio = async () => {
    if (creandoEstudio) return;
    setCreandoEstudio(true);
    try {
      const d = await api.post('/api/abastecimiento/estudios', {
        nombre: `Estudio – ${cot.folio}`,
        cotizacion_id: Number(id),
        margen_pct: 0.35,
      });
      navigate(`/abastecimiento/estudios/${d.id}`);
    } catch (e) {
      toast.error(e.message ?? 'Error al crear estudio');
      setCreandoEstudio(false);
    }
  };

  const today = new Date().toISOString().slice(0, 10);

  const steps     = buildSteps(cot);
  const nextAction = buildNextAction(cot, {
    onEnviar:            () => handleCambiarEstado('Pendiente'),
    onGenerarOC:         () => navigate(`/abastecimiento/compras/nueva?cotizacion_id=${cot.id}`),
    onFacturar:          () => setModalVincular(true),
    onRegistrarSinCfdi:  () => { setNroFactura(''); setFechaFactura(today); setModalSinCfdi(true); },
    onNotaRemision:      handleNotaRemision,
    onRegistrarOC:       () => { setOcInput(cot.orden_compra || ''); setModalOC(true); },
    onEntregar:          () => { setFechaEntrega(today); setConfirmEntregar(true); },
    onPago:              () => { setPagoMonto(cot.total != null ? String(cot.total) : ''); setPagoFecha(today); setModalPago(true); },
  });

  return (
    <>
    <div className="page">
      {/* Breadcrumb */}
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <span>{cot.folio}</span>
      </div>

      {/* Hero */}
      <div className="card" style={{ marginBottom: 20, padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* Folio + badge + fecha */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-400)' }}>{cot.folio}</span>
              <StatusBadge status={cot.estado} />
              {cot.fecha && <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>{cot.fecha}</span>}
            </div>

            {/* Cliente — protagonista */}
            <div style={{ fontFamily: 'var(--serif)', fontSize: 26, letterSpacing: '-0.02em', lineHeight: 1.15, marginBottom: 10 }}>
              {cot.cliente}
            </div>

            {/* Métricas clave */}
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
              {cot.total != null && (
                <div>
                  <div style={{ fontSize: 10, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Total</div>
                  <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.02em', color: 'var(--ink-900)' }}>
                    {MXN.format(cot.total)}
                  </div>
                </div>
              )}
              <div style={{ width: 1, height: 32, background: 'var(--ink-200)' }} />
              <div>
                <div style={{ fontSize: 10, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Partidas</div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>{partidas.length}</div>
              </div>
              {cot.orden_compra && (
                <>
                  <div style={{ width: 1, height: 32, background: 'var(--ink-200)' }} />
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>OC</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{cot.orden_compra}</div>
                  </div>
                </>
              )}
              {cot.fecha_entrega && (
                <>
                  <div style={{ width: 1, height: 32, background: 'var(--ink-200)' }} />
                  <div>
                    <div style={{ fontSize: 10, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Entrega</div>
                    <div style={{ fontSize: 13 }}>{cot.fecha_entrega}</div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Acciones + navegación */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-end', flexShrink: 0 }}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button className="btn btn-sm" onClick={() => navigate('/comercial/cotizaciones')}>← Volver</button>
              {ids.length > 0 && (
                <>
                  <button className="btn btn-sm" disabled={!prevId}
                    onClick={() => navigate(`/comercial/cotizaciones/${prevId}`, { state: { ids } })}>←</button>
                  <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>{currentIdx + 1} / {ids.length}</span>
                  <button className="btn btn-sm" disabled={!nextId}
                    onClick={() => navigate(`/comercial/cotizaciones/${nextId}`, { state: { ids } })}>→</button>
                  <div style={{ width: 1, height: 20, background: 'var(--ink-200)', margin: '0 4px' }} />
                </>
              )}
              <div className="dropdown">
                <button className="btn btn-sm" onClick={() => setDocsOpen(v => !v)}>Documentos ▾</button>
                {docsOpen && (
                  <>
                    <div style={{ position: 'fixed', inset: 0, zIndex: 19 }} onClick={() => setDocsOpen(false)} />
                    <div className="dropdown-menu">
                      <button className="dropdown-item" onClick={() => { handlePdf(); setDocsOpen(false); }}>PDF cotización</button>
                      <button className="dropdown-item" onClick={() => { handleNotaRemision(); setDocsOpen(false); }}>Nota de Remisión</button>
                    </div>
                  </>
                )}
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/comercial/cotizaciones/${id}/expediente`)}>Expediente</button>
              <button className="btn btn-sm" onClick={() => navigate(`/comercial/cotizaciones/${id}/editar`)}>Editar</button>
            </div>
            {!['Cancelada', 'Pagada'].includes(cot.estado) && (
              <button className="btn-link-danger" style={{ fontSize: 11 }} onClick={() => setConfirmCancelar(true)}>
                cancelar cotización
              </button>
            )}
          </div>
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

      {/* Banner: sin costo real */}
      {['Entregada', 'Facturada', 'Pagada'].includes(cot.estado) && compras.length === 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          background: '#fff7ed', border: '1px solid #fed7aa',
          borderRadius: 8, padding: '10px 16px', marginBottom: 20,
          fontSize: 13, color: '#9a3412',
        }}>
          <span style={{ fontSize: 16 }}>⚠</span>
          <div style={{ flex: 1 }}>
            <strong>Sin costo real:</strong> esta cotización no tiene compra vinculada.
            El margen mostrado es estimado (costo snapshot del catálogo).
          </div>
          <button
            className="btn btn-sm"
            style={{ whiteSpace: 'nowrap' }}
            onClick={() => navigate(`/abastecimiento/compras/nueva?cotizacion_id=${cot.id}`)}
          >
            Registrar compra
          </button>
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
                  <th className="num" style={{ width: 72 }}>Margen</th>
                  <th style={{ width: 100 }}>Entrega</th>
                </tr>
              </thead>
              <tbody>
                {partidas.map((p, i) => {
                  const costoAlto  = p.costo_real != null && p.costo_snapshot != null
                                     && p.costo_real > p.costo_snapshot;

                  const DELIVERED = ['Entregada', 'Pagada', 'Facturada'];
                  const isDelivered = DELIVERED.includes(cot.estado);
                  const isPartial   = cot.estado === 'Parcialmente Entregada';
                  const entregado   = p.ya_entregado ?? 0;
                  let barPct, barColor, barLabel;
                  if (isDelivered) {
                    barPct = 100; barColor = 'var(--accent)'; barLabel = null;
                  } else if (isPartial || entregado > 0) {
                    barPct    = p.cantidad > 0 ? Math.min(entregado / p.cantidad * 100, 100) : 0;
                    barColor  = barPct >= 100 ? 'var(--accent)' : 'var(--warn)';
                    barLabel  = `${entregado} / ${p.cantidad}`;
                  } else {
                    const stock = p.stock_actual ?? 0;
                    barPct    = p.cantidad > 0 ? Math.min(stock / p.cantidad * 100, 100) : 0;
                    barColor  = p.stock_ok ? 'var(--accent)' : 'var(--danger)';
                    barLabel  = `${stock} / ${p.cantidad}`;
                  }

                  return (
                    <tr key={i} style={costoAlto ? { background: 'rgba(239,68,68,0.04)' } : {}}>
                      <td style={{ color: 'var(--ink-400)' }}>{i + 1}</td>
                      <td>
                        {p.nombre}
                        {p.pendiente_catalogo && (
                          <span className="qb-tag" style={{ marginLeft: 4, color: 'var(--warn)' }}>libre</span>
                        )}
                        {costoAlto && (
                          <span title={`Costo real ${MXN.format(p.costo_real)} > snapshot ${MXN.format(p.costo_snapshot)}`}
                                style={{ marginLeft: 6, fontSize: 10, color: 'var(--danger)', cursor: 'help' }}>
                            ⚠ costo real mayor
                          </span>
                        )}
                      </td>
                      <td className="num">{p.cantidad}</td>
                      <td className="num">{p.precio_unitario != null ? MXN.format(p.precio_unitario) : '—'}</td>
                      <td className="num" style={{ fontWeight: 500 }}>
                        {p.total != null ? MXN.format(p.total) : '—'}
                      </td>
                      <td className="num" style={{
                        fontSize: 11.5,
                        color: p.margen_pct == null ? 'var(--ink-400)'
                             : p.margen_pct < 0    ? 'var(--danger)'
                             : p.margen_pct < 15   ? 'var(--warn)'
                             : 'var(--ink-600)',
                      }}>
                        {p.margen_pct != null ? `${p.margen_pct.toFixed(1)}%` : '—'}
                      </td>
                      <td style={{ fontSize: 11 }}>
                        {p.producto_id ? (
                          <div style={{ paddingRight: 4 }}>
                            <div style={{ height: 4, background: 'var(--ink-100)', borderRadius: 2, marginBottom: 3 }}>
                              <div style={{ width: `${barPct}%`, height: '100%', background: barColor, borderRadius: 2 }} />
                            </div>
                            {barLabel && (
                              <span style={{ color: 'var(--ink-500)' }}>{barLabel}</span>
                            )}
                            {!p.stock_ok && !isDelivered && !isPartial && (
                              <span className="qb-tag" style={{ marginLeft: 4 }}>Falta</span>
                            )}
                          </div>
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
                <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ink-400)', fontStyle: 'italic' }}>
                  Aún no hay compra vinculada.
                </div>
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
                <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ink-400)', fontStyle: 'italic' }}>
                  Aún no hay factura vinculada.
                </div>
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

          {/* Traslado / carta porte */}
          <div className="eyebrow">Traslado</div>
          <div className="card" style={{ marginBottom: 14 }}>
            {traslado ? (
              <div style={{ padding: '10px 14px', fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {[
                  ['Origen',       traslado.origen],
                  ['Destino',      traslado.destino],
                  ['Transportista',traslado.transportista],
                  ['Placas',       traslado.placas],
                  ['Fecha',        traslado.fecha_traslado],
                ].map(([k, v]) => v ? (
                  <div key={k}>
                    <span style={{ color: 'var(--ink-400)', marginRight: 4 }}>{k}:</span>
                    <span style={{ color: 'var(--ink-700)' }}>{v}</span>
                  </div>
                ) : null)}
                {traslado.notas && (
                  <div style={{ color: 'var(--ink-600)', fontSize: 11, marginTop: 2 }}>{traslado.notas}</div>
                )}
              </div>
            ) : (
              <div style={{ padding: '10px 14px', fontSize: 12, color: 'var(--ink-400)', fontStyle: 'italic' }}>
                Sin datos de traslado registrados.
              </div>
            )}
            <div style={{ padding: '8px 14px', borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn" style={{ width: '100%', fontSize: 11 }}
                onClick={() => {
                  setTOrigen(traslado?.origen ?? '');
                  setTDestino(traslado?.destino ?? '');
                  setTTransportista(traslado?.transportista ?? '');
                  setTPlacas(traslado?.placas ?? '');
                  setTFecha(traslado?.fecha_traslado ?? today);
                  setTNotas(traslado?.notas ?? '');
                  setModalTraslado(true);
                }}>
                {traslado ? 'Editar traslado' : '+ Registrar traslado'}
              </button>
            </div>
          </div>

          {/* Resultado de la cotización */}
          <div className="eyebrow">Resultado</div>
          <div className="card" style={{ marginBottom: 14, padding: '10px 14px' }}>
            <div style={{ marginBottom: 8 }}>
              {['ganada', 'perdida', 'sin_respuesta'].map((r) => (
                <button key={r} onClick={() => setResultado(r)} style={{
                  marginRight: 6, marginBottom: 4, padding: '3px 10px', fontSize: 11,
                  borderRadius: 4, border: '1px solid',
                  cursor: 'pointer',
                  background: resActual === r
                    ? r === 'ganada' ? '#dcfce7' : r === 'perdida' ? '#fee2e2' : '#f3f4f6'
                    : 'transparent',
                  borderColor: resActual === r
                    ? r === 'ganada' ? '#16a34a' : r === 'perdida' ? '#dc2626' : '#9ca3af'
                    : 'var(--ink-200)',
                  color: resActual === r
                    ? r === 'ganada' ? '#166534' : r === 'perdida' ? '#991b1b' : '#374151'
                    : 'var(--ink-500)',
                }}>
                  {r === 'ganada' ? 'Ganada' : r === 'perdida' ? 'Perdida' : 'Sin respuesta'}
                </button>
              ))}
            </div>
            {resActual === 'perdida' && (
              <select className="input" style={{ fontSize: 11, marginBottom: 8 }}
                value={motivoActual}
                onChange={(e) => setMotivoPerdida(e.target.value)}>
                <option value="">— Motivo —</option>
                <option value="precio">Precio</option>
                <option value="tiempo">Tiempo de entrega</option>
                <option value="competidor">Competidor</option>
                <option value="presupuesto">Sin presupuesto</option>
                <option value="otro">Otro</option>
              </select>
            )}
            <button className="btn" style={{ width: '100%', fontSize: 11 }}
              disabled={!resActual || guardandoRes}
              onClick={handleGuardarResultado}>
              {guardandoRes ? 'Guardando…' : 'Guardar resultado'}
            </button>
          </div>

          {/* Estudios de mercado */}
          <div className="eyebrow">Estudios de mercado</div>
          <div className="card" style={{ marginBottom: 14 }}>
            {estudios.length === 0 ? (
              <div style={{ padding: '10px 14px', fontSize: 12, color: 'var(--ink-400)', fontStyle: 'italic' }}>
                Aún no hay estudios de mercado vinculados.
              </div>
            ) : estudios.map((e, i) => {
              const esActivo = e.estado === 'abierto';
              return (
                <div key={i} style={{
                  padding: '10px 14px',
                  borderBottom: i < estudios.length - 1 ? '1px solid var(--ink-100)' : 'none',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: esActivo ? 600 : 400 }}>{e.nombre}</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>
                      {e.fecha}
                      {' · '}
                      <span style={{ color: esActivo ? 'var(--accent)' : 'var(--ink-300)' }}>
                        {esActivo ? 'Activo' : 'Cerrado'}
                      </span>
                    </div>
                  </div>
                  <button
                    className="btn btn-sm"
                    style={{ fontSize: 11, padding: '2px 8px' }}
                    onClick={() => navigate(`/abastecimiento/estudios/${e.id}`)}
                  >
                    Ver →
                  </button>
                </div>
              );
            })}
            <div style={{ padding: '10px 14px', borderTop: estudios.length > 0 ? '1px solid var(--ink-100)' : 'none' }}>
              <button className="btn" onClick={handleNuevoEstudio}
                      style={{ width: '100%', fontSize: 11 }}
                      disabled={creandoEstudio}>
                {creandoEstudio ? 'Creando…' : '+ Nuevo estudio de mercado'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    {/* Modal: Registrar OC */}
    <Modal open={modalOC} onClose={() => setModalOC(false)} title="Registrar Orden de Compra" width={400}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>NÚMERO DE OC</div>
          <input className="input" value={ocInput} onChange={(e) => setOcInput(e.target.value)}
            placeholder="Ej. OC-2025-001" autoFocus />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalOC(false)}>Cancelar</button>
          <button className="btn btn-primary" disabled={!ocInput.trim() || guardandoEst}
            onClick={async () => {
              await handleCambiarEstado('Programada', { orden_compra: ocInput.trim() });
              setModalOC(false);
            }}>
            {guardandoEst ? 'Guardando…' : 'Confirmar'}
          </button>
        </div>
      </div>
    </Modal>

    {/* Confirm: Cancelar cotización */}
    <ConfirmModal
      open={confirmCancelar}
      onClose={() => setConfirmCancelar(false)}
      onConfirm={async () => {
        setConfirmCancelar(false);
        await handleCambiarEstado('Cancelada');
      }}
      title="¿Cancelar cotización?"
      description={`Se marcará ${cot.folio} como Cancelada. Esta acción no se puede deshacer.`}
      confirmLabel="Cancelar cotización"
      danger
    />

    {/* Confirm: Marcar entregada (aviso de stock) */}
    <ConfirmModal
      open={confirmEntregar}
      onClose={() => setConfirmEntregar(false)}
      onConfirm={() => { setConfirmEntregar(false); setModalEntregar(true); }}
      title="¿Marcar como Entregada?"
      description={`Se descontará del inventario el stock de los productos de catálogo en esta cotización. Esta acción no se puede deshacer.`}
      confirmLabel="Continuar"
      danger
    />

    {/* Modal: Fecha de entrega */}
    <Modal open={modalEntregar} onClose={() => setModalEntregar(false)} title="Fecha de entrega" width={400}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>FECHA DE ENTREGA</div>
          <input className="input" type="date" value={fechaEntrega}
            onChange={(e) => setFechaEntrega(e.target.value)} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalEntregar(false)}>Cancelar</button>
          <button className="btn btn-primary" disabled={guardandoEst}
            onClick={async () => {
              await handleCambiarEstado('Entregada', { fecha_entrega: fechaEntrega || null });
              setModalEntregar(false);
            }}>
            {guardandoEst ? 'Guardando…' : 'Confirmar entrega'}
          </button>
        </div>
      </div>
    </Modal>

    {/* Modal: Registrar pago */}
    <Modal open={modalPago} onClose={() => setModalPago(false)} title="Registrar pago" width={400}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>MONTO PAGADO (MXN)</div>
          <input className="input" type="number" step="0.01" min="0"
            value={pagoMonto} onChange={(e) => setPagoMonto(e.target.value)}
            placeholder="0.00" autoFocus />
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>FECHA DE PAGO</div>
          <input className="input" type="date" value={pagoFecha}
            onChange={(e) => setPagoFecha(e.target.value)} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalPago(false)}>Cancelar</button>
          <button className="btn btn-primary"
            disabled={!pagoMonto || parseFloat(pagoMonto) <= 0 || guardandoEst}
            onClick={async () => {
              await handleCambiarEstado('Pagada', {
                monto_pagado: parseFloat(pagoMonto),
                fecha_pago: pagoFecha || null,
              });
              setModalPago(false);
            }}>
            {guardandoEst ? 'Guardando…' : 'Confirmar pago'}
          </button>
        </div>
      </div>
    </Modal>

    {/* Modal: Traslado */}
    <Modal open={modalTraslado} onClose={() => setModalTraslado(false)} title="Datos de traslado" width={440}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>ORIGEN</div>
            <input className="input" value={tOrigen} onChange={(e) => setTOrigen(e.target.value)} placeholder="Ciudad origen" />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>DESTINO</div>
            <input className="input" value={tDestino} onChange={(e) => setTDestino(e.target.value)} placeholder="Ciudad destino" />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>TRANSPORTISTA</div>
            <input className="input" value={tTransportista} onChange={(e) => setTTransportista(e.target.value)} placeholder="Nombre transportista" />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>PLACAS</div>
            <input className="input" value={tPlacas} onChange={(e) => setTPlacas(e.target.value)} placeholder="ABC-123" />
          </div>
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>FECHA DE TRASLADO</div>
          <input className="input" type="date" value={tFecha} onChange={(e) => setTFecha(e.target.value)} />
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
          <textarea className="input" rows={2} value={tNotas} onChange={(e) => setTNotas(e.target.value)} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalTraslado(false)}>Cancelar</button>
          <button className="btn btn-primary" disabled={guardandoTras}
            onClick={async () => {
              setGuardandoTras(true);
              try {
                await api.post(`/api/comercial/cotizaciones/${id}/traslado`, {
                  origen: tOrigen || null,
                  destino: tDestino || null,
                  transportista: tTransportista || null,
                  placas: tPlacas || null,
                  fecha_traslado: tFecha || null,
                  notas: tNotas || null,
                });
                toast.success('Traslado registrado');
                setModalTraslado(false);
                refetchTraslado();
              } catch (e) {
                toast.error(e.message);
              } finally {
                setGuardandoTras(false);
              }
            }}>
            {guardandoTras ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </Modal>

    {/* Modal: Vincular CFDI */}
    <VincularCfdiModal
      open={modalVincular}
      onClose={() => setModalVincular(false)}
      cotizacionId={Number(id)}
      onLinked={refetch}
      facturasVinculadas={facturas}
    />

    {/* Modal: Registrar factura sin CFDI */}
    <Modal open={modalSinCfdi} onClose={() => setModalSinCfdi(false)} title="Registrar número de factura" width={400}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>NÚMERO DE FACTURA</div>
          <input className="input" value={nroFactura} onChange={(e) => setNroFactura(e.target.value)}
            placeholder="Ej. FAC-2026-001" autoFocus />
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>FECHA DE FACTURA</div>
          <input className="input" type="date" value={fechaFactura}
            onChange={(e) => setFechaFactura(e.target.value)} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalSinCfdi(false)}>Cancelar</button>
          <button className="btn btn-primary" disabled={!nroFactura.trim() || guardandoEst}
            onClick={async () => {
              await handleCambiarEstado('Facturada', {
                numero_factura: nroFactura.trim(),
                fecha_entrega: fechaFactura || null,
              });
              setModalSinCfdi(false);
            }}>
            {guardandoEst ? 'Guardando…' : 'Confirmar'}
          </button>
        </div>
      </div>
    </Modal>
    </>
  );
}
