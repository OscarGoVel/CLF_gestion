import { useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { StatusBadge } from '../../components/StatusBadge';
import { EmptyState } from '../../components/EmptyState';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-MX');
}

export default function CompraDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch(`/api/abastecimiento/compras/${id}`);
  const [cantidades, setCantidades] = useState({});
  const [guardando, setGuardando] = useState(false);

  const compra = data?.compra ?? null;
  const lineas = data?.lineas ?? [];

  async function handleRecibir() {
    const lineasRecepcion = lineas
      .filter((l) => {
        const v = parseFloat(cantidades[l.id] ?? 0);
        return v > 0;
      })
      .map((l) => ({ linea_id: l.id, cantidad_recibida: parseFloat(cantidades[l.id]) }));

    if (lineasRecepcion.length === 0) {
      toast.error('Ingresa al menos una cantidad a recibir');
      return;
    }
    setGuardando(true);
    try {
      const res = await api.patch(`/api/abastecimiento/compras/${id}/recibir`, { lineas: lineasRecepcion });
      toast.success(res.estado === 'Recibida Completa' ? 'Recepción completa registrada' : 'Recepción parcial registrada');
      setCantidades({});
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>
      </div>
    );
  }

  if (!compra) {
    return (
      <div className="page">
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>Compra no encontrada</div>
      </div>
    );
  }

  const subtotal = lineas.reduce((s, l) => s + (l.importe ?? 0), 0);

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/abastecimiento/compras')}>Compras</a>
        <span className="sep">/</span>
        <span>{compra.folio}</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title" style={{ fontFamily: 'var(--mono)', display: 'flex', alignItems: 'center', gap: 10 }}>
            {compra.folio}
            {compra.estado && <StatusBadge status={compra.estado} />}
          </div>
          <div className="page-sub">{compra.proveedor} · {fmt(compra.fecha_compra)}</div>
        </div>
        <button className="btn" onClick={() => navigate('/abastecimiento/compras')}>← Volver</button>
      </div>

      {/* Encabezado */}
      <div className="card" style={{ padding: 20, marginBottom: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16 }}>
          <div>
            <div className="note">PROVEEDOR</div>
            <div style={{ fontWeight: 500, marginTop: 4 }}>{compra.proveedor}</div>
            {compra.proveedor_rfc && (
              <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>
                {compra.proveedor_rfc}
              </div>
            )}
          </div>
          <div>
            <div className="note">FECHA</div>
            <div style={{ marginTop: 4 }}>{fmt(compra.fecha_compra)}</div>
          </div>
          <div>
            <div className="note">TOTAL</div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.02em', marginTop: 4 }}>
              {compra.total != null ? MXN.format(compra.total) : '—'}
            </div>
          </div>
          {compra.ticket_referencia && (
            <div>
              <div className="note">TICKET</div>
              <div style={{ fontFamily: 'var(--mono)', fontSize: 12, marginTop: 4 }}>{compra.ticket_referencia}</div>
            </div>
          )}
          {compra.folio_factura && (
            <div>
              <div className="note">FACTURA PROVEEDOR</div>
              <div style={{ marginTop: 4, fontSize: 12 }}>
                {compra.serie}{compra.folio_factura}
                {compra.uuid && (
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-400)', marginTop: 2 }}>
                    {compra.uuid}
                  </div>
                )}
              </div>
            </div>
          )}
          {compra.notas && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div className="note">NOTAS</div>
              <div style={{ marginTop: 4, fontSize: 13, color: 'var(--ink-600)' }}>{compra.notas}</div>
            </div>
          )}
        </div>
      </div>

      {/* Líneas */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--ink-100)', fontWeight: 600, fontSize: 13 }}>
          Líneas ({lineas.length})
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)' }}>
                Producto
              </th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 90 }}>
                SKU
              </th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 60 }}>
                UDM
              </th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 80 }}>
                Cantidad
              </th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 120 }}>
                Costo unit.
              </th>
              <th style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 130 }}>
                Importe
              </th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)', width: 100 }}>
                Recibido
              </th>
              <th style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, fontSize: 12, color: 'var(--ink-500)' }}>
                Asignado a
              </th>
            </tr>
          </thead>
          <tbody>
            {lineas.length === 0 ? (
              <tr><td colSpan={7}><EmptyState message="Aún no hay líneas registradas." /></td></tr>
            ) : lineas.map((l, i) => (
              <tr key={l.id ?? i} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 16px', fontWeight: 500 }}>{l.nombre}</td>
                <td style={{ padding: '10px 12px', fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-500)' }}>
                  {l.codigo ?? '—'}
                </td>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-500)' }}>
                  {l.unidad_medida ?? '—'}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'right' }}>{l.cantidad}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                  {l.costo_unitario != null ? MXN.format(l.costo_unitario) : '—'}
                </td>
                <td style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 500 }}>
                  {l.importe != null ? MXN.format(l.importe) : '—'}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                  {compra.estado !== 'Recibida Completa' ? (
                    <input
                      type="number" min="0" step="0.01"
                      style={{ width: 72, textAlign: 'right', padding: '3px 6px',
                        border: '1px solid var(--ink-200)', borderRadius: 4, fontSize: 12 }}
                      placeholder={String(l.cantidad - (l.cantidad_recibida ?? 0))}
                      value={cantidades[l.id] ?? ''}
                      onChange={(e) => setCantidades((p) => ({ ...p, [l.id]: e.target.value }))}
                    />
                  ) : (
                    <span style={{ fontSize: 12, color: 'var(--accent)' }}>
                      {l.cantidad_recibida ?? 0} / {l.cantidad}
                    </span>
                  )}
                </td>
                <td style={{ padding: '8px 16px' }}>
                  {l.asignaciones && l.asignaciones.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {l.asignaciones.map((a) => (
                        <div key={a.cot_id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Link to={`/comercial/cotizaciones/${a.cot_id}`}
                            style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--accent)' }}>
                            {a.folio}
                          </Link>
                          <span style={{ fontSize: 10.5, color: 'var(--ink-500)' }}>
                            {a.cliente}
                          </span>
                          <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 500, color: 'var(--ink-700)' }}>
                            ×{a.cantidad}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <span style={{ fontSize: 11.5, color: 'var(--ink-300)' }}>Sin asignar</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          {lineas.length > 0 && (
            <tfoot>
              <tr style={{ borderTop: '2px solid var(--ink-200)', background: 'var(--ink-50)' }}>
                <td colSpan={5} style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>
                  Total
                </td>
                <td style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 700, fontSize: 14 }}>
                  {MXN.format(compra.total ?? subtotal)}
                </td>
                <td colSpan={2} style={{ padding: '10px 16px', textAlign: 'right' }}>
                  {compra.estado !== 'Recibida Completa' && (
                    <button className="btn btn-primary btn-sm" disabled={guardando} onClick={handleRecibir}>
                      {guardando ? 'Guardando…' : 'Confirmar recepción'}
                    </button>
                  )}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
