import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { ContextMenu } from '../../components/ContextMenu';

const ESTADOS = ['borrador', 'revision', 'aprobada', 'enviando', 'completada'];

const ESTADO_COLOR = {
  borrador:   { bg: '#f3f4f6', color: '#374151' },
  revision:   { bg: '#fef3c7', color: '#92400e' },
  aprobada:   { bg: '#dbeafe', color: '#1e40af' },
  enviando:   { bg: '#fef9c3', color: '#713f12' },
  completada: { bg: '#d1fae5', color: '#065f46' },
};

function EstadoPill({ estado }) {
  const s = ESTADO_COLOR[estado] ?? ESTADO_COLOR.borrador;
  return (
    <span style={{
      background: s.bg, color: s.color,
      padding: '2px 8px', borderRadius: 10,
      fontSize: 11, fontWeight: 600,
    }}>
      {estado}
    </span>
  );
}

export default function Campanas() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/crm/campanas');
  const campanas = data?.campanas ?? [];

  const [showModal, setShowModal] = useState(false);
  const [enviando, setEnviando]   = useState(null);
  const [ctxMenu, setCtxMenu]     = useState(null);
  const longPressTimer = useRef(null);

  function getCtxItems(c) {
    const estadoSubmenu = [];
    if (c.estado === 'borrador')   estadoSubmenu.push({ type: 'item', label: 'Aprobar', onClick: () => handleCambiarEstado(c.id, 'aprobada') });
    if (c.estado === 'aprobada')   estadoSubmenu.push({ type: 'item', label: 'Revertir a borrador', onClick: () => handleCambiarEstado(c.id, 'borrador') });
    if (c.estado === 'revision')   estadoSubmenu.push({ type: 'item', label: 'Aprobar', onClick: () => handleCambiarEstado(c.id, 'aprobada') });
    if (c.estado === 'enviando')   estadoSubmenu.push({ type: 'item', label: 'Marcar completada', onClick: () => handleCambiarEstado(c.id, 'completada') });

    const items = [];
    if (c.estado === 'aprobada') {
      items.push({ type: 'item', label: 'Enviar campaña', onClick: () => handleEnviar(c.id), disabled: enviando === c.id });
    }
    if (c.estado === 'completada') {
      items.push({ type: 'item', label: 'Calcular ROI', onClick: () => handleAtribuir(c.id) });
    }
    if (estadoSubmenu.length) {
      if (items.length) items.push({ type: 'divider' });
      items.push({ type: 'item', label: 'Cambiar estado', submenu: estadoSubmenu });
    }
    return items;
  }

  async function handleAtribuir(id) {
    try {
      const r = await api.post(`/api/crm/campanas/${id}/atribuir`, {});
      toast.success(`ROI calculado: ${r.insertados} ventas — $${r.total_atribuido.toLocaleString('es-MX')}`);
      refetch();
    } catch (e) { toast.error(e.message); }
  }

  async function handleEnviar(id) {
    if (!confirm('¿Generar envíos para esta campaña?')) return;
    setEnviando(id);
    try {
      const r = await api.post(`/api/crm/campanas/${id}/enviar`, {});
      toast.success(`${r.envios_generados} envíos generados`);
      refetch();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setEnviando(null);
    }
  }

  async function handleCambiarEstado(id, estado) {
    try {
      await api.patch(`/api/crm/campanas/${id}`, { estado });
      refetch();
      toast.success(`Estado actualizado: ${estado}`);
    } catch (e) {
      toast.error(e.message);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Campañas</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Campañas</div>
          <div className="page-sub">Crea, aprueba y envía campañas de correo</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          Nueva campaña
        </button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              {['Campaña','Segmento','Plantilla','Estado','Programada','Envíos','Apertura','ROI','Acciones',''].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: 'var(--ink-400)' }}
                    className={h === '' ? 'ctx-col' : ''}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && campanas.length === 0 && (
              <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>
                Sin campañas — crea la primera
              </td></tr>
            )}
            {campanas.map(c => {
              const tasaApertura = c.enviados > 0
                ? Math.round(c.aperturas / c.enviados * 100) : 0;
              return (
                <tr key={c.id} style={{ borderBottom: '1px solid var(--ink-100)' }}
                    onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, row: c }); }}
                    onTouchStart={(e) => { const t = e.touches[0]; longPressTimer.current = setTimeout(() => setCtxMenu({ x: t.clientX, y: t.clientY, row: c }), 500); }}
                    onTouchMove={() => clearTimeout(longPressTimer.current)}
                    onTouchEnd={() => clearTimeout(longPressTimer.current)}
                >
                  <td style={{ padding: '10px 12px', fontWeight: 500, fontSize: 13 }}>{c.nombre}</td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>
                    {c.segmento_nombre ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>
                    {c.plantilla_nombre ?? '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}><EstadoPill estado={c.estado} /></td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>
                    {c.fecha_programada
                      ? new Date(c.fecha_programada).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })
                      : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.total_envios}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13 }}>
                    {c.enviados > 0 ? `${tasaApertura}%` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12 }}>
                    {c.revenue_atribuido != null && c.revenue_atribuido > 0
                      ? <span style={{ color: '#166534', fontWeight: 600 }}>
                          {new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 }).format(c.revenue_atribuido)}
                        </span>
                      : <span style={{ color: 'var(--ink-300)' }}>—</span>
                    }
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <AccionesCampana
                      campana={c}
                      onEnviar={() => handleEnviar(c.id)}
                      onAprobar={() => handleCambiarEstado(c.id, 'aprobada')}
                      onBorrador={() => handleCambiarEstado(c.id, 'borrador')}
                      enviando={enviando === c.id}
                    />
                  </td>
                  <td className="ctx-col" onClick={(e) => { e.stopPropagation(); setCtxMenu({ x: e.clientX, y: e.clientY, row: c }); }}>
                    <button className="ctx-kebab" aria-label="Acciones">⋮</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showModal && (
        <CampanaModal
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); refetch(); toast.success('Campaña creada'); }}
        />
      )}
      {ctxMenu && getCtxItems(ctxMenu.row).length > 0 && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          items={getCtxItems(ctxMenu.row)}
          onClose={() => setCtxMenu(null)}
        />
      )}
    </div>
  );
}

