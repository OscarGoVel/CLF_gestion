import { useNavigate } from 'react-router-dom';

const ROLES = ['Administrador', 'Operador', 'Almacenista', 'Solo lectura'];

const PERMISOS = [
  { modulo: 'Dashboard',         admin: true, operador: true,  almacenista: true,  lectura: true  },
  { modulo: 'Cotizaciones',      admin: true, operador: true,  almacenista: false, lectura: true  },
  { modulo: 'Compras',           admin: true, operador: true,  almacenista: false, lectura: false },
  { modulo: 'Stock',             admin: true, operador: true,  almacenista: true,  lectura: false },
  { modulo: 'Pre-inventario',    admin: true, operador: true,  almacenista: true,  lectura: false },
  { modulo: 'Facturas',          admin: true, operador: false, almacenista: false, lectura: false },
  { modulo: 'Estado de Cuenta',  admin: true, operador: false, almacenista: false, lectura: false },
  { modulo: 'Análisis',          admin: true, operador: true,  almacenista: false, lectura: true  },
  { modulo: 'Costos Fijos',      admin: true, operador: false, almacenista: false, lectura: false },
  { modulo: 'Estudio de Mercado',admin: true, operador: true,  almacenista: false, lectura: false },
  { modulo: 'Catálogos',         admin: true, operador: true,  almacenista: false, lectura: true  },
  { modulo: 'Admin',             admin: true, operador: false, almacenista: false, lectura: false },
];

export default function AdminPermisos() {
  const navigate = useNavigate();

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Administración</span>
        <span className="sep">/</span>
        <span>Permisos</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Permisos por rol</div>
          <div className="page-sub">Mapa de acceso a módulos según rol de usuario</div>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--ink-100)' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, fontSize: 13 }}>Módulo</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 13 }}>Administrador</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 13 }}>Operador</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 13 }}>Almacenista</th>
              <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600, fontSize: 13 }}>Solo lectura</th>
            </tr>
          </thead>
          <tbody>
            {PERMISOS.map(p => (
              <tr key={p.modulo} style={{ borderBottom: '1px solid var(--ink-100)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500, fontSize: 13 }}>{p.modulo}</td>
                {['admin', 'operador', 'almacenista', 'lectura'].map(rol => (
                  <td key={rol} style={{ padding: '10px 12px', textAlign: 'center', fontSize: 16 }}>
                    {p[rol] ? '✓' : <span style={{ color: 'var(--ink-200)' }}>—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16, fontSize: 13, color: 'var(--ink-400)' }}>
        Los permisos son configurados por el administrador del sistema. Para cambiar el rol de un usuario, ve a la sección de Usuarios.
      </div>
    </div>
  );
}
