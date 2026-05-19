import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { exportCSV } from '../../lib/exportCSV';
import { Pill } from '../../components/Pill';
import { Stepper, buildSteps } from '../../components/Stepper';
import { NextRibbon, buildNextAction } from '../../components/NextRibbon';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { DataTable } from '../../components/DataTable';
import { SidePreview } from '../../components/SidePreview';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const FILTROS = [
  { label: 'Todos',                  value: '' },
  { label: 'Borrador',               value: 'Borrador' },
  { label: 'Pendiente',              value: 'Pendiente' },
  { label: 'Programada',             value: 'Programada' },
  { label: 'Parcialmente Entregada', value: 'Parcialmente Entregada' },
  { label: 'Entregada',              value: 'Entregada' },
  { label: 'Facturada',              value: 'Facturada' },
  { label: 'Pagada',                 value: 'Pagada' },
];

const COLUMNS = [
  { header: 'Folio',   key: 'folio',         className: 'folio', sortKey: 'folio' },
  { header: 'Fecha',   key: 'fecha',         sortKey: 'fecha',   style: { color: 'var(--ink-500)' } },
  { header: 'Cliente', key: 'cliente',       sortKey: 'cliente' },
  { header: 'Total',   className: 'num',     sortKey: 'total',
    render: (c) => c.total != null ? MXN.format(c.total) : '—' },
  { header: 'Estado',  render: (c) => <Pill status={c.estado} /> },
  { header: 'Prods.',  key: 'num_productos', width: 80, style: { color: 'var(--ink-500)', textAlign: 'center' } },
];

