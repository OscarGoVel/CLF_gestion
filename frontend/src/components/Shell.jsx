import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export const NAV_BY_ROLE = {
  admin: [
    { id: 'inicio',    label: 'Inicio',       path: '/dashboard',   paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial',    path: '/cotizaciones', paths: ['/cotizaciones', '/catalogos/clientes'] },
    { id: 'operacion', label: 'Operación',    path: '/compras',      paths: ['/compras', '/stock', '/preinventario', '/catalogos/productos', '/catalogos/proveedores'] },
    { id: 'cobranza',  label: 'Cobranza',     path: '/facturas',     paths: ['/facturas', '/estado-cuenta'] },
    { id: 'analisis',  label: 'Análisis',     path: '/analisis',     paths: ['/analisis', '/costos-fijos', '/estudio-mercado'] },
    { id: 'config',    label: 'Configuración', path: '/ajustes',     paths: ['/ajustes', '/admin'] },
  ],
  operador: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard',   paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial', path: '/cotizaciones', paths: ['/cotizaciones', '/catalogos/clientes'] },
    { id: 'operacion', label: 'Operación', path: '/compras',      paths: ['/compras', '/stock', '/preinventario', '/catalogos/productos'] },
    { id: 'cobranza',  label: 'Cobranza',  path: '/facturas',     paths: ['/facturas', '/estado-cuenta'] },
    { id: 'analisis',  label: 'Análisis',  path: '/analisis',     paths: ['/analisis'] },
  ],
  almacenista: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard', paths: ['/dashboard'] },
    { id: 'operacion', label: 'Operación', path: '/stock',     paths: ['/stock', '/preinventario', '/catalogos/productos'] },
  ],
  lectura: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard',    paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial', path: '/cotizaciones', paths: ['/cotizaciones', '/catalogos/clientes'] },
    { id: 'analisis',  label: 'Reportes',  path: '/analisis',     paths: ['/analisis'] },
  ],
};

const SUBNAV_BY_ROLE = {
  admin: {
    comercial: [
      { label: 'Cotizaciones', path: '/cotizaciones' },
      { label: 'Clientes',     path: '/catalogos/clientes' },
    ],
    operacion: [
      { label: 'Compras',        path: '/compras' },
      { label: 'Stock',          path: '/stock' },
      { label: 'Pre-inventario', path: '/preinventario' },
      { label: 'Productos',      path: '/catalogos/productos' },
      { label: 'Proveedores',    path: '/catalogos/proveedores' },
    ],
    cobranza: [
      { label: 'Facturas',         path: '/facturas' },
      { label: 'Estado de Cuenta', path: '/estado-cuenta' },
    ],
    analisis: [
      { label: 'Análisis',           path: '/analisis' },
      { label: 'Costos Fijos',       path: '/costos-fijos' },
      { label: 'Estudio de Mercado', path: '/estudio-mercado' },
    ],
    config: [
      { label: 'Ajustes',     path: '/ajustes' },
      { label: 'Usuarios',    path: '/admin/usuarios' },
      { label: 'Permisos',    path: '/admin/permisos' },
      { label: 'Ubicaciones', path: '/admin/ubicaciones' },
      { label: 'Auditoría',   path: '/admin/auditoria' },
    ],
  },
  operador: {
    comercial: [
      { label: 'Cotizaciones', path: '/cotizaciones' },
      { label: 'Clientes',     path: '/catalogos/clientes' },
    ],
    operacion: [
      { label: 'Compras',        path: '/compras' },
      { label: 'Stock',          path: '/stock' },
      { label: 'Pre-inventario', path: '/preinventario' },
      { label: 'Productos',      path: '/catalogos/productos' },
    ],
    cobranza: [
      { label: 'Facturas',         path: '/facturas' },
      { label: 'Estado de Cuenta', path: '/estado-cuenta' },
    ],
  },
  almacenista: {
    operacion: [
      { label: 'Stock',          path: '/stock' },
      { label: 'Pre-inventario', path: '/preinventario' },
      { label: 'Productos',      path: '/catalogos/productos' },
    ],
  },
  lectura: {
    comercial: [
      { label: 'Cotizaciones', path: '/cotizaciones' },
      { label: 'Clientes',     path: '/catalogos/clientes' },
    ],
  },
};

const ROLE_LABEL = {
  admin:          'Admin',
  operador:       'Operador',
  almacenista:    'Almacén',
  lectura:        'Solo lectura',
  Administrador:  'Admin',
  Operador:       'Operador',
  Almacenista:    'Almacén',
  'Solo lectura': 'Solo lectura',
};

function activeId(items, pathname) {
  let best = null;
  let bestLen = 0;
  for (const it of items) {
    for (const p of (it.paths ?? [it.path])) {
      if (pathname.startsWith(p) && p.length > bestLen) {
        best = it.id;
        bestLen = p.length;
      }
    }
  }
  return best;
}

const ROLE_KEY = {
  'Administrador': 'admin',
  'Operador':      'operador',
  'Almacenista':   'almacenista',
  'Solo lectura':  'lectura',
};

export function Shell({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const role = ROLE_KEY[user?.role] ?? 'lectura';
  const items = NAV_BY_ROLE[role] ?? NAV_BY_ROLE.lectura;
  const current = activeId(items, location.pathname);
  const subitems = (SUBNAV_BY_ROLE[role] ?? {})[current] ?? [];

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
              {it.label}
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

      {subitems.length > 0 && (
        <div className="subnav">
          {subitems.map((s) => (
            <Link
              key={s.path}
              to={s.path}
              className={location.pathname.startsWith(s.path) ? 'active' : ''}
            >
              {s.label}
            </Link>
          ))}
        </div>
      )}

      <div className="scroll" style={{ background: 'var(--paper)' }}>
        {children}
      </div>
    </div>
  );
}
