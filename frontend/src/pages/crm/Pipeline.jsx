import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { Modal } from '../../components/Modal';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const ETAPAS = [
  { key: 'nuevo',       label: 'Nuevo',        color: '#8b5cf6' },
  { key: 'contactado',  label: 'Contactado',   color: '#3b82f6' },
  { key: 'propuesta',   label: 'Propuesta',    color: '#f59e0b' },
  { key: 'negociacion', label: 'Negociación',  color: '#f97316' },
  { key: 'ganado',      label: 'Ganado',       color: '#10b981' },
  { key: 'perdido',     label: 'Perdido',      color: '#ef4444' },
];

const PROBA_ETAPA = { nuevo: 10, contactado: 20, propuesta: 40, negociacion: 70, ganado: 100, perdido: 0 };

const BLANK = {
  nombre: '', contacto_nombre: '', contacto_email: '', contacto_tel: '',
  etapa: 'nuevo', valor_estimado: '', probabilidad: 10,
  notas: '', fecha_estimada_cierre: '', motivo_perdida: '',
};

export default function Pipeline() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/comercial/crm/prospectos');

  const [modal,    setModal]    = useState(false);
  const [editing,  setEditing]  = useState(null);   // null = nuevo
  const [form,     setForm]     = useState(BLANK);
  const [guardando, setGuardando] = useState(false);
  const [moverOpen, setMoverOpen] = useState(null);  // id del prospecto con select abierto

  const byEtapa = data?.by_etapa ?? {};
  const totales = data?.totales  ?? {};

  function abrirNuevo(etapa = 'nuevo') {
    setEditing(null);
    setForm({ ...BLANK, etapa, probabilidad: PROBA_ETAPA[etapa] ?? 10 });
    setModal(true);
  }

  function abrirEditar(p) {
    setEditing(p.id);
    setForm({
      nombre:                p.nombre ?? '',
      contacto_nombre:       p.contacto_nombre ?? '',
      contacto_email:        p.contacto_email  ?? '',
      contacto_tel:          p.contacto_tel    ?? '',
      etapa:                 p.etapa,
      valor_estimado:        p.valor_estimado  ?? '',
      probabilidad:          p.probabilidad    ?? 0,
      notas:                 p.notas           ?? '',
      fecha_estimada_cierre: p.fecha_estimada_cierre ?? '',
      motivo_perdida:        p.motivo_perdida  ?? '',
    });
    setModal(true);
  }

  async function handleGuardar() {
    if (!form.nombre.trim()) { toast.error('Nombre requerido'); return; }
    setGuardando(true);
    try {
      const payload = {
        ...form,
        valor_estimado: form.valor_estimado !== '' ? parseFloat(form.valor_estimado) : null,
        probabilidad:   parseInt(form.probabilidad) || 0,
        fecha_estimada_cierre: form.fecha_estimada_cierre || null,
        motivo_perdida: form.etapa === 'perdido' ? form.motivo_perdida || null : null,
      };
      if (editing) {
        await api.patch(`/api/comercial/crm/prospectos/${editing}`, payload);
        toast.success('Prospecto actualizado');
      } else {
        await api.post('/api/comercial/crm/prospectos', payload);
        toast.success('Prospecto creado');
      }
      setModal(false);
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGuardando(false);
    }
  }

  async function handleMover(id, nuevaEtapa) {
    setMoverOpen(null);
    try {
      await api.patch(`/api/comercial/crm/prospectos/${id}`, {
        etapa: nuevaEtapa,
        probabilidad: PROBA_ETAPA[nuevaEtapa] ?? 0,
      });
      refetch();
    } catch (e) {
      toast.error(e.message);
    }
  }

  async function handleEliminar(id) {
    if (!window.confirm('¿Eliminar este prospecto?')) return;
    try {
      await api.delete(`/api/comercial/crm/prospectos/${id}`);
      refetch();
    } catch (e) {
      toast.error(e.message);
    }
  }

  const valorPipeline = Object.entries(byEtapa)
    .filter(([k]) => !['ganado', 'perdido'].includes(k))
    .reduce((s, [, cards]) => s + cards.reduce((a, c) => a + (c.valor_estimado || 0), 0), 0);

  return (
    <>
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Pipeline</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Pipeline comercial</div>
          <div className="page-sub">
            {(data?.prospectos ?? []).length} prospectos ·
            {valorPipeline > 0 && ` Pipeline activo: ${MXN.format(valorPipeline)}`}
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => abrirNuevo()}>+ Nuevo prospecto</button>
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>
      ) : (
        <div style={{ display: 'flex', gap: 12, overflowX: 'auto', paddingBottom: 16, alignItems: 'flex-start' }}>
          {ETAPAS.map((et) => {
            const cards    = byEtapa[et.key] ?? [];
            const tot      = totales[et.key] ?? {};
            return (
              <div key={et.key} style={{ minWidth: 240, flexShrink: 0 }}>
                {/* Columna header */}
                <div style={{
                  padding: '8px 12px', borderRadius: '6px 6px 0 0',
                  background: et.color, color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                }}>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>{et.label}</span>
                  <span style={{ fontSize: 11, opacity: 0.85 }}>
                    {tot.count ?? 0}
                    {tot.valor > 0 && ` · ${MXN.format(tot.valor)}`}
                  </span>
                </div>

                {/* Cards */}
                <div style={{
                  background: 'var(--ink-50)', borderRadius: '0 0 6px 6px',
                  minHeight: 80, padding: 8, display: 'flex', flexDirection: 'column', gap: 8,
                }}>
                  {cards.map((p) => (
                    <div key={p.id} style={{
                      background: '#fff', borderRadius: 6, padding: 10,
                      border: '1px solid var(--ink-100)',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                    }}>
                      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 2 }}>{p.nombre}</div>
                      {p.cliente_nombre && (
                        <div style={{ fontSize: 11, color: 'var(--ink-500)', marginBottom: 4 }}>{p.cliente_nombre}</div>
                      )}
                      {p.contacto_nombre && (
                        <div style={{ fontSize: 11, color: 'var(--ink-600)' }}>{p.contacto_nombre}</div>
                      )}
                      {p.valor_estimado != null && (
                        <div style={{ fontSize: 12, fontWeight: 500, marginTop: 4, color: et.color }}>
                          {MXN.format(p.valor_estimado)}
                          {p.probabilidad > 0 && (
                            <span style={{ fontSize: 10, color: 'var(--ink-400)', marginLeft: 4 }}>
                              {p.probabilidad}%
                            </span>
                          )}
                        </div>
                      )}
                      {p.fecha_estimada_cierre && (
                        <div style={{ fontSize: 10, color: 'var(--ink-400)', marginTop: 3 }}>
                          Cierre: {p.fecha_estimada_cierre}
                        </div>
                      )}
                      <div style={{ marginTop: 8, display: 'flex', gap: 6, alignItems: 'center' }}>
                        <button className="btn btn-sm" style={{ fontSize: 10, padding: '2px 8px' }}
                          onClick={() => abrirEditar(p)}>
                          Editar
                        </button>
                        <div style={{ position: 'relative', flex: 1 }}>
                          <select
                            style={{ width: '100%', fontSize: 10, padding: '2px 4px',
                              border: '1px solid var(--ink-200)', borderRadius: 4, cursor: 'pointer' }}
                            value={p.etapa}
                            onChange={(e) => handleMover(p.id, e.target.value)}>
                            {ETAPAS.map((e2) => (
                              <option key={e2.key} value={e2.key}>{e2.label}</option>
                            ))}
                          </select>
                        </div>
                        <button className="btn-link-danger" style={{ fontSize: 10 }}
                          onClick={() => handleEliminar(p.id)}>×</button>
                      </div>
                    </div>
                  ))}
                  {!['ganado', 'perdido'].includes(et.key) && (
                    <button
                      style={{ background: 'none', border: '1px dashed var(--ink-200)',
                        borderRadius: 6, padding: '6px 0', fontSize: 11,
                        color: 'var(--ink-400)', cursor: 'pointer', width: '100%' }}
                      onClick={() => abrirNuevo(et.key)}>
                      + Agregar
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>

    {/* Modal nuevo / editar */}
    <Modal open={modal} onClose={() => setModal(false)}
      title={editing ? 'Editar prospecto' : 'Nuevo prospecto'} width={480}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="note" style={{ marginBottom: 4 }}>NOMBRE / EMPRESA *</div>
            <input className="input" autoFocus value={form.nombre}
              onChange={(e) => setForm(f => ({ ...f, nombre: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>CONTACTO</div>
            <input className="input" value={form.contacto_nombre}
              onChange={(e) => setForm(f => ({ ...f, contacto_nombre: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>EMAIL</div>
            <input className="input" type="email" value={form.contacto_email}
              onChange={(e) => setForm(f => ({ ...f, contacto_email: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>TELÉFONO</div>
            <input className="input" value={form.contacto_tel}
              onChange={(e) => setForm(f => ({ ...f, contacto_tel: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>ETAPA</div>
            <select className="input" value={form.etapa}
              onChange={(e) => setForm(f => ({
                ...f, etapa: e.target.value,
                probabilidad: PROBA_ETAPA[e.target.value] ?? f.probabilidad,
              }))}>
              {ETAPAS.map((e) => <option key={e.key} value={e.key}>{e.label}</option>)}
            </select>
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>PROBABILIDAD %</div>
            <input className="input" type="number" min="0" max="100"
              value={form.probabilidad}
              onChange={(e) => setForm(f => ({ ...f, probabilidad: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>VALOR ESTIMADO (MXN)</div>
            <input className="input" type="number" min="0" step="100"
              value={form.valor_estimado}
              onChange={(e) => setForm(f => ({ ...f, valor_estimado: e.target.value }))} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>FECHA ESTIMADA CIERRE</div>
            <input className="input" type="date" value={form.fecha_estimada_cierre}
              onChange={(e) => setForm(f => ({ ...f, fecha_estimada_cierre: e.target.value }))} />
          </div>
          {form.etapa === 'perdido' && (
            <div style={{ gridColumn: '1 / -1' }}>
              <div className="note" style={{ marginBottom: 4 }}>MOTIVO PÉRDIDA</div>
              <select className="input" value={form.motivo_perdida}
                onChange={(e) => setForm(f => ({ ...f, motivo_perdida: e.target.value }))}>
                <option value="">— Seleccionar —</option>
                <option value="precio">Precio</option>
                <option value="competidor">Competidor</option>
                <option value="tiempo">Tiempo de entrega</option>
                <option value="presupuesto">Sin presupuesto</option>
                <option value="sin_respuesta">Sin respuesta</option>
                <option value="otro">Otro</option>
              </select>
            </div>
          )}
          <div style={{ gridColumn: '1 / -1' }}>
            <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
            <textarea className="input" rows={2} value={form.notas}
              onChange={(e) => setForm(f => ({ ...f, notas: e.target.value }))} />
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn" onClick={() => setModal(false)}>Cancelar</button>
          <button className="btn btn-primary" disabled={guardando || !form.nombre.trim()}
            onClick={handleGuardar}>
            {guardando ? 'Guardando…' : editing ? 'Guardar cambios' : 'Crear prospecto'}
          </button>
        </div>
      </div>
    </Modal>
    </>
  );
}
