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
import DevolucionesList   from './pages/devoluciones/DevolucionesList';
import DevolucionNueva    from './pages/devoluciones/DevolucionNueva';
import DevolucionDetalle  from './pages/devoluciones/DevolucionDetalle';
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
import Pipeline     from './pages/crm/Pipeline';

// Cuentas por Pagar
import CuentasPagarList from './pages/cuentas-pagar/CuentasPagarList';

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
                    <Route path="/"       element={<Navigate to="/panel" replace />} />
                    <Route path="/panel"  element={<Dashboard />} />

                    {/* Gestión Comercial */}
                    <Route path="/comercial/cotizaciones"                      element={<CotList />} />
                    <Route path="/comercial/cotizaciones/nueva"                element={<CotNueva />} />
                    <Route path="/comercial/cotizaciones/:id/editar"           element={<CotEditar />} />
                    <Route path="/comercial/cotizaciones/:id/expediente"       element={<CotExpediente />} />
                    <Route path="/comercial/cotizaciones/:id"                  element={<CotDetalle />} />
                    <Route path="/comercial/clientes"                          element={<ClienteList />} />
                    <Route path="/comercial/devoluciones"                      element={<DevolucionesList />} />
                    <Route path="/comercial/devoluciones/nueva"                element={<DevolucionNueva />} />
                    <Route path="/comercial/devoluciones/:id"                  element={<DevolucionDetalle />} />
                    <Route path="/comercial/crm"                               element={<CrmDashboard />} />
                    <Route path="/comercial/crm/pipeline"                      element={<Pipeline />} />
                    <Route path="/comercial/crm/campanas"                      element={<Campanas />} />
                    <Route path="/comercial/crm/plantillas"                    element={<Plantillas />} />
                    <Route path="/comercial/crm/contactos"                     element={<Contactos />} />
                    <Route path="/comercial/crm/secuencias"                    element={<Secuencias />} />
                    <Route path="/comercial/crm/segmentos"                     element={<Segmentos />} />
                    <Route path="/comercial/crm/rfm"                           element={<RfmView />} />
                    <Route path="/comercial"                                    element={<Navigate to="/comercial/cotizaciones" replace />} />

                    {/* Abastecimiento */}
                    <Route path="/abastecimiento/compras"                      element={<CompraList />} />
                    <Route path="/abastecimiento/compras/nueva"                element={<CompraNueva />} />
                    <Route path="/abastecimiento/compras/:id"                  element={<CompraDetalle />} />
                    <Route path="/abastecimiento/proveedores"                  element={<ProveedorList />} />
                    <Route path="/abastecimiento/estudios"                     element={<MercadoList />} />
                    <Route path="/abastecimiento/estudios/:id"                 element={<MercadoDetalle />} />
                    <Route path="/abastecimiento"                              element={<Navigate to="/abastecimiento/compras" replace />} />

                    {/* Inventario */}
                    <Route path="/inventario/stock"                            element={<StockList />} />
                    <Route path="/inventario/stock/*"                          element={<StockList />} />
                    <Route path="/inventario/conteos"                          element={<PreInvList />} />
                    <Route path="/inventario/conteos/nueva"                    element={<PreInvNueva />} />
                    <Route path="/inventario/conteos/:id"                      element={<PreInvDetalle />} />
                    <Route path="/inventario/productos"                        element={<ProductoList />} />
                    <Route path="/inventario/productos/nuevo"                  element={<ProductoNuevo />} />
                    <Route path="/inventario"                                  element={<Navigate to="/inventario/stock" replace />} />

                    {/* Documentos fiscales */}
                    <Route path="/documentos/cfdi"                             element={<FacturaList />} />
                    <Route path="/documentos/cfdi/importar"                    element={<FacturaImportar />} />
                    <Route path="/documentos"                                  element={<Navigate to="/documentos/cfdi" replace />} />

                    {/* Finanzas */}
                    <Route path="/finanzas/cobranza"                           element={<EstadoCuentaList />} />
                    <Route path="/finanzas/cobranza/:cliente_id"               element={<EstadoCuentaDetalle />} />
                    <Route path="/finanzas/cuentas-pagar"                      element={<CuentasPagarList />} />
                    <Route path="/finanzas/costos-fijos"                       element={<CostosFijosList />} />
                    <Route path="/finanzas/costos-fijos/:id/editar"            element={<CostosFijosEditar />} />
                    <Route path="/finanzas"                                    element={<Navigate to="/finanzas/cobranza" replace />} />

                    {/* Reportes */}
                    <Route path="/reportes"                                    element={<Analisis />} />
                    <Route path="/reportes/*"                                  element={<Analisis />} />

                    {/* Ajustes */}
                    <Route path="/ajustes"                                     element={<Ajustes />} />

                    {/* Admin */}
                    <Route path="/admin/usuarios"    element={<AdminUsuarios />} />
                    <Route path="/admin/permisos"    element={<AdminPermisos />} />
                    <Route path="/admin/ubicaciones" element={<AdminUbicaciones />} />
                    <Route path="/admin/auditoria"   element={<AdminAuditoria />} />
                    <Route path="/admin/*"           element={<Placeholder title="Administración" />} />

                    <Route path="*" element={<Navigate to="/panel" replace />} />
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
