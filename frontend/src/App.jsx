import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthContext, useAuthState } from './hooks/useAuth';
import { Shell } from './components/Shell';

import Login       from './pages/Login';
import Dashboard   from './pages/Dashboard';
import CotList     from './pages/cotizaciones/CotList';
import CotDetalle  from './pages/cotizaciones/CotDetalle';
import CotNueva    from './pages/cotizaciones/CotNueva';
import ClienteList from './pages/catalogos/ClienteList';
import ProductoList from './pages/catalogos/ProductoList';
import CompraList  from './pages/compras/CompraList';
import CompraNueva from './pages/compras/CompraNueva';
import StockList   from './pages/stock/StockList';
import FacturaList    from './pages/facturas/FacturaList';
import FacturaImportar from './pages/facturas/FacturaImportar';

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
                    <Route path="/cotizaciones"       element={<CotList />} />
                    <Route path="/cotizaciones/nueva" element={<CotNueva />} />
                    <Route path="/cotizaciones/:id"   element={<CotDetalle />} />

                    {/* Operación */}
                    <Route path="/stock"          element={<StockList />} />
                    <Route path="/stock/*"        element={<StockList />} />
                    <Route path="/compras"         element={<CompraList />} />
                    <Route path="/compras/nueva"   element={<CompraNueva />} />
                    <Route path="/compras/*"       element={<Placeholder title="Detalle compra" />} />
                    <Route path="/preinventario/*" element={<Placeholder title="Pre-inventario" />} />

                    {/* Cobranza */}
                    <Route path="/facturas"           element={<FacturaList />} />
                    <Route path="/facturas/importar" element={<FacturaImportar />} />
                    <Route path="/facturas/*"         element={<Placeholder title="Facturación" />} />
                    <Route path="/estado-cuenta/*" element={<Placeholder title="Estado de cuenta" />} />

                    {/* Análisis */}
                    <Route path="/analisis/*"      element={<Placeholder title="Análisis" />} />

                    {/* Catálogos */}
                    <Route path="/catalogos"          element={<Navigate to="/catalogos/clientes" replace />} />
                    <Route path="/catalogos/clientes"  element={<ClienteList />} />
                    <Route path="/catalogos/productos" element={<ProductoList />} />
                    <Route path="/catalogos/*"         element={<Placeholder title="Catálogos" />} />

                    {/* Admin */}
                    <Route path="/admin/*" element={<Placeholder title="Administración" />} />

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
