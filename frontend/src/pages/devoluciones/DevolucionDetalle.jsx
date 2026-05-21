import { useParams, useNavigate, Link } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { useState } from 'react';
import { StatusBadge } from '../../components/StatusBadge';
import { EmptyState } from '../../components/EmptyState';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

export default function DevolucionDetalle() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch(`/api/comercial/devoluciones/${id}`);
  const [cerrando, setCerrando] = useState(false);

  const dev   = data?.devolucion ?? null;
  const lineas = data?.lineas ?? [];

  async function handleCerrar() {
    setCerrando(true);
    try {
      await api.patch(`/api/comercial/devoluciones/${id}/cerrar`, {});
      toast.success('Devolución cerrada');
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCerrando(false);
    }
  }

  if (loading) return <div className="page"><div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div></div>;
  if (!dev)    return <div className="page"><div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>Devolución no encontrada</div></div>;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/devoluciones')}>Devoluciones</a>
        <span className="sep">/</span>
        <span>{dev.folio}</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title" style={{ fontFamily: 'var(--mono)', display: 'flex', alignItems: 'center', gap: 10 }}>
            {dev.folio}
            {dev.estado && <StatusBadge status={dev.estado} />}
          </div>
          <div className="page-sub">
            {dev.cliente}
            {dev.fecha && ` · ${dev.fecha}`}
            {dev.motivo && ` · ${dev.motivo}`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {dev.estado === 'Abierta' && (
            <button className="btn btn-primary" disabled={cerrando} onClick={handleCerrar}>
              {cerrando ? 'Cerrando…' : 'Cerrar devolución'}
            </button>
          )}
          <button className="btn" onClick={() => navigate('/comercial/devoluciones')}>← Volver</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 20 }}>
        <div>
          {/* Líneas */}
          <div className="card" style={{ padding: 0 }}>
            <div className="card-h"><h3>Productos devueltos</h3></div>
            <table className="tbl">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th style={{ width: 80 }}>SKU</th>
                  <th className="num" style={{ width: 80 }}>Cant.</th>
                  <th className="num" style={{ width: 110 }}>Precio unit.</th>
                  <th className="num" style={{ width: 110 }}>Total</th>
                  <th style={{ width: 110 }}>Retorna stock</th>
                </tr>
              </thead>
              <tbody>
                {lineas.length === 0 ? (
                  <tr><td colSpan={6}><EmptyState message="Aún no hay productos devueltos." /></td></tr>
                ) : lineas.map((l, i) => (
                  <tr key={l.id ?? i}>
                    <td style={{ fontWeight: 500 }}>{l.nombre}</td>
                    <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink-500)' }}>{l.codigo ?? '—'}</td>
                    <td className="num">{l.cantidad}</td>
                    <td className="num">{l.precio_unitario != null ? MXN.format(l.precio_unitario) : '—'}</td>
                    <td className="num" style={{ fontWeight: 500 }}>{l.total != null ? MXN.format(l.total) : '—'}</td>
                    <td style={{ textAlign: 'center', fontSize: 12 }}>
                      {l.retorna_stock ? (
                        <span style={{ color: 'var(--accent)' }}>Sí</span>
                      ) : (
                        <span style={{ color: 'var(--ink-400)' }}>No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Panel derecho */}
        <div>
          <div className="card" style={{ padding: 16 }}>
            <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>TOTAL DEVOLUCIÓN</div>
            <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>
              {dev.total != null ? MXN.format(dev.total) : '—'}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              {dev.cot_folio && (
                <div>
                  <div className="note" style={{ marginBottom: 2 }}>COTIZACIÓN</div>
                  <Link to={`/comercial/cotizaciones/${dev.cotizacion_id}`}
                    style={{ fontFamily: 'var(--mono)', color: 'var(--accent)' }}>
                    {dev.cot_folio}
                  </Link>
                </div>
              )}
              {dev.notas && (
                <div>
                  <div className="note" style={{ marginBottom: 2 }}>NOTAS</div>
                  <div style={{ color: 'var(--ink-700)' }}>{dev.notas}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
