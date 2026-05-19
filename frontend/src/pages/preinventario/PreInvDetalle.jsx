import { useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { api } from '../../lib/apiClient';
import { ConfirmModal } from '../../components/ConfirmModal';
import { Modal } from '../../components/Modal';
import { toast } from '../../lib/toast';

export default function PreInvDetalle() {
  const { id }   = useParams();
  const navigate = useNavigate();

  const { data, loading, refetch } = useFetch(`/api/preinventario/sesiones/${id}`);

  const sesion = data?.sesion ?? {};
  const items  = data?.items  ?? [];

  const [busq, setBusq]           = useState('');
  const [sugerencias, setSugs]    = useState([]);
  const [prodSel, setProdSel]     = useState(null);
  const [cantidad, setCantidad]   = useState('');
  const [obs, setObs]             = useState('');
  const [saving, setSaving]       = useState(false);
  const [cerrando, setCerrando]   = useState(false);
  const [showAprobar, setShowAprobar]   = useState(false);
  const [clave, setClave]               = useState('');
  const [notas, setNotas]               = useState('');
  const [aprobando, setAprobando]       = useState(false);
  const [errAprob, setErrAprob]         = useState('');
  const [deleteItemId, setDeleteItemId] = useState(null);
  const [deleting, setDeleting]         = useState(false);
  const [confirmCerrar, setConfirmCerrar] = useState(false);
  const [showRechazar, setShowRechazar] = useState(false);
  const [motivoRechazo, setMotivoRechazo] = useState('');
  const [rechazando, setRechazando]     = useState(false);
  const busqTimer = useRef(null);

  const isAbierta = sesion.estado === 'abierta';
  const isCerrada = sesion.estado === 'cerrada';

  async function handleBuscar(e) {
    const v = e.target.value;
    setBusq(v);
    setProdSel(null);
    clearTimeout(busqTimer.current);
    if (v.length < 2) { setSugs([]); return; }
    busqTimer.current = setTimeout(async () => {
      const res = await api.get(`/api/preinventario/buscar?q=${encodeURIComponent(v)}`);
      setSugs(res.resultados ?? []);
    }, 250);
  }

  function selProd(p) {
    setProdSel(p);
    setBusq(p.nombre);
    setSugs([]);
    setCantidad('');
    setObs('');
  }

  async function handleAgregar(e) {
    e.preventDefault();
    if (!prodSel || cantidad === '') return;
    setSaving(true);
    try {
      await api.post(`/api/preinventario/sesiones/${id}/items`, {
        producto_id:     prodSel.id,
        cantidad_contada: parseFloat(cantidad),
        observaciones:   obs || null,
      });
      setBusq(''); setProdSel(null); setCantidad(''); setObs('');
      await refetch();
      toast.success('Ítem registrado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleEliminar() {
    setDeleting(true);
    try {
      await api.delete(`/api/preinventario/items/${deleteItemId}`);
      setDeleteItemId(null);
      await refetch();
      toast.success('Ítem eliminado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeleting(false);
    }
  }

  async function handleCerrar() {
    setCerrando(true);
    try {
      await api.post(`/api/preinventario/sesiones/${id}/cerrar`, {});
      setConfirmCerrar(false);
      await refetch();
      toast.success('Sesión cerrada');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setCerrando(false);
    }
  }

  async function handleAprobar(e) {
    e.preventDefault();
    setAprobando(true); setErrAprob('');
    try {
      await api.post(`/api/preinventario/sesiones/${id}/aprobar`, { clave, notas });
      setShowAprobar(false);
      await refetch();
      toast.success('Pre-inventario aprobado — ajustes de stock aplicados');
    } catch (e) {
      setErrAprob(e.message);
    } finally {
      setAprobando(false);
    }
  }

  async function handleRechazar() {
    if (!motivoRechazo.trim()) return;
    setRechazando(true);
    try {
      await api.post(`/api/preinventario/sesiones/${id}/rechazar`, { motivo: motivoRechazo.trim() });
      setShowRechazar(false);
      setMotivoRechazo('');
      await refetch();
      toast.success('Sesión rechazada');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setRechazando(false);
    }
  }

  if (loading) {
    return <div className="page"><div className="card" style={{ padding: 24 }}>Cargando…</div></div>;
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/preinventario')}>Pre-inventario</a>
        <span className="sep">/</span>
        <span>{sesion.nombre}</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">{sesion.nombre}</div>
          <div className="page-sub" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Pill label={sesion.estado} />
            <span style={{ fontSize: 13, color: 'var(--ink-400)' }}>{sesion.tipo} · {sesion.creado_por}</span>
            <span style={{ fontSize: 13, color: 'var(--ink-400)' }}>{items.length} ítems</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {isAbierta && (
            <button className="btn btn-primary" onClick={() => setConfirmCerrar(true)} disabled={cerrando}>
              Finalizar sesión
            </button>
          )}
          {isCerrada && (
            <>
              <button className="btn btn-primary" onClick={() => setShowAprobar(true)}>Aprobar</button>
              <button className="btn" onClick={() => { setMotivoRechazo(''); setShowRechazar(true); }}>Rechazar</button>
            </>
          )}
        </div>
      </div>

      {/* Formulario de captura (solo sesión abierta) */}
      {isAbierta && (
        <div className="card" style={{ padding: 20, marginBottom: 24 }}>
          <div style={{ fontWeight: 600, marginBottom: 14, fontSize: 14 }}>Agregar producto</div>
          <form onSubmit={handleAgregar}>
            <div style={{ position: 'relative', marginBottom: 12 }}>
              <input
                className="input"
                style={{ width: '100%' }}
                placeholder="Buscar por SKU o nombre…"
                value={busq}
                onChange={handleBuscar}
              />
              {sugerencias.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 20,
                  background: '#fff', border: '1px solid var(--ink-200)', borderRadius: 6,
                  boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
                }}>
                  {sugerencias.map(p => (
                    <div
                      key={p.id}
                      onClick={() => selProd(p)}
                      style={{ padding: '10px 14px', cursor: 'pointer', borderBottom: '1px solid var(--ink-100)' }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--ink-50)'}
                      onMouseLeave={e => e.currentTarget.style.background = ''}
                    >
                      <span style={{ fontWeight: 500 }}>{p.nombre}</span>
                      <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--ink-400)' }}>
                        {p.codigo} · Stock: {p.stock_actual ?? 0}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {prodSel && (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                    Cantidad física *
                  </label>
                  <input
                    className="input"
                    type="number"
                    inputMode="numeric"
                    style={{ width: 120 }}
                    value={cantidad}
                    onChange={e => setCantidad(e.target.value)}
                    min="0"
                    step="any"
                    autoFocus
                  />
                </div>
                <div style={{ flex: 1, minWidth: 180 }}>
                  <label style={{ display: 'block', fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
                    Observaciones
                  </label>
                  <input
                    className="input"
                    style={{ width: '100%' }}
                    value={obs}
                    onChange={e => setObs(e.target.value)}
                    placeholder="Opcional"
                  />
                </div>
                <button type="submit" className="btn btn-primary" disabled={saving || cantidad === ''}>
                  {saving ? '…' : 'Registrar'}
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* Tabla de ítems */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Producto</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Sistema</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Contado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Diferencia</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Notas</th>
              {isAbierta && <th style={{ padding: '10px 12px', width: 40 }} />}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={isAbierta ? 6 : 5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>
                Sin ítems registrados
              </td></tr>
            )}
            {items.map(i => {
              const dif = i.diferencia ?? 0;
              const difColor = dif > 0 ? '#16a34a' : dif < 0 ? '#dc2626' : 'var(--ink-400)';
              return (
                <tr key={i.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                  <td style={{ padding: '10px 12px' }}>
                    <div style={{ fontWeight: 500 }}>{i.producto}</div>
                    <div style={{ fontSize: 11, color: 'var(--ink-400)' }}>{i.codigo} · {i.unidad_medida}</div>
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                    {i.cantidad_sistema ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>
                    {i.cantidad_contada ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, fontSize: 13, color: difColor }}>
                    {dif > 0 ? `+${dif}` : dif}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>
                    {i.notas ?? ''}
                  </td>
                  {isAbierta && (
                    <td style={{ padding: '10px 12px' }}>
                      <button
                        className="btn"
                        style={{ padding: '2px 8px', fontSize: 12 }}
                        onClick={() => setDeleteItemId(i.id)}
                      >✕</button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Modal aprobación */}
      {showAprobar && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card" style={{ width: 400, padding: 28 }}>
            <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 16 }}>Confirmar aprobación</div>
            <p style={{ fontSize: 13, color: 'var(--ink-500)', marginBottom: 16 }}>
              Se aplicarán los ajustes al stock real. Ingresa tu contraseña de administrador.
            </p>
            {errAprob && (
              <div style={{ marginBottom: 12, padding: '8px 12px', background: '#fef2f2',
                            border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>
                {errAprob}
              </div>
            )}
            <form onSubmit={handleAprobar}>
              <input
                className="input"
                type="password"
                style={{ width: '100%', marginBottom: 12 }}
                placeholder="Contraseña"
                value={clave}
                onChange={e => setClave(e.target.value)}
                autoFocus
              />
              <textarea
                className="input"
                style={{ width: '100%', marginBottom: 16, height: 72, resize: 'vertical' }}
                placeholder="Notas de aprobación (opcional)"
                value={notas}
                onChange={e => setNotas(e.target.value)}
              />
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button type="button" className="btn" onClick={() => { setShowAprobar(false); setErrAprob(''); }}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={aprobando || !clave}>
                  {aprobando ? 'Aprobando…' : 'Aprobar y aplicar ajustes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmModal
        open={!!deleteItemId}
        onClose={() => setDeleteItemId(null)}
        onConfirm={handleEliminar}
        loading={deleting}
        title="¿Eliminar este ítem?"
        description="Se eliminará el conteo de este producto de la sesión."
        confirmLabel="Eliminar"
        danger
      />

      <ConfirmModal
        open={confirmCerrar}
        onClose={() => setConfirmCerrar(false)}
        onConfirm={handleCerrar}
        loading={cerrando}
        title="¿Finalizar la sesión?"
        description="Una vez cerrada, no podrás agregar más ítems. La sesión quedará lista para aprobación."
        confirmLabel="Finalizar sesión"
        danger
      />

      {/* Modal rechazar con motivo */}
      <Modal open={showRechazar} onClose={() => setShowRechazar(false)} title="Rechazar sesión" width={400}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>MOTIVO DE RECHAZO</div>
            <textarea className="input" rows={3} value={motivoRechazo}
              onChange={(e) => setMotivoRechazo(e.target.value)}
              placeholder="Describe el motivo…" style={{ resize: 'vertical' }} autoFocus />
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn" onClick={() => setShowRechazar(false)}>Cancelar</button>
            <button className="btn" disabled={!motivoRechazo.trim() || rechazando}
              style={{ background: 'var(--danger)', borderColor: 'var(--danger)', color: '#fff' }}
              onClick={handleRechazar}>
              {rechazando ? 'Rechazando…' : 'Confirmar rechazo'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
