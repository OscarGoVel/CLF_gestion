import { useState } from 'react';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { Modal } from '../../components/Modal';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
function fmt(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

const ALERTA_COLOR = {
  vencida: '#dc2626',
  proximo: '#ea580c',
  ok:      '#16a34a',
  pagada:  'var(--ink-400)',
};

const ALERTA_LABEL = {
  vencida: 'Vencida',
  proximo: 'Próximo',
  ok:      'Vigente',
  pagada:  'Pagada',
};

const BLANK_CXP = {
  proveedor_id: '',
  compra_id: '',
  monto_total: '',
  fecha_vencimiento: '',
  referencia_pago: '',
  notas: '',
};

export default function CuentasPagarList() {
  const { activeRS, razonSociales } = useRazonSocial();
  const multiRS = razonSociales.length > 1;
  const [filtroEstado,    setFiltroEstado]   = useState('');
  const [filtroProveedor, setFiltroProveedor] = useState(0);

  const params = new URLSearchParams();
  if (filtroEstado)    params.set('estado', filtroEstado);
  if (filtroProveedor) params.set('proveedor_id', filtroProveedor);
  if (activeRS != null) params.set('razon_social_id', activeRS);
  const { data, loading, refetch } = useFetch(`/api/cuentas-pagar?${params}`);

  const [modalNueva,  setModalNueva]  = useState(false);
  const [modalPago,   setModalPago]   = useState(null);  // cxp object
  const [form,        setForm]        = useState(BLANK_CXP);
  const [pagoMonto,   setPagoMonto]   = useState('');
  const [pagoRef,     setPagoRef]     = useState('');
  const [guardando,   setGuardando]   = useState(false);

  const items      = data?.items      ?? [];
  const kpis       = data?.kpis       ?? {};
  const proveedores = data?.proveedores ?? [];

  function abrirNueva() {
    setForm(BLANK_CXP);
    setModalNueva(true);
  }

  async function handleCrear() {
    if (!form.proveedor_id || !form.monto_total) {
      toast.error('Proveedor y monto son requeridos');
      return;
    }
    setGuardando(true);
    try {
      await api.post('/api/cuentas-pagar', {
        proveedor_id:      parseInt(form.proveedor_id),
        compra_id:         form.compra_id ? parseInt(form.compra_id) : null,
        monto_total:       parseFloat(form.monto_total),
        fecha_vencimiento: form.fecha_vencimiento || null,
        referencia_pago:   form.referencia_pago || null,
        notas:             form.notas || null,
      });
      toast.success('Cuenta por pagar creada');
      setModalNueva(false);
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  async function handlePagar() {
    if (!pagoMonto || parseFloat(pagoMonto) <= 0) return;
    setGuardando(true);
    try {
      const res = await api.patch(`/api/cuentas-pagar/${modalPago.id}/pagar`, {
        monto:      parseFloat(pagoMonto),
        referencia: pagoRef || null,
      });
      toast.success(res.estado === 'Pagada' ? 'Cuenta pagada completamente' : 'Pago parcial registrado');
      setModalPago(null);
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  async function handleEliminar(id) {
    if (!window.confirm('¿Eliminar esta cuenta por pagar?')) return;
    try {
      await api.delete(`/api/cuentas-pagar/${id}`);
      refetch();
    } catch (e) {
      toast.error(e.message);
    }
  }

  return (
    <>
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Cuentas por Pagar</div>
          <div className="page-sub">Obligaciones con proveedores</div>
        </div>
        <button className="btn btn-primary" onClick={abrirNueva}>+ Nueva CxP</button>
      </div>

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 150, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Total pendiente</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{MXN.format(kpis.pendiente ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 150, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Vencido</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: (kpis.vencido ?? 0) > 0 ? '#dc2626' : '' }}>
            {MXN.format(kpis.vencido ?? 0)}
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <select className="input" style={{ width: 160 }}
          value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
          <option value="">Todos los estados</option>
          <option value="Pendiente">Pendiente</option>
          <option value="Parcial">Parcial</option>
          <option value="Vencida">Vencida</option>
          <option value="Pagada">Pagada</option>
        </select>
        <select className="input" style={{ width: 220 }}
          value={filtroProveedor} onChange={e => setFiltroProveedor(Number(e.target.value))}>
          <option value={0}>Todos los proveedores</option>
          {proveedores.map(p => (
            <option key={p.id} value={p.id}>{p.nombre}</option>
          ))}
        </select>
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Proveedor</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Compra</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Total</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pagado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Saldo</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Vencimiento</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              {multiRS && <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13, width: 140 }}>RS</th>}
              <th style={{ padding: '10px 12px', width: 120 }}></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={multiRS ? 9 : 8} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={multiRS ? 9 : 8} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin cuentas por pagar</td></tr>
            )}
            {items.map(item => {
              const alerta = item.alerta ?? 'ok';
              const color  = ALERTA_COLOR[alerta];
              return (
                <tr key={item.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>
                    {item.proveedor_nombre}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-500)' }}>
                    {item.compra_folio || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                    {MXN.format(item.monto_total ?? 0)}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                    {MXN.format(item.monto_pagado ?? 0)}
                  </td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13,
                               color: (item.saldo ?? 0) > 0.01 ? color : '' }}>
                    {MXN.format(item.saldo ?? 0)}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>
                    <span style={{ color: alerta !== 'pagada' ? color : undefined }}>
                      {fmt(item.fecha_vencimiento)}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{
                      display: 'inline-block', padding: '2px 8px', borderRadius: 10,
                      fontSize: 11, fontWeight: 600,
                      background: color + '20', color,
                    }}>
                      {ALERTA_LABEL[alerta]}
                    </span>
                  </td>
                  {multiRS && (
                    <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--ink-500)' }}
                        title={item.razon_social_nombre}>
                      {(item.razon_social_nombre ?? '—').length > 18
                        ? item.razon_social_nombre.slice(0, 18) + '…'
                        : item.razon_social_nombre ?? '—'}
                    </td>
                  )}
                  <td style={{ padding: '8px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    {item.estado !== 'Pagada' && (
                      <button
                        className="btn btn-sm btn-primary"
                        style={{ fontSize: 11, marginRight: 4 }}
                        onClick={() => {
                          setModalPago(item);
                          setPagoMonto('');
                          setPagoRef('');
                        }}>
                        Pagar
                      </button>
                    )}
                    <button className="btn-link-danger" style={{ fontSize: 11 }}
                      onClick={() => handleEliminar(item.id)}>×</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>

    {/* Modal: Nueva CxP */}
    <Modal open={modalNueva} onClose={() => setModalNueva(false)} title="Nueva cuenta por pagar" width={460}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="note" style={{ marginBottom: 4 }}>PROVEEDOR *</div>
            <select className="input" autoFocus value={form.proveedor_id}
              onChange={e => setForm(f => ({ ...f, proveedor_id: e.target.value }))}>
              <option value="">— Seleccionar —</option>
              {proveedores.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>MONTO TOTAL (MXN) *</div>
            <input className="input" type="number" min="0.01" step="0.01"
              value={form.monto_total}
              onChange={e => setForm(f => ({ ...f, monto_total: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>FECHA VENCIMIENTO</div>
            <input className="input" type="date" value={form.fecha_vencimiento}
              onChange={e => setForm(f => ({ ...f, fecha_vencimiento: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>COMPRA ID (opcional)</div>
            <input className="input" type="number" min="1" value={form.compra_id}
              onChange={e => setForm(f => ({ ...f, compra_id: e.target.value }))}
              placeholder="Ej. 42" />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>REFERENCIA / FOLIO FACTURA</div>
            <input className="input" value={form.referencia_pago}
              onChange={e => setForm(f => ({ ...f, referencia_pago: e.target.value }))}
              placeholder="Ej. FAC-2026-001" />
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
            <textarea className="input" rows={2} value={form.notas}
              onChange={e => setForm(f => ({ ...f, notas: e.target.value }))} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalNueva(false)}>Cancelar</button>
          <button className="btn btn-primary"
            disabled={guardando || !form.proveedor_id || !form.monto_total}
            onClick={handleCrear}>
            {guardando ? 'Guardando…' : 'Crear'}
          </button>
        </div>
      </div>
    </Modal>

    {/* Modal: Registrar pago */}
    {modalPago && (
      <Modal open={!!modalPago} onClose={() => setModalPago(null)} title="Registrar pago" width={380}>
        <div style={{ marginBottom: 16, fontSize: 13, color: 'var(--ink-500)' }}>
          <strong>{modalPago.proveedor_nombre}</strong> — Saldo pendiente: {MXN.format(modalPago.saldo ?? 0)}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>MONTO A PAGAR (MXN)</div>
            <input className="input" type="number" step="0.01" min="0.01" autoFocus
              value={pagoMonto} onChange={e => setPagoMonto(e.target.value)}
              placeholder={MXN.format(modalPago.saldo ?? 0)} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>REFERENCIA (transferencia, cheque…)</div>
            <input className="input" value={pagoRef}
              onChange={e => setPagoRef(e.target.value)}
              placeholder="Ej. TRF-20260520" />
          </div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button className="btn" onClick={() => setModalPago(null)}>Cancelar</button>
            <button className="btn btn-primary"
              disabled={!pagoMonto || parseFloat(pagoMonto) <= 0 || guardando}
              onClick={handlePagar}>
              {guardando ? 'Guardando…' : 'Confirmar pago'}
            </button>
          </div>
        </div>
      </Modal>
    )}
    </>
  );
}
