import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

function StockBadge({ actual, minimo }) {
  const a = actual ?? 0;
  const m = minimo ?? 0;
  if (a < 0) return <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{a}</span>;
  if (m > 0 && a < m) return <span style={{ color: 'var(--warn)', fontWeight: 500 }}>{a}</span>;
  return <span style={{ color: 'var(--ink-700)' }}>{a}</span>;
}

export default function ProductoList() {
  const navigate = useNavigate();
  const [q, setQ]               = useState('');
  const [categoria, setCategoria] = useState('');
  const [bajoMin, setBajoMin]   = useState('');
  const [sel, setSel]           = useState(null);

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (categoria) params.set('categoria', categoria);
  if (bajoMin) params.set('bajo_minimo', bajoMin);

  const { data, loading } = useFetch(`/api/catalogos/productos?${params}`);
  const productos   = data?.productos  ?? [];
  const categorias  = data?.categorias ?? [];
  const stats       = data?.stats      ?? {};
  const selected    = sel != null ? productos.find((p) => p.id === sel) : null;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Catálogos</span>
        <span className="sep">/</span>
        <span>Productos</span>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--ink-200)', marginBottom: 20 }}>
        {[
          { label: 'Clientes',    path: '/catalogos/clientes' },
          { label: 'Productos',   path: '/catalogos/productos' },
        ].map((t) => (
          <button key={t.path} onClick={() => navigate(t.path)} style={{
            padding: '7px 18px', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer',
            fontWeight: t.path === '/catalogos/productos' ? 500 : 400,
            color: t.path === '/catalogos/productos' ? 'var(--ink-900)' : 'var(--ink-500)',
            borderBottom: t.path === '/catalogos/productos' ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>{t.label}</button>
        ))}
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Productos</div>
          <div className="page-sub">
            {stats.total ?? 0} productos · {stats.bajo_minimo ?? 0} bajo mínimo · {stats.sin_stock ?? 0} sin stock
          </div>
        </div>
        <button className="btn btn-primary">Nuevo producto</button>
      </div>

      {/* Stats rápidos */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20,
        border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden' }}>
        {[
          ['Valor inventario', stats.total_valor != null ? MXN.format(stats.total_valor) : '—'],
          ['Bajo mínimo',  stats.bajo_minimo ?? 0],
          ['Sin stock',    stats.sin_stock   ?? 0],
          ['Total prods.', stats.total       ?? 0],
        ].map(([k, v], i, arr) => (
          <div key={k} style={{ flex: 1, padding: '14px 18px',
            borderRight: i < arr.length - 1 ? '1px solid var(--ink-200)' : 'none' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-500)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{k}</div>
            <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em' }}>{v}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
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

      <div style={{
        display: 'grid', gridTemplateColumns: selected ? '1fr 320px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 100 }}>Código</th>
              <th>Nombre</th>
              <th style={{ width: 100 }}>Categoría</th>
              <th style={{ width: 60 }}>U/M</th>
              <th className="num" style={{ width: 80 }}>Stock</th>
              <th className="num" style={{ width: 70 }}>Mín.</th>
              <th className="num" style={{ width: 100 }}>Costo prom.</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Cargando…</td></tr>
            ) : productos.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>Sin resultados</td></tr>
            ) : productos.map((p) => (
              <tr key={p.id} className={sel === p.id ? 'sel' : ''} style={{ cursor: 'pointer' }}
                  onClick={() => setSel(sel === p.id ? null : p.id)}>
                <td style={{ fontFamily: 'var(--mono)', fontSize: 11.5 }}>{p.codigo ?? '—'}</td>
                <td>{p.nombre}</td>
                <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.categoria ?? '—'}</td>
                <td style={{ fontSize: 11.5, color: 'var(--ink-500)' }}>{p.unidad_medida}</td>
                <td className="num"><StockBadge actual={p.stock_actual} minimo={p.stock_minimo} /></td>
                <td className="num" style={{ color: 'var(--ink-400)', fontSize: 12 }}>{p.stock_minimo ?? '—'}</td>
                <td className="num">{p.costo_prom ? MXN.format(p.costo_prom) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {selected && (
          <div className="side-pre" style={{ padding: '18px 20px', overflowY: 'auto', maxHeight: '70vh' }}>
            <div className="note">PRODUCTO</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)', marginTop: 4 }}>
              {selected.codigo}
            </div>
            <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>{selected.nombre}</div>

            <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0,
              border: '1px solid var(--ink-200)', borderRadius: 4 }}>
              {[
                ['Categoría', selected.categoria],
                ['Subcategoría', selected.subcategoria],
                ['U/M', selected.unidad_medida],
                ['IVA', selected.aplica_iva ? 'Sí' : 'No'],
                ['Stock actual', selected.stock_actual],
                ['Stock mínimo', selected.stock_minimo],
                ['Costo prom.', selected.costo_prom != null ? MXN.format(selected.costo_prom) : '—'],
                ['Precio base', selected.precio_base != null ? MXN.format(selected.precio_base) : '—'],
              ].map(([k, v], i, arr) => (
                <div key={i} style={{
                  padding: '10px 12px',
                  borderBottom: i < arr.length - 2 ? '1px solid var(--ink-100)' : 'none',
                  borderRight: i % 2 === 0 ? '1px solid var(--ink-100)' : 'none',
                }}>
                  <div className="note">{k.toUpperCase()}</div>
                  <div style={{ fontSize: 12, marginTop: 2 }}>{v ?? '—'}</div>
                </div>
              ))}
            </div>

            {selected.proveedor_principal && (
              <div style={{ marginTop: 12 }}>
                <div className="note">PROVEEDOR PRINCIPAL</div>
                <div style={{ fontSize: 12.5, marginTop: 2 }}>{selected.proveedor_principal}</div>
              </div>
            )}

            <div style={{ marginTop: 14, display: 'flex', gap: 6 }}>
              <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
