import { useState } from 'react';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';
import { Modal } from '../../components/Modal';
import { api } from '../../lib/apiClient';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

const MOTIVOS_AJUSTE = ['Conteo físico', 'Merma', 'Corrección sistema', 'Donación', 'Robo/pérdida', 'Otro'];

function StockBar({ actual, minimo }) {
  const a = actual ?? 0;
  const m = minimo ?? 0;
  if (a < 0) return <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{a}</span>;
  const color = m > 0 && a < m ? 'var(--warn)' : 'var(--ink-700)';
  return <span style={{ color, fontWeight: m > 0 && a < m ? 600 : 400 }}>{a}</span>;
}

const ABC_STYLE = {
  A: { background: '#dcfce7', color: '#166534' },
  B: { background: '#fef9c3', color: '#854d0e' },
  C: { background: '#f3f4f6', color: '#6b7280' },
};

function ABCBadge({ abc }) {
  const s = ABC_STYLE[abc] ?? ABC_STYLE.C;
  return <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, fontWeight: 600, ...s }}>{abc ?? 'C'}</span>;
}

function PrecioBadge({ dias }) {
  if (dias == null) return <span style={{ color: 'var(--ink-300)', fontSize: 11 }}>—</span>;
  if (dias > 30) return (
    <span title={`Hace ${dias} días`} style={{ fontSize: 10.5, color: 'var(--danger)', fontWeight: 600, cursor: 'help' }}>
      ⚠ {dias}d
    </span>
  );
  return <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>{dias}d</span>;
}

function TipoBadge({ tipo }) {
  const styles = {
    entrada: { background: '#dcfce7', color: '#166534' },
    salida:  { background: '#fee2e2', color: '#991b1b' },
    ajuste:  { background: '#e0f2fe', color: '#075985' },
  };
  const s = styles[tipo] ?? { background: '#f3f4f6', color: '#374151' };
  return (
    <span style={{ fontSize: 10.5, padding: '2px 6px', borderRadius: 3, ...s }}>{tipo}</span>
  );
}

function LoteBadge({ alerta, count }) {
  if (!alerta) return null;
  const cfg = {
    vencido: { bg: '#fee2e2', color: '#991b1b', label: `${count ?? '?'}L Vencido` },
    proximo: { bg: '#ffedd5', color: '#9a3412', label: `${count ?? '?'}L Próximo` },
    ok:      { bg: '#dcfce7', color: '#166534', label: `${count ?? 0}L` },
  }[alerta] ?? { bg: '#f3f4f6', color: '#6b7280', label: '—' };
  return (
    <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, fontWeight: 600,
      background: cfg.bg, color: cfg.color }}>{cfg.label}</span>
  );
}

