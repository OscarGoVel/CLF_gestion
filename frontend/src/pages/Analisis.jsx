import { useFetch } from '../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
const PCT = (n) => `${n ?? 0}%`;

function KPI({ label, value, sub, accent }) {
  return (
    <div className="kpi" style={{ borderRight: '1px solid var(--ink-200)' }}>
      <div className="k-label">{label}</div>
      <div className="k-value" style={accent ? { color: 'var(--accent)' } : {}}>{value ?? '—'}</div>
      {sub && <div className="k-foot">{sub}</div>}
    </div>
  );
}

function BarRow({ label, value, max, color, sub }) {
  const pct = max > 0 ? Math.max(2, Math.round(value / max * 100)) : 0;
  return (
    <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--ink-100)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12.5, fontWeight: 500 }}>{label}</span>
        <div style={{ textAlign: 'right' }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 13 }}>{MXN.format(value)}</span>
          {sub && <span style={{ fontSize: 11, color: 'var(--ink-400)', marginLeft: 6 }}>{sub}</span>}
        </div>
      </div>
      <div style={{ height: 4, background: 'var(--ink-100)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color ?? 'var(--accent)', borderRadius: 2 }} />
      </div>
    </div>
  );
}

export default function Analisis() {
  const { data, loading } = useFetch('/api/analisis');

  const kpis         = data?.kpis         ?? {};
  const meses        = data?.meses        ?? [];
  const porEstado    = data?.por_estado   ?? [];
  const topClientes  = data?.top_clientes ?? [];
  const topProductos = data?.top_productos ?? [];
  const porTipo      = data?.por_tipo     ?? [];

  const maxMes      = Math.max(...meses.map((m) => m.monto), 1);
  const maxCliente  = topClientes[0]?.monto ?? 1;
  const maxProducto = topProductos[0]?.monto ?? 1;
  const totalEstado = porEstado.reduce((s, e) => s + (e.estado !== 'Cancelada' ? e.monto : 0), 0) || 1;

  if (loading) return (
    <div className="page" style={{ paddingTop: 60, textAlign: 'center', color: 'var(--ink-400)' }}>
      Cargando análisis…
    </div>
  );

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Análisis</div>
          <div className="page-sub">Resumen histórico de ventas y cobranza</div>
        </div>
      </div>

      {/* KPIs */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
        border: '1px solid var(--ink-200)', borderRadius: 6, marginBottom: 28, overflow: 'hidden',
      }}>
        <KPI label="Cotizaciones vendidas" value={kpis.total_cots} sub="estados activos" />
        <KPI label="Monto total vendido"   value={kpis.monto_total != null ? MXN.format(kpis.monto_total) : null} />
        <KPI label="Cobrado"               value={kpis.cobrado != null ? MXN.format(kpis.cobrado) : null} accent />
        <KPI label="Por cobrar"            value={kpis.pendiente_cobro != null ? MXN.format(kpis.pendiente_cobro) : null} />
        <KPI label="Tasa de cobro"         value={kpis.tasa_cobro != null ? PCT(kpis.tasa_cobro) : null}
             sub={`${kpis.num_pagadas ?? 0} pagadas · ${kpis.num_canceladas ?? 0} canceladas`}
             style={{ borderRight: 'none' }} />
      </div>

      {/* Tendencia mensual + Por estado */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20, marginBottom: 20 }}>

        {/* Tendencia */}
        <div className="card">
          <div className="card-h">
            <h3>Tendencia mensual</h3>
            <span className="meta">Últimos 12 meses</span>
          </div>
          {meses.length === 0 ? (
            <div style={{ padding: 24, color: 'var(--ink-400)', fontSize: 12 }}>Sin datos</div>
          ) : (
            <div style={{ padding: '0 0 4px' }}>
              {meses.map((m, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '7px 16px', borderBottom: i < meses.length - 1 ? '1px solid var(--ink-100)' : 'none',
                }}>
                  <div style={{ width: 52, fontSize: 11, color: 'var(--ink-500)', flexShrink: 0 }}>
                    {m.label}
                  </div>
                  <div style={{ flex: 1, height: 6, background: 'var(--ink-100)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 3,
                      width: `${Math.max(2, Math.round(m.monto / maxMes * 100))}%`,
                      background: 'var(--accent)',
                    }} />
                  </div>
                  <div style={{ width: 100, textAlign: 'right', fontFamily: 'var(--serif)', fontSize: 12.5 }}>
                    {MXN.format(m.monto)}
                  </div>
                  <div style={{ width: 32, textAlign: 'right', fontSize: 11, color: 'var(--ink-400)' }}>
                    {m.total}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Por estado */}
        <div className="card">
          <div className="card-h"><h3>Por estado</h3></div>
          <div style={{ padding: '0 0 4px' }}>
            {porEstado.filter((e) => e.estado !== 'Cancelada').map((e, i) => (
              <div key={i} style={{
                padding: '8px 16px',
                borderBottom: '1px solid var(--ink-100)',
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                  background: e.color,
                }} />
                <div style={{ flex: 1, fontSize: 12 }}>{e.estado}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)', marginRight: 4 }}>{e.count}</div>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 12 }}>{MXN.format(e.monto)}</div>
              </div>
            ))}
            {porEstado.find((e) => e.estado === 'Cancelada') && (
              <div style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', flexShrink: 0 }} />
                <div style={{ flex: 1, fontSize: 12, color: 'var(--ink-400)' }}>Cancelada</div>
                <div style={{ fontSize: 11, color: 'var(--ink-400)' }}>
                  {porEstado.find((e) => e.estado === 'Cancelada')?.count}
                </div>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 12, color: 'var(--ink-400)' }}>
                  {MXN.format(porEstado.find((e) => e.estado === 'Cancelada')?.monto ?? 0)}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Top clientes + Top productos */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>

        <div className="card" style={{ padding: 0 }}>
          <div className="card-h"><h3>Top 10 clientes</h3><span className="meta">por monto vendido</span></div>
          {topClientes.map((c, i) => (
            <BarRow
              key={i}
              label={c.nombre}
              value={c.monto}
              max={maxCliente}
              sub={`${c.num_cots} cots`}
            />
          ))}
        </div>

        <div className="card" style={{ padding: 0 }}>
          <div className="card-h"><h3>Top 10 productos</h3><span className="meta">por monto en cotizaciones</span></div>
          {topProductos.map((p, i) => (
            <BarRow
              key={i}
              label={p.nombre}
              value={p.monto}
              max={maxProducto}
              color="#6366f1"
              sub={`${p.apariciones} aparic.`}
            />
          ))}
        </div>
      </div>

      {/* Por tipo de cliente */}
      {porTipo.length > 0 && (
        <div className="card" style={{ padding: 0, marginBottom: 20 }}>
          <div className="card-h"><h3>Por tipo de cliente</h3></div>
          <table className="tbl">
            <thead>
              <tr>
                <th>Tipo</th>
                <th className="num" style={{ width: 100 }}>Clientes</th>
                <th className="num" style={{ width: 120 }}>Cotizaciones</th>
                <th className="num" style={{ width: 160 }}>Monto total</th>
                <th style={{ width: '35%' }}>Participación</th>
              </tr>
            </thead>
            <tbody>
              {porTipo.map((t, i) => {
                const maxTipo = porTipo[0]?.monto ?? 1;
                return (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{t.tipo}</td>
                    <td className="num">{t.clientes}</td>
                    <td className="num">{t.cots}</td>
                    <td className="num" style={{ fontFamily: 'var(--serif)' }}>{MXN.format(t.monto)}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ flex: 1, height: 6, background: 'var(--ink-100)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{
                            height: '100%', borderRadius: 3,
                            width: `${Math.max(2, Math.round(t.monto / maxTipo * 100))}%`,
                            background: 'var(--accent)',
                          }} />
                        </div>
                        <span style={{ fontSize: 11, color: 'var(--ink-400)', width: 36, textAlign: 'right' }}>
                          {Math.round(t.monto / totalEstado * 100)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
