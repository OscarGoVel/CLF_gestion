import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';

let _nextId = 1;
const newLinea = () => ({
  _id: _nextId++,
  producto_id: null,
  nombre: '',
  cantidad: 1,
  costo_unitario: '',
  aplica_iva: false,
});

function fmt(n) {
  if (!n && n !== 0) return '—';
  return new Intl.NumberFormat('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function calcImporte(l) {
  const q = parseFloat(l.cantidad) || 0;
  const c = parseFloat(l.costo_unitario) || 0;
  const sub = q * c;
  return l.aplica_iva ? sub * 1.16 : sub;
}

function ModalProductoRapido({ nombreInicial, onCreado, onCerrar }) {
  const [nombre, setNombre] = useState(nombreInicial || '');
  const [codigo, setCodigo] = useState('');
  const [categoriaId, setCategoriaId] = useState('');
  const [subcategoriaId, setSubcategoriaId] = useState('');
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

  async function handleCrear() {
    if (!nombre.trim()) { setErr('El nombre es requerido'); return; }
    setSaving(true);
    setErr('');
    try {
      const res = await api.post('/api/catalogos/productos/rapido', {
        nombre: nombre.trim(),
        codigo: codigo.trim() || null,
        categoria_id: categoriaId ? parseInt(categoriaId) : null,
        subcategoria_id: subcategoriaId ? parseInt(subcategoriaId) : null,
      });
      onCreado({ id: res.id, nombre: res.nombre, codigo: res.codigo, aplica_iva: false });
    } catch (e) {
      setErr(e.message ?? 'Error al crear producto');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        background: '#fff', borderRadius: 8, padding: 24, width: 380,
        boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
      }}>
        <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 16 }}>Crear producto rápido</div>
        {err && <div className="alert-warn" style={{ marginBottom: 10 }}>{err}</div>}
        <div style={{ marginBottom: 12 }}>
          <label className="label">Nombre *</label>
          <input className="input" value={nombre} onChange={(e) => setNombre(e.target.value)}
            placeholder="Nombre del producto" autoFocus style={{ width: '100%' }} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
          <div>
            <label className="label">Categoría</label>
            <select className="input" value={categoriaId} onChange={handleCategoriaChange} style={{ width: '100%' }}>
              <option value="">— Sin categoría —</option>
              {cats.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Subcategoría</label>
            <select className="input" value={subcategoriaId} onChange={(e) => setSubcategoriaId(e.target.value)}
              disabled={!categoriaId || filteredSubcats.length === 0} style={{ width: '100%' }}>
              <option value="">— Ninguna —</option>
              {filteredSubcats.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginBottom: 16 }}>
          <label className="label">Código</label>
          <input className="input" value={codigo} onChange={(e) => setCodigo(e.target.value)}
            placeholder={categoriaId ? 'Auto-generado' : 'Selecciona categoría'}
            style={{ width: '100%' }} />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn btn-sm" onClick={onCerrar}>Cancelar</button>
          <button className="btn btn-sm btn-primary" onClick={handleCrear} disabled={saving}>
            {saving ? 'Creando…' : 'Crear y seleccionar'}
          </button>
        </div>
      </div>
    </div>
  );
}

