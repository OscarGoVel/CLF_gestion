import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useFetch } from '../hooks/useFetch';
import { api } from '../lib/apiClient';
import { toast } from '../lib/toast';

const ROLES = ['Administrador', 'Operador', 'Almacenista', 'Solo lectura'];
const ROL_LABEL = { Administrador: 'Admin', Operador: 'Operador', Almacenista: 'Almacén', 'Solo lectura': 'Solo lectura' };

const USUARIO_EMPTY = { username: '', nombre: '', rol: 'Operador', password: '' };

// ── Sección: Mi cuenta ────────────────────────────────────────────────────────

function MiCuenta({ user }) {
  const { data: perfil, loading } = useFetch('/api/ajustes/perfil');

  const [nombre, setNombre]       = useState('');
  const [savingNombre, setSavingNombre] = useState(false);
  const [nombreMsg, setNombreMsg] = useState('');

  const [pwActual, setPwActual]   = useState('');
  const [pwNuevo, setPwNuevo]     = useState('');
  const [pwConf, setPwConf]       = useState('');
  const [savingPw, setSavingPw]   = useState(false);
  const [pwMsg, setPwMsg]         = useState('');

  useEffect(() => {
    if (perfil?.nombre) setNombre(perfil.nombre);
  }, [perfil]);

  const handleNombre = async (e) => {
    e.preventDefault();
    setSavingNombre(true);
    setNombreMsg('');
    try {
      await api.put('/api/ajustes/perfil', { nombre });
      setNombreMsg('Guardado');
      setTimeout(() => setNombreMsg(''), 2500);
    } catch (err) {
      setNombreMsg(err.message);
    } finally {
      setSavingNombre(false);
    }
  };

  const handlePassword = async (e) => {
    e.preventDefault();
    setPwMsg('');
    if (pwNuevo !== pwConf) { setPwMsg('Las contraseñas no coinciden'); return; }
    if (pwNuevo.length < 6) { setPwMsg('Mínimo 6 caracteres'); return; }
    setSavingPw(true);
    try {
      await api.post('/api/ajustes/password', {
        password_actual: pwActual,
        password_nuevo: pwNuevo,
      });
      setPwActual(''); setPwNuevo(''); setPwConf('');
      setPwMsg('Contraseña actualizada');
      setTimeout(() => setPwMsg(''), 3000);
    } catch (err) {
      setPwMsg(err.message);
    } finally {
      setSavingPw(false);
    }
  };

  if (loading) return <div className="page"><div className="page-state">Cargando…</div></div>;

  return (
    <div style={{ display: 'grid', gap: 20, maxWidth: 520 }}>
      {/* Info */}
      <div className="card" style={{ padding: 0 }}>
        <div className="card-h"><h3>Información de la cuenta</h3></div>
        {[
          ['Usuario', perfil?.username],
          ['Rol', ROL_LABEL[perfil?.rol] ?? perfil?.rol],
          ['Último acceso', perfil?.ultimo_acceso ? perfil.ultimo_acceso.slice(0, 10) : '—'],
        ].map(([k, v], i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 16px', borderTop: i > 0 ? '1px solid var(--ink-100)' : 'none',
          }}>
            <div className="note">{k.toUpperCase()}</div>
            <div style={{ fontSize: 13 }}>{v ?? '—'}</div>
          </div>
        ))}
      </div>

      {/* Cambiar nombre */}
      <div className="card">
        <div className="card-h"><h3>Nombre para mostrar</h3></div>
        <form onSubmit={handleNombre} style={{ padding: '0 0 4px' }}>
          <input
            className="input" style={{ width: '100%', marginBottom: 12 }}
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            required
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button className="btn btn-primary" disabled={savingNombre}>
              {savingNombre ? 'Guardando…' : 'Guardar nombre'}
            </button>
            {nombreMsg && (
              <span style={{ fontSize: 12.5, color: nombreMsg === 'Guardado' ? 'var(--accent)' : 'var(--danger)' }}>
                {nombreMsg}
              </span>
            )}
          </div>
        </form>
      </div>

      {/* Cambiar contraseña */}
      <div className="card">
        <div className="card-h"><h3>Contraseña</h3></div>
        <form onSubmit={handlePassword} style={{ display: 'grid', gap: 10, padding: '0 0 4px' }}>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>CONTRASEÑA ACTUAL</div>
            <input className="input" type="password" style={{ width: '100%' }}
              value={pwActual} onChange={(e) => setPwActual(e.target.value)} required />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>NUEVA CONTRASEÑA</div>
            <input className="input" type="password" style={{ width: '100%' }}
              value={pwNuevo} onChange={(e) => setPwNuevo(e.target.value)} required minLength={6} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>CONFIRMAR NUEVA</div>
            <input className="input" type="password" style={{ width: '100%' }}
              value={pwConf} onChange={(e) => setPwConf(e.target.value)} required />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
            <button className="btn btn-primary" disabled={savingPw}>
              {savingPw ? 'Guardando…' : 'Cambiar contraseña'}
            </button>
            {pwMsg && (
              <span style={{ fontSize: 12.5, color: pwMsg.includes('actualizada') ? 'var(--accent)' : 'var(--danger)' }}>
                {pwMsg}
              </span>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Sección: Empresa ──────────────────────────────────────────────────────────

function Empresa({ user }) {
  return (
    <div style={{ maxWidth: 520 }}>
      <div className="card" style={{ padding: 0 }}>
        <div className="card-h"><h3>Empresa activa</h3></div>
        {[
          ['Nombre', user?.empresa],
          ['ID', user?.empresa_id ?? '—'],
        ].map(([k, v], i) => (
          <div key={i} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 16px', borderTop: i > 0 ? '1px solid var(--ink-100)' : 'none',
          }}>
            <div className="note">{k.toUpperCase()}</div>
            <div style={{ fontSize: 13 }}>{v ?? '—'}</div>
          </div>
        ))}
      </div>
      <div className="card" style={{ marginTop: 16, padding: '14px 16px', fontSize: 12.5, color: 'var(--ink-500)' }}>
        La configuración avanzada de empresa (series de folio, IVA por defecto, términos del PDF)
        se administra directamente en el servidor. Contacta al administrador del sistema para realizar cambios.
      </div>
    </div>
  );
}

