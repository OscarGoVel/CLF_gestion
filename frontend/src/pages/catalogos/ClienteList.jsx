import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { DataTable } from '../../components/DataTable';
import { SidePreview, FieldGrid } from '../../components/SidePreview';
import { Historial } from '../../components/Historial';
import { MultiSelectDropdown } from '../../components/MultiSelectDropdown';
import { Modal } from '../../components/Modal';
import { exportCSV } from '../../lib/exportCSV';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });

const TIPO_COLOR = {
  Empresa:  { bg: '#eff6ff', color: '#1d4ed8' },
  Gobierno: { bg: '#f5f3ff', color: '#6d28d9' },
  Persona:  { bg: '#f0fdf4', color: '#166534' },
};

const FORM_EMPTY = {
  nombre_comercial: '', razon_social: '', tipo: '',
  rfc: '', contacto: '', telefono: '', email: '', direccion: '',
};

const COLUMNS = [
  {
    header: 'Nombre comercial', sortKey: 'nombre_comercial',
    render: (c) => <span style={{ fontWeight: 500 }}>{c.nombre_comercial}</span>,
  },
  {
    header: 'Tipo', width: 90,
    render: (c) => c.tipo ? (
      <span style={{
        fontSize: 11, padding: '2px 7px', borderRadius: 3,
        background: TIPO_COLOR[c.tipo]?.bg ?? '#f3f4f6',
        color: TIPO_COLOR[c.tipo]?.color ?? '#374151',
      }}>{c.tipo}</span>
    ) : null,
  },
  { header: 'RFC',      width: 130, style: { fontFamily: 'var(--mono)', fontSize: 11.5 },
    render: (c) => c.rfc ?? '—' },
  { header: 'Contacto', width: 160, style: { fontSize: 12, color: 'var(--ink-600)' },
    render: (c) => c.contacto ?? '—' },
  { header: 'Cots.',  key: 'num_cotizaciones', className: 'num', width: 80,  sortKey: 'num_cotizaciones' },
  { header: 'Total',  className: 'num', width: 120, sortKey: 'monto_total',
    render: (c) => c.monto_total ? MXN.format(c.monto_total) : '—' },
];

