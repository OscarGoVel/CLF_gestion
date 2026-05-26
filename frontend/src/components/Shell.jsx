import { useState, useEffect, useRef, useCallback } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { ToastContainer } from './ToastContainer';
import { api } from '../lib/apiClient';

function Icon({ name, size = 16 }) {
  const paths = {
    panel:          <><rect x="2" y="2" width="5" height="5" rx="0.5"/><rect x="9" y="2" width="5" height="5" rx="0.5"/><rect x="2" y="9" width="5" height="5" rx="0.5"/><rect x="9" y="9" width="5" height="5" rx="0.5"/></>,
    comercial:      <><path d="M2 5h12M2 8h9M2 11h6"/></>,
    abastecimiento: <><rect x="1" y="6" width="8" height="7" rx="1"/><path d="M9 10l2.5-4H13l1.5 4"/><circle cx="3.5" cy="14" r="1"/><circle cx="12" cy="14" r="1"/></>,
    inventario:     <><path d="M8 2L14 5v6L8 14 2 11V5z"/></>,
    documentos:     <><path d="M3 2h7l3 3v9H3z"/><path d="M10 2v3h3"/><path d="M6 9h4M6 12h3"/></>,
    finanzas:       <><circle cx="8" cy="8" r="6"/><path d="M8 5v6M6.5 6.5a1.5 1.5 0 0 1 3 0c0 1.5-3 1.5-3 3a1.5 1.5 0 0 0 3 0"/></>,
    reportes:       <><path d="M2 13V9.5h2.5V13zm3.5 0V6h2.5v7zm3.5 0V2.5H11.5V13z"/></>,
    admin:          <><circle cx="8" cy="5.5" r="2.5"/><path d="M2 14c0-3 2.7-5 6-5s6 2 6 5"/></>,
    chevron:        <><path d="M5 7l3 3 3-3"/></>,
    menu:           <><path d="M2 4h12M2 8h12M2 12h12"/></>,
    x:              <><path d="M3 3l10 10M13 3L3 13"/></>,
    logout:         <><path d="M10 8H3M7 5l-3 3 3 3M10 3h3a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-3"/></>,
    search:         <><circle cx="7" cy="7" r="4"/><path d="M13 13l-3.5-3.5"/></>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none"
      stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      {paths[name]}
    </svg>
  );
}

