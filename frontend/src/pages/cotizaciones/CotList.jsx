import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { Pill } from '../../components/Pill';
import { Stepper, buildSteps } from '../../components/Stepper';
import { NextRibbon, buildNextAction } from '../../components/NextRibbon';

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

export default function CotList() {
  const navigate = useNavigate();
  const [filtro, setFiltro]   = useState('');
  const [buscar, setBuscar]   = useState('');
  const [selected, setSelected] = useState(null);
  const [pagina, setPagina]   = useState(1);

  const params = new URLSearchParams({ pagina });
  if (filtro) params.set('estado', filtro);
  if (buscar) params.set('q', buscar);

  const { data, loading } = useFetch(`/api/cotizaciones?${params}`);
  const cotizaciones  = data?.cotizaciones   ?? [];
  const conteoEstado  = data?.conteo_estado  ?? {};
  const total         = data?.total          ?? 0;
  const totalPags     = data?.total_pags     ?? 1;

  const sel = selected != null ? cotizaciones.find((c) => c.id === selected) : null;

  function handleFiltro(v) { setFiltro(v); setPagina(1); setBuscar(''); }
  function handleBuscar(e) { setBuscar(e.target.value); setPagina(1); }

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
          <div className="page-sub">
            {total} registros en total
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" onClick={() => navigate('/cotizaciones/nueva')}>
            Nueva cotización
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
        <input
          className="input"
          style={{ maxWidth: 280 }}
          placeholder="Buscar folio o cliente…"
          value={buscar}
          onChange={handleBuscar}
        />
        {FILTROS.map((f) => (
          <span
            key={f.value}
            className={`chip${filtro === f.value ? ' active' : ''}`}
            onClick={() => handleFiltro(f.value)}
          >
            {f.label}
            {conteoEstado[f.value] != null && (
              <span className="n">{conteoEstado[f.value]}</span>
            )}
            {f.value === '' && (
              <span className="n">{Object.values(conteoEstado).reduce((a, b) => a + b, 0)}</span>
            )}
          </span>
        ))}
      </div>

      {/* List + side preview */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: sel ? '1fr 380px' : '1fr',
        gap: 0,
        border: '1px solid var(--ink-200)',
        borderRadius: 6,
        overflow: 'hidden',
      }}>
        {/* Tabla */}
        <div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Folio</th>
                <th>Fecha</th>
                <th>Cliente</th>
                <th className="num">Total</th>
                <th>Estado</th>
                <th style={{ width: 80 }}>Prods.</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>
                    Cargando…
                  </td>
                </tr>
              ) : cotizaciones.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>
                    Sin resultados
                  </td>
                </tr>
              ) : (
                cotizaciones.map((c) => (
                  <tr
                    key={c.id}
                    className={selected === c.id ? 'sel' : ''}
                    style={{ cursor: 'pointer' }}
                    onClick={() => setSelected(selected === c.id ? null : c.id)}
                  >
                    <td className="folio">{c.folio}</td>
                    <td style={{ color: 'var(--ink-500)' }}>{c.fecha}</td>
                    <td>{c.cliente}</td>
                    <td className="num">{c.total != null ? MXN.format(c.total) : '—'}</td>
                    <td><Pill status={c.estado} /></td>
                    <td style={{ color: 'var(--ink-500)', textAlign: 'center' }}>{c.num_productos}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Paginación */}
          <div style={{
            padding: '10px 16px',
            borderTop: '1px solid var(--ink-100)',
            fontSize: 11.5,
            color: 'var(--ink-500)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <span>Mostrando {cotizaciones.length} de {total}</span>
            <span style={{ display: 'flex', gap: 12 }}>
              {pagina > 1 && (
                <a className="linkish" onClick={() => setPagina(p => p - 1)}>← anterior</a>
              )}
              {pagina < totalPags && (
                <a className="linkish" onClick={() => setPagina(p => p + 1)}>siguiente →</a>
              )}
            </span>
          </div>
        </div>

        {/* Side preview */}
        {sel && (
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '70vh' }}>
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

            {/* Stepper */}
            <div className="eyebrow" style={{ marginTop: 16 }}>Proceso</div>
            <div style={{ marginTop: 6 }}>
              <Stepper steps={buildSteps(sel)} />
            </div>

            {/* Acciones */}
            <div className="eyebrow" style={{ marginTop: 16 }}>Acciones</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 6 }}>
              <button className="btn btn-sm btn-primary" onClick={() => navigate(`/cotizaciones/${sel.id}`)}>
                Abrir
              </button>
              <button className="btn btn-sm" onClick={() => navigate(`/cotizaciones/${sel.id}/editar`)}>
                Editar
              </button>
              <a
                className="btn btn-sm"
                href={`/cotizaciones/${sel.id}/pdf`}
                target="_blank"
                rel="noreferrer"
                style={{ textAlign: 'center', textDecoration: 'none' }}
              >
                PDF
              </a>
              <button className="btn btn-sm" onClick={() => setSelected(null)}>Cerrar ×</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
