import { useState, useRef } from 'react';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { ConfirmModal } from '../../components/ConfirmModal';
import { ContextMenu } from '../../components/ContextMenu';
import { toast } from '../../lib/toast';
import { useAuth } from '../../hooks/useAuth';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

const TIPO_COLOR = {
  I: { bg: '#dcfce7', color: '#166534' },
  E: { bg: '#fee2e2', color: '#991b1b' },
  P: { bg: '#e0f2fe', color: '#075985' },
  N: { bg: '#f3f4f6', color: '#374151' },
  T: { bg: '#fef9c3', color: '#854d0e' },
};

const TIPO_OPCIONES = [
  { value: 'I', label: 'I — Ingreso' },
  { value: 'E', label: 'E — Egreso' },
  { value: 'P', label: 'P — Pago' },
  { value: 'N', label: 'N — Nómina' },
  { value: 'T', label: 'T — Traslado' },
];

export default function FacturaList() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'Administrador';
  const { activeRS, razonSociales } = useRazonSocial();
  const multiRS = razonSociales.length > 1;
  const [q, setQ]             = useState('');
  const [tipoFiltro, setTipoFiltro] = useState([]);
  const [sinVincular, setSinVincular] = useState(false);
  const [pagina, setPag]      = useState(1);
  const [sel, setSel]         = useState(null);
  const [vinculando, setVinculando] = useState(null);
  const [sugKey, setSugKey]   = useState(0);
  const [confirmCancelar, setConfirmCancelar] = useState(false);
  const [ctxMenu, setCtxMenu] = useState(null);
  const longPressTimer = useRef(null);

  const [cotQ, setCotQ] = useState('');
  const [cotResults, setCotResults] = useState(null);
  const [cotBuscando, setCotBuscando] = useState(false);
  const [vinculandoCot, setVinculandoCot] = useState(null);

  const [nuevoTipo, setNuevoTipo] = useState('');
  const [guardandoTipo, setGuardandoTipo] = useState(false);

  const params = new URLSearchParams({ pagina });
  if (q) params.set('q', q);
  if (sinVincular) params.set('sin_vincular', 'true');
  tipoFiltro.forEach((t) => params.append('tipo', t));
  if (activeRS != null) params.set('razon_social_id', activeRS);

  const { data, loading, refetch } = useFetch(`/api/documentos/cfdi?${params}`);
  const { data: detData, refetch: refetchDet } = useFetch(sel ? `/api/documentos/cfdi/${sel}` : null);
  const { data: sugData } = useFetch(
    sel && detData?.factura?.tipo === 'I' ? `/api/documentos/cfdi/${sel}/sugerencias?_k=${sugKey}` : null
  );

  const facturas   = data?.facturas   ?? [];
  const total      = data?.total      ?? 0;
  const totalPags  = data?.total_pags ?? 1;
  const tipos      = data?.tipos      ?? [];

  const factura      = detData?.factura      ?? null;
  const conceptos    = detData?.conceptos    ?? [];
  const cotizaciones = detData?.cotizaciones ?? [];
  const sugerencias  = sugData?.sugerencias  ?? [];

  async function handleVincular(cotizacionId) {
    setVinculando(cotizacionId);
    try {
      await api.post(`/api/documentos/cfdi/${sel}/vincular`, { cotizacion_id: cotizacionId });
      setSugKey((k) => k + 1);
      refetchDet();
      refetch();
    } finally {
      setVinculando(null);
    }
  }

  function handleSelToggle(id) {
    if (sel !== id) { setCotQ(''); setCotResults(null); setNuevoTipo(''); }
    setSel(sel === id ? null : id);
  }

  async function buscarCotizaciones(texto) {
    setCotQ(texto);
    setCotBuscando(true);
    try {
      const params = new URLSearchParams();
      if (texto.trim()) params.set('q', texto.trim());
      const data = await api.get(`/api/comercial/cotizaciones?${params}`);
      setCotResults(data.cotizaciones ?? []);
    } catch {
      setCotResults([]);
    } finally {
      setCotBuscando(false);
    }
  }

  async function handleVincularCot(cotizacionId) {
    setVinculandoCot(cotizacionId);
    try {
      await api.post(`/api/documentos/cfdi/${sel}/vincular`, { cotizacion_id: cotizacionId });
      setSugKey((k) => k + 1);
      setCotResults(null);
      setCotQ('');
      refetchDet();
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setVinculandoCot(null);
    }
  }

  function startLongPress(e, f) {
    const touch = e.touches[0];
    longPressTimer.current = setTimeout(() => setCtxMenu({ x: touch.clientX, y: touch.clientY, row: f }), 500);
  }

  function getCtxItems(f) {
    const items = [];
    if (f.tipo === 'E') {
      if (f.compra_id) {
        items.push({ type: 'item', label: 'Ver compra',
          onClick: () => navigate(`/abastecimiento/compras/${f.compra_id}`) });
      } else {
        items.push({ type: 'item', label: 'Registrar compra',
          onClick: () => navigate('/abastecimiento/compras/nueva', { state: { prefill: {
            factura_id: f.id, fecha: f.fecha, rfc_emisor: f.rfc_emisor, nombre_emisor: f.nombre_emisor,
          }}}) });
      }
    }
    if (f.tipo === 'I' && !f.cancelada) {
      if (items.length) items.push({ type: 'divider' });
      items.push({ type: 'item', label: 'Cancelar factura', danger: true,
        onClick: () => { setSel(f.id); setConfirmCancelar(true); } });
    }
    return items;
  }

  async function handleCancelar() {
    try {
      await api.patch(`/api/documentos/cfdi/${sel}/cancelar`, {});
      toast.success('Factura marcada como cancelada');
      setConfirmCancelar(false);
      refetchDet();
      refetch();
    } catch (e) {
      toast.error(e.message);
    }
  }

  async function handleCambiarTipo() {
    if (!nuevoTipo || nuevoTipo === factura?.tipo) return;
    setGuardandoTipo(true);
    try {
      await api.patch(`/api/documentos/cfdi/${sel}/tipo`, { tipo: nuevoTipo });
      toast.success(`Tipo cambiado a ${nuevoTipo}`);
      setNuevoTipo('');
      refetchDet();
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardandoTipo(false);
    }
  }

  return (
    <>
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Facturas</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Facturas CFDI</div>
          <div className="page-sub">{total} facturas importadas</div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/documentos/cfdi/importar')}>
          Importar XML
        </button>
      </div>

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16, alignItems: 'center' }}>
        <input className="input" style={{ maxWidth: 300 }}
          placeholder="Buscar folio, RFC, nombre, UUID…"
          value={q} onChange={(e) => { setQ(e.target.value); setPag(1); }} />
        <MultiSelectDropdown
          options={tipos}
          values={tipoFiltro}
          onChange={(v) => { setTipoFiltro(v); setPag(1); }}
          placeholder="Tipo…"
        />
        <button
          className={`btn btn-sm${sinVincular ? ' btn-primary' : ''}`}
          onClick={() => { setSinVincular((v) => !v); setPag(1); }}
          title="Facturas de ingreso sin cotización vinculada"
        >
          Sin vincular
        </button>
      </div>

      <div className="list-layout" style={{
        display: 'grid', gridTemplateColumns: sel ? '1fr 400px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div>
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 40 }}>Tipo</th>
                <th style={{ width: 90 }}>Folio</th>
                <th style={{ width: 95 }}>Fecha</th>
                <th>Emisor</th>
                <th>Receptor</th>
                <th className="num" style={{ width: 120 }}>Total</th>
                <th style={{ width: 55 }}>Cots.</th>
                {multiRS && <th style={{ width: 140 }}>RS</th>}
                <th className="ctx-col" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : facturas.length === 0 ? (
                <tr><td colSpan={multiRS ? 9 : 8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
              ) : facturas.map((f) => (
                <tr key={f.id} className={sel === f.id ? 'sel' : ''} style={{ cursor: 'pointer' }}
                    onClick={() => handleSelToggle(f.id)}
                    onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, row: f }); }}
                    onTouchStart={(e) => startLongPress(e, f)}
                    onTouchMove={() => clearTimeout(longPressTimer.current)}
                    onTouchEnd={() => clearTimeout(longPressTimer.current)}
                >
                  <td>
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: '2px 5px', borderRadius: 3,
                      background: TIPO_COLOR[f.tipo]?.bg ?? '#f3f4f6',
                      color: TIPO_COLOR[f.tipo]?.color ?? '#374151',
                    }}>{f.tipo_label}</span>
                  </td>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>
                    {f.folio || '—'}
                    {f.cancelada && (
                      <span style={{ marginLeft: 5, fontSize: 9, fontWeight: 700, padding: '1px 4px',
                        borderRadius: 3, background: '#fee2e2', color: '#991b1b' }}>
                        CANCELADA
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--ink-500)' }}>{f.fecha ?? f.fecha_timbrado ?? '—'}</td>
                  <td>
                    <div style={{ fontSize: 12.5 }}>{f.nombre_emisor ?? '—'}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)' }}>
                      {f.rfc_emisor ?? ''}
                    </div>
                  </td>
                  <td>
                    <div style={{ fontSize: 12.5 }}>{f.nombre_receptor ?? '—'}</div>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-400)' }}>
                      {f.rfc_receptor ?? ''}
                    </div>
                  </td>
                  <td className="num" style={{ fontWeight: 500 }}>{f.total != null ? MXN.format(f.total) : '—'}</td>
                  <td style={{ textAlign: 'center', color: f.num_cotizaciones > 0 ? 'var(--accent)' : 'var(--ink-300)' }}>
                    {f.num_cotizaciones}
                  </td>
                  {multiRS && (
                    <td style={{ fontSize: 11, color: 'var(--ink-500)' }} title={f.razon_social_nombre}>
                      {(f.razon_social_nombre ?? '—').length > 18
                        ? f.razon_social_nombre.slice(0, 18) + '…'
                        : f.razon_social_nombre ?? '—'}
                    </td>
                  )}
                  <td className="ctx-col" onClick={(e) => { e.stopPropagation(); setCtxMenu({ x: e.clientX, y: e.clientY, row: f }); }}>
                    <button className="ctx-kebab" aria-label="Acciones">⋮</button>
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
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '80vh' }}>
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
                    ['IVA',      factura.iva     != null ? MXN.format(factura.iva)     : '—'],
                    ['Total',    factura.total   != null ? MXN.format(factura.total)   : '—'],
                    ['Fecha',    factura.fecha ?? '—'],
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

                {/* Cotizaciones ya vinculadas */}
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
                          onClick={() => navigate(`/comercial/cotizaciones/${c.id}`)}>Abrir →</a>
                      </div>
                    ))}
                  </>
                )}

                {/* Sugerencias Fuzzy Match (solo para facturas de ingreso sin vincular o con pocas vinculaciones) */}
                {factura.tipo === 'I' && (
                  <>
                    <div className="eyebrow" style={{ marginTop: 14 }}>
                      Sugerencias de vinculación
                    </div>
                    {sugerencias.length === 0 ? (
                      <div style={{ fontSize: 11.5, color: 'var(--ink-400)', padding: '8px 0' }}>
                        Sin cotizaciones coincidentes por RFC y monto.
                      </div>
                    ) : (
                      sugerencias.map((s) => (
                        <div key={s.cot_id} style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '7px 0', borderBottom: '1px solid var(--ink-100)', gap: 8,
                        }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 12, fontWeight: 500 }}>
                              <span className="folio">{s.folio}</span>
                              <span style={{
                                marginLeft: 6, fontSize: 10.5,
                                color: s.diff_pct < 2 ? 'var(--accent)' : 'var(--warn)',
                              }}>
                                {s.diff_pct < 0.1 ? 'exacto' : `±${s.diff_pct}%`}
                              </span>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 1 }}>
                              {s.cliente} · {MXN.format(s.total)} · {s.estado}
                            </div>
                          </div>
                          <button
                            className="btn btn-sm btn-primary"
                            style={{ fontSize: 10.5, whiteSpace: 'nowrap' }}
                            disabled={vinculando === s.cot_id}
                            onClick={() => handleVincular(s.cot_id)}
                          >
                            {vinculando === s.cot_id ? '…' : 'Vincular'}
                          </button>
                        </div>
                      ))
                    )}
                  </>
                )}

                {factura.tipo === 'I' && (
                  <>
                    <div className="eyebrow" style={{ marginTop: 14 }}>Vincular cotización</div>
                    <input
                      className="input"
                      style={{ fontSize: 11.5, marginBottom: 6 }}
                      placeholder="Buscar por folio o cliente…"
                      value={cotQ}
                      onChange={(e) => buscarCotizaciones(e.target.value)}
                    />
                    {cotBuscando && (
                      <div style={{ fontSize: 11.5, color: 'var(--ink-400)', padding: '4px 0' }}>Buscando…</div>
                    )}
                    {!cotBuscando && cotResults !== null && cotResults.length === 0 && (
                      <div style={{ fontSize: 11.5, color: 'var(--ink-400)', padding: '4px 0' }}>Sin resultados.</div>
                    )}
                    {!cotBuscando && cotResults && cotResults.length > 0 && cotResults.map((c) => (
                      <div key={c.id} style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        padding: '6px 0', borderBottom: '1px solid var(--ink-100)', gap: 8,
                      }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12, fontWeight: 500 }}>
                            <span className="folio">{c.folio}</span>
                          </div>
                          <div style={{ fontSize: 11, color: 'var(--ink-500)', marginTop: 1 }}>
                            {c.cliente} · {c.total != null ? MXN.format(c.total) : '—'} · {c.estado}
                          </div>
                        </div>
                        <button
                          className="btn btn-sm btn-primary"
                          style={{ fontSize: 10.5, whiteSpace: 'nowrap' }}
                          disabled={vinculandoCot === c.id}
                          onClick={() => handleVincularCot(c.id)}
                        >
                          {vinculandoCot === c.id ? '…' : 'Vincular'}
                        </button>
                      </div>
                    ))}
                  </>
                )}

                {isAdmin && !factura.cancelada && (
                  <>
                    <div className="eyebrow" style={{ marginTop: 14 }}>Corrección de tipo</div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                      <select
                        className="input"
                        style={{ fontSize: 11.5, flex: 1 }}
                        value={nuevoTipo || factura.tipo}
                        onChange={(e) => setNuevoTipo(e.target.value)}
                      >
                        {TIPO_OPCIONES.map((o) => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                      <button
                        className="btn btn-sm btn-primary"
                        style={{ fontSize: 11, whiteSpace: 'nowrap' }}
                        disabled={guardandoTipo || !nuevoTipo || nuevoTipo === factura.tipo}
                        onClick={handleCambiarTipo}
                      >
                        {guardandoTipo ? '…' : 'Guardar'}
                      </button>
                    </div>
                  </>
                )}

                <div style={{ marginTop: 14, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
                  {factura.tipo === 'I' && !factura.cancelada && (
                    <button className="btn btn-sm btn-danger" onClick={() => setConfirmCancelar(true)}>
                      Cancelar factura
                    </button>
                  )}
                  {factura.tipo === 'E' && (
                    factura.compra_id ? (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => navigate(`/abastecimiento/compras/${factura.compra_id}`)}
                      >
                        Ver compra →
                      </button>
                    ) : (
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => navigate('/abastecimiento/compras/nueva', {
                          state: {
                            prefill: {
                              factura_id: factura.id,
                              fecha: factura.fecha ?? factura.fecha_timbrado,
                              uuid: factura.uuid,
                              rfc_emisor: factura.rfc_emisor,
                              nombre_emisor: factura.nombre_emisor,
                              conceptos: conceptos.map((c) => ({
                                descripcion: c.descripcion,
                                cantidad: c.cantidad,
                                valor_unitario: c.valor_unitario,
                              })),
                            },
                          },
                        })}
                      >
                        Registrar compra →
                      </button>
                    )
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>

    <ConfirmModal
      open={confirmCancelar}
      onClose={() => setConfirmCancelar(false)}
      onConfirm={handleCancelar}
      title="¿Cancelar esta factura?"
      description="Se marcará como cancelada. Esta acción no se puede deshacer."
      confirmLabel="Cancelar factura"
      danger
    />
    {ctxMenu && (
      <ContextMenu
        x={ctxMenu.x}
        y={ctxMenu.y}
        items={getCtxItems(ctxMenu.row)}
        onClose={() => setCtxMenu(null)}
      />
    )}
    </>
  );
}
