import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const NAV_BY_ROLE = {
  admin: [
    { id: 'inicio',    label: 'Inicio',        path: '/dashboard' },
    { id: 'comercial', label: 'Comercial',      path: '/cotizaciones', sub: 'Cotizar · Vender' },
    { id: 'operacion', label: 'Operación',      path: '/stock',        sub: 'Comprar · Almacén' },
    { id: 'cobranza',  label: 'Cobranza',       path: '/facturas',     sub: 'Facturar · Cobrar' },
    { id: 'analisis',  label: 'Análisis',       path: '/analisis',     sub: 'Reportes · Costos' },
    { id: 'config',    label: 'Configuración',  path: '/admin',        sub: 'Maestros · Sistema' },
  ],
  operador: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard' },
    { id: 'comercial', label: 'Comercial', path: '/cotizaciones', sub: 'Cotizar · Vender' },
    { id: 'operacion', label: 'Operación', path: '/stock',        sub: 'Comprar · Almacén' },
    { id: 'cobranza',  label: 'Cobranza',  path: '/facturas',     sub: 'Facturar · Cobrar' },
    { id: 'analisis',  label: 'Análisis',  path: '/analisis' },
  ],
  almacenista: [
    { id: 'inicio',    label: 'Inicio',           path: '/dashboard' },
    { id: 'operacion', label: 'Operación',         path: '/stock', sub: 'Stock · Pre-inv · Recep.' },
    { id: 'catalogos', label: 'Productos',         path: '/catalogos/productos' },
  ],
  lectura: [
    { id: 'inicio',    label: 'Inicio',        path: '/dashboard' },
    { id: 'comercial', label: 'Comercial',     path: '/cotizaciones' },
    { id: 'catalogos', label: 'Catálogos',     path: '/catalogos' },
    { id: 'analisis',  label: 'Reportes',      path: '/analisis' },
  ],
};

const ROLE_LABEL = {
  admin: 'Admin',
  operador: 'Operador',
  almacenista: 'Almacén',
  lectura: 'Solo lectura',
};

/* Determines which nav group is active based on current path */
function activeId(items, pathname) {
  let best = null;
  let bestLen = 0;
  for (const it of items) {
    if (pathname.startsWith(it.path) && it.path.length > bestLen) {
      best = it.id;
      bestLen = it.path.length;
    }
  }
  return best;
}

export function Shell({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const role = user?.role ?? 'lectura';
  const items = NAV_BY_ROLE[role] ?? NAV_BY_ROLE.lectura;
  const current = activeId(items, location.pathname);

  return (
    <div className="shell">
      <div className="topbar">
        <Link to="/dashboard" className="brand">
          CLF<span>Gestión</span>
        </Link>

        <nav>
          {items.map((it) => (
            <Link
              key={it.id}
              to={it.path}
              className={current === it.id ? 'active' : ''}
            >
              <span style={{ fontSize: 12.5, fontWeight: current === it.id ? 500 : 400 }}>
                {it.label}
              </span>
              {it.sub && <span className="sub">{it.sub}</span>}
            </Link>
          ))}
        </nav>

        <div className="right">
          <span className="user">{user?.nombre ?? user?.username ?? '—'}</span>
          <span className="role-tag">{ROLE_LABEL[role] ?? role}</span>
          <span style={{ color: 'var(--ink-300)' }}>·</span>
          <span style={{ fontSize: 11.5 }}>{user?.empresa ?? 'CLF'}</span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={logout}
            style={{ marginLeft: 4 }}
          >
            Salir
          </button>
        </div>
      </div>

      <div className="scroll" style={{ background: 'var(--paper)' }}>
        {children}
      </div>
    </div>
  );
}
