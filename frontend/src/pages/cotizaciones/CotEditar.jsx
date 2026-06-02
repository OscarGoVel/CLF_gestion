import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';

let _nextId = 1;
const newLine = () => ({
  _id: _nextId++,
  producto_id: null,
  descripcion: '',
  cantidad: 1,
  precio_unitario: '',
  aplica_iva: true,
  no_catalogado: false,
  costo_promedio: null,
  precio_desactualizado: false,
  tiene_historial_compras: false,
  dias_sin_actualizar: null,
});

const MXN = new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function fmt(n) {
  if (!n && n !== 0) return '—';
  return MXN.format(n);
}
function calcImporte(l) {
  const q = parseFloat(l.cantidad) || 0;
  const p = parseFloat(l.precio_unitario) || 0;
  return q * p;
}

const MARGEN_MIN = 0.35;
function calcMargen(precio_unitario, costo_promedio) {
  const p = parseFloat(precio_unitario);
  const c = parseFloat(costo_promedio);
  if (!c || c <= 0 || !p || p <= 0) return null;
  return (p - c) / p;
}

function ProductoSearch({ linea, onSelect, onChange, onQuickAdd }) {
  const [q, setQ] = useState(linea.descripcion);
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounce = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (linea.no_catalogado) return;
    clearTimeout(debounce.current);
    if (q.length < 2) { setResults([]); setSearched(false); return; }
    debounce.current = setTimeout(async () => {
      try {
        const data = await api.get(`/api/comercial/cotizaciones/buscar-producto?q=${encodeURIComponent(q)}`);
        setResults(data.resultados ?? []);
        setSearched(true);
        setOpen(true);
      } catch { setResults([]); }
    }, 300);
    return () => clearTimeout(debounce.current);
  }, [q, linea.no_catalogado]);

  useEffect(() => {
    function handleClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (linea.no_catalogado) {
    return (
      <input
        value={linea.descripcion}
        onChange={(e) => onChange('descripcion', e.target.value)}
        placeholder="Descripción libre…"
        style={{ fontStyle: 'italic', flex: 1, minWidth: 0 }}
      />
    );
  }

  const noResults = searched && results.length === 0 && q.length >= 2;

  return (
    <div ref={wrapRef} style={{ position: 'relative', flex: 1 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); onChange('descripcion', e.target.value); }}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Buscar producto…"
        style={{ width: '100%', borderColor: noResults ? 'var(--warn)' : undefined }}
      />
      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          background: '#fff', border: '1px solid var(--ink-200)', borderRadius: 4,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: 240, overflowY: 'auto',
        }}>
          {results.map((p) => (
            <div key={p.id}
              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--ink-100)', fontSize: 13 }}
              onMouseDown={() => { onSelect(p); setQ(p.nombre); setOpen(false); }}
            >
              <div style={{ fontWeight: 500 }}>{p.nombre}</div>
              <div style={{ fontSize: 11, color: 'var(--ink-500)', fontFamily: 'var(--mono)' }}>
                {p.codigo ?? ''}{p.precio ? ` · ${fmt(p.precio)}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}
      {noResults && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
          <span style={{ fontSize: 11.5, color: 'var(--ink-400)' }}>Sin resultados.</span>
          {onQuickAdd && (
            <button
              type="button"
              className="btn btn-sm"
              style={{ fontSize: 11.5, padding: '2px 8px', color: 'var(--accent)', borderColor: 'var(--accent)' }}
              onMouseDown={(e) => { e.preventDefault(); onQuickAdd(q); }}
            >
              + Crear en catálogo
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function QuickAddModal({ nombre: nombreInicial, onConfirm, onClose }) {
  const [nombre, setNombre] = useState(nombreInicial);
  const [codigo, setCodigo] = useState('');
  const [categoriaId, setCategoriaId] = useState('');
  const [subcategoriaId, setSubcategoriaId] = useState('');
  const [precio, setPrecio] = useState('');
  const [iva, setIva] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [cats, setCats] = useState([]);
  const [subcats, setSubcats] = useState([]);

  useEffect(() => {
    api.get('/api/catalogos/categorias').then(d => {
      setCats(d.categorias ?? []);
      setSubcats(d.subcategorias ?? []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!categoriaId) return;
    const qs = subcategoriaId
      ? `?categoria_id=${categoriaId}&subcategoria_id=${subcategoriaId}`
      : `?categoria_id=${categoriaId}`;
    api.get(`/api/catalogos/generar-sku${qs}`).then(d => {
      if (d.sku) setCodigo(d.sku);
    }).catch(() => {});
  }, [categoriaId, subcategoriaId]);

  function handleCategoriaChange(e) {
    setCategoriaId(e.target.value);
    setSubcategoriaId('');
    setCodigo('');
  }

  const filteredSubcats = subcats.filter(s => String(s.categoria_id) === String(categoriaId));

  async function handleSave() {
    if (!nombre.trim()) { setErr('El nombre es requerido'); return; }
    setSaving(true);
    setErr('');
    try {
      const p = await api.post('/api/catalogos/productos/rapido', {
        nombre: nombre.trim(),
        codigo: codigo.trim() || null,
        precio_base: parseFloat(precio) || 0,
        aplica_iva: iva,
        categoria_id: categoriaId ? parseInt(categoriaId) : null,
        subcategoria_id: subcategoriaId ? parseInt(subcategoriaId) : null,
      });
      onConfirm(p);
    } catch (e) {
      setErr(e.message ?? 'Error al crear');
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 300,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ background: '#fff', borderRadius: 8, width: 420, boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--ink-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h3 style={{ margin: 0, fontSize: 15 }}>Agregar al catálogo</h3>
          <span style={{ cursor: 'pointer', fontSize: 20, color: 'var(--ink-400)', lineHeight: 1 }} onClick={onClose}>×</span>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label className="label">Nombre *</label>
            <input className="input" value={nombre} onChange={(e) => setNombre(e.target.value)} autoFocus />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Categoría</label>
              <select className="input" value={categoriaId} onChange={handleCategoriaChange}>
                <option value="">— Sin categoría —</option>
                {cats.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Subcategoría</label>
              <select className="input" value={subcategoriaId} onChange={(e) => setSubcategoriaId(e.target.value)}
                disabled={!categoriaId || filteredSubcats.length === 0}>
                <option value="">— Ninguna —</option>
                {filteredSubcats.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label className="label">Código</label>
              <input className="input" value={codigo} onChange={(e) => setCodigo(e.target.value)}
                placeholder={categoriaId ? 'Auto-generado' : 'Selecciona categoría'} />
            </div>
            <div>
              <label className="label">Precio base ($)</label>
              <input className="input" type="number" min="0" value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="0.00" />
            </div>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
            <input type="checkbox" checked={iva} onChange={(e) => setIva(e.target.checked)} />
            Aplica IVA (16%)
          </label>
          {err && <div style={{ fontSize: 12, color: 'var(--danger)' }}>{err}</div>}
        </div>
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--ink-100)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? 'Creando…' : 'Crear y agregar'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function CotEditar() {
  const { id } = useParams();
  const navigate = useNavigate();

  const { data: cotData, loading: loadingCot, refetch: refetchCot } = useFetch(`/api/comercial/cotizaciones/${id}`);
  const { data: clientesData } = useFetch('/api/catalogos/clientes');
  const clientes = clientesData?.clientes ?? [];

  const [initialized, setInitialized] = useState(false);
  const [lineas, setLineas] = useState([]);
  const [clienteId, setClienteId] = useState('');
  const [fecha, setFecha] = useState('');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [quickAdd, setQuickAdd] = useState(null);
  const [draggingId, setDraggingId] = useState(null);
  const [dragOverId, setDragOverId] = useState(null);
  const dragItemRef = useRef(null);
  const [estudios, setEstudios] = useState([]);
  const [modalAplicar, setModalAplicar] = useState(null);
  const [studyDetail, setStudyDetail] = useState(null);
  const [loadingStudy, setLoadingStudy] = useState(false);
  const [sinCatalogoItems, setSinCatalogoItems] = useState([]);
  const [applyingEstudio, setApplyingEstudio] = useState(false);

  useEffect(() => {
    if (!cotData || initialized) return;
    const cot = cotData.cotizacion;
    const partidas = cotData.partidas ?? [];
    setClienteId(String(cot.cliente_id ?? ''));
    setFecha(cot.fecha ?? '');
    setNotas(cot.notas ?? '');
    setLineas(partidas.map((p) => ({
      _id: _nextId++,
      producto_id: p.producto_id ?? null,
      descripcion: p.nombre || p.descripcion_libre || '',
      cantidad: p.cantidad,
      precio_unitario: p.precio_unitario ?? '',
      aplica_iva: Boolean(p.aplica_iva),
      no_catalogado: !p.producto_id || Boolean(p.pendiente_catalogo),
      costo_promedio: null,
      precio_desactualizado: false,
      tiene_historial_compras: false,
      dias_sin_actualizar: null,
      proveedor_nombre: p.proveedor_nombre ?? null,
    })));
    setEstudios(cotData.estudios ?? []);
    setInitialized(true);
  }, [cotData, initialized]);

  const subtotal = lineas.reduce((s, l) => s + calcImporte(l), 0);
  const ivaTotal = lineas.reduce((s, l) => {
    const imp = calcImporte(l);
    return s + (l.aplica_iva ? imp * 0.16 : 0);
  }, 0);
  const total = subtotal + ivaTotal;

  const updateLinea = useCallback((id, field, value) => {
    setLineas((ls) => ls.map((l) => l._id === id ? { ...l, [field]: value } : l));
  }, []);

  const selectProducto = useCallback((id, producto) => {
    setLineas((ls) => ls.map((l) => l._id === id ? {
      ...l,
      producto_id: producto.id,
      descripcion: producto.nombre,
      precio_unitario: producto.precio ?? '',
      aplica_iva: producto.aplica_iva ?? true,
      no_catalogado: false,
      costo_promedio: producto.costo_promedio ?? null,
      precio_desactualizado: producto.precio_desactualizado ?? false,
      tiene_historial_compras: producto.tiene_historial_compras ?? false,
      dias_sin_actualizar: producto.dias_sin_actualizar ?? null,
    } : l));
  }, []);

  const removeLinea = useCallback((id) => {
    setLineas((ls) => ls.filter((l) => l._id !== id));
  }, []);

  const handleDragStart = useCallback((id, e) => {
    dragItemRef.current = id;
    setDraggingId(id);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(id));
  }, []);

  const handleDragOver = useCallback((id, e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragItemRef.current !== null && dragItemRef.current !== id) setDragOverId(id);
  }, []);

  const handleDragLeave = useCallback((e) => {
    if (!e.currentTarget.contains(e.relatedTarget)) setDragOverId(null);
  }, []);

  const handleDrop = useCallback((id, e) => {
    e.preventDefault();
    if (dragItemRef.current === null || dragItemRef.current === id) {
      setDragOverId(null);
      return;
    }
    setLineas(ls => {
      const arr = [...ls];
      const fromIdx = arr.findIndex(l => l._id === dragItemRef.current);
      const toIdx = arr.findIndex(l => l._id === id);
      const [moved] = arr.splice(fromIdx, 1);
      arr.splice(toIdx, 0, moved);
      return arr;
    });
    dragItemRef.current = null;
    setDraggingId(null);
    setDragOverId(null);
  }, []);

  const handleDragEnd = useCallback(() => {
    dragItemRef.current = null;
    setDraggingId(null);
    setDragOverId(null);
  }, []);

  const noCatalogadas = lineas.filter((l) => l.no_catalogado).length;
  const folio = cotData?.cotizacion?.folio ?? '';
  const estudiosAplicables = estudios.filter((e) => e.tiene_ganadores_aplicables);

  async function openAplicarEstudio(estudio) {
    setLoadingStudy(true);
    setModalAplicar(estudio);
    try {
      const data = await api.get(`/api/abastecimiento/estudios/${estudio.id}`);
      setStudyDetail(data);
    } catch {
      toast.error('No se pudo cargar el estudio');
      setModalAplicar(null);
    } finally {
      setLoadingStudy(false);
    }
  }

  async function handleAplicarConfirm() {
    if (!modalAplicar) return;
    setApplyingEstudio(true);
    try {
      const res = await api.post(`/api/abastecimiento/estudios/${modalAplicar.id}/actualizar-lineas`);
      setModalAplicar(null);
      setStudyDetail(null);
      toast.success(`${res.actualizados} línea(s) actualizada(s)`);
      if (res.sin_catalogo?.length > 0) {
        setSinCatalogoItems(res.sin_catalogo.map((i) => ({ ...i, accion: 'libre' })));
      } else {
        setInitialized(false);
        refetchCot();
      }
    } catch (e) {
      toast.error(e.message ?? 'Error al aplicar estudio');
    } finally {
      setApplyingEstudio(false);
    }
  }

  async function handleSinCatalogoItem(itemId, accion) {
    setSinCatalogoItems((prev) => prev.map((i) => i.item_id === itemId ? { ...i, accion } : i));
  }

  async function handleSinCatalogoConfirm() {
    const crear = sinCatalogoItems.filter((i) => i.accion === 'crear');
    await Promise.all(crear.map((i) =>
      api.patch(`/api/abastecimiento/estudios/items/${i.item_id}/vincular-producto`, { crear: true })
        .catch(() => {})
    ));
    setSinCatalogoItems([]);
    setInitialized(false);
    refetchCot();
  }

  async function handleGuardar() {
    if (!clienteId) { setError('Selecciona un cliente'); return; }
    if (lineas.length === 0) { setError('Agrega al menos una partida'); return; }
    setSaving(true);
    setError('');
    try {
      const payload = {
        cliente_id: parseInt(clienteId),
        fecha,
        notas: notas || null,
        utilidad_pct: 0,
        partidas: lineas.map((l) => ({
          producto_id: l.no_catalogado ? null : (l.producto_id ?? null),
          descripcion_libre: (l.no_catalogado || !l.producto_id) ? l.descripcion : null,
          cantidad: parseFloat(l.cantidad) || 1,
          precio_unitario: parseFloat(l.precio_unitario) || 0,
          aplica_iva: l.aplica_iva,
        })),
      };
      await api.put(`/api/comercial/cotizaciones/${id}`, payload);
      toast.success('Cotización actualizada');
      navigate(`/comercial/cotizaciones/${id}`);
    } catch (e) {
      setError(e.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  if (loadingCot) {
    return <div className="page"><div className="page-state">Cargando…</div></div>;
  }

  const handleQuickAddConfirm = (producto) => {
    selectProducto(quickAdd.lineaId, producto);
    setQuickAdd(null);
    toast.success(`"${producto.nombre}" agregado al catálogo`);
  };

  return (
    <div className="page">
      {quickAdd && (
        <QuickAddModal
          nombre={quickAdd.nombre}
          onClose={() => setQuickAdd(null)}
          onConfirm={handleQuickAddConfirm}
        />
      )}

      {/* Modal: aplicar estudio de mercado */}
      {modalAplicar && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', borderRadius: 8, width: 620, maxHeight: '80vh', display: 'flex', flexDirection: 'column', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--ink-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>Aplicar resultados: {modalAplicar.nombre}</h3>
              <span style={{ cursor: 'pointer', fontSize: 20, color: 'var(--ink-400)', lineHeight: 1 }} onClick={() => { setModalAplicar(null); setStudyDetail(null); }}>×</span>
            </div>
            <div style={{ overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
              {loadingStudy ? (
                <div style={{ textAlign: 'center', color: 'var(--ink-400)', padding: 24 }}>Cargando estudio…</div>
              ) : studyDetail ? (() => {
                const ganadores = (studyDetail.items ?? []).filter((i) => i.ganador_proveedor);
                if (ganadores.length === 0) return <div style={{ color: 'var(--ink-400)' }}>No hay ganadores marcados en este estudio.</div>;
                return (
                  <>
                    <p style={{ fontSize: 12.5, color: 'var(--ink-500)', marginBottom: 12 }}>
                      Las siguientes líneas serán actualizadas con la descripción y precio del proveedor ganador.
                    </p>
                    <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ background: 'var(--ink-50)', textAlign: 'left' }}>
                          <th style={{ padding: '6px 8px', fontWeight: 600 }}>Artículo solicitado</th>
                          <th style={{ padding: '6px 8px', fontWeight: 600 }}>Descripción ganador</th>
                          <th style={{ padding: '6px 8px', fontWeight: 600 }}>Proveedor</th>
                          <th style={{ padding: '6px 8px', fontWeight: 600, textAlign: 'right' }}>Precio</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ganadores.map((item) => {
                          const cot = (item.cotizaciones ?? []).find((c) => c.ganador);
                          const margen = studyDetail.estudio?.margen_pct ?? 0.35;
                          const precio = cot ? cot.precio_unitario * (1 + margen) : null;
                          const descGanador = cot?.descripcion_articulo || item.nombre_articulo;
                          return (
                            <tr key={item.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                              <td style={{ padding: '6px 8px', color: 'var(--ink-500)' }}>{item.nombre_articulo}</td>
                              <td style={{ padding: '6px 8px', fontWeight: 500 }}>{descGanador}</td>
                              <td style={{ padding: '6px 8px' }}>{item.ganador_proveedor ?? '—'}</td>
                              <td style={{ padding: '6px 8px', textAlign: 'right', fontFamily: 'var(--mono)' }}>
                                {precio ? `$${precio.toFixed(2)}` : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </>
                );
              })() : null}
            </div>
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--ink-100)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button className="btn" onClick={() => { setModalAplicar(null); setStudyDetail(null); }}>Cancelar</button>
              <button className="btn btn-primary" onClick={handleAplicarConfirm} disabled={applyingEstudio || loadingStudy}>
                {applyingEstudio ? 'Aplicando…' : 'Aplicar'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: artículos sin catálogo */}
      {sinCatalogoItems.length > 0 && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 310, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', borderRadius: 8, width: 520, boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--ink-100)' }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>Artículos sin catálogo</h3>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--ink-500)' }}>
                Estos artículos no se encontraron en el catálogo. ¿Qué deseas hacer con cada uno?
              </p>
            </div>
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {sinCatalogoItems.map((item) => (
                <div key={item.item_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '8px 10px', background: 'var(--ink-50)', borderRadius: 6 }}>
                  <span style={{ fontSize: 12.5, flex: 1 }}>{item.descripcion}</span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      className="btn btn-sm"
                      style={item.accion === 'crear' ? { background: 'var(--accent)', color: '#fff', borderColor: 'var(--accent)' } : {}}
                      onClick={() => handleSinCatalogoItem(item.item_id, 'crear')}
                    >
                      Crear en catálogo
                    </button>
                    <button
                      className="btn btn-sm"
                      style={item.accion === 'libre' ? { background: 'var(--ink-200)' } : {}}
                      onClick={() => handleSinCatalogoItem(item.item_id, 'libre')}
                    >
                      Texto libre
                    </button>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ padding: '12px 20px', borderTop: '1px solid var(--ink-100)', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" onClick={handleSinCatalogoConfirm}>Confirmar</button>
            </div>
          </div>
        </div>
      )}
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <a onClick={() => navigate(`/comercial/cotizaciones/${id}`)}>{folio}</a>
        <span className="sep">/</span>
        <span>Editar</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Editar cotización</div>
          <div className="page-sub" style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{folio}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {estudiosAplicables.length > 0 && (
            <button
              className="btn"
              style={{ color: 'var(--accent)', borderColor: 'var(--accent)' }}
              onClick={() => openAplicarEstudio(estudiosAplicables[0])}
            >
              Aplicar estudio de mercado →
            </button>
          )}
          <button className="btn" onClick={() => navigate(`/comercial/cotizaciones/${id}`)}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleGuardar} disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar cambios'}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert-warn" style={{ marginBottom: 16 }}>
          <strong>{error}</strong>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20 }}>
        <div>
          {/* 1 · Cliente */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h"><h3>1 · Cliente</h3></div>
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
              <div>
                <label className="label">Cliente *</label>
                <select
                  className="select"
                  value={clienteId}
                  onChange={(e) => setClienteId(e.target.value)}
                  style={{ borderColor: !clienteId ? 'var(--warn)' : undefined }}
                >
                  <option value="">— Seleccionar —</option>
                  {clientes.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre_comercial}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Fecha</label>
                <input className="input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
              </div>
            </div>
          </div>

          {/* 2 · Partidas */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h">
              <h3>2 · Partidas</h3>
              <div style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>
                Busca en catálogo o crea un producto nuevo.
              </div>
            </div>
            <div className="qb-line" style={{ background: 'var(--ink-50)', fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span></span>
              <span>Producto</span>
              <span style={{ textAlign: 'right' }}>Cant.</span>
              <span style={{ textAlign: 'right' }}>Precio unit.</span>
              <span style={{ textAlign: 'center' }}>IVA</span>
              <span style={{ textAlign: 'right' }}>Importe</span>
              <span></span>
            </div>

            {lineas.map((l) => (
              <div
                key={l._id}
                onDragOver={(e) => handleDragOver(l._id, e)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(l._id, e)}
                style={{
                  opacity: draggingId === l._id ? 0.4 : 1,
                  outline: dragOverId === l._id ? '2px solid var(--accent)' : undefined,
                  borderRadius: dragOverId === l._id ? 3 : undefined,
                  transition: 'opacity 0.15s',
                }}
              >
                <div className={`qb-line${l.no_catalogado ? ' flag' : ''}`}>
                  <span
                    className="grip"
                    draggable
                    onDragStart={(e) => handleDragStart(l._id, e)}
                    onDragEnd={handleDragEnd}
                    style={{ cursor: 'grab' }}
                  >⠿⠿</span>
                  <span style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <ProductoSearch
                        linea={l}
                        onSelect={(p) => selectProducto(l._id, p)}
                        onChange={(field, val) => updateLinea(l._id, field, val)}
                        onQuickAdd={(nombre) => setQuickAdd({ lineaId: l._id, nombre })}
                      />
                      {l.no_catalogado && <span className="qb-tag">Libre</span>}
                      {l.no_catalogado && (
                        <button
                          type="button"
                          className="btn btn-sm"
                          style={{ fontSize: 11, padding: '1px 7px', color: 'var(--accent)', borderColor: 'var(--accent)', whiteSpace: 'nowrap' }}
                          onClick={() => setQuickAdd({ lineaId: l._id, nombre: l.descripcion })}
                        >
                          + Catálogo
                        </button>
                      )}
                    </span>
                    {l.proveedor_nombre && (
                      <span style={{ fontSize: 10, color: 'var(--ink-400)', paddingLeft: 2 }}>
                        Proveedor: {l.proveedor_nombre}
                      </span>
                    )}
                  </span>
                  <input
                    className="num"
                    type="number"
                    min="0"
                    value={l.cantidad}
                    onChange={(e) => updateLinea(l._id, 'cantidad', e.target.value)}
                    style={{ width: 60 }}
                  />
                  <input
                    className="num"
                    type="number"
                    min="0"
                    value={l.precio_unitario}
                    onChange={(e) => updateLinea(l._id, 'precio_unitario', e.target.value)}
                    placeholder="0.00"
                    style={{ width: 90 }}
                  />
                  <input
                    type="checkbox"
                    checked={l.aplica_iva}
                    onChange={(e) => updateLinea(l._id, 'aplica_iva', e.target.checked)}
                    style={{ justifySelf: 'center' }}
                    title="Aplica IVA"
                  />
                  <span className="num" style={{ fontWeight: 500 }}>
                    {calcImporte(l) > 0 ? fmt(calcImporte(l)) : '—'}
                  </span>
                  <span
                    style={{ color: 'var(--ink-300)', cursor: 'pointer', textAlign: 'center' }}
                    onClick={() => removeLinea(l._id)}
                  >
                    ×
                  </span>
                </div>
                {!l.no_catalogado && l.producto_id && (() => {
                  const margen = calcMargen(l.precio_unitario, l.costo_promedio);
                  const diasSin = l.dias_sin_actualizar;
                  const sinHistorial = !l.tiene_historial_compras;
                  return (
                    <div style={{ padding: '1px 12px 4px 36px', display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      {margen !== null && (
                        <span style={{ fontSize: 10.5, fontFamily: 'var(--mono)',
                          color: margen < 0 ? '#c0392b' : margen >= MARGEN_MIN ? '#27ae60' : '#e67e22' }}>
                          Costo prom: ${parseFloat(l.costo_promedio).toFixed(2)}
                          {' | Margen: '}{(margen * 100).toFixed(1)}%
                          {margen < 0 && ' ⚠ NEGATIVO'}
                        </span>
                      )}
                      {l.precio_desactualizado && (
                        <span style={{ fontSize: 10, background: '#fff3cd', color: '#856404',
                                       padding: '1px 6px', borderRadius: 3, border: '1px solid #ffc107' }}>
                          ⚠ costo reciente supera margen — actualizar precio
                        </span>
                      )}
                      {sinHistorial && !l.precio_desactualizado && (
                        <span style={{ fontSize: 10, background: '#f0f0f0', color: '#555',
                                       padding: '1px 6px', borderRadius: 3, border: '1px solid #ddd' }}>
                          {diasSin === null
                            ? 'ℹ precio de catálogo — sin fecha de referencia'
                            : diasSin > 90
                              ? `ℹ precio de catálogo — ${diasSin} días sin actualizar`
                              : 'precio de catálogo'}
                        </span>
                      )}
                      {!sinHistorial && diasSin !== null && diasSin > 90 && !l.precio_desactualizado && (
                        <span style={{ fontSize: 10, background: '#fff7ed', color: '#92400e',
                                       padding: '1px 6px', borderRadius: 3, border: '1px solid #fed7aa' }}>
                          ⚠ {diasSin} días sin nueva compra registrada
                        </span>
                      )}
                    </div>
                  );
                })()}
              </div>
            ))}

            {noCatalogadas > 0 && (
              <div style={{ padding: '8px 12px', background: '#fffbf2', borderTop: '1px solid #f5e6c0', fontSize: 11.5, color: 'var(--warn)' }}>
                <strong>{noCatalogadas} línea(s) libre(s)</strong> — se guardarán con descripción manual.
              </div>
            )}

            <div style={{ padding: '10px 12px', display: 'flex', gap: 6, borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn btn-sm" onClick={() => setLineas((ls) => [...ls, newLine()])}>
                + Agregar partida
              </button>
            </div>
          </div>

          {/* 3 · Notas */}
          <div className="card">
            <div className="card-h"><h3>3 · Notas</h3></div>
            <div style={{ padding: 16 }}>
              <label className="label">Notas (PDF)</label>
              <input className="input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Precio sujeto a cambio…" />
            </div>
          </div>
        </div>

        {/* Sidebar resumen */}
        <div>
          <div className="eyebrow">Resumen</div>
          <div className="card" style={{ padding: 16, marginBottom: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, padding: '4px 0' }}>
              <span>Subtotal</span><span className="num">{fmt(subtotal)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, padding: '4px 0' }}>
              <span>IVA</span><span className="num">{fmt(ivaTotal)}</span>
            </div>
            <div className="rule"></div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
              <span style={{ fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Total MXN
              </span>
              <span style={{ fontFamily: 'var(--serif)', fontSize: 24, letterSpacing: '-0.02em', fontVariantNumeric: 'tabular-nums' }}>
                {fmt(total)}
              </span>
            </div>
          </div>

          <div className="eyebrow">Validaciones</div>
          <div style={{ fontSize: 11.5 }}>
            <div style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-100)', color: clienteId ? 'var(--ink-700)' : 'var(--warn)' }}>
              {clienteId ? '✓ Cliente seleccionado' : '! Cliente requerido'}
            </div>
            <div style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-100)', color: lineas.length > 0 ? 'var(--ink-700)' : 'var(--warn)' }}>
              {lineas.length > 0 ? `✓ ${lineas.length} partida(s)` : '! Sin partidas'}
            </div>
            {noCatalogadas > 0 && (
              <div style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-100)', color: 'var(--warn)' }}>
                ! {noCatalogadas} línea(s) libre(s)
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