function AccionesCampana({ campana, onEnviar, onAprobar, onBorrador, enviando }) {
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {campana.estado === 'borrador' && (
        <button className="btn" style={{ padding: '2px 8px', fontSize: 11 }} onClick={onAprobar}>
          Aprobar
        </button>
      )}
      {campana.estado === 'aprobada' && (
        <>
          <button className="btn btn-primary" style={{ padding: '2px 8px', fontSize: 11 }}
            onClick={onEnviar} disabled={enviando}>
            {enviando ? '…' : 'Enviar'}
          </button>
          <button className="btn" style={{ padding: '2px 8px', fontSize: 11 }} onClick={onBorrador}>
            Reabrir
          </button>
        </>
      )}
      {campana.estado === 'completada' && (
        <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>Completada</span>
      )}
    </div>
  );
}

function CampanaModal({ onClose, onSaved }) {
  const { data: platData } = useFetch('/api/crm/plantillas');
  const { data: segData  } = useFetch('/api/crm/segmentos');
  const plantillas = platData?.plantillas ?? [];
  const segmentos  = segData?.segmentos  ?? [];

  const [nombre, setNombre]     = useState('');
  const [asunto, setAsunto]     = useState('');
  const [platId, setPlatId]     = useState('');
  const [segId,  setSegId]      = useState('');
  const [fecha,  setFecha]      = useState('');
  const [notas,  setNotas]      = useState('');
  const [saving, setSaving]     = useState(false);
  const [error,  setError]      = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim() || !asunto.trim()) { setError('Nombre y asunto son requeridos'); return; }
    setSaving(true); setError('');
    try {
      await api.post('/api/crm/campanas', {
        nombre:          nombre.trim(),
        asunto:          asunto.trim(),
        plantilla_id:    platId   || null,
        segmento_id:     segId    || null,
        fecha_programada: fecha   || null,
        notas:           notas.trim() || null,
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
      <div className="card" style={{ width: 480, padding: 28, maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>Nueva campaña</div>
        {error && <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                               border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <Field label="Nombre *">
            <input className="input" style={{ width: '100%' }} value={nombre}
              onChange={e => setNombre(e.target.value)} placeholder="Ej. Campaña Mayo 2026" />
          </Field>
          <Field label="Asunto del correo *">
            <input className="input" style={{ width: '100%' }} value={asunto}
              onChange={e => setAsunto(e.target.value)} placeholder="Ej. Novedades de este mes" />
          </Field>
          <Field label="Plantilla">
            <select className="input" style={{ width: '100%' }} value={platId}
              onChange={e => setPlatId(e.target.value)}>
              <option value="">— Sin plantilla —</option>
              {plantillas.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </Field>
          <Field label="Segmento de destino">
            <select className="input" style={{ width: '100%' }} value={segId}
              onChange={e => setSegId(e.target.value)}>
              <option value="">— Todos los contactos activos —</option>
              {segmentos.map(s => <option key={s.id} value={s.id}>{s.nombre} ({s.num_clientes})</option>)}
            </select>
          </Field>
          <Field label="Fecha y hora de envío">
            <input className="input" type="datetime-local" style={{ width: '100%' }}
              value={fecha} onChange={e => setFecha(e.target.value)} />
          </Field>
          <Field label="Notas">
            <textarea className="input" style={{ width: '100%', minHeight: 64, resize: 'vertical' }}
              value={notas} onChange={e => setNotas(e.target.value)}
              placeholder="Observaciones para el equipo" />
          </Field>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Crear campaña'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{label}</label>
      {children}
    </div>
  );
}