function ProductoSearch({ linea, onSelect, onChange }) {
  const [q, setQ] = useState(linea.nombre);
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const debounce = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    clearTimeout(debounce.current);
    if (q.length < 2) { setResults([]); return; }
    debounce.current = setTimeout(async () => {
      try {
        const data = await api.get(`/api/cotizaciones/buscar-producto?q=${encodeURIComponent(q)}`);
        setResults(data.resultados ?? []);
        setOpen(true);
      } catch { setResults([]); }
    }, 300);
    return () => clearTimeout(debounce.current);
  }, [q]);

  useEffect(() => {
    function handle(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handle);
    return () => document.removeEventListener('mousedown', handle);
  }, []);

  function handleCreado(p) {
    onSelect(p);
    setQ(p.nombre);
    setOpen(false);
    setShowModal(false);
  }

  return (
    <div ref={wrapRef} style={{ position: 'relative', flex: 1 }}>
      {showModal && (
        <ModalProductoRapido
          nombreInicial={q}
          onCreado={handleCreado}
          onCerrar={() => setShowModal(false)}
        />
      )}
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); onChange('nombre', e.target.value); }}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Buscar producto del catálogo…"
        style={{
          width: '100%',
          ...(linea.producto_id
            ? { borderColor: '#16a34a', backgroundColor: '#f0fdf4' }
            : linea.nombre ? { borderColor: '#d97706' } : {}),
        }}
      />
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          background: '#fff', border: '1px solid var(--ink-200)', borderRadius: 4,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: 200, overflowY: 'auto',
        }}>
          {results.map((p) => (
            <div key={p.id}
              style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--ink-100)', fontSize: 13 }}
              onMouseDown={() => {
                onSelect(p);
                setQ(p.nombre);
                setOpen(false);
              }}
            >
              <div style={{ fontWeight: 500 }}>{p.nombre}</div>
              <div style={{ fontSize: 11, color: 'var(--ink-500)', fontFamily: 'var(--mono)' }}>
                {p.codigo ?? ''}{p.proveedor_nombre ? ` · ${p.proveedor_nombre}` : ''}
              </div>
            </div>
          ))}
          {q.length >= 2 && (
            <div
              style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12,
                color: 'var(--accent)', borderTop: results.length > 0 ? '1px solid var(--ink-100)' : 'none' }}
              onMouseDown={() => { setOpen(false); setShowModal(true); }}
            >
              + Crear "{q}" como nuevo producto
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CompraNueva() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const cotizacionId = searchParams.get('cotizacion_id') ? parseInt(searchParams.get('cotizacion_id')) : null;

  const prefill = location.state?.prefill ?? null;

  const [lineas, setLineas] = useState(() => {
    if (prefill?.conceptos?.length > 0) {
      return prefill.conceptos.map((c) => {
        const qty = parseFloat(c.cantidad) || 1;
        const neto = (parseFloat(c.importe) || 0) - (parseFloat(c.descuento) || 0);
        const costoUnit = neto > 0 ? neto / qty : (parseFloat(c.valor_unitario) || '');
        return {
          _id: _nextId++,
          producto_id: null,
          nombre: c.descripcion ?? '',
          cantidad: qty,
          costo_unitario: costoUnit,
          aplica_iva: false,
        };
      });
    }
    return [newLinea()];
  });

  const [proveedorId, setProveedorId] = useState('');
  const [fecha, setFecha] = useState(() => {
    if (prefill?.fecha) return prefill.fecha.slice(0, 10);
    return new Date().toISOString().slice(0, 10);
  });
  const [ticket, setTicket] = useState(prefill?.uuid ?? '');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [bannerProveedor, setBannerProveedor] = useState('');

  // Estado para factura importada dinámicamente
  const [facturaId, setFacturaId] = useState(prefill?.factura_id ?? null);
  const [rfcEmisor, setRfcEmisor] = useState(prefill?.rfc_emisor ?? null);
  const [nombreEmisor, setNombreEmisor] = useState(prefill?.nombre_emisor ?? null);
  const [uploadingXml, setUploadingXml] = useState(false);
  const [xmlBanner, setXmlBanner] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const xmlInputRef = useRef(null);

  const { data: provData } = useFetch('/api/catalogos/proveedores');
  const proveedores = provData?.proveedores ?? [];

  // Match proveedor por RFC (reacciona tanto al prefill inicial como a importación dinámica)
  useEffect(() => {
    const rfc = rfcEmisor ?? prefill?.rfc_emisor;
    if (!rfc || proveedores.length === 0 || proveedorId) return;
    const match = proveedores.find(
      (p) => (p.rfc ?? '').toUpperCase() === rfc.toUpperCase()
    );
    if (match) setProveedorId(String(match.id));
  }, [proveedores, rfcEmisor, prefill]);

  const subtotal = lineas.reduce((s, l) => {
    const q = parseFloat(l.cantidad) || 0;
    const c = parseFloat(l.costo_unitario) || 0;
    return s + q * c;
  }, 0);
  const ivaTotal = lineas.reduce((s, l) => {
    const q = parseFloat(l.cantidad) || 0;
    const c = parseFloat(l.costo_unitario) || 0;
    return s + (l.aplica_iva ? q * c * 0.16 : 0);
  }, 0);
  const total = subtotal + ivaTotal;

  const updateLinea = useCallback((id, field, value) => {
    setLineas((ls) => ls.map((l) => l._id === id ? { ...l, [field]: value } : l));
  }, []);

  const selectProducto = useCallback((id, p) => {
    setLineas((ls) => ls.map((l) => l._id === id ? {
      ...l,
      producto_id: p.id,
      nombre: p.nombre,
      aplica_iva: p.aplica_iva ?? false,
    } : l));
  }, []);

  const removeLinea = useCallback((id) => {
    setLineas((ls) => ls.filter((l) => l._id !== id));
  }, []);

  function applyFactura(data) {
    setFacturaId(data.id);
    setRfcEmisor(data.rfc_emisor ?? null);
    setNombreEmisor(data.emisor ?? null);
    if (data.fecha) setFecha(data.fecha.slice(0, 10));
    if (data.uuid) setTicket(data.uuid);
    const nuevas = (data.conceptos ?? []).map((c) => {
      const qty = parseFloat(c.cantidad) || 1;
      const neto = (parseFloat(c.importe) || 0) - (parseFloat(c.descuento) || 0);
      const costoUnit = neto > 0 ? neto / qty : (parseFloat(c.valor_unitario) || '');
      return {
        _id: _nextId++,
        producto_id: null,
        nombre: c.descripcion ?? '',
        cantidad: qty,
        costo_unitario: costoUnit,
        aplica_iva: false,
      };
    });
    setLineas(nuevas.length > 0 ? nuevas : [newLinea()]);
    setXmlBanner(
      `${data.already_exists ? 'Factura existente vinculada' : 'Factura importada'}: ${data.folio || data.uuid?.slice(0, 8)} — ${data.emisor ?? ''}`
    );
  }

  async function handleXmlFile(file) {
    if (!file.name.endsWith('.xml')) return;
    const touched = lineas.length > 1 || lineas.some((l) => l.producto_id || l.nombre || l.costo_unitario);
    if (touched && !window.confirm('¿Reemplazar los datos actuales con los de la factura?')) return;
    setUploadingXml(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('archivo', file);
      const token = sessionStorage.getItem('clf_token');
      const res = await fetch('/api/facturas/importar', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const json = await res.json();
      if (!res.ok) { setError(json.detail ?? 'Error al importar la factura'); return; }
      if (json.tipo !== 'E') { setError('Solo se pueden importar facturas de egreso (tipo E) para registrar compras'); return; }
      applyFactura(json);
    } catch (e) {
      setError(e.message ?? 'Error al importar');
    } finally {
      setUploadingXml(false);
    }
  }

  async function resolverProveedor() {
    if (proveedorId) return parseInt(proveedorId);
    const rfc = rfcEmisor ?? prefill?.rfc_emisor;
    const nombre = nombreEmisor ?? prefill?.nombre_emisor;
    if (!rfc) return null;

    try {
      const res = await api.post('/api/catalogos/proveedores', {
        nombre: nombre ?? rfc,
        rfc,
      });
      setBannerProveedor(`Proveedor "${nombre ?? rfc}" creado automáticamente`);
      return res.id;
    } catch {
      return null;
    }
  }

  async function handleGuardar() {
    if (lineas.length === 0) { setError('Agrega al menos una línea'); return; }
    const sinProducto = lineas.filter((l) => !l.producto_id);
    if (sinProducto.length > 0) { setError('Todas las líneas deben tener un producto del catálogo'); return; }

    setSaving(true);
    setError('');
    try {
      const prov_id = await resolverProveedor();
      const payload = {
        proveedor_id: prov_id,
        fecha_compra: fecha,
        ticket_referencia: ticket || null,
        notas: notas || null,
        factura_xml_id: facturaId ?? prefill?.factura_id ?? null,
        lineas: lineas.map((l) => ({
          producto_id: l.producto_id,
          cantidad: parseFloat(l.cantidad) || 1,
          costo_unitario: parseFloat(l.costo_unitario) || 0,
          aplica_iva: l.aplica_iva,
          cotizacion_id: cotizacionId,
        })),
      };
      await api.post('/api/compras', payload);
      toast.success('Compra registrada');
      navigate('/compras');
    } catch (e) {
      setError(e.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  const mostrarZonaXml = !prefill?.factura_id;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/compras')}>Compras</a>
        <span className="sep">/</span>
        <span>Nueva compra</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Nueva compra</div>
          {cotizacionId && (
            <div className="page-sub">Vinculada a cotización #{cotizacionId}</div>
          )}
          {prefill && (
            <div className="page-sub">Desde factura {prefill.uuid?.slice(0, 8)}…</div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate(prefill ? '/facturas' : '/compras')}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleGuardar} disabled={saving}>
            {saving ? 'Guardando…' : 'Registrar compra'}
          </button>
        </div>
      </div>

      {bannerProveedor && (
        <div className="alert-warn" style={{ marginBottom: 16 }}>
          {bannerProveedor}
        </div>
      )}

      {error && (
        <div className="alert-warn" style={{ marginBottom: 16 }}>
          <strong>{error}</strong>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>
        <div>
          {/* Zona de importación XML */}
          {mostrarZonaXml && (
            <div
              className="card"
              style={{
                marginBottom: 16,
                border: dragOver ? '2px dashed var(--accent)' : '2px dashed var(--ink-200)',
                background: dragOver ? '#f0f9ff' : undefined,
                transition: 'border-color 0.15s, background 0.15s',
              }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragOver(false);
                const f = [...e.dataTransfer.files].find((f) => f.name.endsWith('.xml'));
                if (f) handleXmlFile(f);
              }}
            >
              <input
                ref={xmlInputRef}
                type="file"
                accept=".xml"
                style={{ display: 'none' }}
                onChange={(e) => { if (e.target.files[0]) handleXmlFile(e.target.files[0]); e.target.value = ''; }}
              />
              {xmlBanner ? (
                <div style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
                  <span style={{ color: '#166534' }}>✓</span>
                  <span style={{ color: 'var(--ink-700)' }}>{xmlBanner}</span>
                  <button
                    className="btn btn-sm"
                    style={{ marginLeft: 'auto', fontSize: 11 }}
                    onClick={() => xmlInputRef.current?.click()}
                  >
                    Cambiar XML
                  </button>
                </div>
              ) : (
                <div
                  onClick={() => xmlInputRef.current?.click()}
                  style={{
                    padding: '14px 16px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 10,
                    fontSize: 13, color: 'var(--ink-500)',
                  }}
                >
                  {uploadingXml
                    ? '⏳ Importando…'
                    : <><span>📄</span><span>Importar factura XML (opcional) — arrastra o haz clic</span></>}
                </div>
              )}
            </div>
          )}

          {/* Cabecera */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h"><h3>1 · Proveedor y fecha</h3></div>
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
              <div>
                <label className="label">Proveedor</label>
                <select className="select" value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
                  <option value="">
                    {(nombreEmisor ?? prefill?.nombre_emisor)
                      ? `— ${nombreEmisor ?? prefill?.nombre_emisor} (se creará al guardar) —`
                      : '— Sin proveedor —'}
                  </option>
                  {proveedores.map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Fecha compra *</label>
                <input className="input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
              </div>
              <div>
                <label className="label">Ticket / referencia</label>
                <input className="input" value={ticket} onChange={(e) => setTicket(e.target.value)} placeholder="Nº ticket…" />
              </div>
            </div>
          </div>

          {/* Líneas */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h">
              <h3>2 · Productos</h3>
              {(prefill?.conceptos?.length > 0 || xmlBanner) && (
                <span style={{ fontSize: 11, color: 'var(--ink-500)', fontWeight: 400 }}>
                  Pre-llenado desde XML — asigna cada línea a un producto del catálogo
                </span>
              )}
            </div>

            <div className="qb-line" style={{ background: 'var(--ink-50)', fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              <span></span>
              <span>Producto</span>
              <span style={{ textAlign: 'right' }}>Cant.</span>
              <span style={{ textAlign: 'right' }}>Costo unit.</span>
              <span style={{ textAlign: 'center' }}>IVA</span>
              <span style={{ textAlign: 'right' }}>Total</span>
              <span></span>
            </div>

            {lineas.map((l) => (
              <div key={l._id} className="qb-line">
                <span className="grip">⠿⠿</span>
                <ProductoSearch
                  linea={l}
                  onSelect={(p) => selectProducto(l._id, p)}
                  onChange={(field, val) => updateLinea(l._id, field, val)}
                />
                <input
                  className="num"
                  type="number"
                  min="0"
                  value={l.cantidad}
                  onChange={(e) => updateLinea(l._id, 'cantidad', e.target.value)}
                  style={{ width: 65 }}
                />
                <input
                  className="num"
                  type="number"
                  min="0"
                  value={l.costo_unitario}
                  onChange={(e) => updateLinea(l._id, 'costo_unitario', e.target.value)}
                  placeholder="0.00"
                  style={{ width: 95 }}
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
            ))}

            <div style={{ padding: '10px 12px', borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn btn-sm" onClick={() => setLineas((ls) => [...ls, newLinea()])}>
                + Agregar línea
              </button>
            </div>
          </div>

          {/* Notas */}
          <div className="card">
            <div className="card-h"><h3>3 · Notas</h3></div>
            <div style={{ padding: 16 }}>
              <textarea
                className="input"
                rows={3}
                value={notas}
                onChange={(e) => setNotas(e.target.value)}
                placeholder="Observaciones internas…"
                style={{ width: '100%', resize: 'vertical' }}
              />
            </div>
          </div>
        </div>

        {/* Sidebar */}
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
              <span style={{ fontFamily: 'var(--serif)', fontSize: 24, letterSpacing: '-0.02em' }}>
                {fmt(total)}
              </span>
            </div>
          </div>

          <div className="eyebrow">Validaciones</div>
          <div style={{ fontSize: 11.5 }}>
            <div style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-100)', color: lineas.length > 0 ? 'var(--ink-700)' : 'var(--warn)' }}>
              {lineas.length > 0 ? `✓ ${lineas.length} producto(s)` : '! Sin productos'}
            </div>
            <div style={{ padding: '6px 0', borderBottom: '1px solid var(--ink-100)', color: fecha ? 'var(--ink-700)' : 'var(--warn)' }}>
              {fecha ? `✓ Fecha: ${fecha}` : '! Fecha requerida'}
            </div>
            {lineas.some((l) => !l.producto_id) && (
              <div style={{ padding: '6px 0', color: 'var(--warn)' }}>
                ! Hay líneas sin producto asignado
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
