import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';

let _nextId = 1;
const newLine = () => ({
  _id: _nextId++,
  producto_id: null,
  descripcion: '',
  cantidad: 1,
  precio_unitario: '',
  aplica_iva: true,
  no_catalogado: false,
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

function ProductoSearch({ linea, onSelect, onChange }) {
  const [q, setQ] = useState(linea.descripcion);
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const debounce = useRef(null);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (linea.no_catalogado) return;
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
        style={{ fontStyle: 'italic', width: '100%' }}
      />
    );
  }

  return (
    <div ref={wrapRef} style={{ position: 'relative', flex: 1 }}>
      <input
        value={q}
        onChange={(e) => { setQ(e.target.value); onChange('descripcion', e.target.value); }}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder="Buscar producto…"
        style={{ width: '100%' }}
      />
      {open && results.length > 0 && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
          background: '#fff', border: '1px solid var(--ink-200)', borderRadius: 4,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: 220, overflowY: 'auto',
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
                {p.codigo ?? ''}{p.precio ? ` · ${fmt(p.precio)}` : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function CotNueva() {
  const navigate = useNavigate();
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
    } : l));
  }, []);

  const removeLinea = useCallback((id) => {
    setLineas((ls) => ls.filter((l) => l._id !== id));
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
        partidas: lineas.map((l) => ({
          producto_id: l.no_catalogado ? null : (l.producto_id ?? null),
          descripcion_libre: (l.no_catalogado || !l.producto_id) ? l.descripcion : null,
          cantidad: parseFloat(l.cantidad) || 1,
          precio_unitario: parseFloat(l.precio_unitario) || 0,
          aplica_iva: l.aplica_iva,
        })),
      };
      const res = await api.post('/api/cotizaciones', payload);
      navigate(`/cotizaciones/${res.id}`);
    } catch (e) {
      setError(e.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  const noCatalogadas = lineas.filter((l) => l.no_catalogado).length;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/cotizaciones')}>Cotizaciones</a>
        <span className="sep">/</span>
        <span>Nueva</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Nueva cotización</div>
          <div className="page-sub">Fecha: {fecha}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/cotizaciones')}>Cancelar</button>
          <button className="btn" onClick={() => handleGuardar('Borrador')} disabled={saving}>
            Guardar borrador
          </button>
          <button className="btn btn-primary" onClick={() => handleGuardar('Pendiente')} disabled={saving}>
            {saving ? 'Guardando…' : 'Enviar al cliente'}
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
              <div key={l._id}>
                <div className={`qb-line${l.no_catalogado ? ' flag' : ''}`}>
                  <span className="grip">⠿⠿</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 1 }}>
                    <ProductoSearch
                      linea={l}
                      onSelect={(p) => selectProducto(l._id, p)}
                      onChange={(field, val) => updateLinea(l._id, field, val)}
                    />
                    {l.no_catalogado && <span className="qb-tag">Libre</span>}
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
                <div style={{ padding: '2px 12px 4px 36px', display: 'flex', gap: 8 }}>
                  <label style={{ fontSize: 11, color: 'var(--ink-500)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <input
                      type="checkbox"
                      checked={l.no_catalogado}
                      onChange={(e) => updateLinea(l._id, 'no_catalogado', e.target.checked)}
                    />
                    Línea libre (sin catálogo)
                  </label>
                </div>
              </div>
            ))}

            {noCatalogadas > 0 && (
              <div style={{ padding: '8px 12px', background: '#fffbf2', borderTop: '1px solid #f5e6c0', fontSize: 11.5, color: 'var(--warn)' }}>
                <strong>{noCatalogadas} línea(s) libre(s)</strong> — se guardarán con descripción manual.
              </div>
            )}

            <div style={{ padding: '10px 12px', display: 'flex', gap: 6, borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn btn-sm" onClick={() => setLineas((ls) => [...ls, newLine()])}>
                + Del catálogo
              </button>
              <button className="btn btn-sm" onClick={() => setLineas((ls) => [...ls, { ...newLine(), no_catalogado: true }])}>
                + Línea libre
              </button>
            </div>
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
    </div>
  );
}
