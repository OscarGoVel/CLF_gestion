import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { DataTable } from '../../components/DataTable';
import { SidePreview } from '../../components/SidePreview';
import { Modal } from '../../components/Modal';
import { exportCSV } from '../../lib/exportCSV';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

const COLUMNS = [
  { header: 'Folio',    key: 'folio',           className: 'folio', sortKey: 'folio', width: 120 },
  { header: 'Fecha',    key: 'fecha_compra',     width: 100, style: { color: 'var(--ink-500)', fontSize: 12 } },
  { header: 'Proveedor', key: 'proveedor',       sortKey: 'proveedor' },
  { header: 'Líneas',   key: 'num_lineas',       width: 60,  style: { textAlign: 'center', color: 'var(--ink-500)' } },
  { header: 'Cots.',    key: 'num_cotizaciones', width: 70,  style: { textAlign: 'center', color: 'var(--ink-500)' } },
  { header: 'Total',    className: 'num', width: 120, sortKey: 'total',
    render: (c) => c.total != null ? MXN.format(c.total) : '—', style: { fontWeight: 500 } },
];

const INSUMO_EMPTY = { nombre: '', unidad: 'pza', cantidad: 1, costo: 0 };

function PresupuestoModal({ onClose }) {
  const { data, loading } = useFetch('/api/abastecimiento/compras/presupuesto/faltantes');
  const pedidos = data?.pedidos ?? [];

  const [selIds, setSelIds]     = useState([]);
  const [insumos, setInsumos]   = useState([]);
  const [generando, setGenerando] = useState(false);
  const [error, setError]       = useState('');

  function togglePedido(id) {
    setSelIds((prev) => prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]);
  }

  function addInsumo() {
    setInsumos((prev) => [...prev, { ...INSUMO_EMPTY }]);
  }

  function updateInsumo(i, field, val) {
    setInsumos((prev) => prev.map((ins, idx) => idx === i ? { ...ins, [field]: val } : ins));
  }

  function removeInsumo(i) {
    setInsumos((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleGenerar() {
    if (selIds.length === 0) { setError('Selecciona al menos un pedido'); return; }
    setGenerando(true);
    setError('');
    try {
      await api.downloadPost('/api/abastecimiento/compras/presupuesto/pdf', 'PresupuestoCompra.pdf', {
        cotizacion_ids: selIds,
        insumos,
      });
      onClose();
    } catch (e) {
      setError(e.message ?? 'Error al generar el PDF');
    } finally {
      setGenerando(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Presupuesto de Compra">
      <div style={{ maxHeight: '70vh', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Sección A — Pedidos programados */}
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            A · Pedidos programados con faltante de stock
          </div>
          {loading ? (
            <div style={{ color: 'var(--ink-400)', fontSize: 13 }}>Cargando pedidos…</div>
          ) : pedidos.length === 0 ? (
            <div style={{ color: 'var(--ink-400)', fontSize: 13 }}>
              No hay pedidos programados con faltante de stock.
            </div>
          ) : (
            <table className="tbl" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ width: 32 }}></th>
                  <th>Folio</th>
                  <th>Cliente</th>
                  <th>F. Entrega</th>
                  <th className="num" style={{ width: 80 }}>Faltantes</th>
                </tr>
              </thead>
              <tbody>
                {pedidos.map((p) => (
                  <tr key={p.id} style={{ cursor: 'pointer' }} onClick={() => togglePedido(p.id)}>
                    <td>
                      <input type="checkbox" checked={selIds.includes(p.id)} onChange={() => togglePedido(p.id)} />
                    </td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>{p.folio}</td>
                    <td>{p.cliente}</td>
                    <td style={{ color: 'var(--ink-500)' }}>{p.fecha_entrega ?? '—'}</td>
                    <td className="num">{p.productos_faltantes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Sección B — Insumos internos (opcional) */}
        <div>
          <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            B · Insumos internos <span style={{ fontWeight: 400, color: 'var(--ink-400)', fontSize: 11 }}>(opcional)</span>
          </div>
          {insumos.length > 0 && (
            <table className="tbl" style={{ fontSize: 12, marginBottom: 8 }}>
              <thead>
                <tr>
                  <th>Descripción</th>
                  <th style={{ width: 60 }}>Unidad</th>
                  <th className="num" style={{ width: 70 }}>Cant.</th>
                  <th className="num" style={{ width: 90 }}>Costo u.</th>
                  <th style={{ width: 28 }}></th>
                </tr>
              </thead>
              <tbody>
                {insumos.map((ins, i) => (
                  <tr key={i}>
                    <td>
                      <input className="input" style={{ width: '100%', fontSize: 12 }}
                        value={ins.nombre} placeholder="Nombre del insumo"
                        onChange={(e) => updateInsumo(i, 'nombre', e.target.value)} />
                    </td>
                    <td>
                      <input className="input" style={{ width: '100%', fontSize: 12 }}
                        value={ins.unidad}
                        onChange={(e) => updateInsumo(i, 'unidad', e.target.value)} />
                    </td>
                    <td>
                      <input className="input num" type="number" min="0" style={{ width: '100%', fontSize: 12 }}
                        value={ins.cantidad}
                        onChange={(e) => updateInsumo(i, 'cantidad', parseFloat(e.target.value) || 0)} />
                    </td>
                    <td>
                      <input className="input num" type="number" min="0" step="0.01" style={{ width: '100%', fontSize: 12 }}
                        value={ins.costo}
                        onChange={(e) => updateInsumo(i, 'costo', parseFloat(e.target.value) || 0)} />
                    </td>
                    <td>
                      <span style={{ cursor: 'pointer', color: 'var(--ink-300)' }} onClick={() => removeInsumo(i)}>×</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button className="btn btn-sm" onClick={addInsumo}>+ Agregar insumo</button>
        </div>

        {error && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{error}</div>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleGenerar} disabled={generando}>
            {generando ? 'Generando…' : 'Descargar PDF'}
          </button>
        </div>
      </div>
    </Modal>
  );
}

export default function CompraList() {
  const navigate = useNavigate();
  const { activeRS } = useRazonSocial();
  const [q, setQ]       = useState('');
  const [pagina, setPag] = useState(1);
  const [sel, setSel]   = useState(null);
  const [showPresupuesto, setShowPresupuesto] = useState(false);

  const params = new URLSearchParams({ pagina });
  if (q) params.set('q', q);
  if (activeRS != null) params.set('razon_social_id', activeRS);

  const { data, loading }   = useFetch(`/api/abastecimiento/compras?${params}`);
  const { data: detData }   = useFetch(sel ? `/api/abastecimiento/compras/${sel}` : null);

  const compras    = data?.compras    ?? [];
  const total      = data?.total      ?? 0;
  const totalPags  = data?.total_pags ?? 1;
  const compra     = detData?.compra  ?? null;
  const lineas     = detData?.lineas  ?? [];

  return (
    <>
      {showPresupuesto && <PresupuestoModal onClose={() => setShowPresupuesto(false)} />}

      <div className="page">
        <div className="crumbs">
          <a onClick={() => navigate('/panel')}>LOGOS</a>
          <span className="sep">/</span>
          <span>Compras</span>
        </div>

        <div className="page-header">
          <div>
            <div className="page-title">Compras</div>
            <div className="page-sub">{total} registros</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => exportCSV(
              ['folio', 'fecha_compra', 'proveedor', 'num_lineas', 'num_cotizaciones', 'total'],
              compras,
              'compras'
            )}>
              Exportar CSV
            </button>
            <button className="btn" onClick={() => setShowPresupuesto(true)}>
              Presupuesto
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/abastecimiento/compras/nueva')}>
              Nueva compra
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <input className="input" style={{ maxWidth: 280 }}
            placeholder="Buscar folio, proveedor, ticket…"
            value={q} onChange={(e) => { setQ(e.target.value); setPag(1); }} />
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: sel ? '1fr 380px' : '1fr',
          gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
        }}>
          <div>
            <DataTable
              columns={COLUMNS}
              data={compras}
              loading={loading}
              selectedId={sel}
              onRowClick={(row) => setSel(sel === row.id ? null : row.id)}
              getContextMenuItems={(compra) => [
                { type: 'item', label: 'Abrir detalle',
                  onClick: () => navigate(`/abastecimiento/compras/${compra.id}`) },
              ]}
              footer={
                <>
                  <span>{compras.length} de {total}</span>
                  <span style={{ display: 'flex', gap: 12 }}>
                    {pagina > 1 && <a className="linkish" onClick={() => setPag((p) => p - 1)}>← anterior</a>}
                    {pagina < totalPags && <a className="linkish" onClick={() => setPag((p) => p + 1)}>siguiente →</a>}
                  </span>
                </>
              }
            />
          </div>

          {sel && (
            <SidePreview>
              {!compra ? (
                <div style={{ color: 'var(--ink-400)', fontSize: 12 }}>Cargando detalle…</div>
              ) : (
                <>
                  <div className="note">COMPRA</div>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 15, fontWeight: 600, marginTop: 4 }}>{compra.folio}</div>
                  <div style={{ fontSize: 12, color: 'var(--ink-500)', marginTop: 2 }}>
                    {compra.proveedor} · {compra.fecha_compra}
                  </div>
                  {compra.proveedor_rfc && (
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>
                      {compra.proveedor_rfc}
                    </div>
                  )}
                  {compra.folio_factura && (
                    <div style={{ marginTop: 8, fontSize: 12, color: 'var(--ink-600)' }}>
                      Factura: {compra.serie}{compra.folio_factura}
                      {compra.uuid && (
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-400)', display: 'block', marginTop: 2 }}>
                          {compra.uuid}
                        </span>
                      )}
                    </div>
                  )}
                  {compra.ticket_referencia && (
                    <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-600)' }}>
                      Ticket: {compra.ticket_referencia}
                    </div>
                  )}

                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontFamily: 'var(--serif)', fontSize: 24, letterSpacing: '-0.02em' }}>
                      {compra.total != null ? MXN.format(compra.total) : '—'}
                    </div>
                    <div className="note" style={{ marginTop: 2 }}>TOTAL</div>
                  </div>

                  <div className="eyebrow" style={{ marginTop: 16 }}>Líneas ({lineas.length})</div>
                  <table className="tbl" style={{ marginTop: 6, fontSize: 11.5 }}>
                    <thead>
                      <tr>
                        <th>Producto</th>
                        <th className="num" style={{ width: 55 }}>Cant.</th>
                        <th className="num" style={{ width: 90 }}>Costo unit.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lineas.map((l, i) => (
                        <tr key={i}>
                          <td>
                            <div>{l.nombre}</div>
                            {l.cotizaciones !== '—' && (
                              <div style={{ fontSize: 10, color: 'var(--ink-500)', marginTop: 1 }}>
                                → {l.cotizaciones}
                              </div>
                            )}
                          </td>
                          <td className="num">{l.cantidad}</td>
                          <td className="num">{l.costo_unitario != null ? MXN.format(l.costo_unitario) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div style={{ marginTop: 14, display: 'flex', gap: 6 }}>
                    <button className="btn btn-sm" onClick={() => navigate(`/abastecimiento/compras/${sel}`)}>Abrir</button>
                    <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
                  </div>
                </>
              )}
            </SidePreview>
          )}
        </div>
      </div>
    </>
  );
}
