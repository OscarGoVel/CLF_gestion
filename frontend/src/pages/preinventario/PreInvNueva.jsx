import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';

export default function PreInvNueva() {
  const navigate = useNavigate();

  const { data } = useFetch('/api/preinventario/sesiones');
  const sucursales = data?.sucursales ?? [];

  const [nombre, setNombre]           = useState('');
  const [tipo, setTipo]               = useState('parcial');
  const [sucursalId, setSucursalId]   = useState('');
  const [areaIds, setAreaIds]         = useState([]);
  const [saving, setSaving]           = useState(false);
  const [error, setError]             = useState('');

  const sucursal = sucursales.find(s => s.id === Number(sucursalId));
  const areas    = sucursal?.areas ?? [];

  function toggleArea(id) {
    setAreaIds(prev =>
      prev.includes(id) ? prev.filter(a => a !== id) : [...prev, id]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setError('El nombre es requerido'); return; }

    setSaving(true);
    setError('');
    try {
      const res = await api.post('/api/preinventario/sesiones', {
        nombre: nombre.trim(),
        tipo,
        sucursal_id: sucursalId ? Number(sucursalId) : null,
        area_ids: areaIds,
      });
      navigate(`/preinventario/${res.id}`);
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/preinventario')}>Pre-inventario</a>
        <span className="sep">/</span>
        <span>Nueva sesión</span>
      </div>

      <div className="page-header">
        <div className="page-title">Nueva sesión de conteo</div>
      </div>

      <div className="card" style={{ maxWidth: 540, padding: 28 }}>
        <form onSubmit={handleSubmit}>
          {error && (
            <div style={{ marginBottom: 16, padding: '10px 14px', background: '#fef2f2',
                          border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>
              {error}
            </div>
          )}

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>
              Nombre de la sesión *
            </label>
            <input
              className="input"
              style={{ width: '100%' }}
              value={nombre}
              onChange={e => setNombre(e.target.value)}
              placeholder="Ej. Conteo junio 2026 — Bodega A"
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Tipo</label>
            <div style={{ display: 'flex', gap: 16 }}>
              {['parcial', 'completo'].map(t => (
                <label key={t} style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input type="radio" name="tipo" value={t} checked={tipo === t} onChange={() => setTipo(t)} />
                  <span style={{ fontSize: 14, textTransform: 'capitalize' }}>{t}</span>
                </label>
              ))}
            </div>
          </div>

          {sucursales.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Sucursal</label>
              <select
                className="input"
                style={{ width: '100%' }}
                value={sucursalId}
                onChange={e => { setSucursalId(e.target.value); setAreaIds([]); }}
              >
                <option value="">Sin especificar</option>
                {sucursales.map(s => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </div>
          )}

          {areas.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 8 }}>
                Áreas a contar
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {areas.map(a => (
                  <label
                    key={a.id}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      padding: '6px 12px', borderRadius: 20, cursor: 'pointer',
                      border: `1px solid ${areaIds.includes(a.id) ? 'var(--primary)' : 'var(--ink-200)'}`,
                      background: areaIds.includes(a.id) ? 'var(--primary-light, #e8f5ee)' : '',
                      fontSize: 13,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={areaIds.includes(a.id)}
                      onChange={() => toggleArea(a.id)}
                      style={{ display: 'none' }}
                    />
                    {a.nombre}
                  </label>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={() => navigate('/preinventario')}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Creando…' : 'Iniciar sesión'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
