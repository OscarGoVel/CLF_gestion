import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const TIPOS = ['bienvenida', 'seguimiento', 'reactivacion', 'estacional'];

const TIPO_COLOR = {
  bienvenida:   '#10b981',
  seguimiento:  '#3b82f6',
  reactivacion: '#ef4444',
  estacional:   '#f59e0b',
};

export default function Secuencias() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/crm/secuencias');
  const secuencias = data?.secuencias ?? [];
  const [showModal,  setShowModal]  = useState(false);
  const [detalle,    setDetalle]    = useState(null);
  const [showInscrModal, setShowInscrModal] = useState(null);

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Secuencias</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Secuencias automáticas</div>
          <div className="page-sub">Cadenas de correos programadas por días de distancia</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          Nueva secuencia
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: 14 }}>
        {loading && <div style={{ padding: 24, color: 'var(--ink-400)' }}>Cargando…</div>}
        {!loading && secuencias.length === 0 && (
          <div className="card" style={{ padding: 24, color: 'var(--ink-400)', gridColumn: '1/-1' }}>
            Sin secuencias — crea la primera
          </div>
        )}
        {secuencias.map(s => (
          <div key={s.id} className="card" style={{ padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{s.nombre}</div>
              <span style={{
                background: `${TIPO_COLOR[s.tipo]}20`,
                color: TIPO_COLOR[s.tipo],
                padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
              }}>
                {s.tipo}
              </span>
            </div>
            {s.descripcion && (
              <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 8 }}>
                {s.descripcion}
              </div>
            )}
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--ink-500)', marginBottom: 12 }}>
              <span>{s.num_pasos} pasos</span>
              <span>{s.inscritos_activos} inscritos activos</span>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={async () => {
                  const r = await api.get(`/api/crm/secuencias/${s.id}`);
                  setDetalle(r);
                }}>
                Ver pasos
              </button>
              <button className="btn btn-primary" style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => setShowInscrModal(s)}>
                Inscribir clientes
              </button>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <SecuenciaModal
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); refetch(); toast.success('Secuencia creada'); }}
        />
      )}

      {detalle && (
        <DetallePasos secuencia={detalle} onClose={() => setDetalle(null)} />
      )}

      {showInscrModal && (
        <InscribirModal
          secuencia={showInscrModal}
          onClose={() => setShowInscrModal(null)}
          onSaved={() => { setShowInscrModal(null); refetch(); toast.success('Clientes inscritos'); }}
        />
      )}
    </div>
  );
}

function DetallePasos({ secuencia, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: 520, padding: 28, maxHeight: '80vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ fontWeight: 700, fontSize: 16 }}>{secuencia.nombre} — pasos</div>
          <button className="btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {(secuencia.pasos ?? []).map(p => (
            <div key={p.id} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: 'var(--ink-100)', color: 'var(--ink-600)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 700, fontSize: 12, flexShrink: 0,
              }}>
                {p.orden}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{p.asunto}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 2 }}>
                  Día +{p.dias_offset}
                  {p.plantilla_nombre && ` · Plantilla: ${p.plantilla_nombre}`}
                  {p.condicion_salida && ` · Sale si: ${p.condicion_salida}`}
                </div>
              </div>
            </div>
          ))}
          {(!secuencia.pasos || secuencia.pasos.length === 0) && (
            <div style={{ color: 'var(--ink-400)', fontSize: 13 }}>Sin pasos definidos</div>
          )}
        </div>
      </div>
    </div>
  );
}

