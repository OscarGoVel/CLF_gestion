import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';
import { useFetch } from '../../hooks/useFetch';
import { toast } from '../../lib/toast';

const UNIDADES = ['pza', 'kg', 'lt', 'mt', 'cja', 'par', 'set', 'srv'];

export default function ProductoNuevo() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    nombre: '',
    codigo: '',
    descripcion: '',
    categoria_id: '',
    subcategoria_id: '',
    unidad_medida: '',
    precio_base: '',
    aplica_iva: false,
    stock_minimo: '',
    clave_sat: '',
    clave_unidad_sat: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  const { data: catData } = useFetch('/api/catalogos/categorias');
  const categorias    = catData?.categorias    ?? [];
  const subcategorias = catData?.subcategorias ?? [];
  const subsFiltradas = form.categoria_id
    ? subcategorias.filter((s) => s.categoria_id === parseInt(form.categoria_id))
    : subcategorias;

  function set(field, value) {
    setForm((f) => {
      const next = { ...f, [field]: value };
      if (field === 'categoria_id') next.subcategoria_id = '';
      return next;
    });
    setFieldErrors((e) => ({ ...e, [field]: '' }));
  }

  function validate() {
    const errs = {};
    if (!form.nombre.trim()) errs.nombre = 'Requerido';
    if (!form.codigo.trim()) errs.codigo = 'Requerido';
    if (form.precio_base !== '' && (isNaN(parseFloat(form.precio_base)) || parseFloat(form.precio_base) < 0))
      errs.precio_base = 'Debe ser número ≥ 0';
    if (form.stock_minimo !== '' && (isNaN(parseFloat(form.stock_minimo)) || parseFloat(form.stock_minimo) < 0))
      errs.stock_minimo = 'Debe ser número ≥ 0';
    return errs;
  }

  async function handleGuardar(e) {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setFieldErrors(errs); return; }

    setSaving(true);
    setError('');
    try {
      await api.post('/api/catalogos/productos', {
        nombre:           form.nombre.trim(),
        codigo:           form.codigo.trim(),
        descripcion:      form.descripcion.trim() || null,
        categoria_id:     form.categoria_id    ? parseInt(form.categoria_id)    : null,
        subcategoria_id:  form.subcategoria_id ? parseInt(form.subcategoria_id) : null,
        unidad_medida:    form.unidad_medida.trim() || null,
        precio_base:      form.precio_base !== '' ? parseFloat(form.precio_base) : 0,
        aplica_iva:       form.aplica_iva,
        stock_minimo:     form.stock_minimo !== '' ? parseFloat(form.stock_minimo) : 0,
        clave_sat:        form.clave_sat.trim() || null,
        clave_unidad_sat: form.clave_unidad_sat.trim() || null,
      });
      toast.success('Producto creado');
      navigate('/catalogos/productos');
    } catch (err) {
      if (err.status === 409) setFieldErrors((e) => ({ ...e, codigo: 'Este código ya existe' }));
      else setError(err.message ?? 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/dashboard')}>CLF Gestión</a>
        <span className="sep">/</span>
        <a onClick={() => navigate('/catalogos/productos')}>Productos</a>
        <span className="sep">/</span>
        <span>Nuevo producto</span>
      </div>

      <form onSubmit={handleGuardar}>
        <div className="page-header">
          <div>
            <div className="page-title">Nuevo producto</div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn" onClick={() => navigate('/catalogos/productos')}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar producto'}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ color: 'var(--danger)', background: 'var(--danger-bg, #fff0f0)',
            border: '1px solid var(--danger)', borderRadius: 6, padding: '10px 14px',
            fontSize: 13, marginBottom: 16 }}>
            {error}
          </div>
        )}

        <div style={{ display: 'grid', gap: 16 }}>

          {/* Datos básicos */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: 'var(--ink-700)' }}>
              Datos básicos
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>NOMBRE *</div>
                <input
                  className="input" style={{ width: '100%' }}
                  value={form.nombre}
                  onChange={(e) => set('nombre', e.target.value)}
                  autoFocus placeholder="Nombre del producto"
                />
                {fieldErrors.nombre && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 3 }}>{fieldErrors.nombre}</div>}
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CÓDIGO / SKU *</div>
                <input
                  className="input" style={{ width: '100%', fontFamily: 'var(--mono)' }}
                  value={form.codigo}
                  onChange={(e) => set('codigo', e.target.value)}
                  placeholder="P-001, SKU-XXX…"
                />
                {fieldErrors.codigo && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 3 }}>{fieldErrors.codigo}</div>}
              </div>
            </div>
          </div>

          {/* Categorización */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: 'var(--ink-700)' }}>
              Categorización
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CATEGORÍA</div>
                <select
                  className="input" style={{ width: '100%' }}
                  value={form.categoria_id}
                  onChange={(e) => set('categoria_id', e.target.value)}
                >
                  <option value="">Sin categoría</option>
                  {categorias.map((c) => (
                    <option key={c.id} value={c.id}>{c.nombre}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>SUBCATEGORÍA</div>
                <select
                  className="input" style={{ width: '100%' }}
                  value={form.subcategoria_id}
                  onChange={(e) => set('subcategoria_id', e.target.value)}
                  disabled={!form.categoria_id}
                >
                  <option value="">Sin subcategoría</option>
                  {subsFiltradas.map((s) => (
                    <option key={s.id} value={s.id}>{s.nombre}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>UNIDAD DE MEDIDA</div>
                <input
                  className="input" list="unidades-list" style={{ width: '100%' }}
                  value={form.unidad_medida}
                  onChange={(e) => set('unidad_medida', e.target.value)}
                  placeholder="pza, kg, lt…"
                />
                <datalist id="unidades-list">
                  {UNIDADES.map((u) => <option key={u} value={u} />)}
                </datalist>
              </div>
            </div>
          </div>

          {/* Comercial */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: 'var(--ink-700)' }}>
              Comercial
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>COSTO BASE (catálogo)</div>
                <input
                  className="input" type="number" min="0" step="0.01" style={{ width: '100%' }}
                  value={form.precio_base}
                  onChange={(e) => set('precio_base', e.target.value)}
                  placeholder="0.00"
                />
                {fieldErrors.precio_base && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 3 }}>{fieldErrors.precio_base}</div>}
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>STOCK MÍNIMO</div>
                <input
                  className="input" type="number" min="0" step="1" style={{ width: '100%' }}
                  value={form.stock_minimo}
                  onChange={(e) => set('stock_minimo', e.target.value)}
                  placeholder="0"
                />
                {fieldErrors.stock_minimo && <div style={{ color: 'var(--danger)', fontSize: 12, marginTop: 3 }}>{fieldErrors.stock_minimo}</div>}
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-end', paddingBottom: 2 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13 }}>
                  <input
                    type="checkbox"
                    checked={form.aplica_iva}
                    onChange={(e) => set('aplica_iva', e.target.checked)}
                  />
                  Aplica IVA (16%)
                </label>
              </div>
            </div>
          </div>

          {/* Adicionales */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: 'var(--ink-700)' }}>
              Adicionales
            </div>
            <div>
              <div className="note" style={{ marginBottom: 4 }}>DESCRIPCIÓN</div>
              <textarea
                className="input" rows={3} style={{ width: '100%', resize: 'vertical' }}
                value={form.descripcion}
                onChange={(e) => set('descripcion', e.target.value)}
                placeholder="Descripción del producto…"
              />
            </div>
          </div>

          {/* SAT */}
          <div className="card" style={{ padding: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 16, color: 'var(--ink-700)' }}>
              Facturación SAT
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CLAVE SAT (PRODUCTO/SERVICIO)</div>
                <input
                  className="input" style={{ width: '100%', fontFamily: 'var(--mono)' }}
                  value={form.clave_sat}
                  onChange={(e) => set('clave_sat', e.target.value)}
                  placeholder="ej. 43211500"
                />
              </div>
              <div>
                <div className="note" style={{ marginBottom: 4 }}>CLAVE UNIDAD SAT</div>
                <input
                  className="input" style={{ width: '100%', fontFamily: 'var(--mono)' }}
                  value={form.clave_unidad_sat}
                  onChange={(e) => set('clave_unidad_sat', e.target.value)}
                  placeholder="ej. H87"
                />
              </div>
            </div>
          </div>

        </div>
      </form>
    </div>
  );
}
