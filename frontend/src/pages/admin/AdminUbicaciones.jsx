import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

export default function AdminUbicaciones() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/ajustes/ubicaciones');
  const sucursales = data?.sucursales ?? [];

  const [showForm, setShowForm] = useState(false);
  const [nombre, setNombre]     = useState('');
  const [desc, setDesc]         = useState('');
  const [saving, setSaving]     = useState(false);

  async function handleCrear(e) {
    e.preventDefault();
    if (!nombre.trim()) return;
    setSaving(true);
    try {
      await api.post('/api/ajustes/ubicaciones', { nombre: nombre.trim(), descripcion: desc.trim() });
      setNombre(''); setDesc(''); setShowForm(false);
      await refetch();
      toast.success('Ubicación creada');
    } catch (e) { toast.error(e.message); }
    finally { setSaving(false); }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Administración</span>
        <span className="sep">/</span>
        <span>Ubicaciones</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Ubicaciones</div>
          <div className="page-sub">Sucursales y áreas del almacén</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          Nueva sucursal
        </button>
      </div>

      {showForm && (
        <div className="card" style={{ padding: 20, marginBottom: 20, maxWidth: 400 }}>
          <form onSubmit={handleCrear}>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Nombre *</label>
              <input className="input" style={{ width: '100%' }} value={nombre}
                onChange={e => setNombre(e.target.value)} autoFocus />
            </div>
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Descripción</label>
              <input className="input" style={{ width: '100%' }} value={desc}
                onChange={e => setDesc(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Guardando…' : 'Crear'}
              </button>
              <button type="button" className="btn" onClick={() => setShowForm(false)}>Cancelar</button>
            </div>
          </form>
        </div>
      )}

      {loading ? (
        <div className="card" style={{ padding: 24 }}>Cargando…</div>
      ) : sucursales.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>
          Sin sucursales registradas
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {sucursales.map(s => (
            <div key={s.id} className="card" style={{ padding: 16 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>{s.nombre}</div>
              {s.descripcion && (
                <div style={{ fontSize: 13, color: 'var(--ink-400)', marginBottom: 8 }}>{s.descripcion}</div>
              )}
              {s.areas?.length > 0 && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {s.areas.map(a => (
                    <span key={a.id} style={{ padding: '3px 10px', border: '1px solid var(--ink-200)',
                                             borderRadius: 12, fontSize: 12 }}>
                      {a.nombre}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
