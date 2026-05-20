import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

export default function Segmentos() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/crm/segmentos');
  const segmentos = data?.segmentos ?? [];

  const [showModal, setShowModal]     = useState(false);
  const [editSeg,   setEditSeg]       = useState(null);
  const [asignarSeg, setAsignarSeg]   = useState(null);
  const [ctxMenu,   setCtxMenu]       = useState(null); // { x, y, segmento }

  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    window.addEventListener('click', close);
    window.addEventListener('contextmenu', close);
    return () => { window.removeEventListener('click', close); window.removeEventListener('contextmenu', close); };
  }, [ctxMenu]);

  function openCtx(e, s) {
    e.preventDefault();
    e.stopPropagation();
    setCtxMenu({ x: e.clientX, y: e.clientY, segmento: s });
  }

  async function handleEliminar(s) {
    if (!confirm(`¿Eliminar el segmento "${s.nombre}"? Se perderán todas las asignaciones.`)) return;
    try {
      await api.delete(`/api/crm/segmentos/${s.id}`);
      toast.success('Segmento eliminado');
      refetch();
    } catch (e) {
      toast.error(e.message);
    }
  }

  return (
    <div className="page" onClick={() => setCtxMenu(null)}>
      <div className="crumbs">
        <a onClick={() => navigate('/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Segmentos</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Segmentos</div>
          <div className="page-sub">Agrupa clientes para campañas dirigidas</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          Nuevo segmento
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
        {loading && <div style={{ padding: 24, color: 'var(--ink-400)' }}>Cargando…</div>}
        {!loading && segmentos.length === 0 && (
          <div className="card" style={{ padding: 24, color: 'var(--ink-400)', gridColumn: '1/-1' }}>
            Sin segmentos — crea el primero
          </div>
        )}
        {segmentos.map(s => (
          <div
            key={s.id}
            className="card"
            style={{ padding: 18, position: 'relative', userSelect: 'none' }}
            onContextMenu={e => openCtx(e, s)}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{s.nombre}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                  background: s.tipo === 'automatico' ? '#dbeafe' : '#f3f4f6',
                  color:      s.tipo === 'automatico' ? '#1e40af' : '#374151',
                }}>
                  {s.tipo}
                </span>
                <button
                  className="btn"
                  style={{ padding: '1px 7px', fontSize: 16, lineHeight: 1, minWidth: 0 }}
                  onClick={e => openCtx(e, s)}
                  title="Opciones"
                >
                  ⋯
                </button>
              </div>
            </div>
            {s.descripcion && (
              <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 8 }}>{s.descripcion}</div>
            )}
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink-600)' }}>
              {s.num_clientes} clientes
            </div>
          </div>
        ))}
      </div>

      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          onAsignar={() => { setCtxMenu(null); setAsignarSeg(ctxMenu.segmento); }}
          onEditar={() => { setCtxMenu(null); setEditSeg(ctxMenu.segmento); }}
          onEliminar={() => { const s = ctxMenu.segmento; setCtxMenu(null); handleEliminar(s); }}
        />
      )}

      {showModal && (
        <SegmentoModal
          onClose={() => setShowModal(false)}
          onSaved={(seg) => {
            setShowModal(false);
            refetch();
            toast.success('Segmento creado');
            setAsignarSeg(seg);
          }}
        />
      )}

      {editSeg && (
        <SegmentoModal
          segmento={editSeg}
          onClose={() => setEditSeg(null)}
          onSaved={() => { setEditSeg(null); refetch(); toast.success('Segmento actualizado'); }}
        />
      )}

      {asignarSeg && (
        <AsignarClientesModal
          segmento={asignarSeg}
          onClose={() => setAsignarSeg(null)}
          onSaved={() => { setAsignarSeg(null); refetch(); toast.success('Clientes asignados'); }}
        />
      )}
    </div>
  );
}

