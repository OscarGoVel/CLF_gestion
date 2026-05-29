import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFetch } from '../../hooks/useFetch';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const CATEGORIAS = ['informativo', 'promocional', 'secuencia', 'reactivacion'];

export default function Plantillas() {
  const navigate = useNavigate();
  const { data, loading, refetch } = useFetch('/api/comercial/crm/plantillas');
  const plantillas = data?.plantillas ?? [];
  const [showModal, setShowModal] = useState(false);
  const [editando, setEditando]   = useState(null);

  function handleEditar(p) {
    setEditando(p);
    setShowModal(true);
  }

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/comercial/crm')}>CRM</a>
        <span className="sep">/</span>
        <span>Plantillas</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Plantillas de correo</div>
          <div className="page-sub">Diseños HTML reutilizables con variables dinámicas</div>
        </div>
        <button className="btn btn-primary" onClick={() => { setEditando(null); setShowModal(true); }}>
          Nueva plantilla
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
        {loading && <div style={{ padding: 24, color: 'var(--ink-400)' }}>Cargando…</div>}
        {!loading && plantillas.length === 0 && (
          <div className="card" style={{ padding: 24, color: 'var(--ink-400)', gridColumn: '1/-1' }}>
            Sin plantillas — crea la primera
          </div>
        )}
        {plantillas.map(p => (
          <div key={p.id} className="card" style={{ padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{p.nombre}</div>
              <CategoriaPill cat={p.categoria} />
            </div>
            {p.asunto_default && (
              <div style={{ fontSize: 12, color: 'var(--ink-400)', marginBottom: 8 }}>
                Asunto: {p.asunto_default}
              </div>
            )}
            {Array.isArray(p.variables_json) && p.variables_json.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                {p.variables_json.map(v => (
                  <span key={v} style={{
                    display: 'inline-block', marginRight: 4, marginBottom: 4,
                    padding: '1px 6px', background: '#f3f4f6', borderRadius: 4,
                    fontSize: 11, color: '#374151', fontFamily: 'monospace',
                  }}>
                    {`{{${v}}}`}
                  </span>
                ))}
              </div>
            )}
            <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
              <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }}
                onClick={() => handleEditar(p)}>Editar</button>
              <PreviewBtn plantillaId={p.id} />
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <PlantillaModal
          initial={editando}
          onClose={() => { setShowModal(false); setEditando(null); }}
          onSaved={() => {
            setShowModal(false); setEditando(null);
            refetch();
            toast.success(editando ? 'Plantilla actualizada' : 'Plantilla creada');
          }}
        />
      )}
    </div>
  );
}

function CategoriaPill({ cat }) {
  const map = {
    informativo:  { bg: '#dbeafe', color: '#1e40af' },
    promocional:  { bg: '#fef3c7', color: '#92400e' },
    secuencia:    { bg: '#d1fae5', color: '#065f46' },
    reactivacion: { bg: '#fee2e2', color: '#991b1b' },
  };
  const s = map[cat] ?? { bg: '#f3f4f6', color: '#374151' };
  return (
    <span style={{ background: s.bg, color: s.color, padding: '2px 8px',
                   borderRadius: 10, fontSize: 11, fontWeight: 600 }}>
      {cat}
    </span>
  );
}

function PreviewBtn({ plantillaId }) {
  const [open, setOpen] = useState(false);
  const [html, setHtml] = useState('');

  async function handleOpen() {
    try {
      const r = await api.post(`/api/comercial/crm/plantillas/${plantillaId}/preview`, {});
      setHtml(r.html);
      setOpen(true);
    } catch (e) {
      toast.error(e.message);
    }
  }

  return (
    <>
      <button className="btn" style={{ padding: '2px 10px', fontSize: 12 }} onClick={handleOpen}>
        Vista previa
      </button>
      {open && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
          <div className="card" style={{ width: '80vw', maxWidth: 700, maxHeight: '85vh',
                                        display: 'flex', flexDirection: 'column', padding: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          padding: '14px 20px', borderBottom: '1px solid var(--ink-100)' }}>
              <span style={{ fontWeight: 600 }}>Vista previa</span>
              <button className="btn" onClick={() => setOpen(false)}>✕ Cerrar</button>
            </div>
            <iframe
              srcDoc={html || '<p style="padding:20px;color:#888">Sin contenido</p>'}
              style={{ flex: 1, border: 'none', minHeight: 400 }}
              sandbox="allow-same-origin"
              title="preview"
            />
          </div>
        </div>
      )}
    </>
  );
}