export default function StockList() {
  const navigate = useNavigate();
  const [q, setQ]               = useState('');
  const [catFiltro, setCatFiltro] = useState([]);
  const [bajoMin, setBajoMin]   = useState('');
  const [abcFiltro, setAbcFiltro] = useState([]);
  const [vista, setVista]       = useState('inventario');
  const [movPag, setMovPag]     = useState(1);

  // Modal ajuste
  const [ajusteProd, setAjusteProd] = useState(null);
  const [sNuevo, setSNuevo]         = useState('');
  const [motivo, setMotivo]         = useState('Conteo físico');
  const [notas, setNotas]           = useState('');
  const [referencia, setReferencia] = useState('');
  const [saving, setSaving]         = useState(false);
  const [ajusteErr, setAjusteErr]   = useState('');

  // Modal lotes
  const [lotesProd, setLotesProd]   = useState(null);
  const [lotes, setLotes]           = useState([]);
  const [lotesLoading, setLotesLoading] = useState(false);
  const [nuevoLote, setNuevoLote]   = useState({ numero_lote: '', fecha_vencimiento: '', cantidad: '', notas: '' });
  const [savingLote, setSavingLote] = useState(false);

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  catFiltro.forEach((c) => params.append('categoria', c));
  if (bajoMin) params.set('bajo_minimo', bajoMin);

  const { data, loading, refetch }    = useFetch(vista === 'inventario' ? `/api/inventario/stock?${params}` : null);
  const { data: movData, loading: movLoading } = useFetch(
    vista === 'movimientos' ? `/api/inventario/stock/movimientos?pagina=${movPag}` : null
  );

  const productos  = data?.productos  ?? [];
  const categorias = data?.categorias ?? [];
  const stats      = data?.stats      ?? {};
  const movs       = movData?.movimientos ?? [];
  const movTotal   = movData?.total ?? 0;
  const movPags    = movData?.total_pags ?? 1;

  function abrirAjuste(p) {
    setAjusteProd(p);
    setSNuevo(String(p.stock_actual ?? 0));
    setMotivo('Conteo físico');
    setNotas('');
    setReferencia('');
    setAjusteErr('');
  }

  function cerrarAjuste() {
    setAjusteProd(null);
  }

  async function submitAjuste(e) {
    e.preventDefault();
    setAjusteErr('');
    const stockNuevo = parseFloat(sNuevo);
    if (isNaN(stockNuevo)) { setAjusteErr('Ingresa un número válido'); return; }
    if (motivo === 'Otro' && !notas.trim()) { setAjusteErr('Las notas son obligatorias cuando el motivo es "Otro"'); return; }
    setSaving(true);
    try {
      await api.post('/api/inventario/stock/ajuste', {
        producto_id: ajusteProd.id,
        stock_nuevo: stockNuevo,
        motivo,
        notas: notas.trim() || null,
        referencia: referencia.trim() || null,
      });
      cerrarAjuste();
      await refetch();
      toast.success('Stock ajustado');
    } catch (err) {
      setAjusteErr(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function abrirLotes(p) {
    setLotesProd(p);
    setNuevoLote({ numero_lote: '', fecha_vencimiento: '', cantidad: '', notas: '' });
    setLotesLoading(true);
    try {
      const res = await api.get(`/api/inventario/stock/${p.id}/lotes`);
      setLotes(res.lotes ?? []);
    } catch { setLotes([]); } finally { setLotesLoading(false); }
  }

  async function crearLote() {
    if (!nuevoLote.numero_lote.trim() || !nuevoLote.cantidad) return;
    setSavingLote(true);
    try {
      await api.post(`/api/inventario/stock/${lotesProd.id}/lotes`, {
        numero_lote:       nuevoLote.numero_lote.trim(),
        fecha_vencimiento: nuevoLote.fecha_vencimiento || null,
        cantidad:          parseFloat(nuevoLote.cantidad),
        notas:             nuevoLote.notas || null,
      });
      toast.success('Lote registrado');
      const res = await api.get(`/api/inventario/stock/${lotesProd.id}/lotes`);
      setLotes(res.lotes ?? []);
      setNuevoLote({ numero_lote: '', fecha_vencimiento: '', cantidad: '', notas: '' });
      await refetch();
    } catch (err) { toast.error(err.message); } finally { setSavingLote(false); }
  }

  const diferencia = ajusteProd != null ? parseFloat(sNuevo) - (ajusteProd.stock_actual ?? 0) : 0;
  const difLabel = isNaN(diferencia) ? '' : diferencia === 0 ? 'Sin cambio' : diferencia > 0 ? `+${diferencia}` : `${diferencia}`;
  const difColor = isNaN(diferencia) || diferencia === 0 ? 'var(--ink-400)' : diferencia > 0 ? 'var(--accent)' : 'var(--danger)';

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Almacén</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Almacén & Stock</div>
          <div className="page-sub">
            {stats.total_productos ?? 0} productos · {stats.bajo_minimo ?? 0} bajo mínimo · {stats.negativo ?? 0} negativos
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn${vista === 'inventario' ? ' btn-primary' : ''}`} onClick={() => setVista('inventario')}>Inventario</button>
          <button className={`btn${vista === 'movimientos' ? ' btn-primary' : ''}`} onClick={() => setVista('movimientos')}>Movimientos</button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20,
        border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden' }}>
        {[
          ['Valor inventario', stats.total_valor != null ? MXN.format(stats.total_valor) : '—'],
          ['Bajo mínimo',  stats.bajo_minimo ?? 0],
          ['Stock negativo', stats.negativo ?? 0],
          ['Precio stale >30d', stats.precio_stale ?? 0],
        ].map(([k, v], i, arr) => (
          <div key={k} style={{ flex: 1, padding: '14px 18px',
            borderRight: i < arr.length - 1 ? '1px solid var(--ink-200)' : 'none' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em',
              color: (k === 'Bajo mínimo' || k === 'Stock negativo') && v > 0 ? 'var(--danger)' : 'inherit' }}>
              {v}
            </div>
          </div>
        ))}
      </div>

      {vista === 'inventario' ? (
        <>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
            <input className="input" style={{ maxWidth: 260 }}
              placeholder="Buscar nombre o código…" value={q}
              onChange={(e) => setQ(e.target.value)} />
            <MultiSelectDropdown
              options={categorias.map((c) => ({ label: c, value: c }))}
              values={catFiltro}
              onChange={setCatFiltro}
              placeholder="Categoría…"
            />
            <span className={`chip${bajoMin === '1' ? ' active' : ''}`}
              onClick={() => setBajoMin(bajoMin === '1' ? '' : '1')}>
              ⚠ Bajo mínimo
            </span>
            {['A', 'B', 'C'].map((letra) => (
              <span key={letra}
                className={`chip${abcFiltro.includes(letra) ? ' active' : ''}`}
                style={abcFiltro.includes(letra) ? ABC_STYLE[letra] : {}}
                onClick={() => setAbcFiltro((f) =>
                  f.includes(letra) ? f.filter((x) => x !== letra) : [...f, letra]
                )}>
                ABC {letra}
              </span>
            ))}
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 100 }}>Código</th>
                  <th>Nombre</th>
                  <th style={{ width: 100 }}>Categoría</th>
                  <th style={{ width: 50 }}>U/M</th>
                  <th className="num" style={{ width: 80 }}>Stock</th>
                  <th className="num" style={{ width: 70 }}>Mín.</th>
                  <th className="num" style={{ width: 100 }}>Valor inv.</th>
                  <th className="num" style={{ width: 70 }}>Días inv.</th>
                  <th style={{ width: 40 }}>ABC</th>
                  <th className="num" style={{ width: 70 }} title="Días desde última actualización del precio base">Precio</th>
                  <th style={{ width: 70 }}>Lotes</th>
                  <th style={{ width: 72 }}></th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={11} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
                ) : productos.length === 0 ? (
                  <tr><td colSpan={11} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
                ) : productos
                    .filter((p) => abcFiltro.length === 0 || abcFiltro.includes(p.abc))
                    .map((p) => {
                  const valorInv = (p.stock_actual ?? 0) * (p.costo_prom || p.precio_base || 0);
                  const dias = p.dias_inventario;
                  const diasColor = dias == null ? 'var(--ink-300)'
                    : dias === 0    ? 'var(--danger)'
                    : dias <= 30    ? 'var(--accent)'
                    : dias <= 90    ? 'var(--warn)'
                    : 'var(--danger)';
                  return (
                    <tr key={p.id}>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{p.codigo ?? '—'}</td>
                      <td>{p.nombre}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.categoria ?? '—'}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.unidad_medida}</td>
                      <td className="num"><StockBar actual={p.stock_actual} minimo={p.stock_minimo} /></td>
                      <td className="num" style={{ color: 'var(--ink-400)', fontSize: 11.5 }}>{p.stock_minimo ?? '—'}</td>
                      <td className="num" style={{ fontSize: 11.5 }}>{valorInv > 0 ? MXN.format(valorInv) : '—'}</td>
                      <td className="num" style={{ fontSize: 11.5, fontWeight: dias != null && dias > 90 ? 600 : 400, color: diasColor }}
                          title={dias == null ? 'Sin ventas recientes' : `${dias} días de inventario`}>
                        {dias == null ? '—' : `${dias}d`}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <ABCBadge abc={p.abc} />
                      </td>
                      <td className="num">
                        <PrecioBadge dias={p.precio_base_dias} />
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {p.maneja_lotes ? (
                          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                            onClick={() => abrirLotes(p)}>
                            <LoteBadge alerta={p.lote_alerta ?? 'ok'} count={p.lote_count} />
                          </button>
                        ) : <span style={{ color: 'var(--ink-300)', fontSize: 11 }}>—</span>}
                      </td>
                      <td style={{ textAlign: 'right', paddingRight: 10 }}>
                        <button className="btn" style={{ fontSize: 11, padding: '2px 8px' }}
                          onClick={() => abrirAjuste(p)}>
                          Ajustar
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        /* Movimientos */
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th style={{ width: 70 }}>Tipo</th>
                <th>Motivo</th>
                <th className="num" style={{ width: 80 }}>Cantidad</th>
                <th className="num" style={{ width: 80 }}>Antes</th>
                <th className="num" style={{ width: 80 }}>Después</th>
                <th style={{ width: 120 }}>Referencia</th>
              </tr>
            </thead>
            <tbody>
              {movLoading ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : movs.length === 0 ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin movimientos</td></tr>
              ) : movs.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{m.fecha}</td>
                  <td>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-500)' }}>{m.codigo}</div>
                    <div style={{ fontSize: 12 }}>{m.nombre}</div>
                  </td>
                  <td><TipoBadge tipo={m.tipo} /></td>
                  <td style={{ fontSize: 11.5, color: 'var(--ink-600)' }}>{m.motivo}</td>
                  <td className="num" style={{ fontWeight: 500,
                    color: m.tipo === 'entrada' ? 'var(--accent)' : m.tipo === 'salida' ? 'var(--danger)' : 'var(--ink-600)' }}>
                    {m.tipo === 'entrada' ? '+' : m.tipo === 'salida' ? '-' : '±'}{m.cantidad}
                  </td>
                  <td className="num" style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{m.stock_antes}</td>
                  <td className="num" style={{ fontSize: 11.5,
                    color: (m.stock_despues ?? 0) < 0 ? 'var(--danger)' : 'var(--ink-700)' }}>
                    {m.stock_despues}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--ink-500)' }}>{m.referencia ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)',
            fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between' }}>
            <span>{movs.length} de {movTotal} movimientos</span>
            <span style={{ display: 'flex', gap: 12 }}>
              {movPag > 1 && <a className="linkish" onClick={() => setMovPag(p => p - 1)}>← anterior</a>}
              {movPag < movPags && <a className="linkish" onClick={() => setMovPag(p => p + 1)}>siguiente →</a>}
            </span>
          </div>
        </div>
      )}

      {/* Modal ajuste */}
      <Modal open={!!ajusteProd} onClose={cerrarAjuste} title="Ajuste de stock" width={420}>
        {ajusteProd && (
          <form onSubmit={submitAjuste}>
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)' }}>{ajusteProd.codigo}</div>
              <div style={{ fontWeight: 600 }}>{ajusteProd.nombre}</div>
              <div style={{ fontSize: 12, color: 'var(--ink-500)', marginTop: 2 }}>
                Stock actual: <strong>{ajusteProd.stock_actual ?? 0}</strong> {ajusteProd.unidad_medida}
              </div>
            </div>

            <div className="field" style={{ marginBottom: 14 }}>
              <label className="label">Nuevo stock</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <input className="input" type="number" step="any" style={{ width: 140 }}
                  value={sNuevo} onChange={(e) => setSNuevo(e.target.value)} required />
                {sNuevo !== '' && (
                  <span style={{ fontSize: 13, fontWeight: 600, color: difColor }}>{difLabel}</span>
                )}
              </div>
            </div>

            <div className="field" style={{ marginBottom: 14 }}>
              <label className="label">Motivo</label>
              <select className="input" value={motivo} onChange={(e) => setMotivo(e.target.value)} required>
                {MOTIVOS_AJUSTE.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>

            <div className="field" style={{ marginBottom: 14 }}>
              <label className="label">
                Notas {motivo === 'Otro' ? <span style={{ color: 'var(--danger)' }}>*</span> : <span style={{ color: 'var(--ink-400)', fontSize: 11 }}>(opcional)</span>}
              </label>
              <textarea className="input" rows={2} style={{ resize: 'vertical' }}
                value={notas} onChange={(e) => setNotas(e.target.value)} />
            </div>

            <div className="field" style={{ marginBottom: 20 }}>
              <label className="label">Referencia <span style={{ color: 'var(--ink-400)', fontSize: 11 }}>(opcional)</span></label>
              <input className="input" type="text" placeholder="Folio, documento…"
                value={referencia} onChange={(e) => setReferencia(e.target.value)} />
            </div>

            {ajusteErr && (
              <div style={{ color: 'var(--danger)', fontSize: 12, marginBottom: 12 }}>{ajusteErr}</div>
            )}

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button type="button" className="btn" onClick={cerrarAjuste} disabled={saving}>Cancelar</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Guardando…' : 'Confirmar ajuste'}
              </button>
            </div>
          </form>
        )}
      </Modal>

      {/* Modal lotes */}
      <Modal open={!!lotesProd} onClose={() => setLotesProd(null)}
        title={`Lotes — ${lotesProd?.nombre ?? ''}`} width={540}>
        {lotesProd && (
          <div>
            {lotesLoading ? (
              <div style={{ textAlign: 'center', padding: 24, color: 'var(--ink-400)' }}>Cargando…</div>
            ) : lotes.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 16, color: 'var(--ink-400)', fontSize: 13, marginBottom: 16 }}>Sin lotes registrados</div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ink-200)' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 11, fontWeight: 600, color: 'var(--ink-500)' }}>Lote</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 11, fontWeight: 600, color: 'var(--ink-500)' }}>Vence</th>
                    <th style={{ textAlign: 'right', padding: '6px 8px', fontSize: 11, fontWeight: 600, color: 'var(--ink-500)' }}>Cant.</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', fontSize: 11, fontWeight: 600, color: 'var(--ink-500)' }}>Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {lotes.map((lt) => {
                    const color = lt.alerta === 'vencido' ? '#dc2626' : lt.alerta === 'proximo' ? '#ea580c' : '#16a34a';
                    return (
                      <tr key={lt.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                        <td style={{ padding: '7px 8px', fontFamily: 'var(--mono)', fontSize: 12 }}>{lt.numero_lote}</td>
                        <td style={{ padding: '7px 8px', fontSize: 12 }}>{lt.fecha_vencimiento ?? '—'}</td>
                        <td style={{ padding: '7px 8px', textAlign: 'right', fontSize: 12 }}>{lt.cantidad}</td>
                        <td style={{ padding: '7px 8px' }}>
                          <span style={{ fontSize: 10, padding: '1px 5px', borderRadius: 3, fontWeight: 600,
                            background: color + '20', color }}>
                            {lt.alerta === 'vencido' ? 'Vencido' : lt.alerta === 'proximo' ? 'Próximo' : 'OK'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}

            <div style={{ borderTop: '1px solid var(--ink-200)', paddingTop: 14, marginTop: 4 }}>
              <div className="note" style={{ marginBottom: 10 }}>NUEVO LOTE</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
                <div>
                  <div className="note" style={{ marginBottom: 3 }}>Nº LOTE *</div>
                  <input className="input" value={nuevoLote.numero_lote}
                    onChange={(e) => setNuevoLote((f) => ({ ...f, numero_lote: e.target.value }))} />
                </div>
                <div>
                  <div className="note" style={{ marginBottom: 3 }}>CANTIDAD *</div>
                  <input className="input" type="number" min="0.001" step="0.001"
                    value={nuevoLote.cantidad}
                    onChange={(e) => setNuevoLote((f) => ({ ...f, cantidad: e.target.value }))} />
                </div>
                <div>
                  <div className="note" style={{ marginBottom: 3 }}>FECHA VENCIMIENTO</div>
                  <input className="input" type="date" value={nuevoLote.fecha_vencimiento}
                    onChange={(e) => setNuevoLote((f) => ({ ...f, fecha_vencimiento: e.target.value }))} />
                </div>
                <div>
                  <div className="note" style={{ marginBottom: 3 }}>NOTAS</div>
                  <input className="input" value={nuevoLote.notas}
                    onChange={(e) => setNuevoLote((f) => ({ ...f, notas: e.target.value }))} />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                <button className="btn" onClick={() => setLotesProd(null)}>Cerrar</button>
                <button className="btn btn-primary"
                  disabled={savingLote || !nuevoLote.numero_lote.trim() || !nuevoLote.cantidad}
                  onClick={crearLote}>
                  {savingLote ? 'Guardando…' : 'Agregar lote'}
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