function ContextMenu({ x, y, onAsignar, onEditar, onEliminar }) {
  const ref = useRef(null);

  const style = {
    position: 'fixed',
    left: x,
    top: y,
    zIndex: 200,
    background: '#fff',
    border: '1px solid var(--ink-100)',
    borderRadius: 8,
    boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
    minWidth: 180,
    overflow: 'hidden',
  };

  const itemStyle = {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '9px 14px', fontSize: 13, cursor: 'pointer',
    transition: 'background 0.1s',
  };

  return (
    <div ref={ref} style={style} onClick={e => e.stopPropagation()}>
      <div style={itemStyle} onMouseEnter={e => e.currentTarget.style.background='#f5f5f5'}
           onMouseLeave={e => e.currentTarget.style.background=''}
           onClick={onAsignar}>
        <span>👥</span> Asignar clientes
      </div>
      <div style={{ ...itemStyle }} onMouseEnter={e => e.currentTarget.style.background='#f5f5f5'}
           onMouseLeave={e => e.currentTarget.style.background=''}
           onClick={onEditar}>
        <span>✏️</span> Editar
      </div>
      <div style={{ height: 1, background: 'var(--ink-100)' }} />
      <div style={{ ...itemStyle, color: '#dc2626' }}
           onMouseEnter={e => e.currentTarget.style.background='#fef2f2'}
           onMouseLeave={e => e.currentTarget.style.background=''}
           onClick={onEliminar}>
        <span>🗑</span> Eliminar
      </div>
    </div>
  );
}

function SegmentoModal({ segmento, onClose, onSaved }) {
  const isEdit = !!segmento;
  const [nombre, setNombre] = useState(segmento?.nombre ?? '');
  const [tipo,   setTipo]   = useState(segmento?.tipo   ?? 'manual');
  const [desc,   setDesc]   = useState(segmento?.descripcion ?? '');
  const [saving, setSaving] = useState(false);
  const [error,  setError]  = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setError('Nombre requerido'); return; }
    setSaving(true); setError('');
    try {
      if (isEdit) {
        await api.patch(`/api/crm/segmentos/${segmento.id}`, {
          nombre: nombre.trim(), tipo, descripcion: desc.trim() || null,
        });
        onSaved();
      } else {
        const res = await api.post('/api/crm/segmentos', {
          nombre: nombre.trim(), tipo, descripcion: desc.trim() || null,
        });
        onSaved({ id: res.id, nombre: nombre.trim(), tipo, descripcion: desc.trim() || null, num_clientes: 0 });
      }
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: 440, padding: 28 }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>
          {isEdit ? 'Editar segmento' : 'Nuevo segmento'}
        </div>
        {error && <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                               border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          {[
            ['Nombre *', <input className="input" style={{ width: '100%' }} value={nombre}
              onChange={e => setNombre(e.target.value)} placeholder="Ej. Clientes Sector Construcción" />],
            ['Tipo', <select className="input" style={{ width: '100%' }} value={tipo} onChange={e => setTipo(e.target.value)}>
              <option value="manual">Manual (asignación libre)</option>
              <option value="automatico">Automático (calculado)</option>
            </select>],
            ['Descripción', <input className="input" style={{ width: '100%' }} value={desc}
              onChange={e => setDesc(e.target.value)} placeholder="¿Qué caracteriza a este segmento?" />],
          ].map(([label, inp]) => (
            <div key={label} style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{label}</label>
              {inp}
            </div>
          ))}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : isEdit ? 'Guardar' : 'Crear'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function AsignarClientesModal({ segmento, onClose, onSaved }) {
  const { data } = useFetch('/api/catalogos/clientes');
  const clientes = data?.clientes ?? [];
  const [seleccionados, setSeleccionados] = useState([]);
  const [saving, setSaving] = useState(false);

  function toggle(id) {
    setSeleccionados(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  async function handleSubmit() {
    if (seleccionados.length === 0) return;
    setSaving(true);
    try {
      await api.post(`/api/crm/segmentos/${segmento.id}/clientes`, { cliente_ids: seleccionados });
      onSaved();
    } catch (e) {
      toast.error(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: 460, padding: 28, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          Asignar clientes a "{segmento.nombre}"
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 16 }}>
          Los clientes ya asignados no se duplicarán
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
          {seleccionados.length} seleccionado(s)
        </div>
        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleSubmit}
            disabled={saving || seleccionados.length === 0}>
            {saving ? 'Asignando…' : 'Asignar'}
          </button>
        </div>
      </div>
    </div>
  );
}
