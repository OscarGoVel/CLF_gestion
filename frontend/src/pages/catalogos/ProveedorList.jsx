import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { DataTable } from '../../components/DataTable';
import { SidePreview, FieldGrid } from '../../components/SidePreview';
import { Modal } from '../../components/Modal';
import { exportCSV } from '../../lib/exportCSV';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const FORM_EMPTY = {
  nombre: '', razon_social: '', rfc: '', contacto: '', telefono: '', email: '', notas: '',
};

const TABS = [
  { label: 'Clientes',    path: '/catalogos/clientes' },
  { label: 'Productos',   path: '/catalogos/productos' },
  { label: 'Proveedores', path: '/catalogos/proveedores' },
];

const COLUMNS = [
  {
    header: 'Nombre', sortKey: 'nombre',
    render: (p) => <span style={{ fontWeight: 500 }}>{p.nombre}</span>,
  },
  { header: 'RFC',      width: 140, style: { fontFamily: 'var(--mono)', fontSize: 11.5 },
    render: (p) => p.rfc ?? '—' },
  { header: 'Contacto', width: 160, style: { fontSize: 12, color: 'var(--ink-600)' },
    render: (p) => p.contacto ?? '—' },
  { header: 'Teléfono', width: 140, style: { fontSize: 12, color: 'var(--ink-600)' },
    render: (p) => p.telefono ?? '—' },
  { header: 'Compras', key: 'num_compras', className: 'num', width: 70, sortKey: 'num_compras' },
  { header: 'Total',   className: 'num', width: 130, sortKey: 'monto_total',
    render: (p) => p.monto_total ? MXN.format(p.monto_total) : '—' },
];

