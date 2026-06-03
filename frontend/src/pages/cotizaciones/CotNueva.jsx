import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

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
      } catch (err) { console.error('[CotNueva] buscar producto:', err); setResults([]); }
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
      <div style={{
        background: '#fff', borderRadius: 8, width: 420,
        boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
      }}>
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

export default function CotNueva() {
  const navigate = useNavigate();
  const { activeRS } = useRazonSocial();
  const [lineas, setLineas] = useState([newLine()]);
  const [clienteId, setClienteId] = useState('');
  const [comprador, setComprador] = useState('');
  const [vigencia, setVigencia] = useState('30 días');
  const [lugarEntrega, setLugarEntrega] = useState('');
  const [tiempoEntrega, setTiempoEntrega] = useState('');
  const [anticipo, setAnticipo] = useState('');
  const [notas, setNotas] = useState('');
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [quickAdd, setQuickAdd] = useState(null); // { lineaId, nombre }
  const [importModal, setImportModal] = useState(null); // { matched, unmatched, mappings }
  const [importError, setImportError] = useState('');
  const [draggingId, setDraggingId] = useState(null);
  const [dragOverId, setDragOverId] = useState(null);
  const dragItemRef = useRef(null);
  const fileRef = useRef(null);

  const { data: clientesData } = useFetch('/api/catalogos/clientes');
  const clientes = clientesData?.clientes ?? [];

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

  const utilidadPct = total > 0
    ? parseFloat(((total - lineas.reduce((s, l) => {
        const q = parseFloat(l.cantidad) || 0;
        return s + q * 0;
      }, 0)) / total * 100).toFixed(1))
    : 0;

  async function handleGuardar(estado = 'Borrador') {
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
        razon_social_id: activeRS ?? null,
        partidas: lineas.map((l) => ({
          producto_id: l.no_catalogado ? null : (l.producto_id ?? null),
          descripcion_libre: (l.no_catalogado || !l.producto_id) ? l.descripcion : null,
          cantidad: parseFloat(l.cantidad) || 1,
          precio_unitario: parseFloat(l.precio_unitario) || 0,
          aplica_iva: l.aplica_iva,
        })),
      };
      const res = await api.post('/api/comercial/cotizaciones', payload);
      toast.success('Cotización creada');
      navigate(`/comercial/cotizaciones/${res.id}`);
    } catch (e) {
      setError(e.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  const noCatalogadas = lineas.filter((l) => l.no_catalogado).length;

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setImportError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await api.upload('/api/comercial/cotizaciones/importar-plantilla', formData);
      const mappings = {};
      (data.unmatched ?? []).forEach((_, idx) => { mappings[idx] = null; });
      setImportModal({ matched: data.matched ?? [], unmatched: data.unmatched ?? [], mappings, matchedOverrides: {} });
    } catch (err) {
      setImportError(err.message ?? 'Error al procesar el archivo.');
    }
  };

  const setMapping = (idx, value) => {
    setImportModal((m) => ({ ...m, mappings: { ...m.mappings, [idx]: value } }));
  };

  const setMatchedOverride = (idx, value) => {
    setImportModal((m) => ({ ...m, matchedOverrides: { ...m.matchedOverrides, [idx]: value } }));
  };

  const handleConfirmImport = () => {
    const { matched, unmatched, mappings, matchedOverrides = {} } = importModal;
    const nuevas = [];
    for (let i = 0; i < matched.length; i++) {
      const m = matched[i];
      const ov = matchedOverrides[i];
      if (ov?.tipo === 'catalogo') {
        nuevas.push({ _id: _nextId++, producto_id: ov.producto_id, descripcion: ov.nombre, cantidad: m.cantidad, precio_unitario: ov.precio ?? '', aplica_iva: ov.aplica_iva ?? true, no_catalogado: false });
      } else if (ov?.tipo === 'libre') {
        nuevas.push({ _id: _nextId++, producto_id: null, descripcion: m.descripcion_csv, cantidad: m.cantidad, precio_unitario: '', aplica_iva: true, no_catalogado: true });
      } else {
        nuevas.push({ _id: _nextId++, producto_id: m.producto_id, descripcion: m.nombre_catalogo, cantidad: m.cantidad, precio_unitario: m.precio ?? '', aplica_iva: m.aplica_iva ?? true, no_catalogado: false });
      }
    }
    for (let idx = 0; idx < unmatched.length; idx++) {
      const u = unmatched[idx];
      const mp = mappings[idx];
      if (!mp) continue;
      if (mp.tipo === 'catalogo') {
        nuevas.push({ _id: _nextId++, producto_id: mp.producto_id, descripcion: mp.nombre, cantidad: u.cantidad, precio_unitario: mp.precio ?? '', aplica_iva: mp.aplica_iva ?? true, no_catalogado: false });
      } else {
        nuevas.push({ _id: _nextId++, producto_id: null, descripcion: u.descripcion_csv, cantidad: u.cantidad, precio_unitario: '', aplica_iva: true, no_catalogado: true });
      }
    }
    setLineas((ls) => [...ls, ...nuevas]);
    setImportModal(null);
  };

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <span>Nueva</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Nueva cotización</div>
          <div className="page-sub">Fecha: {fecha}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/comercial/cotizaciones')}>Cancelar</button>
          <button className="btn btn-primary" onClick={() => handleGuardar('Pendiente')} disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar'}
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
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
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
                <label className="label">Comprador</label>
                <input className="input" value={comprador} onChange={(e) => setComprador(e.target.value)} />
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
                Busca en catálogo. Si no existe, usa línea libre.
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
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
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

            <div style={{ padding: '10px 12px', display: 'flex', gap: 6, flexWrap: 'wrap', borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn btn-sm" onClick={() => setLineas((ls) => [...ls, newLine()])}>
                + Agregar partida
              </button>
<a href="/api/comercial/cotizaciones/plantilla-import"
                 onClick={(e) => {
                   e.preventDefault();
                   const token = sessionStorage.getItem('clf_token');
                   fetch('/api/comercial/cotizaciones/plantilla-import', { headers: { Authorization: `Bearer ${token}` } })
                     .then(r => r.blob()).then(blob => {
                       const a = document.createElement('a');
                       a.href = URL.createObjectURL(blob);
                       a.download = 'plantilla_cotizacion.csv';
                       a.click();
                     });
                 }}
                 className="btn btn-sm" style={{ marginLeft: 'auto' }}>
                ⬇ Plantilla
              </a>
              <input ref={fileRef} type="file" accept=".csv" style={{ display: 'none' }}
                     onChange={handleImportFile} />
              <button className="btn btn-sm" onClick={() => fileRef.current?.click()}>
                ⬆ Importar CSV
              </button>
            </div>
            {importError && (
              <div style={{ padding: '8px 12px', background: '#fff5f5', borderTop: '1px solid #fecaca', fontSize: 11.5, color: 'var(--danger)' }}>
                {importError}
              </div>
            )}
          </div>

          {/* 3 · Condiciones */}
          <div className="card">
            <div className="card-h"><h3>3 · Condiciones</h3></div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, padding: 16 }}>
              <div>
                <label className="label">Vigencia</label>
                <select className="select" value={vigencia} onChange={(e) => setVigencia(e.target.value)}>
                  <option>15 días</option>
                  <option>30 días</option>
                  <option>60 días</option>
                </select>
              </div>
              <div>
                <label className="label">Lugar entrega</label>
                <input className="input" value={lugarEntrega} onChange={(e) => setLugarEntrega(e.target.value)} />
              </div>
              <div>
                <label className="label">Tiempo entrega</label>
                <input className="input" value={tiempoEntrega} onChange={(e) => setTiempoEntrega(e.target.value)} placeholder="15 días desde anticipo" />
              </div>
              <div>
                <label className="label">Anticipo</label>
                <input className="input" value={anticipo} onChange={(e) => setAnticipo(e.target.value)} placeholder="60%" />
              </div>
              <div>
                <label className="label">Moneda</label>
                <select className="select"><option>MXN</option><option>USD</option></select>
              </div>
              <div>
                <label className="label">Notas (PDF)</label>
                <input className="input" value={notas} onChange={(e) => setNotas(e.target.value)} placeholder="Precio sujeto a cambio…" />
              </div>
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

      {/* Modal quick-add al catálogo */}
      {quickAdd && (
        <QuickAddModal
          nombre={quickAdd.nombre}
          onClose={() => setQuickAdd(null)}
          onConfirm={(producto) => {
            selectProducto(quickAdd.lineaId, producto);
            setQuickAdd(null);
            toast.success(`"${producto.nombre}" agregado al catálogo`);
          }}
        />
      )}

      {/* Modal de revisión de importación CSV */}
      {importModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: '#fff', borderRadius: 8, width: 660, maxHeight: '82vh',
            display: 'flex', flexDirection: 'column', boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
          }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--ink-100)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0 }}>Revisar importación</h3>
              <span style={{ cursor: 'pointer', fontSize: 20, color: 'var(--ink-400)', lineHeight: 1 }}
                    onClick={() => setImportModal(null)}>×</span>
            </div>

            <div style={{ overflowY: 'auto', flex: 1, padding: '16px 20px' }}>
              {importModal.matched.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <div className="eyebrow" style={{ marginBottom: 8 }}>
                    Encontrados ({importModal.matched.length})
                  </div>
                  {importModal.matched.map((m, i) => {
                    const ov = (importModal.matchedOverrides ?? {})[i];
                    const score = m.score;
                    const [scoreBg, scoreColor] = score === undefined ? ['#f3f4f6', '#6b7280']
                      : score >= 0.75 ? ['#dcfce7', '#16a34a']
                      : score >= 0.45 ? ['#fef9c3', '#ca8a04']
                      : ['#ffedd5', '#ea580c'];
                    if (ov === null) {
                      return (
                        <div key={i} style={{ padding: '10px 12px', borderBottom: '1px solid var(--ink-100)', background: '#fffbf2' }}>
                          <div style={{ fontSize: 11, color: 'var(--ink-500)', marginBottom: 6 }}>
                            CSV: <strong>{m.descripcion_csv}</strong>
                          </div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <div style={{ flex: 1 }}>
                              <ProductoSearch
                                linea={{ _id: `match-ovr-${i}`, no_catalogado: false, descripcion: m.descripcion_csv }}
                                onSelect={(p) => setMatchedOverride(i, { tipo: 'catalogo', producto_id: p.id, nombre: p.nombre, precio: p.precio, aplica_iva: p.aplica_iva ?? true })}
                                onChange={() => {}}
                              />
                            </div>
                            <button className="btn btn-sm" onClick={() => setMatchedOverride(i, { tipo: 'libre' })}>Dejar como texto</button>
                            <button className="btn btn-sm" onClick={() => setMatchedOverride(i, undefined)}>Restaurar</button>
                          </div>
                        </div>
                      );
                    }
                    if (ov?.tipo === 'catalogo') {
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderBottom: '1px solid var(--ink-100)', fontSize: 12.5, background: '#f7fdf7' }}>
                          <span style={{ color: 'var(--accent)' }}>✓</span>
                          <span style={{ flex: 1, fontWeight: 500 }}>{ov.nombre}</span>
                          <span style={{ color: 'var(--ink-500)' }}>Cant: {m.cantidad}</span>
                          <button className="btn btn-sm" onClick={() => setMatchedOverride(i, null)}>Cambiar</button>
                        </div>
                      );
                    }
                    if (ov?.tipo === 'libre') {
                      return (
                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderBottom: '1px solid var(--ink-100)', fontSize: 12.5 }}>
                          <span style={{ color: 'var(--ink-400)' }}>T</span>
                          <span style={{ flex: 1, fontStyle: 'italic', color: 'var(--ink-600)' }}>{m.descripcion_csv}</span>
                          <button className="btn btn-sm" onClick={() => setMatchedOverride(i, undefined)}>Restaurar</button>
                        </div>
                      );
                    }
                    return (
                      <div key={i} style={{ padding: '7px 10px', borderBottom: '1px solid var(--ink-100)', fontSize: 12.5 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ color: 'var(--accent)' }}>✓</span>
                          <span style={{ flex: 1 }}>
                            <span style={{ color: 'var(--ink-500)', fontSize: 11 }}>{m.descripcion_csv}</span>
                            <span style={{ color: 'var(--ink-300)', margin: '0 6px' }}>→</span>
                            <span style={{ fontWeight: 500 }}>{m.nombre_catalogo}</span>
                          </span>
                          {score !== undefined && (
                            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: scoreBg, color: scoreColor, fontWeight: 600 }}>
                              {Math.round(score * 100)}%
                            </span>
                          )}
                          <span style={{ color: 'var(--ink-500)', fontSize: 11 }}>×{m.cantidad}</span>
                          {m.precio > 0 && <span style={{ color: 'var(--ink-500)', fontFamily: 'var(--mono)', fontSize: 11 }}>{fmt(m.precio)}</span>}
                          <button className="btn btn-sm" onClick={() => setMatchedOverride(i, null)}>Cambiar</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {importModal.unmatched.length > 0 && (
                <div>
                  <div className="eyebrow" style={{ marginBottom: 8 }}>
                    Sin coincidencia ({importModal.unmatched.length}) — mapear manualmente
                  </div>
                  {importModal.unmatched.map((u, idx) => {
                    const mp = importModal.mappings[idx];
                    return (
                      <div key={idx} style={{
                        padding: '10px 12px', borderBottom: '1px solid var(--ink-100)',
                        background: mp ? '#f7fdf7' : '#fffbf2',
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                          <span style={{ fontSize: 11, color: 'var(--ink-500)', fontFamily: 'var(--mono)', background: 'var(--ink-100)', padding: '1px 6px', borderRadius: 3 }}>CSV</span>
                          <span style={{ fontSize: 12.5, fontWeight: 500 }}>{u.descripcion_csv}</span>
                          <span style={{ fontSize: 11, color: 'var(--ink-500)', marginLeft: 'auto' }}>Cant: {u.cantidad}</span>
                        </div>
                        {mp?.tipo === 'libre' ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 12, flex: 1, fontStyle: 'italic', color: 'var(--ink-600)' }}>
                              Línea libre: "{u.descripcion_csv}"
                            </span>
                            <button className="btn btn-sm" onClick={() => setMapping(idx, null)}>Cambiar</button>
                          </div>
                        ) : mp?.tipo === 'catalogo' ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ color: 'var(--accent)' }}>✓</span>
                            <span style={{ fontSize: 12, flex: 1, fontWeight: 500 }}>{mp.nombre}</span>
                            {mp.precio > 0 && (
                              <span style={{ fontSize: 11, color: 'var(--ink-500)', fontFamily: 'var(--mono)' }}>{fmt(mp.precio)}</span>
                            )}
                            <button className="btn btn-sm" onClick={() => setMapping(idx, null)}>Cambiar</button>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                            <div style={{ flex: 1 }}>
                              <ProductoSearch
                                linea={{ _id: `import-${idx}`, no_catalogado: false, descripcion: u.descripcion_csv }}
                                onSelect={(p) => setMapping(idx, {
                                  tipo: 'catalogo',
                                  producto_id: p.id,
                                  nombre: p.nombre,
                                  precio: p.precio,
                                  aplica_iva: p.aplica_iva ?? true,
                                })}
                                onChange={() => {}}
                              />
                            </div>
                            <button className="btn btn-sm"
                                    onClick={() => setMapping(idx, { tipo: 'libre' })}>
                              Dejar como texto
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {importModal.matched.length === 0 && importModal.unmatched.length === 0 && (
                <div style={{ textAlign: 'center', color: 'var(--ink-400)', padding: 24 }}>
                  El archivo CSV no contiene datos.
                </div>
              )}
            </div>

            <div style={{
              padding: '12px 20px', borderTop: '1px solid var(--ink-100)',
              display: 'flex', justifyContent: 'flex-end', gap: 8,
            }}>
              <button className="btn" onClick={() => setImportModal(null)}>Cancelar</button>
              <button
                className="btn btn-primary"
                onClick={handleConfirmImport}
                disabled={
                  importModal.unmatched.some((_, idx) => importModal.mappings[idx] === null) ||
                  Object.values(importModal.matchedOverrides ?? {}).some((v) => v === null)
                }
              >
                Confirmar y agregar (
                  {importModal.matched.length + Object.values(importModal.mappings).filter(Boolean).length}
                )
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