const SIDEBAR_BY_ROLE = {
  admin: [
    {
      zone: 'OPERATIVO',
      items: [
        { id: 'panel', label: 'Panel principal', icon: 'panel', path: '/panel' },
        {
          id: 'comercial', label: 'Gestión Comercial', icon: 'comercial',
          children: [
            { label: 'Cotizaciones',   path: '/comercial/cotizaciones' },
            { label: 'Pipeline / CRM', path: '/comercial/crm' },
            { label: 'Clientes',       path: '/comercial/clientes' },
            { label: 'Devoluciones',   path: '/comercial/devoluciones' },
          ],
        },
        {
          id: 'abastecimiento', label: 'Abastecimiento', icon: 'abastecimiento',
          children: [
            { label: 'Órdenes de compra',   path: '/abastecimiento/compras' },
            { label: 'Proveedores',          path: '/abastecimiento/proveedores' },
            { label: 'Estudios de mercado', path: '/abastecimiento/estudios' },
          ],
        },
        {
          id: 'inventario', label: 'Inventario', icon: 'inventario',
          children: [
            { label: 'Stock',           path: '/inventario/stock' },
            { label: 'Conteos físicos', path: '/inventario/conteos' },
            { label: 'Productos',       path: '/inventario/productos' },
          ],
        },
        {
          id: 'documentos', label: 'Documentos fiscales', icon: 'documentos',
          children: [
            { label: 'CFDIs recibidos', path: '/documentos/cfdi' },
          ],
        },
      ],
    },
    {
      zone: 'FINANZAS',
      items: [
        {
          id: 'finanzas', label: 'Finanzas', icon: 'finanzas',
          children: [
            { label: 'Cobranza',            path: '/finanzas/cobranza' },
            { label: 'Pagos a proveedores', path: '/finanzas/cuentas-pagar' },
            { label: 'Costos fijos',        path: '/finanzas/costos-fijos' },
          ],
        },
      ],
    },
    {
      zone: 'ANÁLISIS',
      items: [
        { id: 'reportes', label: 'Reportes', icon: 'reportes', path: '/reportes' },
      ],
    },
  ],
  operador: [
    {
      zone: 'OPERATIVO',
      items: [
        { id: 'panel', label: 'Panel principal', icon: 'panel', path: '/panel' },
        {
          id: 'comercial', label: 'Gestión Comercial', icon: 'comercial',
          children: [
            { label: 'Cotizaciones',   path: '/comercial/cotizaciones' },
            { label: 'Pipeline / CRM', path: '/comercial/crm' },
            { label: 'Clientes',       path: '/comercial/clientes' },
            { label: 'Devoluciones',   path: '/comercial/devoluciones' },
          ],
        },
        {
          id: 'abastecimiento', label: 'Abastecimiento', icon: 'abastecimiento',
          children: [
            { label: 'Órdenes de compra',   path: '/abastecimiento/compras' },
            { label: 'Proveedores',          path: '/abastecimiento/proveedores' },
            { label: 'Estudios de mercado', path: '/abastecimiento/estudios' },
          ],
        },
        {
          id: 'inventario', label: 'Inventario', icon: 'inventario',
          children: [
            { label: 'Stock',           path: '/inventario/stock' },
            { label: 'Conteos físicos', path: '/inventario/conteos' },
            { label: 'Productos',       path: '/inventario/productos' },
          ],
        },
        {
          id: 'documentos', label: 'Documentos fiscales', icon: 'documentos',
          children: [
            { label: 'CFDIs recibidos', path: '/documentos/cfdi' },
          ],
        },
      ],
    },
    {
      zone: 'FINANZAS',
      items: [
        {
          id: 'finanzas', label: 'Finanzas', icon: 'finanzas',
          children: [
            { label: 'Cobranza',            path: '/finanzas/cobranza' },
            { label: 'Pagos a proveedores', path: '/finanzas/cuentas-pagar' },
            { label: 'Costos fijos',        path: '/finanzas/costos-fijos' },
          ],
        },
      ],
    },
  ],
  almacenista: [
    {
      zone: 'OPERATIVO',
      items: [
        { id: 'panel', label: 'Panel principal', icon: 'panel', path: '/panel' },
        {
          id: 'inventario', label: 'Inventario', icon: 'inventario',
          children: [
            { label: 'Stock',           path: '/inventario/stock' },
            { label: 'Conteos físicos', path: '/inventario/conteos' },
            { label: 'Productos',       path: '/inventario/productos' },
          ],
        },
      ],
    },
  ],
  lectura: [
    {
      zone: 'OPERATIVO',
      items: [
        { id: 'panel', label: 'Panel principal', icon: 'panel', path: '/panel' },
        {
          id: 'comercial', label: 'Gestión Comercial', icon: 'comercial',
          children: [
            { label: 'Cotizaciones', path: '/comercial/cotizaciones' },
          ],
        },
      ],
    },
    {
      zone: 'ANÁLISIS',
      items: [
        { id: 'reportes', label: 'Reportes', icon: 'reportes', path: '/reportes' },
      ],
    },
  ],
};

const ROLE_LABEL = {
  admin:       'Admin',
  operador:    'Operador',
  almacenista: 'Almacén',
  lectura:     'Solo lectura',
};

export const ROLE_KEY = {
  'Administrador': 'admin',
  'Operador':      'operador',
  'Almacenista':   'almacenista',
  'Solo lectura':  'lectura',
};

function activeModule(zones, pathname) {
  for (const zone of zones) {
    for (const item of zone.items) {
      if (item.path && pathname.startsWith(item.path)) return item.id;
      if (item.children) {
        for (const child of item.children) {
          if (pathname.startsWith(child.path)) return item.id;
        }
      }
    }
  }
  return null;
}

const TIPO_ICON = { cotizacion: '📋', cliente: '🏢', producto: '📦', proveedor: '🚚', compra: '🛒' };
const TIPO_LABEL_ES = { cotizacion: 'Cotización', cliente: 'Cliente', producto: 'Producto', proveedor: 'Proveedor', compra: 'Compra' };

