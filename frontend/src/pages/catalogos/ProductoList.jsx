import { useState } from 'react';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';
import { api } from '../../lib/apiClient';
import { exportCSV } from '../../lib/exportCSV';
import { DataTable } from '../../components/DataTable';
import { SidePreview, FieldGrid } from '../../components/SidePreview';
import { Modal } from '../../components/Modal';

const COLUMNS = [
  { header: 'Código',      key: 'codigo',              width: 100, style: { fontFamily: 'var(--mono)', fontSize: 11.5 } },
  { header: 'Nombre',      key: 'nombre',              sortKey: 'nombre' },
  { header: 'Categoría',   key: 'categoria',           width: 100, style: { fontSize: 11.5, color: 'var(--ink-500)' } },
  { header: 'U/M',         key: 'unidad_medida',       width: 60,  style: { fontSize: 11.5, color: 'var(--ink-500)' } },
  { header: 'Mín.',        key: 'stock_minimo',        className: 'num', width: 70,
    style: { color: 'var(--ink-400)', fontSize: 12 } },
  { header: 'Proveedor',   key: 'proveedor_principal', style: { fontSize: 11.5, color: 'var(--ink-500)' } },
];

export default function ProductoList() {
  const navigate = useNavigate();
  const [q, setQ]               = useState('');
  const [catFiltro, setCatFiltro] = useState([]);
  const [sel, setSel]           = useState(null);
  const [editItem, setEditItem] = useState(null);
  const [editData, setEditData] = useState({});
  const [saving, setSaving]     = useState(false);
  const [editErr, setEditErr]   = useState('');
  const [refetch, setRefetch]   = useState(0);

  function openEdit(p) {
    setEditData({
      nombre:        p.nombre ?? '',
      codigo:        p.codigo ?? '',
      unidad_medida: p.unidad_medida ?? '',
      precio_base:   p.precio_base ?? '',
      stock_minimo:  p.stock_minimo ?? '',
      aplica_iva:    p.aplica_iva ?? false,
      maneja_lotes:  p.maneja_lotes ?? false,
    });
    setEditErr('');
    setEditItem(p);
  }

  async function handleEditar(e) {
    e.preventDefault();
    setSaving(true);
    setEditErr('');
    try {
      await api.patch(`/api/catalogos/productos/${editItem.id}`, {
        ...editData,
        precio_base:  editData.precio_base !== '' ? parseFloat(editData.precio_base) : null,
        stock_minimo: editData.stock_minimo !== '' ? parseFloat(editData.stock_minimo) : null,
      });
      setEditItem(null);
      setSel(null);
      setRefetch((n) => n + 1);
      toast.success('Producto actualizado');
    } catch (err) {
      setEditErr(err.message);
    } finally {
      setSaving(false);
    }
  }

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  catFiltro.forEach((c) => params.append('categoria', c));

  if (refetch) params.set('_r', refetch);
  const { data, loading } = useFetch(`/api/catalogos/productos?${params}`);
  const productos   = data?.productos  ?? [];
  const categorias  = data?.categorias ?? [];
  const stats       = data?.stats      ?? {};
  const selected    = sel != null ? productos.find((p) => p.id === sel) : null;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>CLF Gestión</a>
        <span className="sep">/</span>
        <span>Catálogos</span>
        <span className="sep">/</span>
        <span>Productos</span>
      </div>

      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--ink-200)', marginBottom: 20 }}>
        {[
          { label: 'Clientes',    path: '/comercial/clientes' },
          { label: 'Productos',   path: '/inventario/productos' },
          { label: 'Proveedores', path: '/abastecimiento/proveedores' },
        ].map((t) => (
          <button key={t.path} onClick={() => navigate(t.path)} style={{
            padding: '7px 18px', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer',
            fontWeight: t.path === '/inventario/productos' ? 500 : 400,
            color: t.path === '/inventario/productos' ? 'var(--ink-900)' : 'var(--ink-500)',
            borderBottom: t.path === '/inventario/productos' ? '2px solid var(--accent)' : '2px solid transparent',
            marginBottom: -1,
          }}>{t.label}</button>
        ))}
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Productos</div>
          <div className="page-sub">
            {stats.total ?? 0} productos
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={() => exportCSV(
            ['codigo', 'nombre', 'categoria', 'subcategoria', 'unidad_medida', 'stock_minimo', 'precio_base', 'proveedor_principal'],
            productos, 'productos'
          )}>Exportar CSV</button>
          <button className="btn btn-primary" onClick={() => navigate('/inventario/productos/nuevo')}>Nuevo producto</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 0, marginBottom: 20,
        border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden' }}>
        {[
          ['Total prods.',    stats.total          ?? 0],
          ['Sin precio base', stats.sin_precio      ?? 0],
          ['Sin proveedor',   stats.sin_proveedor   ?? 0],
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
        <MultiSelectDropdown
          options={categorias.map((c) => ({ label: c, value: c }))}
          values={catFiltro}
          onChange={setCatFiltro}
          placeholder="Categoría…"
        />
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: selected ? '1fr 320px' : '1fr',
        gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
      }}>
        <div>
          <DataTable
            columns={COLUMNS}
            data={productos}
            loading={loading}
            selectedId={sel}
            onRowClick={(row) => setSel(sel === row.id ? null : row.id)}
            footer={<span>{productos.length} productos</span>}
            getContextMenuItems={(producto) => [
              { type: 'item', label: 'Editar', onClick: () => openEdit(producto) },
              { type: 'item', label: 'Ver en stock',
                onClick: () => navigate(`/stock?q=${encodeURIComponent(producto.codigo ?? producto.nombre)}`) },
            ]}
          />
        </div>

        {selected && (
          <SidePreview>
            <div className="note">PRODUCTO</div>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-500)', marginTop: 4 }}>
              {selected.codigo}
            </div>
            <div style={{ fontSize: 16, fontWeight: 500, marginTop: 4 }}>{selected.nombre}</div>

            <FieldGrid fields={[
              ['Categoría',            selected.categoria],
              ['Subcategoría',         selected.subcategoria],
              ['U/M',                  selected.unidad_medida],
              ['IVA',                  selected.aplica_iva ? 'Sí' : 'No'],
              ['Stock mínimo',         selected.stock_minimo],
              ['Costo base (catálogo)', selected.precio_base != null ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 }).format(selected.precio_base) : '—'],
            ]} />

            {selected.proveedor_principal && (
              <div style={{ marginTop: 12 }}>
                <div className="note">PROVEEDOR PRINCIPAL</div>
                <div style={{ fontSize: 12.5, marginTop: 2 }}>{selected.proveedor_principal}</div>
              </div>
            )}

            <div style={{ marginTop: 14, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button className="btn btn-sm" onClick={() => openEdit(selected)}>Editar</button>
              <button className="btn btn-sm" onClick={() => navigate(`/inventario/stock?q=${encodeURIComponent(selected.codigo ?? selected.nombre)}`)}>Ver en stock →</button>
              <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
            </div>
          </SidePreview>
        )}
      </div>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Editar producto">
        <form onSubmit={handleEditar}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOMBRE *</div>
              <input className="input" style={{ width: '100%' }}
                value={editData.nombre ?? ''}
                onChange={(e) => setEditData((d) => ({ ...d, nombre: e.target.value }))}
                required autoFocus />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CÓDIGO / SKU</div>
                <input className="input" style={{ width: '100%' }}
                  value={editData.codigo ?? ''}
                  onChange={(e) => setEditData((d) => ({ ...d, codigo: e.target.value }))} />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>UNIDAD DE MEDIDA</div>
                <input className="input" style={{ width: '100%' }}
                  value={editData.unidad_medida ?? ''}
                  placeholder="pza, kg, lt…"
                  onChange={(e) => setEditData((d) => ({ ...d, unidad_medida: e.target.value }))} />
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>COSTO BASE (catálogo)</div>
                <input className="input" type="number" min="0" step="0.01" style={{ width: '100%' }}
                  value={editData.precio_base ?? ''}
                  onChange={(e) => setEditData((d) => ({ ...d, precio_base: e.target.value }))} />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>STOCK MÍNIMO</div>
                <input className="input" type="number" min="0" style={{ width: '100%' }}
                  value={editData.stock_minimo ?? ''}
                  onChange={(e) => setEditData((d) => ({ ...d, stock_minimo: e.target.value }))} />
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox"
                checked={editData.aplica_iva ?? false}
                onChange={(e) => setEditData((d) => ({ ...d, aplica_iva: e.target.checked }))} />
              <span style={{ fontSize: 13 }}>Aplica IVA (16%)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input type="checkbox"
                checked={editData.maneja_lotes ?? false}
                onChange={(e) => setEditData((d) => ({ ...d, maneja_lotes: e.target.checked }))} />
              <span style={{ fontSize: 13 }}>Maneja lotes / vencimientos</span>
            </div>
          </div>
          {editErr && <div style={{ color: 'var(--danger)', fontSize: 13, marginTop: 12 }}>{editErr}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" className="btn" onClick={() => setEditItem(null)}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