// ── Sección: Usuarios ─────────────────────────────────────────────────────────

function RowUsuario({ u, onEdit, onToggle, currentUid }) {
  return (
    <tr style={{ opacity: u.activo ? 1 : 0.5 }}>
      <td style={{ fontFamily: 'var(--mono)', fontSize: 12 }}>{u.username}</td>
      <td style={{ fontWeight: 500 }}>{u.nombre}</td>
      <td>
        <span style={{
          fontSize: 11, padding: '2px 7px', borderRadius: 3,
          background: 'var(--accent-soft)', color: 'var(--accent-ink)',
        }}>
          {ROL_LABEL[u.rol] ?? u.rol}
        </span>
      </td>
      <td style={{ fontSize: 11.5, color: u.activo ? 'var(--accent)' : 'var(--ink-400)' }}>
        {u.activo ? 'Activo' : 'Inactivo'}
      </td>
      <td style={{ fontSize: 12, color: 'var(--ink-500)' }}>
        {u.ultimo_acceso ? u.ultimo_acceso.slice(0, 10) : '—'}
      </td>
      <td>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn btn-sm" onClick={() => onEdit(u)}>Editar</button>
          {String(u.id) !== String(currentUid) && (
            <button className="btn btn-sm" onClick={() => onToggle(u.id)}>
              {u.activo ? 'Desactivar' : 'Activar'}
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function UsuarioForm({ initial, roles, onSave, onCancel }) {
  const isNew = !initial?.id;
  const [form, setForm] = useState(initial ?? USUARIO_EMPTY);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setErr('');
    try {
      if (isNew) {
        await api.post('/api/ajustes/usuarios', form);
      } else {
        await api.put(`/api/ajustes/usuarios/${initial.id}`, {
          nombre: form.nombre,
          rol: form.rol,
          password: form.password || undefined,
        });
      }
      onSave();
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
    }} onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="card" style={{ width: 420, padding: 28 }}>
        <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 20 }}>
          {isNew ? 'Nuevo usuario' : `Editar: ${initial.username}`}
        </div>
        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 12 }}>
          {isNew && (
            <div>
              <div className="note" style={{ marginBottom: 4 }}>USUARIO *</div>
              <input className="input" style={{ width: '100%' }}
                value={form.username} onChange={set('username')} required autoFocus />
            </div>
          )}
          <div>
            <div className="note" style={{ marginBottom: 4 }}>NOMBRE *</div>
            <input className="input" style={{ width: '100%' }}
              value={form.nombre} onChange={set('nombre')} required autoFocus={!isNew} />
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>ROL</div>
            <select className="input" style={{ width: '100%' }}
              value={form.rol} onChange={set('rol')}>
              {roles.map((r) => <option key={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <div className="note" style={{ marginBottom: 4 }}>
              {isNew ? 'CONTRASEÑA *' : 'NUEVA CONTRASEÑA (dejar vacío para no cambiar)'}
            </div>
            <input className="input" type="password" style={{ width: '100%' }}
              value={form.password} onChange={set('password')}
              required={isNew} minLength={isNew ? 6 : undefined} />
          </div>
          {err && <div style={{ color: 'var(--danger)', fontSize: 13 }}>{err}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="btn" onClick={onCancel}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Usuarios({ user }) {
  const [refetch, setRefetch] = useState(0);
  const { data, loading } = useFetch(`/api/ajustes/usuarios?_r=${refetch}`);
  const currentUid = user?.id;
  const [editando, setEditando] = useState(null);
  const [showNew, setShowNew]   = useState(false);

  const roles    = data?.roles ?? ROLES;
  const usuarios = data?.usuarios ?? [];

  const handleToggle = async (uid) => {
    const u = usuarios.find((x) => x.id === uid);
    try {
      await api.patch(`/api/ajustes/usuarios/${uid}/activo`);
      setRefetch((n) => n + 1);
      toast.success(u?.activo ? 'Usuario desactivado' : 'Usuario activado');
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleSaved = () => {
    setEditando(null);
    setShowNew(false);
    setRefetch((n) => n + 1);
    toast.success('Usuario guardado');
  };

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div className="eyebrow">Usuarios del sistema</div>
        <button className="btn btn-primary" onClick={() => setShowNew(true)}>Nuevo usuario</button>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 120 }}>Usuario</th>
                <th>Nombre</th>
                <th style={{ width: 110 }}>Rol</th>
                <th style={{ width: 80 }}>Estado</th>
                <th style={{ width: 110 }}>Último acceso</th>
                <th style={{ width: 120 }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <RowUsuario
                  key={u.id}
                  u={u}
                  onEdit={setEditando}
                  onToggle={handleToggle}
                  currentUid={currentUid}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showNew && (
        <UsuarioForm
          initial={USUARIO_EMPTY}
          roles={roles}
          onSave={handleSaved}
          onCancel={() => setShowNew(false)}
        />
      )}
      {editando && (
        <UsuarioForm
          initial={{ ...editando, password: '' }}
          roles={roles}
          onSave={handleSaved}
          onCancel={() => setEditando(null)}
        />
      )}
    </>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

const TABS = [
  { id: 'cuenta',   label: 'Mi cuenta' },
  { id: 'empresa',  label: 'Empresa',  adminOnly: true },
  { id: 'usuarios', label: 'Usuarios', adminOnly: true },
];

export default function Ajustes() {
  const { user } = useAuth();
  const isAdmin  = user?.role === 'Administrador';
  const tabs     = TABS.filter((t) => !t.adminOnly || isAdmin);
  const [tab, setTab] = useState('cuenta');

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Ajustes</div>
          <div className="page-sub">{user?.nombre ?? user?.username}</div>
        </div>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex', gap: 0, borderBottom: '1px solid var(--ink-200)',
        marginBottom: 24,
      }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: '8px 20px', fontSize: 13, fontWeight: tab === t.id ? 500 : 400,
              color: tab === t.id ? 'var(--ink-900)' : 'var(--ink-500)',
              background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'cuenta'   && <MiCuenta user={user} />}
      {tab === 'empresa'  && <Empresa user={user} />}
      {tab === 'usuarios' && isAdmin && <Usuarios user={user} />}
    </div>
  );
}