export default function ClienteList() {
  const navigate = useNavigate();
  const [q, setQ]           = useState('');
  const [tipoFiltro, setTipoFiltro] = useState([]);
  const [sel, setSel]       = useState(null);
  const [refetch, setRefetch] = useState(0);
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [formData, setFormData] = useState(FORM_EMPTY);
  const [saving, setSaving] = useState(false);
  const [formErr, setFormErr] = useState('');

  const params = new URLSearchParams();
  if (q) params.set('q', q);
  tipoFiltro.forEach((t) => params.append('tipo', t));
  if (refetch) params.set('_r', refetch);

  const { data, loading } = useFetch(`/api/catalogos/clientes?${params}`);
  const clientes = data?.clientes ?? [];
  const tipos    = data?.tipos    ?? [];
  const selected = sel != null ? clientes.find((c) => c.id === sel) : null;

  const tipoOptions = tipos.map((t) => ({ label: t, value: t }));

  const handleCrear = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormErr('');
    try {
      await api.post('/api/catalogos/clientes', formData);
      setShowForm(false);
      setFormData(FORM_EMPTY);
      setRefetch((n) => n + 1);
      toast.success('Cliente guardado');
    } catch (err) {
      setFormErr(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleEditar = async (e) => {
    e.preventDefault();
    setSaving(true);
    setFormErr('');
    try {
      await api.patch(`/api/catalogos/clientes/${editItem.id}`, formData);
      setEditItem(null);
      setFormData(FORM_EMPTY);
      setSel(null);
      setRefetch((n) => n + 1);
      toast.success('Cliente actualizado');
    } catch (err) {
      setFormErr(err.message);
    } finally {
      setSaving(false);
    }
  };

  function openEdit(cliente) {
    setFormData({
      nombre_comercial: cliente.nombre_comercial ?? '',
      razon_social:     cliente.razon_social ?? '',
      tipo:             cliente.tipo ?? '',
      rfc:              cliente.rfc ?? '',
      contacto:         cliente.contacto ?? '',
      telefono:         cliente.telefono ?? '',
      email:            cliente.email ?? '',
      direccion:        cliente.direccion ?? '',
    });
    setFormErr('');
    setEditItem(cliente);
  }

  return (
    <>
      <div className="page">
        <div className="crumbs">
          <a onClick={() => navigate('/panel')}>LOGOS</a>
          <span className="sep">/</span>
          <span>Catálogos</span>
          <span className="sep">/</span>
          <span>Clientes</span>
        </div>

        <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--ink-200)', marginBottom: 20 }}>
          {[
            { label: 'Clientes',    path: '/comercial/clientes' },
            { label: 'Productos',   path: '/inventario/productos' },
            { label: 'Proveedores', path: '/abastecimiento/proveedores' },
          ].map((t) => (
            <button key={t.path} onClick={() => navigate(t.path)} style={{
              padding: '7px 18px', fontSize: 13, background: 'none', border: 'none', cursor: 'pointer',
              fontWeight: t.path === '/comercial/clientes' ? 500 : 400,
              color: t.path === '/comercial/clientes' ? 'var(--ink-900)' : 'var(--ink-500)',
              borderBottom: t.path === '/comercial/clientes' ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: -1,
            }}>{t.label}</button>
          ))}
        </div>

        <div className="page-header">
          <div>
            <div className="page-title">Clientes</div>
            <div className="page-sub">{clientes.length} registros</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn" onClick={() => exportCSV(
              ['nombre_comercial', 'razon_social', 'tipo', 'rfc', 'contacto', 'telefono', 'email'],
              clientes, 'clientes'
            )}>Exportar CSV</button>
            <button className="btn btn-primary" onClick={() => setShowForm(true)}>Nuevo cliente</button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginBottom: 16 }}>
          <input
            className="input" style={{ maxWidth: 280 }}
            placeholder="Buscar nombre, RFC, contacto…"
            value={q} onChange={(e) => setQ(e.target.value)}
          />
          <MultiSelectDropdown options={tipoOptions} values={tipoFiltro} onChange={setTipoFiltro} placeholder="Tipo…" />
        </div>

        <div style={{
          display: 'grid', gridTemplateColumns: selected ? '1fr 360px' : '1fr',
          gap: 0, border: '1px solid var(--ink-200)', borderRadius: 6, overflow: 'hidden',
        }}>
          <div>
            <DataTable
              columns={COLUMNS}
              data={clientes}
              loading={loading}
              selectedId={sel}
              onRowClick={(row) => setSel(sel === row.id ? null : row.id)}
              footer={<span>{clientes.length} clientes</span>}
              getContextMenuItems={(cliente) => [
                { type: 'item', label: 'Ver cotizaciones',
                  onClick: () => navigate(`/cotizaciones?cliente=${cliente.id}`) },
                { type: 'item', label: 'Editar',
                  onClick: () => openEdit(cliente) },
              ]}
            />
          </div>

          {selected && (
            <SidePreview>
              <div className="note">CLIENTE</div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 20, letterSpacing: '-0.015em', marginTop: 4 }}>
                {selected.nombre_comercial}
              </div>
              {selected.razon_social && (
                <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 2 }}>{selected.razon_social}</div>
              )}

              <FieldGrid fields={[
                ['RFC',        selected.rfc],
                ['Tipo',       selected.tipo],
                ['Teléfono',   selected.telefono],
                ['Email',      selected.email],
                ['Cotizaciones', selected.num_cotizaciones],
                ['Última cot.', selected.ultima_cotizacion],
              ]} />

              <div style={{ marginTop: 14 }}>
                <div className="note">TOTAL VENDIDO</div>
                <div style={{ fontFamily: 'var(--serif)', fontSize: 22, marginTop: 4, letterSpacing: '-0.02em' }}>
                  {selected.monto_total ? MXN.format(selected.monto_total) : '—'}
                </div>
              </div>

              {selected.direccion && (
                <div style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-600)' }}>
                  <div className="note">DIRECCIÓN</div>
                  <div style={{ marginTop: 2 }}>{selected.direccion}</div>
                </div>
              )}

              <div style={{ marginTop: 16, display: 'flex', gap: 6 }}>
                <button className="btn btn-sm btn-primary"
                  onClick={() => navigate(`/cotizaciones?cliente=${selected.id}`)}>
                  Ver cotizaciones
                </button>
                <button className="btn btn-sm" onClick={() => openEdit(selected)}>Editar</button>
                <button className="btn btn-sm" onClick={() => setSel(null)}>Cerrar ×</button>
              </div>
              <Historial entidad="cliente" entidadId={selected?.id} />
            </SidePreview>
          )}
        </div>
      </div>

      <Modal open={!!editItem} onClose={() => { setEditItem(null); setFormData(FORM_EMPTY); setFormErr(''); }} title="Editar cliente">
        <form onSubmit={handleEditar}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOMBRE COMERCIAL *</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.nombre_comercial}
                onChange={(e) => setFormData((d) => ({ ...d, nombre_comercial: e.target.value }))}
                required autoFocus />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RAZÓN SOCIAL</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.razon_social}
                onChange={(e) => setFormData((d) => ({ ...d, razon_social: e.target.value }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>TIPO</div>
                <select className="input" style={{ width: '100%' }}
                  value={formData.tipo}
                  onChange={(e) => setFormData((d) => ({ ...d, tipo: e.target.value }))}>
                  <option value="">— Sin tipo —</option>
                  <option>Empresa</option>
                  <option>Gobierno</option>
                  <option>Persona</option>
                </select>
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>RFC</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.rfc}
                  onChange={(e) => setFormData((d) => ({ ...d, rfc: e.target.value.toUpperCase() }))} />
              </div>
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
              <div className="note" style={{ marginBottom: 4 }}>DIRECCIÓN</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.direccion}
                onChange={(e) => setFormData((d) => ({ ...d, direccion: e.target.value }))} />
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

      <Modal open={showForm} onClose={() => { setShowForm(false); setFormData(FORM_EMPTY); setFormErr(''); }} title="Nuevo cliente">
        <form onSubmit={handleCrear}>
          <div style={{ display: 'grid', gap: 12 }}>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>NOMBRE COMERCIAL *</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.nombre_comercial}
                onChange={(e) => setFormData((d) => ({ ...d, nombre_comercial: e.target.value }))}
                required autoFocus />
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>RAZÓN SOCIAL</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.razon_social}
                onChange={(e) => setFormData((d) => ({ ...d, razon_social: e.target.value }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>TIPO</div>
                <select className="input" style={{ width: '100%' }}
                  value={formData.tipo}
                  onChange={(e) => setFormData((d) => ({ ...d, tipo: e.target.value }))}>
                  <option value="">— Sin tipo —</option>
                  <option>Empresa</option>
                  <option>Gobierno</option>
                  <option>Persona</option>
                </select>
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>RFC</div>
                <input className="input" style={{ width: '100%' }}
                  value={formData.rfc}
                  onChange={(e) => setFormData((d) => ({ ...d, rfc: e.target.value.toUpperCase() }))} />
              </div>
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
              <div className="note" style={{ marginBottom: 4 }}>DIRECCIÓN</div>
              <input className="input" style={{ width: '100%' }}
                value={formData.direccion}
                onChange={(e) => setFormData((d) => ({ ...d, direccion: e.target.value }))} />
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