function useGlobalSearch(navigate) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef(null);
  const timerRef = useRef(null);

  const close = useCallback(() => { setOpen(false); setQ(''); setResults([]); setCursor(0); }, []);

  useEffect(() => {
    function onKey(e) {
      const tag = document.activeElement?.tagName ?? '';
      const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || document.activeElement?.isContentEditable;
      if (e.key === 'Escape') { close(); return; }
      if (editing) return;
      if (e.key === '/') { e.preventDefault(); setOpen(true); }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [close]);

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  useEffect(() => {
    if (!q.trim() || q.trim().length < 2) { setResults([]); return; }
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await api.get(`/api/catalogos/buscar?q=${encodeURIComponent(q)}`);
        setResults(data.resultados ?? []);
        setCursor(0);
      } catch { setResults([]); }
      finally { setLoading(false); }
    }, 250);
    return () => clearTimeout(timerRef.current);
  }, [q]);

  function onResultKey(e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor(c => Math.min(c + 1, results.length - 1)); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); setCursor(c => Math.max(c - 1, 0)); }
    if (e.key === 'Enter' && results[cursor]) { goTo(results[cursor]); }
  }

  function goTo(r) {
    navigate(`${r.base_url}/${r.id}`);
    close();
  }

  return { open, setOpen, close, q, setQ, results, loading, cursor, setCursor, inputRef, onResultKey, goTo };
}

