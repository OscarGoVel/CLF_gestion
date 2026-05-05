import { useNavigate } from 'react-router-dom';
import { useFetch } from '../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

function KPI({ label, value, foot }) {
  return (
    <div className="kpi">
      <div className="k-label">{label}</div>
      <div className="k-value">{value ?? '—'}</div>
      {foot && <div className="k-foot">{foot}</div>}
    </div>
  );
}

function PendientesSection({ titulo, items, urgencia, cta, navigate }) {
  if (!items?.length) return null;
  return (
    <>
      <tr style={{ background: 'var(--ink-50)' }}>
        <td colSpan={5} style={{ padding: '6px 12px', fontSize: 11, fontWeight: 600,
          color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {titulo} · {items.length}
        </td>
      </tr>
      {items.map((p, i) => (
        <tr key={i} style={{ cursor: 'pointer' }} onClick={() => navigate(`/cotizaciones/${p.id}`)}>
          <td>
            <span style={{ color: urgencia === 'alta' ? 'var(--danger)' : urgencia === 'media' ? 'var(--warn)' : 'var(--ink-700)', fontWeight: 500 }}>
              {cta}
            </span>
          </td>
          <td className="folio">{p.folio}</td>
          <td>{p.cliente}</td>
          <td className="num">{p.total != null ? MXN.format(p.total) : '—'}</td>
          <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>
            {p.fecha_entrega ?? p.fecha ?? ''}
          </td>
        </tr>
      ))}
    </>
  );
}

export default function Dashboard() {
  const { data, loading } = useFetch('/api/dashboard');
  const navigate = useNavigate();

  const kpis    = data?.kpis ?? {};
  const bloques = data?.bloques ?? {};
  const embudo  = data?.embudo ?? [];

  const pendientes = [
    ...(bloques.comercial?.sin_respuesta ?? []),
    ...(bloques.comercial?.sin_oc ?? []),
    ...(bloques.logistico?.sin_stock ?? []),
    ...(bloques.administrativo?.facturas_sin_pago ?? []),
  ];

  const hoy = new Date().toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long' });

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Resumen del día</div>
          <div className="page-sub">
            {hoy} · {pendientes.length} pendientes · CLF
          </div>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/cotizaciones/nueva')}>
          Nueva cotización
        </button>
      </div>

      {/* KPIs */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4,1fr)',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, marginBottom: 28,
      }}>
        <div style={{ borderRight: '1px solid var(--ink-200)' }}>
          <KPI label="Monto vendido (total)" value={kpis.monto_vendido != null ? MXN.format(kpis.monto_vendido) : null} />
        </div>
        <div style={{ borderRight: '1px solid var(--ink-200)' }}>
          <KPI label="Por cobrar" value={kpis.pendiente_cobrar != null ? MXN.format(kpis.pendiente_cobrar) : null} />
        </div>
        <div style={{ borderRight: '1px solid var(--ink-200)' }}>
          <KPI label="Pendientes de respuesta" value={kpis.num_pendientes ?? '—'} foot="cotizaciones enviadas" />
        </div>
        <KPI label="Programadas para entrega" value={kpis.num_programadas ?? '—'} foot="en proceso" />
      </div>

      {/* Pendientes */}
      <div className="eyebrow" style={{ marginBottom: 8 }}>Acciones pendientes</div>
      <div className="card" style={{ marginBottom: 24, padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>
        ) : pendientes.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--ink-400)' }}>
            Sin pendientes urgentes
          </div>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: '18%' }}>Acción</th>
                <th style={{ width: '13%' }}>Folio</th>
                <th>Cliente</th>
                <th className="num" style={{ width: 120 }}>Total</th>
                <th style={{ width: '15%' }}>Fecha</th>
              </tr>
            </thead>
            <tbody>
              <PendientesSection
                titulo="Sin respuesta (+15 días)"
                items={bloques.comercial?.sin_respuesta}
                urgencia="alta"
                cta="Dar seguimiento"
                navigate={navigate}
              />
              <PendientesSection
                titulo="Programadas sin OC"
                items={bloques.comercial?.sin_oc}
                urgencia="media"
                cta="Solicitar OC"
                navigate={navigate}
              />
              <PendientesSection
                titulo="Sin stock suficiente"
                items={bloques.logistico?.sin_stock}
                urgencia="media"
                cta="Comprar"
                navigate={navigate}
              />
              <PendientesSection
                titulo="Facturas sin cobrar"
                items={bloques.administrativo?.facturas_sin_pago}
                urgencia="alta"
                cta="Registrar pago"
                navigate={navigate}
              />
            </tbody>
          </table>
        )}
      </div>

      {/* Embudo + stock */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
        <div className="card">
          <div className="card-h">
            <h3>Embudo comercial</h3>
            <span className="meta">Todas las cotizaciones activas</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${embudo.length || 5}, 1fr)` }}>
            {embudo.map((e, i) => (
              <div key={i} style={{
                padding: '18px 16px',
                borderRight: i < embudo.length - 1 ? '1px solid var(--ink-100)' : 'none',
              }}>
                <div style={{ fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  {e.estado}
                </div>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 24, marginTop: 4, letterSpacing: '-0.02em' }}>
                  {e.count}
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--ink-600)', marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>
                  {MXN.format(e.monto)}
                </div>
                <div style={{ height: 3, background: 'var(--ink-100)', borderRadius: 2, marginTop: 10, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${e.pct ?? 50}%`, background: 'var(--accent)' }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-h">
            <h3>Stock bajo reorden</h3>
            <span className="meta">{data?.stock_bajo?.length ?? 0} productos</span>
          </div>
          <div style={{ fontSize: 12.5 }}>
            {(data?.stock_bajo ?? []).length === 0 ? (
              <div style={{ padding: '16px', color: 'var(--ink-400)', fontSize: 12 }}>
                Sin alertas de stock
              </div>
            ) : (data?.stock_bajo ?? []).map((s, i) => (
              <div key={i} style={{
                display: 'flex', padding: '10px 16px',
                borderBottom: '1px solid var(--ink-100)', alignItems: 'center',
              }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)' }}>{s.codigo}</div>
                  <div style={{ fontSize: 12.5 }}>{s.nombre}</div>
                </div>
                <div style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: 11.5, color: 'var(--danger)' }}>
                  {s.stock} / {s.minimo}
                </div>
              </div>
            ))}
            <div style={{ padding: '10px 16px' }}>
              <a className="linkish" style={{ fontSize: 12 }} onClick={() => navigate('/compras')}>
                Generar OC sugerida →
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
