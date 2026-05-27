import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { StatusBadge } from '../../components/StatusBadge';
import { Modal } from '../../components/Modal';

const ROLES = ['Administrador', 'Operador', 'Almacenista', 'Solo lectura'];

const EMPTY_FORM = { username: '', nombre: '', rol: 'Operador', password: '' };

export default function AdminUsuarios() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/ajustes/usuarios');
  const usuarios = data?.usuarios ?? data ?? [];

  const [modal, setModal]     = useState(null); // null | 'nuevo' | { ...usuario }
  const [form, setForm]       = useState(EMPTY_FORM);
  const [saving, setSaving]   = useState(false);
  const [error, setError]     = useState('');
  const [toggling, setToggling] = useState(null);

  function abrirNuevo() {
    setForm(EMPTY_FORM);
    setError('');
    setModal('nuevo');
  }

  function abrirEditar(u) {
    setForm({ username: u.username, nombre: u.nombre, rol: u.rol, password: '' });
    setError('');
    setModal(u);
  }

  function cerrar() { setModal(null); setError(''); }

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleGuardar(e) {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      if (modal === 'nuevo') {
        await api.post('/api/ajustes/usuarios', form);
      } else {
        const body = { nombre: form.nombre, rol: form.rol };
        if (form.password) body.password = form.password;
        await api.put(`/api/ajustes/usuarios/${modal.id}`, body);
      }
      cerrar();
      refetch();
    } catch (err) {
      setError(err?.detail ?? err?.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(u) {
    setToggling(u.id);
    try {
      await api.patch(`/api/ajustes/usuarios/${u.id}/activo`, {});
      refetch();
    } finally {
      setToggling(null);
    }
  }

  const esNuevo = modal === 'nuevo';

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Administración</span>
        <span className="sep">/</span>
        <span>Usuarios</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Usuarios</div>
          <div className="page-sub">Gestión de accesos al sistema</div>
        </div>
        <button className="btn btn-primary" onClick={abrirNuevo}>Nuevo usuario</button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Usuario</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Nombre</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Rol</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && Array.isArray(usuarios) && usuarios.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin usuarios</td></tr>
            )}
            {Array.isArray(usuarios) && usuarios.map((u) => (
              <tr key={u.id || u.username} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px', fontSize: 13, fontFamily: 'monospace' }}>{u.username}</td>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>{u.nombre}</td>
                <td style={{ padding: '10px 12px' }}><StatusBadge status={u.rol} /></td>
                <td style={{ padding: '10px 12px' }}>
                  <StatusBadge status={u.activo ? 'Activo' : 'Inactivo'} />
                </td>
                <td style={{ padding: '10px 12px', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                  <button className="btn btn-sm" onClick={() => abrirEditar(u)}>Editar</button>
                  <button
                    className="btn btn-sm"
                    style={{ color: u.activo ? 'var(--color-danger)' : 'var(--color-success)' }}
                    disabled={toggling === u.id}
                    onClick={() => handleToggle(u)}
                  >
                    {toggling === u.id ? '…' : u.activo ? 'Desactivar' : 'Activar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={!!modal} onClose={cerrar} title={esNuevo ? 'Nuevo usuario' : 'Editar usuario'}>
        <form onSubmit={handleGuardar} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <label style={{ fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Usuario</div>
            <input
              className="input" name="username" value={form.username}
              onChange={handleChange} required disabled={!esNuevo}
              placeholder="ej. juan.perez" style={{ width: '100%' }}
            />
          </label>
          <label style={{ fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Nombre completo</div>
            <input
              className="input" name="nombre" value={form.nombre}
              onChange={handleChange} required placeholder="ej. Juan Pérez"
              style={{ width: '100%' }}
            />
          </label>
          <label style={{ fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Rol</div>
            <select className="input" name="rol" value={form.rol} onChange={handleChange} style={{ width: '100%' }}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 13 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              Contraseña{!esNuevo && <span style={{ fontWeight: 400, color: 'var(--ink-400)' }}> (dejar vacío para no cambiar)</span>}
            </div>
            <input
              className="input" name="password" type="password"
              value={form.password} onChange={handleChange}
              required={esNuevo} minLength={6}
              placeholder={esNuevo ? 'Mínimo 6 caracteres' : '••••••'}
              style={{ width: '100%' }}
            />
          </label>
          {error && <div style={{ fontSize: 13, color: 'var(--color-danger)' }}>{error}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button type="button" className="btn" onClick={cerrar} disabled={saving}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : esNuevo ? 'Crear usuario' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
