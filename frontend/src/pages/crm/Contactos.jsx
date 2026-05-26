import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { ContextMenu } from '../../components/ContextMenu';

export default function Contactos() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/comercial/crm/contactos');
  const contactos = data?.contactos ?? [];
  const [showModal, setShowModal] = useState(false);
  const [q, setQ] = useState('');
  const [ctxMenu, setCtxMenu] = useState(null);
  const longPressTimer = useRef(null);

  const filtrados = q
    ? contactos.filter(c =>
        c.nombre.toLowerCase().includes(q.toLowerCase()) ||
        c.email.toLowerCase().includes(q.toLowerCase()) ||
        c.nombre_comercial.toLowerCase().includes(q.toLowerCase())
      )
    : contactos;

  function getCtxItems(c) {
    return [
      { type: 'item', label: c.opt_out ? 'Reactivar' : 'Registrar opt-out',
        danger: !c.opt_out,
        onClick: () => handleOptOut(c.id, c.opt_out) },
    ];
  }

  async function handleOptOut(id, actual) {
    try {
      await api.patch(`/api/comercial/crm/contactos/${id}`, { opt_out: !actual });
      refetch();
      toast.success(!actual ? 'Opt-out registrado' : 'Reactivado');
    } catch (e) {
      toast.error(e.message);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Contactos</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Contactos CRM</div>
          <div className="page-sub">Múltiples contactos por cliente para envíos dirigidos</div>
        </div>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          Agregar contacto
        </button>
      </div>

      <div style={{ marginBottom: 16 }}>
        <input
          className="input"
          style={{ maxWidth: 360 }}
          placeholder="Buscar por nombre, email o empresa…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              {['Nombre','Cargo','Email','Empresa','Principal','Opt-out','Acciones',''].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontSize: 12,
                                    fontWeight: 600, color: 'var(--ink-400)' }}
                    className={h === '' ? 'ctx-col' : ''}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && filtrados.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>
                {q ? 'Sin resultados' : 'Sin contactos — agrega el primero'}
              </td></tr>
            )}
            {filtrados.map(c => (
              <tr key={c.id} style={{ borderBottom: '1px solid var(--ink-100)' }}
                  onContextMenu={(e) => { e.preventDefault(); setCtxMenu({ x: e.clientX, y: e.clientY, row: c }); }}
                  onTouchStart={(e) => { const t = e.touches[0]; longPressTimer.current = setTimeout(() => setCtxMenu({ x: t.clientX, y: t.clientY, row: c }), 500); }}
                  onTouchMove={() => clearTimeout(longPressTimer.current)}
                  onTouchEnd={() => clearTimeout(longPressTimer.current)}
              >
                <td style={{ padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>{c.nombre}</td>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>{c.cargo ?? '—'}</td>
                <td style={{ padding: '10px 12px', fontSize: 13 }}>{c.email}</td>
                <td style={{ padding: '10px 12px', fontSize: 12, color: 'var(--ink-400)' }}>{c.nombre_comercial}</td>
                <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                  {c.es_principal ? '✓' : ''}
                </td>
                <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                  {c.opt_out
                    ? <span style={{ color: '#ef4444', fontSize: 12 }}>Sí</span>
                    : <span style={{ color: '#10b981', fontSize: 12 }}>No</span>}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <button
                    className="btn"
                    style={{ padding: '2px 8px', fontSize: 11 }}
                    onClick={() => handleOptOut(c.id, c.opt_out)}
                  >
                    {c.opt_out ? 'Reactivar' : 'Opt-out'}
                  </button>
                </td>
                <td className="ctx-col" onClick={(e) => { e.stopPropagation(); setCtxMenu({ x: e.clientX, y: e.clientY, row: c }); }}>
                  <button className="ctx-kebab" aria-label="Acciones">⋮</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showModal && (
        <ContactoModal
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); refetch(); toast.success('Contacto agregado'); }}
        />
      )}
      {ctxMenu && (
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

function ContactoModal({ onClose, onSaved }) {
  const { data: cliData } = useFetch('/api/catalogos/clientes');
  const clientes = cliData?.clientes ?? [];

  const [clienteId, setClienteId] = useState('');
  const [nombre,    setNombre]    = useState('');
  const [cargo,     setCargo]     = useState('');
  const [email,     setEmail]     = useState('');
  const [tel,       setTel]       = useState('');
  const [principal, setPrincipal] = useState(false);
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState('');

  async function handleSubmit(e) {
    e.preventDefault();
    if (!clienteId || !nombre.trim() || !email.trim()) {
      setError('Cliente, nombre y email son requeridos');
      return;
    }
    setSaving(true); setError('');
    try {
      await api.post('/api/comercial/crm/contactos', {
        cliente_id:  parseInt(clienteId),
        nombre:      nombre.trim(),
        cargo:       cargo.trim() || null,
        email:       email.trim(),
        telefono:    tel.trim() || null,
        es_principal: principal,
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
      <div className="card" style={{ width: 460, padding: 28 }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>Agregar contacto</div>
        {error && <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                               border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          {[
            ['Cliente *', <select className="input" style={{ width: '100%' }} value={clienteId} onChange={e => setClienteId(e.target.value)}>
              <option value="">— Seleccionar —</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre_comercial}</option>)}
            </select>],
            ['Nombre *', <input className="input" style={{ width: '100%' }} value={nombre} onChange={e => setNombre(e.target.value)} />],
            ['Cargo',    <input className="input" style={{ width: '100%' }} value={cargo}  onChange={e => setCargo(e.target.value)}  placeholder="Ej. Jefe de compras" />],
            ['Email *',  <input className="input" type="email" style={{ width: '100%' }} value={email} onChange={e => setEmail(e.target.value)} />],
            ['Teléfono', <input className="input" style={{ width: '100%' }} value={tel}   onChange={e => setTel(e.target.value)}   placeholder="+52 999..." />],
          ].map(([label, input]) => (
            <div key={label} style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>{label}</label>
              {input}
            </div>
          ))}
          <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" id="principal" checked={principal} onChange={e => setPrincipal(e.target.checked)} />
            <label htmlFor="principal" style={{ fontSize: 13 }}>Contacto principal de esta empresa</label>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Agregar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
