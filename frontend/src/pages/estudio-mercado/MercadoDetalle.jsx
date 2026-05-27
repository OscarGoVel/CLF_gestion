import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { ConfirmModal } from '../../components/ConfirmModal';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function MercadoDetalle() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const { data, loading, refetch } = useFetch(`/api/abastecimiento/estudios/${id}`);

  const estudio    = data?.estudio    ?? {};
  const items      = data?.items      ?? [];
  const proveedores = data?.proveedores ?? [];

  const [margenEdit, setMargenEdit] = useState('');
  const [editingMargen, setEditingMargen] = useState(false);

  // Agregar ítem
  const [showItem, setShowItem]   = useState(false);
  const [itemNombre, setItemNombre] = useState('');
  const [itemCant, setItemCant]   = useState('1');
  const [itemUnidad, setItemUnidad] = useState('');
  const [savingItem, setSavingItem] = useState(false);

  // Agregar cotización proveedor (por ítem)
  const [cotItemId, setCotItemId] = useState(null);
  const [cotProv, setCotProv]     = useState('');
  const [cotPrecio, setCotPrecio] = useState('');
  const [cotNotas, setCotNotas]   = useState('');
  const [savingCot, setSavingCot] = useState(false);

  // Confirmaciones de eliminación
  const [deleteItemId, setDeleteItemId] = useState(null);
  const [deleteCotId, setDeleteCotId]   = useState(null);
  const [deleting, setDeleting]         = useState(false);

  async function handleGuardarMargen(e) {
    e.preventDefault();
    try {
      await api.put(`/api/abastecimiento/estudios/${id}/margen`, { margen_pct: parseFloat(margenEdit) / 100 });
      setEditingMargen(false);
      await refetch();
      toast.success('Margen actualizado');
    } catch (e) { toast.error(e.message); }
  }

  async function handleAgregarItem(e) {
    e.preventDefault();
    if (!itemNombre.trim()) return;
    setSavingItem(true);
    try {
      await api.post(`/api/abastecimiento/estudios/${id}/items`, {
        nombre_articulo: itemNombre.trim(),
        cantidad: parseFloat(itemCant) || 1,
        unidad: itemUnidad,
      });
      setItemNombre(''); setItemCant('1'); setItemUnidad('');
      setShowItem(false);
      await refetch();
      toast.success('Ítem agregado');
    } catch (e) { toast.error(e.message); }
    finally { setSavingItem(false); }
  }

  async function handleEliminarItem() {
    setDeleting(true);
    try {
      await api.delete(`/api/abastecimiento/estudios/items/${deleteItemId}`);
      setDeleteItemId(null);
      await refetch();
      toast.success('Ítem eliminado');
    } catch (e) { toast.error(e.message); }
    finally { setDeleting(false); }
  }

  async function handleAgregarCot(e) {
    e.preventDefault();
    if (!cotProv.trim() || !cotPrecio) return;
    setSavingCot(true);
    try {
      await api.post(`/api/abastecimiento/estudios/items/${cotItemId}/cotizaciones`, {
        nombre_proveedor: cotProv.trim(),
        precio_unitario: parseFloat(cotPrecio),
        notas: cotNotas,
      });
      setCotItemId(null); setCotProv(''); setCotPrecio(''); setCotNotas('');
      await refetch();
      toast.success('Precio de proveedor guardado');
    } catch (e) { toast.error(e.message); }
    finally { setSavingCot(false); }
  }

  async function handleEliminarCot() {
    setDeleting(true);
    try {
      await api.delete(`/api/abastecimiento/estudios/cotizaciones/${deleteCotId}`);
      setDeleteCotId(null);
      await refetch();
      toast.success('Precio eliminado');
    } catch (e) { toast.error(e.message); }
    finally { setDeleting(false); }
  }

  if (loading) {
    return <div className="page"><div className="card" style={{ padding: 24 }}>Cargando…</div></div>;
  }

  const margenPct = estudio.margen_pct ?? 0.35;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/abastecimiento/estudios')}>Estudio de Mercado</a>
        <span className="sep">/</span>
        <span>{estudio.nombre}</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">{estudio.nombre}</div>
          <div className="page-sub" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--ink-400)' }}>{estudio.estado}</span>
            {estudio.descripcion && <span style={{ fontSize: 13 }}>{estudio.descripcion}</span>}
            <span style={{ fontSize: 13 }}>
              Margen:&nbsp;
              {editingMargen ? (
                <form onSubmit={handleGuardarMargen} style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                  <input
                    className="input"
                    type="number"
                    style={{ width: 72, padding: '2px 6px' }}
                    value={margenEdit}
                    onChange={e => setMargenEdit(e.target.value)}
                    min="0" max="200" step="0.1"
                    autoFocus
                  />
                  <span>%</span>
                  <button type="submit" className="btn" style={{ padding: '2px 8px', fontSize: 12 }}>OK</button>
                  <button type="button" className="btn" style={{ padding: '2px 8px', fontSize: 12 }}
                    onClick={() => setEditingMargen(false)}>✕</button>
                </form>
              ) : (
                <span
                  onClick={() => { setMargenEdit(String(Math.round(margenPct * 100))); setEditingMargen(true); }}
                  style={{ cursor: 'pointer', fontWeight: 600, textDecoration: 'underline dotted' }}
                >
                  {Math.round(margenPct * 100)}%
                </span>
              )}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/abastecimiento/estudios')}>← Volver</button>
          <button className="btn btn-primary" onClick={() => setShowItem(true)}>+ Ítem</button>
        </div>
      </div>

      {/* Formulario agregar ítem */}
      {showItem && (
        <div className="card" style={{ padding: 20, marginBottom: 20 }}>
          <form onSubmit={handleAgregarItem} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Artículo *</label>
              <input className="input" value={itemNombre} onChange={e => setItemNombre(e.target.value)}
                placeholder="Nombre del producto" style={{ width: 220 }} autoFocus />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cantidad</label>
              <input className="input" type="number" value={itemCant} onChange={e => setItemCant(e.target.value)}
                style={{ width: 80 }} min="0.01" step="any" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Unidad</label>
              <input className="input" value={itemUnidad} onChange={e => setItemUnidad(e.target.value)}
                placeholder="pza, kg…" style={{ width: 80 }} />
            </div>
            <button type="submit" className="btn btn-primary" disabled={savingItem}>
              {savingItem ? '…' : 'Agregar'}
            </button>
            <button type="button" className="btn" onClick={() => setShowItem(false)}>Cancelar</button>
          </form>
        </div>
      )}

      {/* Tabla pivot */}
      {items.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>
          Sin ítems en este estudio. Agrega el primer producto.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--ink-100)' }}>
                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13, minWidth: 180 }}>
                  Artículo
                </th>
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Cant.</th>
                {proveedores.map(p => (
                  <th key={p} style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>
                    {p}
                  </th>
                ))}
                <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13,
                             background: 'var(--ink-50)' }}>
                  Precio estimado
                </th>
                <th style={{ padding: '10px 12px', width: 80 }} />
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <>
                  <tr key={item.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 500 }}>{item.nombre_articulo}</td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                      {item.cantidad} {item.unidad}
                    </td>
                    {proveedores.map(p => {
                      const precio = item.precios_por_prov?.[p];
                      const esMejor = precio != null && precio === item.min_precio;
                      return (
                        <td key={p} style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                          {precio != null ? (
                            <span style={{ fontWeight: esMejor ? 700 : 400, color: esMejor ? '#16a34a' : '' }}>
                              {esMejor ? '★ ' : ''}{MXN.format(precio)}
                              {/* Botón eliminar cotización */}
                              {item.cotizaciones.find(c => c.nombre_proveedor === p) && (
                                <button
                                  style={{ marginLeft: 6, fontSize: 10, cursor: 'pointer',
                                           background: 'none', border: 'none', color: 'var(--ink-300)' }}
                                  onClick={() => {
                                    const cot = item.cotizaciones.find(c => c.nombre_proveedor === p);
                                    if (cot) setDeleteCotId(cot.id);
                                  }}
                                >✕</button>
                              )}
                            </span>
                          ) : (
                            <span
                              style={{ color: 'var(--ink-300)', cursor: 'pointer', fontSize: 12 }}
                              onClick={() => { setCotItemId(item.id); setCotProv(p); }}
                            >+ precio</span>
                          )}
                        </td>
                      );
                    })}
                    <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, fontSize: 13,
                                 background: 'var(--ink-50)' }}>
                      {item.precio_estimado != null ? MXN.format(item.precio_estimado) : '—'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button
                          className="btn"
                          style={{ padding: '2px 8px', fontSize: 12 }}
                          onClick={() => { setCotItemId(item.id); setCotProv(''); }}
                        >+ Precio</button>
                        <button
                          className="btn"
                          style={{ padding: '2px 8px', fontSize: 12 }}
                          onClick={() => setDeleteItemId(item.id)}
                        >✕</button>
                      </div>
                    </td>
                  </tr>
                  {/* Formulario inline para agregar precio de proveedor */}
                  {cotItemId === item.id && (
                    <tr style={{ background: 'var(--ink-50)' }}>
                      <td colSpan={proveedores.length + 4} style={{ padding: '10px 16px' }}>
                        <form onSubmit={handleAgregarCot} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                          <div>
                            <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                              Proveedor *
                            </label>
                            <input className="input" value={cotProv} onChange={e => setCotProv(e.target.value)}
                              placeholder="Nombre del proveedor" style={{ width: 180 }} autoFocus />
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                              Precio unitario *
                            </label>
                            <input className="input" type="number" value={cotPrecio}
                              onChange={e => setCotPrecio(e.target.value)} style={{ width: 110 }}
                              min="0.01" step="0.01" />
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                              Notas
                            </label>
                            <input className="input" value={cotNotas} onChange={e => setCotNotas(e.target.value)}
                              style={{ width: 140 }} />
                          </div>
                          <button type="submit" className="btn btn-primary" disabled={savingCot}>
                            {savingCot ? '…' : 'Guardar'}
                          </button>
                          <button type="button" className="btn" onClick={() => setCotItemId(null)}>
                            Cancelar
                          </button>
                        </form>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmModal
        open={!!deleteItemId}
        onClose={() => setDeleteItemId(null)}
        onConfirm={handleEliminarItem}
        loading={deleting}
        title="¿Eliminar este ítem?"
        description="Se eliminarán también todos sus precios de proveedor."
        confirmLabel="Eliminar"
        danger
      />
      <ConfirmModal
        open={!!deleteCotId}
        onClose={() => setDeleteCotId(null)}
        onConfirm={handleEliminarCot}
        loading={deleting}
        title="¿Eliminar este precio?"
        confirmLabel="Eliminar"
        danger
      />
    </div>
  );
}
