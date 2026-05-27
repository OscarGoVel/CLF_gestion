import { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/StatusBadge';
import { Modal } from '../../components/Modal';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

function fmt(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

function AgeBar({ value, total }) {
  if (!total) return null;
  const pct = Math.round((value / total) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, background: 'var(--ink-100)', borderRadius: 3 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--primary)', borderRadius: 3 }} />
      </div>
      <span style={{ fontSize: 12, color: 'var(--ink-400)', minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

export default function EstadoCuentaDetalle() {
  const { cliente_id } = useParams();
  const navigate       = useNavigate();

  const { data, loading, refetch } = useFetch(`/api/finanzas/cobranza/${cliente_id}`);

  const [modalPago,   setModalPago]   = useState(false);
  const [cotPagoId,   setCotPagoId]   = useState(null);
  const [pagoMonto,   setPagoMonto]   = useState('');
  const [pagoFecha,   setPagoFecha]   = useState('');
  const [pagoMetodo,  setPagoMetodo]  = useState('');
  const [pagoRef,     setPagoRef]     = useState('');
  const [guardando,   setGuardando]   = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  const cliente     = data?.cliente     ?? {};
  const kpis        = data?.kpis        ?? {};
  const aging       = data?.aging       ?? {};
  const cotizaciones = data?.cotizaciones ?? [];

  const pendienteTotal = kpis.pendiente ?? 0;

  async function handlePdf() {
    try {
      await api.download(`/api/finanzas/cobranza/pdf`, `EstadoCuenta_${cliente.nombre_comercial}.pdf`);
    } catch (e) {
      toast.error(e.message);
    }
  }

  function abrirModalPago(cotId) {
    setCotPagoId(cotId);
    setPagoMonto('');
    setPagoFecha(today);
    setPagoMetodo('');
    setPagoRef('');
    setModalPago(true);
  }

  async function handleRegistrarPago() {
    if (!pagoMonto || parseFloat(pagoMonto) <= 0) return;
    setGuardando(true);
    try {
      const res = await api.post(`/api/finanzas/cobranza/${cotPagoId}/pago`, {
        monto: parseFloat(pagoMonto),
        fecha_pago: pagoFecha,
        metodo: pagoMetodo || null,
        referencia: pagoRef || null,
      });
      toast.success(res.pagada ? 'Pago registrado — cotización marcada como Pagada' : 'Pago registrado');
      setModalPago(false);
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  if (loading) {
    return <div className="page"><div className="card" style={{ padding: 24 }}>Cargando…</div></div>;
  }

  return (
    <>
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/finanzas/cobranza')}>Estado de Cuenta</a>
        <span className="sep">/</span>
        <span>{cliente.nombre_comercial}</span>
      </div>

      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">{cliente.nombre_comercial}</div>
          <div className="page-sub" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            {cliente.rfc && <span>RFC: {cliente.rfc}</span>}
            {cliente.tipo && <StatusBadge status={cliente.tipo} />}
            {cliente.corporativo && <span style={{ color: 'var(--ink-400)' }}>{cliente.corporativo}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => navigate('/finanzas/cobranza')}>← Volver</button>
          <button className="btn" onClick={handlePdf}>Exportar PDF</button>
        </div>
      </div>

      {/* Contacto */}
      {(cliente.contacto || cliente.telefono || cliente.email) && (
        <div className="card" style={{ padding: '12px 16px', marginBottom: 20, fontSize: 13, display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {cliente.contacto && <span>👤 {cliente.contacto}</span>}
          {cliente.telefono && <span>📞 {cliente.telefono}</span>}
          {cliente.email    && <span>✉️ {cliente.email}</span>}
        </div>
      )}

      {/* KPIs */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cartera</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{MXN.format(kpis.cartera ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Cobrado</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>{MXN.format(kpis.cobrado ?? 0)}</div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>Pendiente</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: pendienteTotal > 0 ? 'var(--red-600, #dc2626)' : '' }}>
            {MXN.format(pendienteTotal)}
          </div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 140, padding: 16 }}>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>DSO (días cobro)</div>
          <div style={{ fontSize: 20, fontWeight: 700 }}>
            {kpis.dso != null ? `${kpis.dso} días` : '—'}
          </div>
        </div>
      </div>

      {/* Aging */}
      {pendienteTotal > 0 && (
        <div className="card" style={{ padding: 20, marginBottom: 24 }}>
          <div style={{ fontWeight: 600, marginBottom: 16, fontSize: 14 }}>Antigüedad del saldo pendiente</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
            {[
              { label: '0 – 30 días',  key: 'dias_0_30',   color: '#16a34a' },
              { label: '30 – 60 días', key: 'dias_30_60',  color: '#ca8a04' },
              { label: '60 – 90 días', key: 'dias_60_90',  color: '#ea580c' },
              { label: '+90 días',     key: 'dias_mas_90', color: '#dc2626' },
            ].map(({ label, key, color }) => (
              <div key={key}>
                <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color, marginBottom: 6 }}>
                  {MXN.format(aging[key] ?? 0)}
                </div>
                <AgeBar value={aging[key] ?? 0} total={pendienteTotal} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cotizaciones */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <div style={{ padding: '12px 16px', fontWeight: 600, fontSize: 14, borderBottom: '1px solid var(--ink-100)' }}>
          Cotizaciones
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Folio</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Entrega</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Total</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pagado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Pendiente</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Días</th>
              <th style={{ padding: '10px 12px', width: 90 }}></th>
            </tr>
          </thead>
          <tbody>
            {cotizaciones.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin cotizaciones activas</td></tr>
            )}
            {cotizaciones.map(c => (
              <tr key={c.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px' }}>
                  <Link to={`/comercial/cotizaciones/${c.id}`} style={{ fontWeight: 500 }}>{c.folio}</Link>
                </td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{fmt(c.fecha_entrega)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{MXN.format(c.total ?? 0)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{MXN.format(c.pagado ?? 0)}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13,
                             color: (c.pendiente ?? 0) > 0.01 ? 'var(--red-600, #dc2626)' : '' }}>
                  {MXN.format(c.pendiente ?? 0)}
                </td>
                <td style={{ padding: '10px 12px' }}><StatusBadge status={c.estado} /></td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>
                  {c.dias_desde_entrega != null ? `${Math.round(c.dias_desde_entrega)}d` : '—'}
                </td>
                <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                  {!['Cancelada', 'Pagada'].includes(c.estado) && (c.pendiente ?? 0) > 0.01 && (
                    <button className="btn btn-sm btn-primary" style={{ fontSize: 11 }}
                      onClick={() => abrirModalPago(c.id)}>
                      Registrar pago
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>

    {/* Modal: Registrar pago */}
    <Modal open={modalPago} onClose={() => setModalPago(false)} title="Registrar pago" width={420}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>MONTO (MXN)</div>
          <input className="input" type="number" step="0.01" min="0.01"
            value={pagoMonto} onChange={(e) => setPagoMonto(e.target.value)}
            placeholder="0.00" autoFocus />
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>FECHA DE PAGO</div>
          <input className="input" type="date" value={pagoFecha}
            onChange={(e) => setPagoFecha(e.target.value)} />
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>MÉTODO</div>
          <select className="input" value={pagoMetodo} onChange={(e) => setPagoMetodo(e.target.value)}>
            <option value="">— Seleccionar —</option>
            <option value="efectivo">Efectivo</option>
            <option value="transferencia">Transferencia</option>
            <option value="cheque">Cheque</option>
            <option value="tarjeta">Tarjeta</option>
          </select>
        </div>
        <div>
          <div className="note" style={{ marginBottom: 4 }}>REFERENCIA / FOLIO</div>
          <input className="input" value={pagoRef} onChange={(e) => setPagoRef(e.target.value)}
            placeholder="Ej. TRF-20260520" />
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModalPago(false)}>Cancelar</button>
          <button className="btn btn-primary"
            disabled={!pagoMonto || parseFloat(pagoMonto) <= 0 || guardando}
            onClick={handleRegistrarPago}>
            {guardando ? 'Guardando…' : 'Confirmar pago'}
          </button>
        </div>
      </div>
    </Modal>
    </>
  );
}
