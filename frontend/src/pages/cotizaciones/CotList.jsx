import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { exportCSV } from '../../lib/exportCSV';
import { StatusBadge } from '../../components/StatusBadge';
import { Stepper, buildSteps } from '../../components/Stepper';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { DataTable } from '../../components/DataTable';
import { SidePreview } from '../../components/SidePreview';
import { Historial } from '../../components/Historial';
import { ConfirmModal } from '../../components/ConfirmModal';
import { useRazonSocial } from '../../contexts/RazonSocialContext';

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
  { label: 'Cancelada',              value: 'Cancelada' },
];

function RsBadge({ nombre }) {
  if (!nombre || nombre === '—') return <span style={{ color: 'var(--ink-400)' }}>—</span>;
  const label = nombre.length > 18 ? nombre.slice(0, 18) + '…' : nombre;
  return <span title={nombre} style={{ fontSize: 11, color: 'var(--ink-500)' }}>{label}</span>;
}

export default function CotList() {
  const navigate = useNavigate();
  const { activeRS, razonSociales } = useRazonSocial();
  const multiRS = razonSociales.length > 1;

  const COLUMNS = [
    { header: 'Folio',   key: 'folio',         className: 'folio', sortKey: 'folio' },
    { header: 'Fecha',   key: 'fecha',         sortKey: 'fecha',   style: { color: 'var(--ink-500)' } },
    { header: 'Cliente', key: 'cliente',       sortKey: 'cliente' },
    { header: 'Total',   className: 'num',     sortKey: 'total',
      render: (c) => c.total != null ? MXN.format(c.total) : '—' },
    { header: 'Estado',  render: (c) => <StatusBadge status={c.estado} /> },
    { header: 'Prods.',  key: 'num_productos', width: 80, style: { color: 'var(--ink-500)', textAlign: 'center' } },
    ...(multiRS ? [{ header: 'RS', width: 140, render: (c) => <RsBadge nombre={c.razon_social_nombre} /> }] : []),
  ];
  const [filtros, setFiltros]       = useState([]);
  const [clientesFiltro, setClientesFiltro] = useState([]);
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [buscar, setBuscar]         = useState('');
  const [selected, setSelected]     = useState(null);
  const [pagina, setPagina]         = useState(1);
  const [confirmCancelarId, setConfirmCancelarId] = useState(null);
  const [cancelando, setCancelando] = useState(false);

  const params = new URLSearchParams({ pagina });
  filtros.forEach((e) => params.append('estado', e));
  clientesFiltro.forEach((id) => params.append('cliente_id', id));
  if (fechaDesde) params.set('fecha_desde', fechaDesde);
  if (fechaHasta) params.set('fecha_hasta', fechaHasta);
  if (buscar) params.set('q', buscar);
  if (activeRS != null) params.set('razon_social_id', activeRS);

  const { data, loading, refetch } = useFetch(`/api/comercial/cotizaciones?${params}`);
  const cotizaciones  = data?.cotizaciones   ?? [];
  const conteoEstado  = data?.conteo_estado  ?? {};
  const clientesLista = data?.clientes       ?? [];
  const total         = data?.total          ?? 0;
  const totalPags     = data?.total_pags     ?? 1;

  const sel = selected != null ? cotizaciones.find((c) => c.id === selected) : null;

  const { data: selDetail, loading: loadingDetail } = useFetch(
    selected != null ? `/api/comercial/cotizaciones/${selected}` : null
  );
  const partidas = selDetail?.partidas ?? [];

  function handleFiltro(v) { setFiltros(v); setPagina(1); }
  function handleClientesFiltro(v) { setClientesFiltro(v); setPagina(1); }
  function handleFechaDesde(e) { setFechaDesde(e.target.value); setPagina(1); }
  function handleFechaHasta(e) { setFechaHasta(e.target.value); setPagina(1); }
  function handleBuscar(e) { setBuscar(e.target.value); setPagina(1); }
  async function handlePdf(cotId, folio) {
    await api.download(`/api/comercial/cotizaciones/${cotId}/pdf`, `Cotizacion_${folio ?? cotId}.pdf`);
  }

  async function handleCancelarCot() {
    setCancelando(true);
    try {
      await api.patch(`/api/comercial/cotizaciones/${confirmCancelarId}/cancelar`, {});
      toast.success('Cotización cancelada');
      setConfirmCancelarId(null);
      if (selected === confirmCancelarId) setSelected(null);
      refetch();
    } finally {
      setCancelando(false);
    }
  }

  function getContextMenuItems(cot) {
    const ids = cotizaciones.map((c) => c.id);
    const bloqueada = ['Cancelada', 'Pagada'].includes(cot.estado);
    return [
      { type: 'item', label: 'Abrir detalle',
        onClick: () => navigate(`/comercial/cotizaciones/${cot.id}`, { state: { ids } }) },
      { type: 'item', label: 'Editar',
        disabled: bloqueada,
        onClick: () => navigate(`/comercial/cotizaciones/${cot.id}/editar`) },
      { type: 'item', label: 'Descargar PDF',
        onClick: () => handlePdf(cot.id, cot.folio) },
      { type: 'divider' },
      { type: 'item', label: 'Cancelar cotización', danger: true,
        disabled: bloqueada,
        onClick: () => setConfirmCancelarId(cot.id) },
    ];
  }

  async function handleExportCsv() {
    const COLS = ['Folio', 'Fecha', 'Cliente', 'Estado', 'OC', 'Factura', 'Código', 'Concepto', 'Unidad', 'Cantidad', 'Precio Unitario', 'Subtotal', 'IVA', 'Total Partida'];
    const { partidas: rows, totales } = await api.get('/api/comercial/cotizaciones/export');
    const filas = rows.map((r) => ({
      Folio:             r.folio              ?? '',
      Fecha:             r.fecha              ?? '',
      Cliente:           r.cliente            ?? '',
      Estado:            r.estado             ?? '',
      OC:                r.orden_compra       ?? '',
      Factura:           r.numero_factura     ?? '',
      'Código':          r.codigo             ?? '',
      Concepto:          r.concepto           ?? '',
      Unidad:            r.unidad             ?? '',
      Cantidad:          r.cantidad           ?? '',
      'Precio Unitario': r.precio_unitario    ?? '',
      Subtotal:          r.subtotal           ?? '',
      IVA:               r.iva                ?? '',
      'Total Partida':   r.total_partida      ?? '',
    }));
    const empty = Object.fromEntries(COLS.map((k) => [k, '']));
    filas.push(empty);
    filas.push({ ...empty, Concepto: 'Monto solicitado', 'Total Partida': totales.solicitado });
    filas.push({ ...empty, Concepto: 'Monto entregado',  'Total Partida': totales.entregado  });
    filas.push({ ...empty, Concepto: 'Monto facturado',  'Total Partida': totales.facturado  });
    filas.push({ ...empty, Concepto: 'Monto pagado',     'Total Partida': totales.pagado     });
    exportCSV(COLS, filas, 'Cotizaciones');
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Cotizaciones</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Cotizaciones</div>
          <div className="page-sub">{total} cotizacion{total !== 1 ? 'es' : ''}</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={handleExportCsv}>
            Exportar CSV
          </button>
          <button className="btn btn-primary" onClick={() => navigate('/comercial/cotizaciones/nueva')}>
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
        <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>Estado</span>
          <MultiSelectDropdown
            options={FILTROS.filter((o) => o.value !== '')}
            values={filtros}
            onChange={handleFiltro}
            counts={conteoEstado}
            placeholder="Todos…"
            labelPlural="estados"
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>Cliente</span>
          <MultiSelectDropdown
            options={clientesLista.map((c) => ({ label: c.nombre, value: String(c.id) }))}
            values={clientesFiltro}
            onChange={handleClientesFiltro}
            placeholder="Todos…"
            labelPlural="clientes"
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink-400)', textTransform: 'uppercase', letterSpacing: '0.05em', whiteSpace: 'nowrap' }}>Fecha</span>
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
        </label>
      </div>

      <div className="list-layout" style={{
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
            getContextMenuItems={getContextMenuItems}
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
                  <div style={{ marginTop: 4 }}><StatusBadge status={sel.estado} /></div>
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
                  onClick={() => navigate(`/comercial/cotizaciones/${sel.id}`, { state: { ids: cotizaciones.map((c) => c.id) } })}>
                  Abrir
                </button>
                <button className="btn btn-sm" onClick={() => navigate(`/comercial/cotizaciones/${sel.id}/editar`)}>
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
              <Historial entidad="cotizacion" entidadId={sel?.id} />
            </SidePreview>
          </div>
        )}
      </div>

      <ConfirmModal
        open={!!confirmCancelarId}
        onClose={() => setConfirmCancelarId(null)}
        onConfirm={handleCancelarCot}
        title="¿Cancelar cotización?"
        description="Esta acción no se puede deshacer. La cotización quedará marcada como Cancelada."
        confirmLabel="Sí, cancelar"
        loading={cancelando}
        danger
      />
    </div>
  );
}
