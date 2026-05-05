import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';

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

function ProductoSearch({ linea, onSelect, onChange }) {
  const [q, setQ] = useState(linea.nombre);
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
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

  return (
    <div ref={wrapRef} style={{ position: 'relative', flex: 1 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); onChange('nombre', e.target.value); }}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Buscar producto del catálogo…"
        style={{ width: '100%' }}
      />
      {open && results.length > 0 && (
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
        </div>
      )}
    </div>
  );
}

export default function CompraNueva() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const cotizacionId = searchParams.get('cotizacion_id') ? parseInt(searchParams.get('cotizacion_id')) : null;

  const [lineas, setLineas] = useState([newLinea()]);
  const [proveedorId, setProveedorId] = useState('');
  const [fecha, setFecha] = useState(() => new Date().toISOString().slice(0, 10));
  const [ticket, setTicket] = useState('');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const { data: provData } = useFetch('/api/catalogos/proveedores');
  const proveedores = provData?.proveedores ?? [];

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

  async function handleGuardar() {
    if (lineas.length === 0) { setError('Agrega al menos una línea'); return; }
    const sinProducto = lineas.filter((l) => !l.producto_id);
    if (sinProducto.length > 0) { setError('Todas las líneas deben tener un producto del catálogo'); return; }

    setSaving(true);
    setError('');
    try {
      const payload = {
        proveedor_id: proveedorId ? parseInt(proveedorId) : null,
        fecha_compra: fecha,
        ticket_referencia: ticket || null,
        notas: notas || null,
        lineas: lineas.map((l) => ({
          producto_id: l.producto_id,
          cantidad: parseFloat(l.cantidad) || 1,
          costo_unitario: parseFloat(l.costo_unitario) || 0,
          aplica_iva: l.aplica_iva,
          cotizacion_id: cotizacionId,
        })),
      };
      const res = await api.post('/api/compras', payload);
      navigate(`/compras`);
    } catch (e) {
      setError(e.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

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
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/compras')}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleGuardar} disabled={saving}>
            {saving ? 'Guardando…' : 'Registrar compra'}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert-warn" style={{ marginBottom: 16 }}>
          <strong>{error}</strong>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 20 }}>
        <div>
          {/* Cabecera */}
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-h"><h3>1 · Proveedor y fecha</h3></div>
            <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
              <div>
                <label className="label">Proveedor</label>
                <select className="select" value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
                  <option value="">— Sin proveedor —</option>
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
            <div className="card-h"><h3>2 · Productos</h3></div>

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