export function Shell({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const role = ROLE_KEY[user?.role] ?? 'lectura';
  const zones = SIDEBAR_BY_ROLE[role] ?? SIDEBAR_BY_ROLE.lectura;
  const currentModule = activeModule(zones, location.pathname);

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [expanded, setExpanded] = useState(() => new Set(currentModule ? [currentModule] : []));
  const search = useGlobalSearch(navigate);

  useEffect(() => {
    if (currentModule) setExpanded(prev => new Set([...prev, currentModule]));
    setMobileOpen(false);
  }, [currentModule]);

  function toggleExpand(id) {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    function onKey(e) {
      const tag = document.activeElement?.tagName ?? '';
      const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || document.activeElement?.isContentEditable;
      if (editing) return;
      if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        navigate('/comercial/cotizaciones/nueva');
      }
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [navigate]);

  const searchOverlay = search.open && (
    <div className="search-overlay" onClick={search.close}>
      <div className="search-modal" onClick={e => e.stopPropagation()}>
        <div className="search-input-wrap">
          <Icon name="search" size={15} />
          <input
            ref={search.inputRef}
            className="search-input"
            placeholder="Buscar clientes, productos, cotizaciones…"
            value={search.q}
            onChange={e => search.setQ(e.target.value)}
            onKeyDown={search.onResultKey}
          />
          <kbd className="search-esc" onClick={search.close}>Esc</kbd>
        </div>
        {search.results.length > 0 && (
          <ul className="search-results">
            {search.results.map((r, i) => (
              <li
                key={`${r.tipo}-${r.id}`}
                className={`search-result-item ${i === search.cursor ? 'active' : ''}`}
                onMouseEnter={() => search.setCursor(i)}
                onClick={() => search.goTo(r)}
              >
                <span className="sr-icon">{TIPO_ICON[r.tipo] ?? '🔍'}</span>
                <span className="sr-label">{r.label}</span>
                {r.sub && <span className="sr-sub">{r.sub}</span>}
                <span className="sr-tipo">{TIPO_LABEL_ES[r.tipo] ?? r.tipo}</span>
              </li>
            ))}
          </ul>
        )}
        {search.q.trim().length >= 2 && !search.loading && search.results.length === 0 && (
          <div className="search-empty">Sin resultados para "{search.q}"</div>
        )}
        <div className="search-hint">
          <span><kbd>↑↓</kbd> navegar</span>
          <span><kbd>Enter</kbd> abrir</span>
          <span><kbd>/</kbd> abrir buscador</span>
        </div>
      </div>
    </div>
  );

  const nav = (
    <>
      <div className="sb-brand">
        <Link to="/panel" className="sb-brand-link">
          CLF<span>Gestión</span>
        </Link>
        {!collapsed && (
          <button className="sb-toggle" onClick={() => setCollapsed(true)} title="Colapsar">
            <Icon name="x" size={14} />
          </button>
        )}
      </div>

      <button
        className={`sb-search ${collapsed ? 'sb-search--icon' : ''}`}
        onClick={() => search.setOpen(true)}
        title="Buscar (/)">
        <Icon name="search" size={14} />
        {!collapsed && <span>Buscar…</span>}
        {!collapsed && <kbd>/</kbd>}
      </button>

      <nav className="sb-nav">
        {zones.map((zone, zi) => (
          <div key={zi} className="sb-zone">
            {!collapsed && <div className="sb-zone-label">{zone.zone}</div>}
            {zone.items.map(item => {
              const isActive = currentModule === item.id;
              const isOpen = expanded.has(item.id);
              const hasChildren = !!item.children;

              return (
                <div key={item.id}>
                  {hasChildren ? (
                    <button
                      className={`sb-item ${isActive ? 'active' : ''}`}
                      onClick={() => toggleExpand(item.id)}
                      title={collapsed ? item.label : undefined}
                    >
                      <span className="sb-icon"><Icon name={item.icon} size={15} /></span>
                      {!collapsed && (
                        <>
                          <span className="sb-label">{item.label}</span>
                          <span className={`sb-chevron ${isOpen ? 'open' : ''}`}>
                            <Icon name="chevron" size={11} />
                          </span>
                        </>
                      )}
                    </button>
                  ) : (
                    <Link
                      to={item.path}
                      className={`sb-item ${isActive ? 'active' : ''}`}
                      title={collapsed ? item.label : undefined}
                    >
                      <span className="sb-icon"><Icon name={item.icon} size={15} /></span>
                      {!collapsed && <span className="sb-label">{item.label}</span>}
                    </Link>
                  )}

                  {hasChildren && !collapsed && isOpen && (
                    <div className="sb-children">
                      {item.children.map(child => (
                        <Link
                          key={child.path}
                          to={child.path}
                          className={`sb-child ${location.pathname.startsWith(child.path) ? 'active' : ''}`}
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      <div className="sb-footer">
        {role === 'admin' && (
          <Link
            to="/admin/usuarios"
            className={`sb-item ${location.pathname.startsWith('/admin') ? 'active' : ''}`}
            title={collapsed ? 'Administración' : undefined}
          >
            <span className="sb-icon"><Icon name="admin" size={15} /></span>
            {!collapsed && <span className="sb-label">Administración</span>}
          </Link>
        )}
        {!collapsed ? (
          <div className="sb-user">
            <div className="sb-user-name">{user?.nombre ?? user?.username ?? '—'}</div>
            <div className="sb-user-meta">
              <span className="role-tag">{ROLE_LABEL[role] ?? role}</span>
              <span style={{ color: 'var(--ink-400)' }}>·</span>
              <span>{user?.empresa ?? 'CLF'}</span>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={logout}>Salir</button>
          </div>
        ) : (
          <button className="sb-item" onClick={logout} title="Salir">
            <span className="sb-icon"><Icon name="logout" size={15} /></span>
          </button>
        )}
      </div>
    </>
  );

  return (
    <div className={`shell ${collapsed ? 'shell--collapsed' : ''}`}>
      {searchOverlay}
      {mobileOpen && (
        <div className="sb-backdrop" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`sidebar ${mobileOpen ? 'sidebar--open' : ''}`}>
        {nav}
        {collapsed && (
          <button
            className="sb-expand-btn"
            onClick={() => setCollapsed(false)}
            title="Expandir"
          >
            <Icon name="menu" size={15} />
          </button>
        )}
      </aside>

      <div className="shell-main">
        <div className="mobile-topbar">
          <button className="btn btn-ghost btn-sm" onClick={() => setMobileOpen(true)}>
            <Icon name="menu" size={17} />
          </button>
          <Link to="/panel" className="sb-brand-link">CLF<span>Gestión</span></Link>
          <button className="btn btn-ghost btn-sm" onClick={() => search.setOpen(true)} title="Buscar">
            <Icon name="search" size={17} />
          </button>
        </div>
        <div className="scroll">
          {children}
        </div>
      </div>

      <ToastContainer />
    </div>
  );
}