function InscribirModal({ secuencia, onClose, onSaved }) {
  const { data } = useFetch('/api/catalogos/clientes');
  const clientes = data?.clientes ?? [];
  const [seleccionados, setSeleccionados] = useState([]);
  const [saving, setSaving] = useState(false);

  function toggle(id) {
    setSeleccionados(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  }

  async function handleSubmit() {
    if (seleccionados.length === 0) return;
    setSaving(true);
    try {
      await api.post(`/api/crm/secuencias/${secuencia.id}/inscribir`,
        { cliente_ids: seleccionados });
      onSaved();
    } catch (e) {
      toast.error(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: 480, padding: 28, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          Inscribir a "{secuencia.nombre}"
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 16 }}>
          Selecciona los clientes que iniciarán esta secuencia desde el Día 0
        </div>
        <div style={{ flex: 1, overflowY: 'auto', border: '1px solid var(--ink-100)',
                      borderRadius: 6, marginBottom: 16 }}>
          {clientes.map(c => (
            <label key={c.id} style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 12px', cursor: 'pointer', fontSize: 13,
              borderBottom: '1px solid var(--ink-100)',
            }}>
              <input type="checkbox"
                checked={seleccionados.includes(c.id)}
                onChange={() => toggle(c.id)} />
              {c.nombre_comercial}
            </label>
          ))}
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-500)', marginBottom: 14 }}>
          {seleccionados.length} cliente(s) seleccionado(s)
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleSubmit}
            disabled={saving || seleccionados.length === 0}>
            {saving ? 'Inscribiendo…' : 'Inscribir'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SecuenciaModal({ onClose, onSaved }) {
  const { data } = useFetch('/api/crm/plantillas');
  const plantillas = data?.plantillas ?? [];

  const [nombre, setNombre] = useState('');
  const [tipo,   setTipo]   = useState('seguimiento');
  const [desc,   setDesc]   = useState('');
  const [pasos,  setPasos]  = useState([
    { orden: 1, dias_offset: 0,  asunto: '', plantilla_id: '' },
    { orden: 2, dias_offset: 7,  asunto: '', plantilla_id: '' },
    { orden: 3, dias_offset: 14, asunto: '', plantilla_id: '' },
  ]);
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState('');

  function updatePaso(i, field, val) {
    setPasos(prev => prev.map((p, idx) => idx === i ? { ...p, [field]: val } : p));
  }

  function addPaso() {
    const last = pasos[pasos.length - 1];
    setPasos(prev => [...prev, {
      orden: prev.length + 1,
      dias_offset: (last?.dias_offset ?? 0) + 7,
      asunto: '', plantilla_id: '',
    }]);
  }

  function removePaso(i) {
    setPasos(prev => prev.filter((_, idx) => idx !== i)
      .map((p, idx) => ({ ...p, orden: idx + 1 })));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setError('Nombre requerido'); return; }
    const pasosValidos = pasos.filter(p => p.asunto.trim());
    if (pasosValidos.length === 0) { setError('Al menos un paso con asunto'); return; }
    setSaving(true); setError('');
    try {
      await api.post('/api/crm/secuencias', {
        nombre: nombre.trim(), tipo, descripcion: desc.trim() || null,
        pasos: pasosValidos.map(p => ({
          orden: p.orden,
          dias_offset: parseInt(p.dias_offset) || 0,
          asunto: p.asunto.trim(),
          plantilla_id: p.plantilla_id ? parseInt(p.plantilla_id) : null,
        })),
      });
      onSaved();
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: '90vw', maxWidth: 680, padding: 28,
                                    maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>Nueva secuencia</div>
        {error && <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                               border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Nombre *</label>
              <input className="input" style={{ width: '100%' }} value={nombre}
                onChange={e => setNombre(e.target.value)} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Tipo</label>
              <select className="input" style={{ width: '100%' }} value={tipo} onChange={e => setTipo(e.target.value)}>
                {TIPOS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Descripción</label>
            <input className="input" style={{ width: '100%' }} value={desc}
              onChange={e => setDesc(e.target.value)} placeholder="¿Para qué sirve esta secuencia?" />
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Pasos</span>
              <button type="button" className="btn" style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={addPaso}>+ Agregar paso</button>
            </div>
            {pasos.map((p, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '40px 80px 1fr 160px 28px',
                                    gap: 8, marginBottom: 8, alignItems: 'center' }}>
                <div style={{ textAlign: 'center', fontWeight: 700, fontSize: 13,
                              color: 'var(--ink-400)' }}>{p.orden}</div>
                <div>
                  <input className="input" type="number" min="0"
                    style={{ width: '100%', fontSize: 12 }}
                    value={p.dias_offset}
                    onChange={e => updatePaso(i, 'dias_offset', e.target.value)}
                    title="Días desde inicio" />
                  <div style={{ fontSize: 10, color: 'var(--ink-400)', textAlign: 'center' }}>día +</div>
                </div>
                <input className="input" style={{ width: '100%', fontSize: 12 }}
                  placeholder="Asunto del correo"
                  value={p.asunto}
                  onChange={e => updatePaso(i, 'asunto', e.target.value)} />
                <select className="input" style={{ width: '100%', fontSize: 12 }}
                  value={p.plantilla_id}
                  onChange={e => updatePaso(i, 'plantilla_id', e.target.value)}>
                  <option value="">Sin plantilla</option>
                  {plantillas.map(pt => <option key={pt.id} value={pt.id}>{pt.nombre}</option>)}
                </select>
                <button type="button" style={{ border: 'none', background: 'none',
                                              cursor: 'pointer', color: '#ef4444', fontWeight: 700 }}
                  onClick={() => removePaso(i)}>✕</button>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Crear secuencia'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