export default function ProveedorList() {
  const navigate = useNavigate();
  const [q, setQ]           = useState('');
  const [sel, setSel]       = useState(null);
  const [refetch, setRefetch] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [formData, setFormData] = useState(FORM_EMPTY);
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState('');

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (refetch) params.set('_r', refetch);

  const { data, loading } = useFetch(`/api/catalogos/proveedores?${params}`);
  const proveedores = data?.proveedores ?? [];
  const selected    = sel != null ? proveedores.find((p) => p.id === sel) : null;

  function openEdit(p) {
    setFormData({
      nombre:       p.nombre ?? '',
      razon_social: p.razon_social ?? '',
      rfc:          p.rfc ?? '',
      contacto:     p.contacto ?? '',
      telefono:     p.telefono ?? '',
      email:        p.email ?? '',
      notas:        p.notas ?? '',
    });
    setFormErr('');
    setEditItem(p);
  }

  const handleEditar = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormErr('');
    try {
      await api.patch(`/api/catalogos/proveedores/${editItem.id}`, formData);
      setEditItem(null);
      setFormData(FORM_EMPTY);
      setSel(null);
      setRefetch((n) => n + 1);
      toast.success('Proveedor actualizado');
    } catch (err) {
      setFormErr(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleCrear = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormErr('');
    try {
      await api.post('/api/catalogos/proveedores', formData);
      setShowForm(false);
      setFormData(FORM_EMPTY);
      setRefetch((n) => n + 1);
      toast.success('Proveedor guardado');
    } catch (err) {
      setFormErr(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="page">
        <div className="crumbs">
          <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
          <span className="sep">/</span>
          <span>Catálogos</span>
          <span className="sep">/</span>
          <span>Proveedores</span>
        </div>

        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--ink-200)', marginBottom: 20 }}>
          {TABS.map((t) => (
            <button key={t.path} onClick={() => navigate(t.path)} style={{
              padding: '7px 18px', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer',
              fontWeight: t.path === '/catalogos/proveedores' ? 500 : 400,
              color: t.path === '/catalogos/proveedores' ? 'var(--ink-900)' : 'var(--ink-500)',
              borderBottom: t.path === '/catalogos/proveedores' ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}>{t.label}</button>
          ))}
        </div>

        <div className="page-header">
          <div>
            <div className="page-title">Proveedores</div>
            <div className="page-sub">{proveedores.length} registros</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => exportCSV(
              ['nombre', 'razon_social', 'rfc', 'contacto', 'telefono', 'email'],
              proveedores, 'proveedores'
            )}>Exportar CSV</button>
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>Nuevo proveedor</button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <input
            className="input" style={{ maxWidth: 280 }}
            placeholder="Buscar nombre, RFC…"
            value={q} onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: selected ? '1fr 360px' : '1fr',
          gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
        }}>
          <div>
            <DataTable
              columns={COLUMNS}
              data={proveedores}
              loading={loading}
              selectedId={sel}
              onRowClick={(row) => setSel(sel === row.id ? null : row.id)}
              footer={<span>{proveedores.length} proveedores</span>}
              getContextMenuItems={(prov) => [
                { type: 'item', label: 'Editar', onClick: () => openEdit(prov) },
                { type: 'item', label: 'Ver compras',
                  onClick: () => navigate(`/compras?q=${encodeURIComponent(prov.nombre)}`) },
              ]}
            />
          </div>

          {selected && (
            <SidePreview>
              <div className="note">PROVEEDOR</div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.015em', marginTop: 4 }}>
                {selected.nombre}
              </div>
              {selected.razon_social && (
                <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 2 }}>{selected.razon_social}</div>
              )}

              <FieldGrid fields={[
                ['RFC',          selected.rfc],
                ['Contacto',     selected.contacto],
                ['Teléfono',     selected.telefono],
                ['Email',        selected.email],
                ['Compras',      selected.num_compras ?? 0],
                ['Última compra', selected.ultima_compra],
              ]} />

              <div style={{ marginTop: 14 }}>
                <div className="note">TOTAL COMPRADO</div>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em' }}>
                  {selected.monto_total ? MXN.format(selected.monto_total) : '—'}
                </div>
              </div>

              {selected.notas && (
                <div style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-600)' }}>
                  <div className="note">NOTAS</div>
                  <div style={{ marginTop: 2 }}>{selected.notas}</div>
                </div>
              )}

              <div style={{ marginTop: 16, display: 'flex', gap: 6 }}>
                <button className="btn btn-sm btn-primary"
                  onClick={() => navigate(`/compras?proveedor=${selected.id}`)}>
                  Ver compras
                </button>
                <button className="btn btn-sm" onClick={() => openEdit(selected)}>Editar</button>
                <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
              </div>
            </SidePreview>
          )}
        </div>
      </div>

      <Modal open={!!editItem} onClose={() => { setEditItem(null); setFormData(FORM_EMPTY); setFormErr(''); }} title="Editar proveedor">
        <form onSubmit={handleEditar}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOMBRE *</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.nombre}
                onChange={(e) => setFormData((d) => ({ ...d, nombre: e.target.value }))}
                required autoFocus />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RAZÓN SOCIAL</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.razon_social}
                onChange={(e) => setFormData((d) => ({ ...d, razon_social: e.target.value }))} />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RFC</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.rfc}
                onChange={(e) => setFormData((d) => ({ ...d, rfc: e.target.value.toUpperCase() }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CONTACTO</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.contacto}
                  onChange={(e) => setFormData((d) => ({ ...d, contacto: e.target.value }))} />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>TELÉFONO</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.telefono}
                  onChange={(e) => setFormData((d) => ({ ...d, telefono: e.target.value }))} />
              </div>
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>EMAIL</div>
              <input className="input" type="email" style={{ width: '100%' }}
                value={formData.email}
                onChange={(e) => setFormData((d) => ({ ...d, email: e.target.value }))} />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
              <textarea className="input" rows={2} style={{ width: '100%' }}
                value={formData.notas}
                onChange={(e) => setFormData((d) => ({ ...d, notas: e.target.value }))} />
            </div>
          </div>
          {formErr && <div style={{ color: 'var(--danger)', fontSize: 13, marginTop: 12 }}>{formErr}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" className="btn"
              onClick={() => { setEditItem(null); setFormData(FORM_EMPTY); setFormErr(''); }}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      </Modal>

      <Modal open={showForm} onClose={() => { setShowForm(false); setFormData(FORM_EMPTY); setFormErr(''); }} title="Nuevo proveedor">
        <form onSubmit={handleCrear}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOMBRE *</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.nombre}
                onChange={(e) => setFormData((d) => ({ ...d, nombre: e.target.value }))}
                required autoFocus />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RAZÓN SOCIAL</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.razon_social}
                onChange={(e) => setFormData((d) => ({ ...d, razon_social: e.target.value }))} />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RFC</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.rfc}
                onChange={(e) => setFormData((d) => ({ ...d, rfc: e.target.value.toUpperCase() }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CONTACTO</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.contacto}
                  onChange={(e) => setFormData((d) => ({ ...d, contacto: e.target.value }))} />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>TELÉFONO</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.telefono}
                  onChange={(e) => setFormData((d) => ({ ...d, telefono: e.target.value }))} />
              </div>
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>EMAIL</div>
              <input className="input" type="email" style={{ width: '100%' }}
                value={formData.email}
                onChange={(e) => setFormData((d) => ({ ...d, email: e.target.value }))} />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOTAS</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.notas}
                onChange={(e) => setFormData((d) => ({ ...d, notas: e.target.value }))} />
            </div>
          </div>
          {formErr && <div style={{ color: 'var(--danger)', fontSize: 13, marginTop: 12 }}>{formErr}</div>}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 20 }}>
            <button type="button" className="btn"
              onClick={() => { setShowForm(false); setFormData(FORM_EMPTY); setFormErr(''); }}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