export default function CotList() {
  const navigate = useNavigate();
  const [filtros, setFiltros]       = useState([]);
  const [clientesFiltro, setClientesFiltro] = useState([]);
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [buscar, setBuscar]         = useState('');
  const [selected, setSelected]     = useState(null);
  const [pagina, setPagina]         = useState(1);

  const params = new URLSearchParams({ pagina });
  filtros.forEach((e) => params.append('estado', e));
  clientesFiltro.forEach((id) => params.append('cliente_id', id));
  if (fechaDesde) params.set('fecha_desde', fechaDesde);
  if (fechaHasta) params.set('fecha_hasta', fechaHasta);
  if (buscar) params.set('q', buscar);

  const { data, loading } = useFetch(`/api/cotizaciones?${params}`);
  const cotizaciones  = data?.cotizaciones   ?? [];
  const conteoEstado  = data?.conteo_estado  ?? {};
  const clientesLista = data?.clientes       ?? [];
  const total         = data?.total          ?? 0;
  const totalPags     = data?.total_pags     ?? 1;

  const sel = selected != null ? cotizaciones.find((c) => c.id === selected) : null;

  const { data: selDetail, loading: loadingDetail } = useFetch(
    selected != null ? `/api/cotizaciones/${selected}` : null
  );
  const partidas = selDetail?.partidas ?? [];

  function handleFiltro(v) { setFiltros(v); setPagina(1); }
  function handleClientesFiltro(v) { setClientesFiltro(v); setPagina(1); }
  function handleFechaDesde(e) { setFechaDesde(e.target.value); setPagina(1); }
  function handleFechaHasta(e) { setFechaHasta(e.target.value); setPagina(1); }
  function handleBuscar(e) { setBuscar(e.target.value); setPagina(1); }
  async function handlePdf(cotId, folio) {
    await api.download(`/api/cotizaciones/${cotId}/pdf`, `Cotizacion_${folio ?? cotId}.pdf`);
  }

  async function handleExportCsv() {
    const { cotizaciones: rows, totales } = await api.get('/api/cotizaciones/export');
    const filas = rows.map((c) => ({
      Folio:           c.folio          ?? '',
      Fecha:           c.fecha          ?? '',
      Cliente:         c.cliente        ?? '',
      Monto:           c.total          ?? 0,
      Estado:          c.estado         ?? '',
      'Orden de Compra': c.orden_compra ?? '',
      Factura:         c.numero_factura ?? '',
    }));
    const empty = { Folio: '', Fecha: '', Cliente: '', Monto: '', Estado: '', 'Orden de Compra': '', Factura: '' };
    filas.push(empty);
    filas.push({ ...empty, Cliente: 'Monto solicitado', Monto: totales.solicitado });
    filas.push({ ...empty, Cliente: 'Monto entregado',  Monto: totales.entregado  });
    filas.push({ ...empty, Cliente: 'Monto facturado',  Monto: totales.facturado  });
    filas.push({ ...empty, Cliente: 'Monto pagado',     Monto: totales.pagado     });
    exportCSV(['Folio', 'Fecha', 'Cliente', 'Monto', 'Estado', 'Orden de Compra', 'Factura'], filas, 'Cotizaciones');
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Cotizaciones</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Cotizaciones</div>
          <div className="page-sub">{total} registros en total</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={handleExportCsv}>
            Exportar CSV
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/cotizaciones/nueva')}>
            Nueva cotización
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <input
          className="input" style={{ maxWidth: 280 }}
          placeholder="Buscar folio o cliente…"
          value={buscar} onChange={handleBuscar}
        />
        <MultiSelectDropdown
          options={FILTROS.filter((o) => o.value !== '')}
          values={filtros}
          onChange={handleFiltro}
          counts={conteoEstado}
          placeholder="Estado…"
          labelPlural="estados"
        />
        <MultiSelectDropdown
          options={clientesLista.map((c) => ({ label: c.nombre, value: String(c.id) }))}
          values={clientesFiltro}
          onChange={handleClientesFiltro}
          placeholder="Cliente…"
          labelPlural="clientes"
        />
        <input
          className="input" type="date" style={{ maxWidth: 150 }}
          title="Fecha desde"
          value={fechaDesde} onChange={handleFechaDesde}
        />
        <span style={{ fontSize: 12, color: 'var(--ink-400)' }}>—</span>
        <input
          className="input" type="date" style={{ maxWidth: 150 }}
          title="Fecha hasta"
          value={fechaHasta} onChange={handleFechaHasta}
        />
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: sel ? '1fr 380px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'clip',
      }}>
        <div>
          <DataTable
            columns={COLUMNS}
            data={cotizaciones}
            loading={loading}
            selectedId={selected}
            onRowClick={(row) => setSelected(selected === row.id ? null : row.id)}
            footer={
              <>
                <span>Mostrando {cotizaciones.length} de {total}</span>
                <span style={{ display: 'flex', gap: 12 }}>
                  {pagina > 1 && (
                    <a className="linkish" onClick={() => setPagina((p) => p - 1)}>← anterior</a>
                  )}
                  {pagina < totalPags && (
                    <a className="linkish" onClick={() => setPagina((p) => p + 1)}>siguiente →</a>
                  )}
                </span>
              </>
            }
          />
        </div>

        {sel && (
          <div style={{ position: 'sticky', top: 16, alignSelf: 'start' }}>
            <SidePreview>
              <div className="note" style={{ marginBottom: 8 }}>SELECCIONADO</div>
              <div className="folio" style={{ fontFamily: 'var(--mono)', fontSize: 13 }}>{sel.folio}</div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-0.015em', marginTop: 4 }}>
                {sel.cliente}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 2 }}>
                {sel.tipo_cliente ?? ''} · {sel.fecha}
              </div>

              <div style={{
                display: 'flex', justifyContent: 'space-between',
                marginTop: 18, padding: '12px 0',
                borderTop: '1px solid var(--ink-200)', borderBottom: '1px solid var(--ink-200)',
              }}>
                <div>
                  <div className="note">TOTAL</div>
                  <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.02em', marginTop: 2 }}>
                    {sel.total != null ? MXN.format(sel.total) : '—'}
                  </div>
                </div>
                <div>
                  <div className="note">ESTADO</div>
                  <div style={{ marginTop: 4 }}><Pill status={sel.estado} /></div>
                </div>
                <div>
                  <div className="note">PARTIDAS</div>
                  <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.02em', marginTop: 2 }}>
                    {sel.num_productos ?? '—'}
                  </div>
                </div>
              </div>

              <div className="eyebrow" style={{ marginTop: 16 }}>Proceso</div>
              <div style={{ marginTop: 6 }}>
                <Stepper steps={buildSteps(sel)} />
              </div>

              <div className="eyebrow" style={{ marginTop: 16 }}>Acciones</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
                <button className="btn btn-sm btn-primary"
                  onClick={() => navigate(`/cotizaciones/${sel.id}`, { state: { ids: cotizaciones.map((c) => c.id) } })}>
                  Abrir
                </button>
                <button className="btn btn-sm" onClick={() => navigate(`/cotizaciones/${sel.id}/editar`)}>
                  Editar
                </button>
                <button className="btn btn-sm" onClick={() => handlePdf(sel.id, sel.folio)}>
                  PDF
                </button>
                <button className="btn btn-sm" onClick={() => setSelected(null)}>Cerrar ×</button>
              </div>

              <div className="eyebrow" style={{ marginTop: 16 }}>Productos</div>
              {loadingDetail ? (
                <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 6 }}>Cargando…</div>
              ) : (
                <div style={{ marginTop: 6 }}>
                  {partidas.map((p, i) => (
                    <div key={p.id} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                      gap: 8, fontSize: 11.5, padding: '5px 0',
                      borderBottom: i < partidas.length - 1 ? '1px solid var(--ink-100)' : 'none',
                    }}>
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.nombre || p.descripcion_libre}
                      </span>
                      <span style={{ color: 'var(--ink-500)', whiteSpace: 'nowrap', fontSize: 11 }}>
                        {p.cantidad} × {MXN.format(p.precio_unitario)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </SidePreview>
          </div>
        )}
      </div>
    </div>
  );
}
