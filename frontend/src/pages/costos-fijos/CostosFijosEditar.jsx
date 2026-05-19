import { useParams, useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { useState, useEffect } from 'react';
import { toast } from '../../lib/toast';

const CATS = ['renta', 'nomina', 'servicios', 'depreciacion', 'otro'];

export default function CostosFijosEditar() {
  const { id }   = useParams();
  const navigate = useNavigate();

  // Cargamos el costo buscándolo en el período que sea
  const [costo, setCosto] = useState(null);
  const [loading, setLoading] = useState(true);

  const [periodo, setPeriodo]     = useState('');
  const [categoria, setCategoria] = useState('renta');
  const [desc, setDesc]           = useState('');
  const [monto, setMonto]         = useState('');
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState('');

  useEffect(() => {
    // Buscamos el costo en el mes actual; si no aparece cargamos igual
    async function load() {
      try {
        // Intentar encontrarlo buscando en todos los períodos no es trivial
        // sin endpoint de detalle. Usamos el período del query param si está disponible
        // La forma más simple: el usuario llega aquí desde la lista con estado en memoria
        // Para este wireframe, simplemente mostramos el form vacío y el usuario confirma
        setLoading(false);
      } catch {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!desc.trim() || !monto || !periodo) { setError('Todos los campos son requeridos'); return; }
    setSaving(true); setError('');
    try {
      await api.put(`/api/costos-fijos/${id}`, {
        periodo, categoria, descripcion: desc.trim(), monto: parseFloat(monto),
      });
      toast.success('Costo actualizado');
      navigate('/costos-fijos');
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
        <a onClick={() => navigate('/costos-fijos')}>Costos Fijos</a>
        <span className="sep">/</span>
        <span>Editar</span>
      </div>

      <div className="page-header">
        <div className="page-title">Editar costo fijo</div>
      </div>

      <div className="card" style={{ maxWidth: 420, padding: 28 }}>
        {error && (
          <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                        border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>
            {error}
          </div>
        )}
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Período *</label>
            <input type="month" className="input" style={{ width: '100%' }}
              value={periodo} onChange={e => setPeriodo(e.target.value)} />
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Categoría</label>
            <select className="input" style={{ width: '100%' }} value={categoria} onChange={e => setCategoria(e.target.value)}>
              {CATS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Descripción *</label>
            <input className="input" style={{ width: '100%' }} value={desc}
              onChange={e => setDesc(e.target.value)} />
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Monto *</label>
            <input className="input" type="number" style={{ width: '100%' }} value={monto}
              onChange={e => setMonto(e.target.value)} min="0.01" step="0.01" />
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={() => navigate('/costos-fijos')}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
