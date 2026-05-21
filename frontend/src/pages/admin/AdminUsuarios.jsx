import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { StatusBadge } from '../../components/StatusBadge';

export default function AdminUsuarios() {
  const navigate = useNavigate();
  const { data, loading } = useFetch('/api/ajustes/usuarios');
  const usuarios = data?.usuarios ?? data ?? [];

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
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
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Usuario</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Nombre</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Rol</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</td></tr>
            )}
            {!loading && Array.isArray(usuarios) && usuarios.length === 0 && (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: 'center', color: 'var(--ink-400)' }}>Sin usuarios</td></tr>
            )}
            {Array.isArray(usuarios) && usuarios.map(u => (
              <tr key={u.id || u.username} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px', fontSize: 13, fontFamily: 'monospace' }}>{u.username}</td>
                <td style={{ padding: '10px 12px', fontWeight: 500 }}>{u.nombre}</td>
                <td style={{ padding: '10px 12px' }}><StatusBadge status={u.rol} /></td>
                <td style={{ padding: '10px 12px' }}>
                  <StatusBadge status={u.activo ? 'Activo' : 'Inactivo'} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
