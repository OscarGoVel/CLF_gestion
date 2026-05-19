import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, useAuthState } from './hooks/useAuth';
import { Shell } from './components/Shell';

import Login       from './pages/Login';
import Dashboard   from './pages/Dashboard';
import CotList     from './pages/cotizaciones/CotList';
import CotDetalle  from './pages/cotizaciones/CotDetalle';
import CotNueva    from './pages/cotizaciones/CotNueva';
import CotEditar      from './pages/cotizaciones/CotEditar';
import CotExpediente  from './pages/cotizaciones/CotExpediente';
import ClienteList    from './pages/catalogos/ClienteList';
import ProductoList   from './pages/catalogos/ProductoList';
import ProductoNuevo  from './pages/catalogos/ProductoNuevo';
import ProveedorList  from './pages/catalogos/ProveedorList';
import CompraList    from './pages/compras/CompraList';
import CompraNueva   from './pages/compras/CompraNueva';
import CompraDetalle from './pages/compras/CompraDetalle';
import StockList   from './pages/stock/StockList';
import FacturaList    from './pages/facturas/FacturaList';
import FacturaImportar from './pages/facturas/FacturaImportar';
import Ajustes        from './pages/Ajustes';
import Analisis       from './pages/Analisis';

// Estado de Cuenta
import EstadoCuentaList   from './pages/estado-cuenta/EstadoCuentaList';
import EstadoCuentaDetalle from './pages/estado-cuenta/EstadoCuentaDetalle';

// Pre-inventario
import PreInvList   from './pages/preinventario/PreInvList';
import PreInvNueva  from './pages/preinventario/PreInvNueva';
import PreInvDetalle from './pages/preinventario/PreInvDetalle';

// Costos Fijos
import CostosFijosList   from './pages/costos-fijos/CostosFijosList';
import CostosFijosEditar from './pages/costos-fijos/CostosFijosEditar';

// Estudio de Mercado
import MercadoList   from './pages/estudio-mercado/MercadoList';
import MercadoDetalle from './pages/estudio-mercado/MercadoDetalle';

// CRM
import CrmDashboard from './pages/crm/CrmDashboard';
import Campanas     from './pages/crm/Campanas';
import Plantillas   from './pages/crm/Plantillas';
import Contactos    from './pages/crm/Contactos';
import Secuencias   from './pages/crm/Secuencias';
import Segmentos    from './pages/crm/Segmentos';
import RfmView      from './pages/crm/RfmView';

// Admin
import AdminUsuarios   from './pages/admin/AdminUsuarios';
import AdminPermisos   from './pages/admin/AdminPermisos';
import AdminUbicaciones from './pages/admin/AdminUbicaciones';
import AdminAuditoria  from './pages/admin/AdminAuditoria';

const Placeholder = ({ title }) => (
  <div className="page">
    <div className="page-header">
      <div><div className="page-title">{title}</div></div>
    </div>
    <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--ink-400)' }}>
      Módulo en construcción
    </div>
  </div>
);

function RequireAuth({ children }) {
  const token = sessionStorage.getItem('clf_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  const auth = useAuthState();

  return (
    <AuthContext.Provider value={auth}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            path="/*"
            element={
              <RequireAuth>
                <Shell>
                  <Routes>
                    <Route path="/"           element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard"  element={<Dashboard />} />

                    {/* Comercial */}
                    <Route path="/cotizaciones"            element={<CotList />} />
                    <Route path="/cotizaciones/nueva"      element={<CotNueva />} />
                    <Route path="/cotizaciones/:id/editar"      element={<CotEditar />} />
                    <Route path="/cotizaciones/:id/expediente" element={<CotExpediente />} />
                    <Route path="/cotizaciones/:id"            element={<CotDetalle />} />

                    {/* Operación */}
                    <Route path="/stock"             element={<StockList />} />
                    <Route path="/stock/*"           element={<StockList />} />
                    <Route path="/compras"           element={<CompraList />} />
                    <Route path="/compras/nueva"     element={<CompraNueva />} />
                    <Route path="/compras/:id"       element={<CompraDetalle />} />
                    <Route path="/preinventario"     element={<PreInvList />} />
                    <Route path="/preinventario/nueva" element={<PreInvNueva />} />
                    <Route path="/preinventario/:id" element={<PreInvDetalle />} />

                    {/* Cobranza */}
                    <Route path="/facturas"          element={<FacturaList />} />
                    <Route path="/facturas/importar" element={<FacturaImportar />} />
                    <Route path="/facturas/*"        element={<Placeholder title="Facturación" />} />
                    <Route path="/estado-cuenta"     element={<EstadoCuentaList />} />
                    <Route path="/estado-cuenta/:cliente_id" element={<EstadoCuentaDetalle />} />

                    {/* Análisis */}
                    <Route path="/analisis"          element={<Analisis />} />
                    <Route path="/analisis/*"        element={<Analisis />} />
                    <Route path="/costos-fijos"      element={<CostosFijosList />} />
                    <Route path="/costos-fijos/:id/editar" element={<CostosFijosEditar />} />
                    <Route path="/estudio-mercado"   element={<MercadoList />} />
                    <Route path="/estudio-mercado/:id" element={<MercadoDetalle />} />

                    {/* Catálogos */}
                    <Route path="/catalogos"          element={<Navigate to="/catalogos/clientes" replace />} />
                    <Route path="/catalogos/clientes"    element={<ClienteList />} />
                    <Route path="/catalogos/productos"   element={<ProductoList />} />
                    <Route path="/catalogos/productos/nuevo" element={<ProductoNuevo />} />
                    <Route path="/catalogos/proveedores" element={<ProveedorList />} />
                    <Route path="/catalogos/*"           element={<Placeholder title="Catálogos" />} />

                    {/* CRM */}
                    <Route path="/crm"              element={<CrmDashboard />} />
                    <Route path="/crm/campanas"     element={<Campanas />} />
                    <Route path="/crm/plantillas"   element={<Plantillas />} />
                    <Route path="/crm/contactos"    element={<Contactos />} />
                    <Route path="/crm/secuencias"   element={<Secuencias />} />
                    <Route path="/crm/segmentos"    element={<Segmentos />} />
                    <Route path="/crm/rfm"          element={<RfmView />} />

                    {/* Ajustes */}
                    <Route path="/ajustes" element={<Ajustes />} />

                    {/* Admin */}
                    <Route path="/admin/usuarios"    element={<AdminUsuarios />} />
                    <Route path="/admin/permisos"    element={<AdminPermisos />} />
                    <Route path="/admin/ubicaciones" element={<AdminUbicaciones />} />
                    <Route path="/admin/auditoria"   element={<AdminAuditoria />} />
                    <Route path="/admin/*"           element={<Placeholder title="Administración" />} />

                    <Route path="*" element={<Navigate to="/dashboard" replace />} />
                  </Routes>
                </Shell>
              </RequireAuth>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}