function PlantillaModal({ initial, onClose, onSaved }) {
  const [nombre,   setNombre]   = useState(initial?.nombre   ?? '');
  const [cat,      setCat]      = useState(initial?.categoria ?? 'informativo');
  const [asunto,   setAsunto]   = useState(initial?.asunto_default ?? '');
  const [html,     setHtml]     = useState(initial?.html_body ?? '');
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState('');
  const [showImgs, setShowImgs] = useState(false);
  const textareaRef = useRef(null);

  const HTML_STARTER = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px">
  <h2 style="color:#2563EB">Hola {{nombre_comercial}},</h2>
  <p>Escribe tu mensaje aquí.</p>
  <p style="color:#888;font-size:12px">
    LOGOS — <a href="#">Cancelar suscripción</a>
  </p>
</body>
</html>`;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!nombre.trim()) { setError('Nombre requerido'); return; }
    setSaving(true); setError('');
    try {
      if (initial?.id) {
        await api.patch(`/api/comercial/crm/plantillas/${initial.id}`, {
          nombre: nombre.trim(), categoria: cat,
          asunto_default: asunto.trim() || null, html_body: html,
        });
      } else {
        await api.post('/api/comercial/crm/plantillas', {
          nombre: nombre.trim(), categoria: cat,
          asunto_default: asunto.trim() || null, html_body: html || HTML_STARTER,
        });
      }
      onSaved();
    } catch (e) {
      setError(e.message);
      setSaving(false);
    }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="card" style={{ width: '90vw', maxWidth: 800, padding: 28,
                                    maxHeight: '92vh', overflowY: 'auto' }}>
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 20 }}>
          {initial ? 'Editar plantilla' : 'Nueva plantilla'}
        </div>
        {error && <div style={{ marginBottom: 14, padding: '8px 12px', background: '#fef2f2',
                               border: '1px solid #fca5a5', borderRadius: 6, color: '#dc2626', fontSize: 13 }}>{error}</div>}
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Nombre *</label>
              <input className="input" style={{ width: '100%' }} value={nombre}
                onChange={e => setNombre(e.target.value)} placeholder="Ej. Bienvenida clientes" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Categoría</label>
              <select className="input" style={{ width: '100%' }} value={cat} onChange={e => setCat(e.target.value)}>
                {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 500, marginBottom: 6 }}>Asunto predeterminado</label>
            <input className="input" style={{ width: '100%' }} value={asunto}
              onChange={e => setAsunto(e.target.value)} placeholder="Ej. Novedades de LOGOS para {{nombre_comercial}}" />
          </div>
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ fontSize: 13, fontWeight: 500 }}>HTML del correo</label>
              <div style={{ display: 'flex', gap: 6 }}>
                {!html && (
                  <button type="button" className="btn" style={{ padding: '2px 10px', fontSize: 12 }}
                    onClick={() => setHtml(HTML_STARTER)}>Insertar plantilla base</button>
                )}
                <button type="button" className="btn" style={{ padding: '2px 10px', fontSize: 12 }}
                  onClick={() => setShowImgs(v => !v)}>
                  {showImgs ? 'Ocultar imágenes' : 'Imágenes'}
                </button>
              </div>
            </div>
            <textarea
              ref={textareaRef}
              className="input"
              style={{ width: '100%', minHeight: 280, fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
              value={html}
              onChange={e => setHtml(e.target.value)}
              placeholder="HTML del correo. Usa {{nombre_comercial}}, {{contacto}}, etc."
            />
            {showImgs && (
              <ImagenUploader
                onInsert={(url) => {
                  const ta = textareaRef.current;
                  const tag = `<img src="${url}" alt="" style="max-width:100%">`;
                  if (!ta) { setHtml(h => h + tag); return; }
                  const start = ta.selectionStart;
                  const end   = ta.selectionEnd;
                  setHtml(h => h.slice(0, start) + tag + h.slice(end));
                  requestAnimationFrame(() => {
                    ta.focus();
                    ta.setSelectionRange(start + tag.length, start + tag.length);
                  });
                }}
              />
            )}
            <div style={{ fontSize: 11, color: 'var(--ink-400)', marginTop: 4 }}>
              Variables disponibles: {'{{nombre_comercial}} {{contacto}} {{razon_social}} {{rfc}} {{email}} {{telefono}}'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button type="button" className="btn" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ImagenUploader({ onInsert }) {
  const { data, loading, refetch } = useFetch('/api/comercial/crm/plantillas/imagenes');
  const imagenes   = data?.imagenes ?? [];
  const [uploading, setUploading] = useState(false);
  const inputRef   = useRef(null);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const r = await api.upload('/api/comercial/crm/plantillas/imagenes', form);
      toast.success('Imagen subida');
      refetch();
      onInsert(r.url);
    } catch (err) {
      toast.error(err.message);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  }

  return (
    <div style={{ marginTop: 8, padding: 12, background: '#f8fafc',
                  border: '1px solid var(--ink-100)', borderRadius: 6 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-600)' }}>
          Imágenes disponibles
        </span>
        <button type="button" className="btn btn-primary"
          style={{ padding: '2px 10px', fontSize: 12 }}
          disabled={uploading} onClick={() => inputRef.current?.click()}>
          {uploading ? 'Subiendo…' : 'Subir imagen'}
        </button>
        <input ref={inputRef} type="file"
          accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
          style={{ display: 'none' }} onChange={handleFile} />
      </div>
      {loading && <div style={{ fontSize: 12, color: 'var(--ink-400)' }}>Cargando…</div>}
      {!loading && imagenes.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--ink-400)' }}>
          Sin imágenes — sube una para insertarla en la plantilla.
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, maxHeight: 160, overflowY: 'auto' }}>
        {imagenes.map(img => (
          <div key={img.url} title={`${img.nombre} (${img.size_kb} KB) — clic para insertar`}
            style={{ cursor: 'pointer', border: '1px solid var(--ink-100)',
                     borderRadius: 4, padding: 4, background: '#fff' }}
            onClick={() => onInsert(img.url)}>
            <img src={img.url} alt={img.nombre}
              style={{ width: 64, height: 48, objectFit: 'contain', display: 'block' }} />
            <span style={{ fontSize: 10, color: 'var(--ink-400)', maxWidth: 70, display: 'block',
                           overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {img.nombre}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
