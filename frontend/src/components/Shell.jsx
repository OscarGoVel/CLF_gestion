import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { MobileNav } from './MobileNav';
import { ToastContainer } from './ToastContainer';

const MODULE_COLOR = {
  inicio:       '#10b981',
  comercial:    '#3b82f6',
  operacion:    '#f59e0b',
  stock:        '#f59e0b',
  preinventario:'#f59e0b',
  cobranza:     '#14b8a6',
  catalogos:    '#6b7280',
  analisis:     '#8b5cf6',
  crm:          '#ec4899',
  config:       '#64748b',
};

export const NAV_BY_ROLE = {
  admin: [
    { id: 'inicio',    label: 'Inicio',        path: '/dashboard',   paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial',      path: '/cotizaciones', paths: ['/cotizaciones'] },
    { id: 'operacion', label: 'Operación',      path: '/compras',      paths: ['/compras', '/stock', '/preinventario', '/devoluciones', '/cuentas-pagar'] },
    { id: 'cobranza',  label: 'Cobranza',       path: '/facturas',     paths: ['/facturas', '/estado-cuenta'] },
    { id: 'catalogos', label: 'Catálogos',      path: '/catalogos',    paths: ['/catalogos'] },
    { id: 'analisis',  label: 'Análisis',       path: '/analisis',     paths: ['/analisis', '/costos-fijos', '/estudio-mercado'] },
    { id: 'crm',       label: 'CRM',            path: '/crm',          paths: ['/crm'] },
    { id: 'config',    label: 'Configuración',  path: '/ajustes',      paths: ['/ajustes', '/admin'] },
  ],
  operador: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard',   paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial', path: '/cotizaciones', paths: ['/cotizaciones'] },
    { id: 'operacion', label: 'Operación', path: '/compras',      paths: ['/compras', '/stock', '/preinventario', '/devoluciones', '/cuentas-pagar'] },
    { id: 'cobranza',  label: 'Cobranza',  path: '/facturas',     paths: ['/facturas', '/estado-cuenta'] },
    { id: 'catalogos', label: 'Catálogos', path: '/catalogos',    paths: ['/catalogos'] },
    { id: 'analisis',  label: 'Análisis',  path: '/analisis',     paths: ['/analisis'] },
    { id: 'crm',       label: 'CRM',       path: '/crm',          paths: ['/crm'] },
  ],
  almacenista: [
    { id: 'inicio',        label: 'Inicio',        path: '/dashboard',    paths: ['/dashboard'] },
    { id: 'stock',         label: 'Stock',          path: '/stock',        paths: ['/stock'] },
    { id: 'preinventario', label: 'Pre-inventario', mobileLabel: 'Pre-inv', path: '/preinventario', paths: ['/preinventario'] },
    { id: 'catalogos',     label: 'Catálogos',      path: '/catalogos',    paths: ['/catalogos'] },
  ],
  lectura: [
    { id: 'inicio',    label: 'Inicio',    path: '/dashboard',    paths: ['/dashboard'] },
    { id: 'comercial', label: 'Comercial', path: '/cotizaciones', paths: ['/cotizaciones'] },
    { id: 'analisis',  label: 'Reportes',  path: '/analisis',     paths: ['/analisis'] },
  ],
};

const SUBNAV_BY_ROLE = {
  admin: {
    comercial: [
      { label: 'Cotizaciones', path: '/cotizaciones' },
    ],
    operacion: [
      { label: 'Compras',        path: '/compras' },
      { label: 'Stock',          path: '/stock' },
      { label: 'Pre-inventario', path: '/preinventario' },
      { label: 'Devoluciones',      path: '/devoluciones' },
      { label: 'Cuentas por Pagar', path: '/cuentas-pagar' },
    ],
    cobranza: [
      { label: 'Facturas',         path: '/facturas' },
      { label: 'Estado de Cuenta', path: '/estado-cuenta' },
    ],
    catalogos: [
      { label: 'Clientes',    path: '/catalogos/clientes' },
      { label: 'Productos',   path: '/catalogos/productos' },
      { label: 'Proveedores', path: '/catalogos/proveedores' },
    ],
    analisis: [
      { label: 'Análisis',           path: '/analisis' },
      { label: 'Costos Fijos',       path: '/costos-fijos' },
      { label: 'Estudio de Mercado', path: '/estudio-mercado' },
    ],
    crm: [
      { label: 'Dashboard',  path: '/crm' },
      { label: 'Pipeline',   path: '/crm/pipeline' },
      { label: 'Campañas',   path: '/crm/campanas' },
      { label: 'Plantillas', path: '/crm/plantillas' },
      { label: 'Contactos',  path: '/crm/contactos' },
      { label: 'Secuencias', path: '/crm/secuencias' },
      { label: 'Segmentos',  path: '/crm/segmentos' },
      { label: 'RFM',        path: '/crm/rfm' },
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
    ],
    operacion: [
      { label: 'Compras',        path: '/compras' },
      { label: 'Stock',          path: '/stock' },
      { label: 'Pre-inventario', path: '/preinventario' },
      { label: 'Devoluciones',      path: '/devoluciones' },
      { label: 'Cuentas por Pagar', path: '/cuentas-pagar' },
    ],
    cobranza: [
      { label: 'Facturas',         path: '/facturas' },
      { label: 'Estado de Cuenta', path: '/estado-cuenta' },
    ],
    catalogos: [
      { label: 'Clientes',  path: '/catalogos/clientes' },
      { label: 'Productos', path: '/catalogos/productos' },
    ],
    crm: [
      { label: 'Dashboard',  path: '/crm' },
      { label: 'Pipeline',   path: '/crm/pipeline' },
      { label: 'Campañas',   path: '/crm/campanas' },
      { label: 'Plantillas', path: '/crm/plantillas' },
      { label: 'Contactos',  path: '/crm/contactos' },
      { label: 'Secuencias', path: '/crm/secuencias' },
    ],
  },
  almacenista: {
    catalogos: [
      { label: 'Productos', path: '/catalogos/productos' },
    ],
  },
  lectura: {
    comercial: [
      { label: 'Cotizaciones', path: '/cotizaciones' },
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

export const ROLE_KEY = {
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

  const activeColor = MODULE_COLOR[current] ?? 'var(--accent)';

  return (
    <div className="shell">
      <div className="topbar">
        <Link to="/dashboard" className="brand">
          CLF<span>Gestión</span>
        </Link>

        <nav>
          {items.map((it) => {
            const isActive = current === it.id;
            const color = MODULE_COLOR[it.id] ?? 'var(--accent)';
            return (
              <Link
                key={it.id}
                to={it.path}
                className={isActive ? 'active' : ''}
                style={isActive ? { '--nav-color': color } : undefined}
              >
                {it.label}
              </Link>
            );
          })}
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
        <div className="subnav" style={{ '--subnav-color': activeColor }}>
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

      <div className="scroll">
        {children}
      </div>

      <MobileNav />
      <ToastContainer />
    </div>
  );
}
