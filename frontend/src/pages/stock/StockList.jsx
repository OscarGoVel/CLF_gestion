import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

function StockBar({ actual, minimo }) {
  const a = actual ?? 0;
  const m = minimo ?? 0;
  if (a < 0) return <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{a}</span>;
  const color = m > 0 && a < m ? 'var(--warn)' : 'var(--ink-700)';
  return <span style={{ color, fontWeight: m > 0 && a < m ? 600 : 400 }}>{a}</span>;
}

function ABCBadge({ valor, minimo, actual }) {
  const v = (actual ?? 0) * valor;
  if (v > 50000) return <span style={{ background: '#dcfce7', color: '#166534', fontSize: 10, padding: '1px 5px', borderRadius: 3 }}>A</span>;
  if (v > 10000) return <span style={{ background: '#fef9c3', color: '#854d0e', fontSize: 10, padding: '1px 5px', borderRadius: 3 }}>B</span>;
  return <span style={{ background: '#f3f4f6', color: '#6b7280', fontSize: 10, padding: '1px 5px', borderRadius: 3 }}>C</span>;
}

export default function StockList() {
  const navigate = useNavigate();
  const [q, setQ]               = useState('');
  const [categoria, setCategoria] = useState('');
  const [bajoMin, setBajoMin]   = useState('');
  const [vista, setVista]       = useState('inventario');
  const [movPag, setMovPag]     = useState(1);

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (categoria) params.set('categoria', categoria);
  if (bajoMin) params.set('bajo_minimo', bajoMin);

  const { data, loading }    = useFetch(vista === 'inventario' ? `/api/stock?${params}` : null);
  const { data: movData, loading: movLoading } = useFetch(
    vista === 'movimientos' ? `/api/stock/movimientos?pagina=${movPag}` : null
  );

  const productos  = data?.productos  ?? [];
  const categorias = data?.categorias ?? [];
  const stats      = data?.stats      ?? {};
  const movs       = movData?.movimientos ?? [];
  const movTotal   = movData?.total ?? 0;
  const movPags    = movData?.total_pags ?? 1;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Almacén</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Almacén & Stock</div>
          <div className="page-sub">
            {stats.total_productos ?? 0} productos · {stats.bajo_minimo ?? 0} bajo mínimo · {stats.negativo ?? 0} negativos
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className={`btn${vista === 'inventario' ? ' btn-primary' : ''}`} onClick={() => setVista('inventario')}>Inventario</button>
          <button className={`btn${vista === 'movimientos' ? ' btn-primary' : ''}`} onClick={() => setVista('movimientos')}>Movimientos</button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20,
        border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden' }}>
        {[
          ['Valor inventario', stats.total_valor != null ? MXN.format(stats.total_valor) : '—'],
          ['Bajo mínimo',  stats.bajo_minimo ?? 0],
          ['Stock negativo', stats.negativo ?? 0],
          ['Sin stock',    stats.sin_stock ?? 0],
        ].map(([k, v], i, arr) => (
          <div key={k} style={{ flex: 1, padding: '14px 18px',
            borderRight: i < arr.length - 1 ? '1px solid var(--ink-200)' : 'none' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em',
              color: (k === 'Bajo mínimo' || k === 'Stock negativo') && v > 0 ? 'var(--danger)' : 'inherit' }}>
              {v}
            </div>
          </div>
        ))}
      </div>

      {vista === 'inventario' ? (
        <>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 16 }}>
            <input className="input" style={{ maxWidth: 260 }}
              placeholder="Buscar nombre o código…" value={q}
              onChange={(e) => setQ(e.target.value)} />
            <span className={`chip${categoria === '' ? ' active' : ''}`} onClick={() => setCategoria('')}>Todas</span>
            {categorias.map((c) => (
              <span key={c} className={`chip${categoria === c ? ' active' : ''}`} onClick={() => setCategoria(c)}>{c}</span>
            ))}
            <span className={`chip${bajoMin === '1' ? ' active' : ''}`}
              onClick={() => setBajoMin(bajoMin === '1' ? '' : '1')}>
              ⚠ Bajo mínimo
            </span>
          </div>

          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <table className="tbl">
              <thead>
                <tr>
                  <th style={{ width: 100 }}>Código</th>
                  <th>Nombre</th>
                  <th style={{ width: 100 }}>Categoría</th>
                  <th style={{ width: 50 }}>U/M</th>
                  <th className="num" style={{ width: 80 }}>Stock</th>
                  <th className="num" style={{ width: 70 }}>Mín.</th>
                  <th className="num" style={{ width: 100 }}>Valor inv.</th>
                  <th style={{ width: 40 }}>ABC</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
                ) : productos.length === 0 ? (
                  <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
                ) : productos.map((p) => {
                  const valorInv = (p.stock_actual ?? 0) * (p.costo_prom || p.precio_base || 0);
                  return (
                    <tr key={p.id}>
                      <td style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>{p.codigo ?? '—'}</td>
                      <td>{p.nombre}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.categoria ?? '—'}</td>
                      <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.unidad_medida}</td>
                      <td className="num"><StockBar actual={p.stock_actual} minimo={p.stock_minimo} /></td>
                      <td className="num" style={{ color: 'var(--ink-400)', fontSize: 11.5 }}>{p.stock_minimo ?? '—'}</td>
                      <td className="num" style={{ fontSize: 11.5 }}>{valorInv > 0 ? MXN.format(valorInv) : '—'}</td>
                      <td style={{ textAlign: 'center' }}>
                        <ABCBadge valor={p.costo_prom || p.precio_base || 0} actual={p.stock_actual} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        /* Movimientos */
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Producto</th>
                <th style={{ width: 70 }}>Tipo</th>
                <th>Motivo</th>
                <th className="num" style={{ width: 80 }}>Cantidad</th>
                <th className="num" style={{ width: 80 }}>Antes</th>
                <th className="num" style={{ width: 80 }}>Después</th>
                <th style={{ width: 120 }}>Referencia</th>
              </tr>
            </thead>
            <tbody>
              {movLoading ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
              ) : movs.length === 0 ? (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin movimientos</td></tr>
              ) : movs.map((m) => (
                <tr key={m.id}>
                  <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{m.fecha}</td>
                  <td>
                    <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink-500)' }}>{m.codigo}</div>
                    <div style={{ fontSize: 12 }}>{m.nombre}</div>
                  </td>
                  <td>
                    <span style={{
                      fontSize: 10.5, padding: '2px 6px', borderRadius: 3,
                      background: m.tipo === 'entrada' ? '#dcfce7' : '#fee2e2',
                      color: m.tipo === 'entrada' ? '#166534' : '#991b1b',
                    }}>{m.tipo}</span>
                  </td>
                  <td style={{ fontSize: 11.5, color: 'var(--ink-600)' }}>{m.motivo}</td>
                  <td className="num" style={{ fontWeight: 500,
                    color: m.tipo === 'entrada' ? 'var(--accent)' : 'var(--danger)' }}>
                    {m.tipo === 'entrada' ? '+' : '-'}{m.cantidad}
                  </td>
                  <td className="num" style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{m.stock_antes}</td>
                  <td className="num" style={{ fontSize: 11.5,
                    color: (m.stock_despues ?? 0) < 0 ? 'var(--danger)' : 'var(--ink-700)' }}>
                    {m.stock_despues}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--ink-500)' }}>{m.referencia ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)',
            fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between' }}>
            <span>{movs.length} de {movTotal} movimientos</span>
            <span style={{ display: 'flex', gap: 12 }}>
              {movPag > 1 && <a className="linkish" onClick={() => setMovPag(p => p - 1)}>← anterior</a>}
              {movPag < movPags && <a className="linkish" onClick={() => setMovPag(p => p + 1)}>siguiente →</a>}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
