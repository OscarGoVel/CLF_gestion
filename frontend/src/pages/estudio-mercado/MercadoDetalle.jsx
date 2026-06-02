import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { ConfirmModal } from '../../components/ConfirmModal';
import { ContextMenu } from '../../components/ContextMenu';
import { Modal } from '../../components/Modal';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function MercadoDetalle() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const { data, loading, refetch } = useFetch(`/api/abastecimiento/estudios/${id}`);

  const estudio     = data?.estudio     ?? {};
  const items       = data?.items       ?? [];
  const proveedores = data?.proveedores ?? [];

  const [margenEdit, setMargenEdit]     = useState('');
  const [editingMargen, setEditingMargen] = useState(false);

  // Agregar ítem
  const [showItem, setShowItem]       = useState(false);
  const [itemNombre, setItemNombre]   = useState('');
  const [itemCant, setItemCant]       = useState('1');
  const [itemUnidad, setItemUnidad]   = useState('');
  const [savingItem, setSavingItem]   = useState(false);

  // Agregar cotización proveedor
  const [cotItemId, setCotItemId]     = useState(null);
  const [cotProv, setCotProv]         = useState('');
  const [cotDesc, setCotDesc]         = useState('');
  const [cotPrecio, setCotPrecio]     = useState('');
  const [cotNotas, setCotNotas]       = useState('');
  const [savingCot, setSavingCot]     = useState(false);

  // Eliminaciones
  const [deleteItemId, setDeleteItemId] = useState(null);
  const [deleteCotId, setDeleteCotId]   = useState(null);
  const [deleting, setDeleting]         = useState(false);

  // Ganador / aplicar costos / generar OC
  const [marcandoGanador, setMarcandoGanador] = useState(null);
  const [aplicando, setAplicando]             = useState(false);
  const [generando, setGenerando]             = useState(false);

  // Context menu (clic derecho)
  const [ctxMenu, setCtxMenu]   = useState(null);
  const [vinculando, setVinculando] = useState(null);

  // Enviar a cotización
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [showEnviarModal, setShowEnviarModal] = useState(false);
  const [enviando, setEnviando]   = useState(false);
  const [enviarCotId, setEnviarCotId] = useState('');

  // ── handlers existentes ──────────────────────────────────────────────────────

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
        descripcion_articulo: cotDesc.trim(),
        precio_unitario: parseFloat(cotPrecio),
        notas: cotNotas,
      });
      setCotItemId(null); setCotProv(''); setCotDesc(''); setCotPrecio(''); setCotNotas('');
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

  async function handleMarcarGanador(cotId) {
    setMarcandoGanador(cotId);
    try {
      await api.patch(`/api/abastecimiento/estudios/cotizaciones/${cotId}/ganador`);
      await refetch();
    } catch (e) { toast.error(e.message); }
    finally { setMarcandoGanador(null); }
  }

  async function handleAplicarCostos() {
    setAplicando(true);
    try {
      const r = await api.post(`/api/abastecimiento/estudios/${id}/aplicar-costos`);
      toast.success(`Costos actualizados en ${r.actualizados} producto(s)`);
      await refetch();
    } catch (e) { toast.error(e.message); }
    finally { setAplicando(false); }
  }

  async function handleGenerarOC() {
    setGenerando(true);
    try {
      const r = await api.post(`/api/abastecimiento/estudios/${id}/generar-compra`);
      toast.success('Orden de Compra creada');
      navigate(`/abastecimiento/compras/${r.compra_id}`);
    } catch (e) {
      toast.error(e.message);
      setGenerando(false);
    }
  }

  // ── nuevos handlers ──────────────────────────────────────────────────────────

  async function handleVincularCatalogo(itemId) {
    setVinculando(itemId);
    try {
      await api.patch(`/api/abastecimiento/estudios/items/${itemId}/vincular-producto`, { crear: true });
      await refetch();
      toast.success('Producto agregado al catálogo');
    } catch (e) { toast.error(e.message); }
    finally { setVinculando(null); }
  }

  function toggleItem(itemId) {
    setSelectedItems(prev => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId); else next.add(itemId);
      return next;
    });
  }

  function toggleTodos() {
    if (selectedItems.size === items.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(items.map(i => i.id)));
    }
  }

  function openEnviarModal(preselect = null) {
    if (preselect !== null) {
      setSelectedItems(new Set([preselect]));
    }
    setEnviarCotId(String(cotizacionId || ''));
    setShowEnviarModal(true);
  }

  async function handleEnviarCotizacion() {
    const cotId = parseInt(enviarCotId) || null;
    if (!cotId) { toast.error('Ingresa el número de cotización'); return; }
    const itemIds = selectedItems.size > 0 ? [...selectedItems] : null;
    setEnviando(true);
    try {
      const r = await api.post(`/api/abastecimiento/estudios/${id}/enviar-opciones`, {
        cotizacion_id: cotId,
        item_ids: itemIds,
      });
      toast.success(`${r.lineas_creadas} línea(s) agregadas a la cotización #${cotId}`);
      setShowEnviarModal(false);
      setSelectedItems(new Set());
    } catch (e) { toast.error(e.message); }
    finally { setEnviando(false); }
  }

  function buildCtxItems(item) {
    const menu = [];
    if (!item.producto_id) {
      menu.push({
        label: vinculando === item.id ? 'Agregando…' : 'Agregar al catálogo',
        disabled: vinculando === item.id,
        onClick: () => handleVincularCatalogo(item.id),
      });
    }
    if (item.ganador_proveedor) {
      if (menu.length) menu.push({ type: 'divider' });
      menu.push({
        label: 'Enviar este ítem a cotización',
        onClick: () => openEnviarModal(item.id),
      });
    }
    return menu;
  }

  // ── render ───────────────────────────────────────────────────────────────────

  if (loading) {
    return <div className="page"><div className="card" style={{ padding: 24 }}>Cargando…</div></div>;
  }

  const margenPct    = estudio.margen_pct ?? 0.35;
  const cotizacionId = estudio.cotizacion_id;
  const hayGanadores = items.some(item => item.ganador_proveedor != null);

  const itemsParaEnviar = selectedItems.size > 0
    ? items.filter(i => selectedItems.has(i.id) && i.ganador_proveedor)
    : items.filter(i => i.ganador_proveedor);

  const todosChecked = items.length > 0 && selectedItems.size === items.length;

  return (
    <div className="page">
      {/* Context menu */}
      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          items={ctxMenu.items}
          onClose={() => setCtxMenu(null)}
        />
      )}

      {/* Ribbon cotización vinculada */}
      {cotizacionId && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          background: '#eff6ff', border: '1px solid #bfdbfe',
          borderRadius: 8, padding: '8px 16px', marginBottom: 16,
          fontSize: 12.5, color: '#1e40af',
        }}>
          <span>Estudio vinculado a cotización #{cotizacionId}</span>
          <button
            className="btn btn-sm"
            style={{ fontSize: 11, padding: '2px 10px' }}
            onClick={() => navigate(`/comercial/cotizaciones/${cotizacionId}`)}
          >
            ← Ver cotización
          </button>
        </div>
      )}

      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
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
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {hayGanadores && (
            <>
              <button
                className="btn"
                onClick={handleAplicarCostos}
                disabled={aplicando}
                title="Actualiza precio_base del producto y costo_snapshot en la cotización"
              >
                {aplicando ? 'Aplicando…' : 'Aplicar costos al catálogo'}
              </button>
              <button
                className="btn btn-primary"
                onClick={() => openEnviarModal()}
                title="Crea nuevas líneas en la cotización con precio del proveedor ganador"
              >
                {selectedItems.size > 0
                  ? `Enviar ${selectedItems.size} a cotización →`
                  : 'Enviar a cotización →'}
              </button>
              <button
                className="btn btn-primary"
                onClick={handleGenerarOC}
                disabled={generando}
              >
                {generando ? 'Generando…' : 'Generar OC →'}
              </button>
            </>
          )}
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
        <>
          <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginBottom: 8 }}>
            Haz clic en el precio de un proveedor para marcarlo como ganador.
            Clic derecho en una fila para más opciones.
            {selectedItems.size > 0 && (
              <span style={{ marginLeft: 12, color: 'var(--accent)', fontWeight: 600 }}>
                {selectedItems.size} ítem(s) seleccionado(s)
              </span>
            )}
          </div>
          <div className="card" style={{ padding: 0, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 600 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--ink-100)' }}>
                  <th style={{ padding: '10px 8px', width: 36 }}>
                    <input
                      type="checkbox"
                      checked={todosChecked}
                      onChange={toggleTodos}
                      title="Seleccionar todos"
                    />
                  </th>
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
                  <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: 13 }}>Ganador</th>
                  <th style={{ padding: '10px 12px', width: 80 }} />
                </tr>
              </thead>
              <tbody>
                {items.map(item => {
                  const isSelected = selectedItems.has(item.id);
                  const ctxItems = buildCtxItems(item);
                  return (
                    <>
                      <tr
                        key={item.id}
                        style={{
                          borderBottom: '1px solid var(--ink-100)',
                          background: isSelected ? '#f0f9ff' : undefined,
                        }}
                        onContextMenu={(e) => {
                          if (!ctxItems.length) return;
                          e.preventDefault();
                          setCtxMenu({ x: e.clientX, y: e.clientY, items: ctxItems });
                        }}
                      >
                        <td style={{ padding: '10px 8px' }}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleItem(item.id)}
                            onClick={e => e.stopPropagation()}
                          />
                        </td>
                        <td style={{ padding: '10px 12px', fontWeight: 500 }}>
                          {item.nombre_articulo}
                          {!item.producto_id && (
                            <span
                              style={{
                                marginLeft: 6, fontSize: 10, color: 'var(--ink-400)',
                                background: 'var(--ink-100)', padding: '1px 5px', borderRadius: 3,
                                cursor: 'context-menu',
                              }}
                              title="Clic derecho para agregar al catálogo"
                            >
                              sin catálogo
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                          {item.cantidad} {item.unidad}
                        </td>
                        {proveedores.map(p => {
                          const precio    = item.precios_por_prov?.[p];
                          const cotId     = item.cot_ids_por_prov?.[p];
                          const esGanador = item.ganador_proveedor === p;
                          const esMejor   = precio != null && precio === item.min_precio;
                          const cargando  = marcandoGanador === cotId;

                          return (
                            <td key={p} style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                              {precio != null ? (
                                <button
                                  onClick={() => cotId && handleMarcarGanador(cotId)}
                                  disabled={cargando}
                                  style={{
                                    background: esGanador ? '#dcfce7' : esMejor ? '#f0fdf4' : 'transparent',
                                    border: esGanador ? '1.5px solid #16a34a' : '1px solid transparent',
                                    borderRadius: 4,
                                    padding: '3px 8px',
                                    cursor: cotId ? 'pointer' : 'default',
                                    fontWeight: esGanador ? 700 : esMejor ? 600 : 400,
                                    color: esGanador ? '#166534' : esMejor ? '#15803d' : 'inherit',
                                    fontSize: 13,
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                  }}
                                  title={esGanador ? 'Clic para desmarcar ganador' : 'Clic para marcar como ganador'}
                                >
                                  {esGanador && <span>★</span>}
                                  {MXN.format(precio)}
                                </button>
                              ) : (
                                <span
                                  style={{ color: 'var(--ink-300)', cursor: 'pointer', fontSize: 12 }}
                                  onClick={() => { setCotItemId(item.id); setCotProv(p); setCotDesc(''); }}
                                >+ precio</span>
                              )}
                              {precio != null && cotId && (
                                <button
                                  style={{ marginLeft: 4, fontSize: 10, cursor: 'pointer',
                                           background: 'none', border: 'none', color: 'var(--ink-300)' }}
                                  onClick={() => setDeleteCotId(cotId)}
                                >✕</button>
                              )}
                            </td>
                          );
                        })}
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, fontSize: 13,
                                     background: 'var(--ink-50)' }}>
                          {item.precio_estimado != null ? MXN.format(item.precio_estimado) : '—'}
                        </td>
                        <td style={{ padding: '10px 12px', fontSize: 12 }}>
                          {item.ganador_proveedor ? (
                            <span style={{ color: '#166534', fontWeight: 600 }}>
                              ★ {item.ganador_proveedor}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--ink-300)', fontStyle: 'italic' }}>— sin elegir</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button
                              className="btn"
                              style={{ padding: '2px 8px', fontSize: 12 }}
                              onClick={() => { setCotItemId(item.id); setCotProv(''); setCotDesc(''); }}
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
                          <td colSpan={proveedores.length + 6} style={{ padding: '10px 16px' }}>
                            <form onSubmit={handleAgregarCot} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                              <div>
                                <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                                  Proveedor *
                                </label>
                                <input className="input" value={cotProv} onChange={e => setCotProv(e.target.value)}
                                  placeholder="Nombre del proveedor" style={{ width: 160 }} autoFocus />
                              </div>
                              <div>
                                <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                                  Descripción del artículo
                                </label>
                                <input className="input" value={cotDesc} onChange={e => setCotDesc(e.target.value)}
                                  placeholder="Como lo llama el proveedor" style={{ width: 200 }} />
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
                                  style={{ width: 120 }} />
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
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Barra inferior de acciones */}
      {hayGanadores && (
        <div style={{
          marginTop: 20, padding: '14px 20px',
          background: '#f0fdf4', border: '1px solid #bbf7d0',
          borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
        }}>
          <div style={{ fontSize: 13, color: '#166534' }}>
            <strong>{items.filter(i => i.ganador_proveedor).length}</strong> de {items.length} ítem(s) con ganador seleccionado.
            {cotizacionId && ' Los costos se aplicarán a la cotización vinculada.'}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={handleAplicarCostos} disabled={aplicando}>
              {aplicando ? 'Aplicando…' : 'Aplicar costos al catálogo'}
            </button>
            <button className="btn btn-primary" onClick={() => openEnviarModal()} disabled={enviando}>
              {selectedItems.size > 0
                ? `Enviar ${selectedItems.size} seleccionado(s) →`
                : 'Enviar todos a cotización →'}
            </button>
            <button className="btn btn-primary" onClick={handleGenerarOC} disabled={generando}>
              {generando ? 'Generando…' : 'Generar Orden de Compra →'}
            </button>
          </div>
        </div>
      )}

      {/* Modal: Enviar a cotización */}
      <Modal open={showEnviarModal} onClose={() => setShowEnviarModal(false)} title="Enviar a cotización">
        {itemsParaEnviar.length === 0 ? (
          <div style={{ color: 'var(--ink-500)', fontSize: 13, marginBottom: 16 }}>
            {selectedItems.size > 0
              ? 'Los ítems seleccionados no tienen ganador marcado. Marca un ganador primero.'
              : 'No hay ítems con ganador marcado.'}
          </div>
        ) : (
          <>
            <div style={{ marginBottom: 16 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--ink-200)' }}>
                    <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600 }}>Artículo</th>
                    <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600 }}>Ganador</th>
                    <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600 }}>Costo</th>
                    <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600 }}>
                      Precio ({Math.round(margenPct * 100)}% margen)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {itemsParaEnviar.map(item => (
                    <tr key={item.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                      <td style={{ padding: '6px 8px' }}>
                        {item.nombre_articulo}
                        {!item.producto_id && (
                          <span style={{ marginLeft: 6, fontSize: 10, color: 'var(--ink-400)',
                                         background: 'var(--ink-100)', padding: '1px 4px', borderRadius: 3 }}>
                            se creará en catálogo
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#166534', fontWeight: 500 }}>
                        {item.ganador_proveedor}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                        {item.min_precio != null ? MXN.format(item.min_precio) : '—'}
                      </td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 700 }}>
                        {item.precio_estimado != null ? MXN.format(item.precio_estimado) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div className="note" style={{ marginBottom: 6 }}>NÚMERO DE COTIZACIÓN *</div>
              <input
                className="input"
                type="number"
                style={{ width: '100%' }}
                value={enviarCotId}
                onChange={e => setEnviarCotId(e.target.value)}
                placeholder="Ej: 5"
                autoFocus={!cotizacionId}
                min="1"
              />
              {cotizacionId && (
                <div style={{ fontSize: 12, color: 'var(--ink-400)', marginTop: 4 }}>
                  Pre-llenado con la cotización vinculada #{cotizacionId}
                </div>
              )}
            </div>

            <div style={{ fontSize: 12, color: 'var(--ink-500)', marginBottom: 16,
                          background: 'var(--ink-50)', padding: '8px 12px', borderRadius: 6 }}>
              Se crearán <strong>{itemsParaEnviar.length}</strong> línea(s) nuevas en la cotización.
              El precio de venta = costo del proveedor ganador × (1 + {Math.round(margenPct * 100)}%).
            </div>
          </>
        )}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={() => setShowEnviarModal(false)}>Cancelar</button>
          {itemsParaEnviar.length > 0 && (
            <button className="btn btn-primary" onClick={handleEnviarCotizacion} disabled={enviando}>
              {enviando ? 'Enviando…' : `Enviar ${itemsParaEnviar.length} ítem(s) →`}
            </button>
          )}
        </div>
      </Modal>

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
