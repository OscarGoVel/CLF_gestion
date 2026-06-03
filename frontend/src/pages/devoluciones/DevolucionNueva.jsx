import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

export default function DevolucionNueva() {
  const navigate = useNavigate();
  const { activeRS } = useRazonSocial();
  const [search] = useSearchParams();

  const [clienteQ,   setClienteQ]   = useState('');
  const [clienteSel, setClienteSel] = useState(null);
  const [clienteRes, setClienteRes] = useState([]);
  const [cotFolio,   setCotFolio]   = useState('');
  const [cotId]                     = useState(search.get('cot') ? Number(search.get('cot')) : null);
  const [fecha,      setFecha]      = useState(new Date().toISOString().slice(0, 10));
  const [motivo,     setMotivo]     = useState('');
  const [notas,      setNotas]      = useState('');
  const [lineas,     setLineas]     = useState([{ producto_id: null, prodNombre: '', cantidad: 1, precio_unitario: 0, retorna_stock: true }]);
  const [prodQ,      setProdQ]      = useState({});
  const [prodRes,    setProdRes]    = useState({});
  const [guardando,  setGuardando]  = useState(false);

  async function buscarCliente(q) {
    setClienteQ(q);
    if (q.length < 2) { setClienteRes([]); return; }
    const res = await api.get(`/api/catalogos/clientes/buscar?q=${encodeURIComponent(q)}`).catch(() => null);
    setClienteRes(res?.clientes ?? []);
  }

  async function buscarProducto(idx, q) {
    setProdQ((p) => ({ ...p, [idx]: q }));
    if (q.length < 2) { setProdRes((p) => ({ ...p, [idx]: [] })); return; }
    const res = await api.get(`/api/comercial/cotizaciones/buscar-producto?q=${encodeURIComponent(q)}`).catch(() => null);
    setProdRes((p) => ({ ...p, [idx]: res?.resultados ?? [] }));
  }

  function selProducto(idx, prod) {
    setLineas((ls) => ls.map((l, i) => i === idx ? {
      ...l,
      producto_id: prod.id,
      prodNombre: prod.nombre,
      precio_unitario: prod.precio ?? 0,
    } : l));
    setProdQ((p) => ({ ...p, [idx]: '' }));
    setProdRes((p) => ({ ...p, [idx]: [] }));
  }

  function updateLinea(idx, field, value) {
    setLineas((ls) => ls.map((l, i) => i === idx ? { ...l, [field]: value } : l));
  }

  function addLinea() {
    setLineas((ls) => [...ls, { producto_id: null, prodNombre: '', cantidad: 1, precio_unitario: 0, retorna_stock: true }]);
  }

  function removeLinea(idx) {
    setLineas((ls) => ls.filter((_, i) => i !== idx));
  }

  async function handleGuardar() {
    if (!clienteSel) { toast.error('Selecciona un cliente'); return; }
    const lineasValidas = lineas.filter((l) => l.producto_id && l.cantidad > 0);
    if (lineasValidas.length === 0) { toast.error('Agrega al menos una línea válida'); return; }

    setGuardando(true);
    try {
      const res = await api.post('/api/devoluciones', {
        cotizacion_id: cotId || null,
        cliente_id: clienteSel.id,
        fecha,
        motivo: motivo || null,
        notas: notas || null,
        razon_social_id: activeRS ?? null,
        lineas: lineasValidas.map((l) => ({
          producto_id: l.producto_id,
          cantidad: parseFloat(l.cantidad),
          precio_unitario: parseFloat(l.precio_unitario),
          retorna_stock: l.retorna_stock,
        })),
      });
      toast.success(`Devolución ${res.folio} creada`);
      navigate(`/comercial/devoluciones/${res.id}`);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  const total = lineas.reduce((s, l) => s + (parseFloat(l.cantidad) || 0) * (parseFloat(l.precio_unitario) || 0), 0);

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/devoluciones')}>Devoluciones</a>
        <span className="sep">/</span>
        <span>Nueva</span>
      </div>

      <div className="page-header">
        <div className="page-title">Nueva devolución</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20 }}>
        <div>
          {/* Cabecera */}
          <div className="card" style={{ padding: 20, marginBottom: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div style={{ position: 'relative' }}>
                <div className="note" style={{ marginBottom: 4 }}>CLIENTE *</div>
                {clienteSel ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontWeight: 500 }}>{clienteSel.nombre}</span>
                    <button className="btn-link-danger" style={{ fontSize: 11 }} onClick={() => setClienteSel(null)}>cambiar</button>
                  </div>
                ) : (
                  <>
                    <input className="input" value={clienteQ}
                      onChange={(e) => buscarCliente(e.target.value)}
                      placeholder="Buscar cliente…" />
                    {clienteRes.length > 0 && (
                      <div className="autocomplete-list">
                        {clienteRes.map((c) => (
                          <div key={c.id} className="autocomplete-item"
                            onClick={() => { setClienteSel(c); setClienteRes([]); setClienteQ(''); }}>
                            {c.nombre}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>FECHA</div>
                <input className="input" type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>FOLIO COTIZACIÓN (opcional)</div>
                <input className="input" value={cotFolio}
                  onChange={(e) => setCotFolio(e.target.value)}
                  placeholder="COT-2026-0001" />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>MOTIVO</div>
                <select className="input" value={motivo} onChange={(e) => setMotivo(e.target.value)}>
                  <option value="">— Seleccionar —</option>
                  <option value="producto_dañado">Producto dañado</option>
                  <option value="error_pedido">Error en pedido</option>
                  <option value="producto_incorrecto">Producto incorrecto</option>
                  <option value="exceso">Exceso de inventario</option>
                  <option value="otro">Otro</option>
                </select>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
                <textarea className="input" rows={2} value={notas} onChange={(e) => setNotas(e.target.value)} />
              </div>
            </div>
          </div>

          {/* Líneas */}
          <div className="card" style={{ padding: 0 }}>
            <div className="card-h"><h3>Productos a devolver</h3></div>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th className="num" style={{ width: 80 }}>Cant.</th>
                  <th className="num" style={{ width: 110 }}>Precio unit.</th>
                  <th className="num" style={{ width: 110 }}>Total</th>
                  <th style={{ width: 120 }}>Retorna stock</th>
                  <th style={{ width: 36 }}></th>
                </tr>
              </thead>
              <tbody>
                {lineas.map((l, idx) => (
                  <tr key={idx}>
                    <td style={{ position: 'relative', padding: '6px 12px' }}>
                      {l.producto_id ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 13 }}>{l.prodNombre}</span>
                          <button className="btn-link-danger" style={{ fontSize: 11 }}
                            onClick={() => updateLinea(idx, 'producto_id', null)}>×</button>
                        </div>
                      ) : (
                        <>
                          <input className="input" value={prodQ[idx] ?? ''}
                            onChange={(e) => buscarProducto(idx, e.target.value)}
                            placeholder="Buscar producto…" style={{ fontSize: 12 }} />
                          {(prodRes[idx] ?? []).length > 0 && (
                            <div className="autocomplete-list">
                              {prodRes[idx].map((p) => (
                                <div key={p.id} className="autocomplete-item" onClick={() => selProducto(idx, p)}>
                                  {p.nombre}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </td>
                    <td className="num" style={{ padding: '6px 8px' }}>
                      <input className="input" type="number" min="0.01" step="0.01"
                        value={l.cantidad} onChange={(e) => updateLinea(idx, 'cantidad', e.target.value)}
                        style={{ width: 70, textAlign: 'right' }} />
                    </td>
                    <td className="num" style={{ padding: '6px 8px' }}>
                      <input className="input" type="number" min="0" step="0.01"
                        value={l.precio_unitario} onChange={(e) => updateLinea(idx, 'precio_unitario', e.target.value)}
                        style={{ width: 90, textAlign: 'right' }} />
                    </td>
                    <td className="num" style={{ fontSize: 13 }}>
                      {((parseFloat(l.cantidad) || 0) * (parseFloat(l.precio_unitario) || 0)).toFixed(2)}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <input type="checkbox" checked={l.retorna_stock}
                        onChange={(e) => updateLinea(idx, 'retorna_stock', e.target.checked)} />
                    </td>
                    <td style={{ textAlign: 'center', padding: '6px 4px' }}>
                      {lineas.length > 1 && (
                        <button className="btn-link-danger" onClick={() => removeLinea(idx)}>×</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)' }}>
              <button className="btn btn-sm" onClick={addLinea}>+ Agregar línea</button>
            </div>
          </div>
        </div>

        {/* Panel derecho */}
        <div>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>TOTAL DEVOLUCIÓN</div>
            <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>
              ${total.toLocaleString('es-MX', { minimumFractionDigits: 2 })}
            </div>
            <button className="btn btn-primary" style={{ width: '100%' }}
              disabled={guardando} onClick={handleGuardar}>
              {guardando ? 'Guardando…' : 'Registrar devolución'}
            </button>
            <button className="btn" style={{ width: '100%', marginTop: 8 }}
              onClick={() => navigate('/comercial/devoluciones')}>
              Cancelar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
