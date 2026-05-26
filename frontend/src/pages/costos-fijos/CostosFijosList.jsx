import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { api } from '../../lib/apiClient';
import { ConfirmModal } from '../../components/ConfirmModal';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

function periodoActual() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

function fmtPeriodo(p) {
  if (!p) return '';
  const [y, m] = p.split('-');
  const meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
  return `${meses[parseInt(m, 10) - 1]} ${y}`;
}

export default function CostosFijosList() {
  const navigate  = useNavigate();
  const [periodo, setPeriodo] = useState(periodoActual);
  const [showForm, setShowForm] = useState(false);
  const [deleteId, setDeleteId] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const { data, loading, refetch } = useFetch(`/api/costos-fijos?periodo=${periodo}`);
  const items  = data?.items  ?? [];
  const total  = data?.total  ?? 0;

  async function handleEliminar() {
    setDeleting(true);
    try {
      await api.delete(`/api/finanzas/costos-fijos/${deleteId}`);
      setDeleteId(null);
      await refetch();
      toast.success('Costo eliminado');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Costos Fijos</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Costos Fijos</div>
          <div className="page-sub">Registro mensual de costos fijos</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          Registrar costo
        </button>
      </div>

      {/* Selector de período */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <span style={{ fontSize: 13, color: 'var(--ink-500)' }}>Período:</span>
        <input
          type="month"
          className="input"
          style={{ maxWidth: 160 }}
          value={periodo}
          onChange={e => setPeriodo(e.target.value)}
        />
        <span style={{ fontSize: 14, color: 'var(--ink-400)' }}>{fmtPeriodo(periodo)}</span>
      </div>

      {/* KPI total */}
      <div className="card" style={{ padding: 20, marginBottom: 24, display: 'inline-flex', alignItems: 'center', gap: 16 }}>
        <div>
          <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 4 }}>
            Total costos fijos — {fmtPeriodo(periodo)}
          </div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{MXN.format(total)}</div>
        </div>
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Categoría</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Descripción</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Monto</th>
              <th style={{ padding: '10px 12px', width: 80 }} />
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && items.length === 0 && (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>
                Sin costos registrados para {fmtPeriodo(periodo)}
              </td></tr>
            )}
            {items.map(item => (
              <tr key={item.id} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px' }}>
                  <Pill label={item.categoria} />
                </td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{item.descripcion}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>
                  {MXN.format(item.monto)}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      className="btn"
                      style={{ padding: '2px 8px', fontSize: 12 }}
                      onClick={() => navigate(`/finanzas/costos-fijos/${item.id}/editar`)}
                    >Editar</button>
                    <button
                      className="btn"
                      style={{ padding: '2px 8px', fontSize: 12 }}
                      onClick={() => setDeleteId(item.id)}
                    >✕</button>
                  </div>
                </td>
              </tr>
            ))}
            {items.length > 0 && (
              <tr style={{ background: 'var(--ink-50)' }}>
                <td colSpan={2} style={{ padding: '10px 12px', fontWeight: 700, fontSize: 13 }}>Total</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, fontSize: 14 }}>
                  {MXN.format(total)}
                </td>
                <td />
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal nuevo costo */}
      {showForm && (
        <CostoFijoModal
          periodoDefault={periodo}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); refetch(); toast.success('Costo registrado'); }}
        />
      )}

      <ConfirmModal
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={handleEliminar}
        loading={deleting}
        title="¿Eliminar este costo?"
        description="Esta acción no se puede deshacer."
        confirmLabel="Eliminar"
        danger
      />
    </div>
  );
}

function CostoFijoModal({ periodoDefault, onClose, onSaved, initialData = null }) {
  const [periodo, setPeriodo]     = useState(initialData?.periodo || periodoDefault);
  const [categoria, setCategoria] = useState(initialData?.categoria || 'renta');
  const [desc, setDesc]           = useState(initialData?.descripcion || '');
  const [monto, setMonto]         = useState(initialData?.monto || '');
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState('');

  const CATS = ['renta', 'nomina', 'servicios', 'depreciacion', 'otro'];

  async function handleSubmit(e) {
    e.preventDefault();
    if (!desc.trim() || !monto) { setError('Todos los campos son requeridos'); return; }
    setSaving(true); setError('');
    try {
      if (initialData?.id) {
        await api.put(`/api/finanzas/costos-fijos/${initialData.id}`, {
          periodo, categoria, descripcion: desc.trim(), monto: parseFloat(monto),
        });
      } else {
        await api.post('/api/costos-fijos', {
          periodo, categoria, descripcion: desc.trim(), monto: parseFloat(monto),
        });
      }
      onSaved();
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }}>
      <div className="card" style={{ width: 420, padding: 28 }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>
          {initialData ? 'Editar costo' : 'Registrar costo fijo'}
        </div>
        {error && (
          <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                        border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Período</label>
            <input type="month" className="input" style={{ width: '100%' }}
              value={periodo} onChange={e => setPeriodo(e.target.value)} />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Categoría</label>
            <select className="input" style={{ width: '100%' }} value={categoria} onChange={e => setCategoria(e.target.value)}>
              {CATS.map(c => <option key={c} value={c} style={{ textTransform: 'capitalize' }}>{c}</option>)}
            </select>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Descripción *</label>
            <input className="input" style={{ width: '100%' }} value={desc}
              onChange={e => setDesc(e.target.value)} placeholder="Ej. Renta bodega Mérida" />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Monto *</label>
            <input className="input" type="number" style={{ width: '100%' }} value={monto}
              onChange={e => setMonto(e.target.value)} min="0.01" step="0.01" placeholder="0.00" />
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export { CostoFijoModal };
