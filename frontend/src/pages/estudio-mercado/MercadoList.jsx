import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/StatusBadge';
import { api } from '../../lib/apiClient';

function fmt(iso) {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

export default function MercadoList() {
  const navigate = useNavigate();
  const [filtroEstado, setFiltroEstado] = useState('');
  const [showNuevo, setShowNuevo]       = useState(false);

  const { data, loading, refetch } = useFetch(
    `/api/estudio-mercado${filtroEstado ? `?estado=${filtroEstado}` : ''}`
  );
  const estudios = data?.estudios ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Estudio de Mercado</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Estudio de Mercado</div>
          <div className="page-sub">Comparativa de precios por proveedor</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowNuevo(true)}>
          Nuevo estudio
        </button>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        {['', 'abierto', 'cerrado'].map(v => (
          <span
            key={v}
            onClick={() => setFiltroEstado(v)}
            style={{
              padding: '4px 14px', borderRadius: 20, cursor: 'pointer', fontSize: 13,
              border: `1px solid ${filtroEstado === v ? 'var(--primary)' : 'var(--ink-200)'}`,
              background: filtroEstado === v ? 'var(--primary-light, #e8f5ee)' : '',
              fontWeight: filtroEstado === v ? 600 : 400,
            }}
          >
            {v === '' ? 'Todos' : v.charAt(0).toUpperCase() + v.slice(1)}
          </span>
        ))}
      </div>

      {/* Tabla */}
      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Nombre</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Fecha</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Ítems</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, fontSize: 13 }}>Precios</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && estudios.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin estudios registrados</td></tr>
            )}
            {estudios.map(e => (
              <tr
                key={e.id}
                onClick={() => navigate(`/abastecimiento/estudios/${e.id}`)}
                style={{ borderBottom: '1px solid var(--ink-100)', cursor: 'pointer' }}
                onMouseEnter={ev => ev.currentTarget.style.background = 'var(--ink-50)'}
                onMouseLeave={ev => ev.currentTarget.style.background = ''}
              >
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>
                  {e.nombre}
                  {e.descripcion && (
                    <div style={{ fontSize: 11, color: 'var(--ink-400)' }}>{e.descripcion}</div>
                  )}
                </td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{fmt(e.fecha)}</td>
                <td style={{ padding: '10px 12px' }}><StatusBadge status={e.estado} /></td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{e.total_items ?? 0}</td>
                <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 13 }}>{e.total_cotizaciones ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal nuevo estudio */}
      {showNuevo && (
        <NuevoEstudioModal
          onClose={() => setShowNuevo(false)}
          onSaved={id => { setShowNuevo(false); navigate(`/abastecimiento/estudios/${id}`); }}
        />
      )}
    </div>
  );
}

function NuevoEstudioModal({ onClose, onSaved }) {
  const [nombre, setNombre]   = useState('');
  const [desc, setDesc]       = useState('');
  const [margen, setMargen]   = useState('35');
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setError('El nombre es requerido'); return; }
    setSaving(true); setError('');
    try {
      const res = await api.post('/api/estudio-mercado', {
        nombre: nombre.trim(),
        descripcion: desc.trim(),
        margen_pct: parseFloat(margen) / 100,
      });
      onSaved(res.id);
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
      <div className="card" style={{ width: 400, padding: 28 }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>Nuevo estudio de mercado</div>
        {error && (
          <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                        border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Nombre *</label>
            <input className="input" style={{ width: '100%' }} value={nombre}
              onChange={e => setNombre(e.target.value)} autoFocus />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Descripción</label>
            <input className="input" style={{ width: '100%' }} value={desc}
              onChange={e => setDesc(e.target.value)} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              Margen % (sobre precio mínimo)
            </label>
            <input className="input" type="number" style={{ width: 120 }} value={margen}
              onChange={e => setMargen(e.target.value)} min="0" max="200" step="0.1" />
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Creando…' : 'Crear estudio'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
