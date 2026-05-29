import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';
import { StatusBadge } from '../../components/StatusBadge';
import { Modal } from '../../components/Modal';
import { EmptyState } from '../../components/EmptyState';

const BLANK = { nombre: '', rfc: '', regimen_fiscal: '', codigo_postal: '', domicilio: '', es_default: false, activa: true };

export default function AdminRazonesSociales() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/razones-sociales');
  const lista = data?.razones_sociales ?? [];

  const [modal, setModal] = useState(null); // null | 'nueva' | { ...rs }
  const [form, setForm]   = useState(BLANK);
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  function abrirNueva() { setForm(BLANK); setError(''); setModal('nueva'); }
  function abrirEditar(rs) {
    setForm({
      nombre: rs.nombre, rfc: rs.rfc, regimen_fiscal: rs.regimen_fiscal ?? '',
      codigo_postal: rs.codigo_postal ?? '', domicilio: rs.domicilio ?? '',
      es_default: rs.es_default, activa: rs.activa,
    });
    setError('');
    setModal(rs);
  }
  function cerrar() { setModal(null); setError(''); }

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })); }

  async function handleGuardar(e) {
    e.preventDefault();
    if (!form.nombre.trim() || !form.rfc.trim()) { setError('Nombre y RFC son requeridos'); return; }
    setSaving(true);
    setError('');
    try {
      const body = { ...form, rfc: form.rfc.trim().toUpperCase() };
      if (modal === 'nueva') {
        await api.post('/api/razones-sociales', body);
        toast.success('Razón social creada');
      } else {
        await api.put(`/api/razones-sociales/${modal.id}`, body);
        toast.success('Razón social actualizada');
      }
      cerrar();
      await refetch();
    } catch (err) { setError(err.message ?? 'Error al guardar'); }
    finally { setSaving(false); }
  }

  async function handleDesactivar(rs) {
    if (!window.confirm(`¿Desactivar "${rs.nombre}"?`)) return;
    try {
      await api.delete(`/api/razones-sociales/${rs.id}`);
      toast.success('Razón social desactivada');
      await refetch();
    } catch (err) { toast.error(err.message ?? 'Error'); }
  }

  async function handleDefault(rs) {
    try {
      await api.put(`/api/razones-sociales/${rs.id}/default`);
      toast.success(`"${rs.nombre}" es ahora la RS predeterminada`);
      await refetch();
    } catch (err) { toast.error(err.message ?? 'Error'); }
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/panel')}>LOGOS</a>
        <span className="sep">/</span>
        <span>Administración</span>
        <span className="sep">/</span>
        <span>Razones Sociales</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Razones Sociales</div>
          <div className="page-sub">Entidades legales con RFC propio que operan bajo LOGOS</div>
        </div>
        <button className="btn btn-primary" onClick={abrirNueva}>Nueva razón social</button>
      </div>

      {loading ? (
        <div className="card" style={{ padding: 32, textAlign: 'center', color: 'var(--ink-400)' }}>Cargando…</div>
      ) : lista.length === 0 ? (
        <EmptyState icon="admin" title="Sin razones sociales" body="Crea la primera entidad legal de la empresa." />
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th>Nombre</th>
                <th>RFC</th>
                <th>Régimen fiscal</th>
                <th>C.P.</th>
                <th>Default</th>
                <th>Estado</th>
                <th style={{ width: 160 }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {lista.map(rs => (
                <tr key={rs.id}>
                  <td style={{ fontWeight: 500 }}>{rs.nombre}</td>
                  <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{rs.rfc}</td>
                  <td style={{ color: 'var(--ink-500)', fontSize: 12 }}>{rs.regimen_fiscal ?? '—'}</td>
                  <td style={{ color: 'var(--ink-500)', fontSize: 12 }}>{rs.codigo_postal ?? '—'}</td>
                  <td>
                    {rs.es_default
                      ? <StatusBadge status="Activo" label="Principal" />
                      : <button className="btn btn-ghost btn-sm" onClick={() => handleDefault(rs)} disabled={!rs.activa}>Marcar</button>
                    }
                  </td>
                  <td><StatusBadge status={rs.activa ? 'Activo' : 'Cancelado'} /></td>
                  <td>
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => abrirEditar(rs)}>Editar</button>
                      {rs.activa && !rs.es_default && (
                        <button className="btn btn-ghost btn-sm" style={{ color: 'var(--danger)' }}
                          onClick={() => handleDesactivar(rs)}>Desactivar</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <Modal open={!!modal} title={modal === 'nueva' ? 'Nueva razón social' : 'Editar razón social'} onClose={cerrar}>
          <form onSubmit={handleGuardar}>
            <div style={{ display: 'grid', gap: 14 }}>
              <div>
                <label className="label">Nombre legal *</label>
                <input className="input" style={{ width: '100%' }}
                  value={form.nombre} onChange={e => setF('nombre', e.target.value)}
                  placeholder="Ej. Distribuciones XYZ S.A. de C.V." autoFocus />
              </div>
              <div>
                <label className="label">RFC *</label>
                <input className="input" style={{ width: '100%', textTransform: 'uppercase' }}
                  value={form.rfc} onChange={e => setF('rfc', e.target.value.toUpperCase())}
                  placeholder="Ej. DXYZ800101AAA" maxLength={13} />
              </div>
              <div>
                <label className="label">Régimen fiscal</label>
                <input className="input" style={{ width: '100%' }}
                  value={form.regimen_fiscal} onChange={e => setF('regimen_fiscal', e.target.value)}
                  placeholder="Ej. 601 - General de Ley Personas Morales" />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <div>
                  <label className="label">Código postal</label>
                  <input className="input" style={{ width: '100%' }}
                    value={form.codigo_postal} onChange={e => setF('codigo_postal', e.target.value)}
                    placeholder="97345" maxLength={5} />
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
                  <input type="checkbox" id="rs-default" checked={form.es_default}
                    onChange={e => setF('es_default', e.target.checked)} />
                  <label htmlFor="rs-default" style={{ fontSize: 13, cursor: 'pointer' }}>RS predeterminada</label>
                </div>
              </div>
              <div>
                <label className="label">Domicilio fiscal</label>
                <textarea className="input" style={{ width: '100%', minHeight: 60, resize: 'vertical' }}
                  value={form.domicilio} onChange={e => setF('domicilio', e.target.value)}
                  placeholder="Calle, No., Colonia, Municipio, Estado" />
              </div>
            </div>
            {error && <div className="login-error" style={{ marginTop: 12 }}>{error}</div>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 20 }}>
              <button type="button" className="btn btn-ghost" onClick={cerrar}>Cancelar</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Guardando…' : 'Guardar'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
