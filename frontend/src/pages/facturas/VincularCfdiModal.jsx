import { useState, useRef } from 'react';
import { Modal } from '../../components/Modal';
import { api } from '../../lib/apiClient';
import { toast } from '../../lib/toast';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 2 });

function FileZone({ onFiles, disabled }) {
  const [over, setOver] = useState(false);
  const inputRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setOver(false);
    if (disabled) return;
    const files = [...e.dataTransfer.files].filter((f) => f.name.endsWith('.xml'));
    if (files.length) onFiles(files);
  }

  function handleChange(e) {
    const files = [...e.target.files];
    if (files.length) onFiles(files);
    e.target.value = '';
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${over ? 'var(--accent)' : 'var(--ink-300)'}`,
        borderRadius: 8, padding: '28px 20px', textAlign: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'border-color 0.15s',
        background: disabled ? '#f9fafb' : over ? '#f0f9ff' : '#fafafa',
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <div style={{ fontSize: 26, marginBottom: 6 }}>📄</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink-700)' }}>
        Arrastra un XML aquí o haz clic para seleccionar
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--ink-400)', marginTop: 3 }}>
        CFDI 4.0 / 3.3 — solo archivos .xml
      </div>
      <input ref={inputRef} type="file" accept=".xml" onChange={handleChange} style={{ display: 'none' }} />
    </div>
  );
}

// facturasVinculadas: array de facturas ya ligadas a esta cotización específica (de CotDetalle)
export function VincularCfdiModal({ open, onClose, cotizacionId, onLinked, facturasVinculadas = [] }) {
  const yaVinculadasIds = new Set(facturasVinculadas.map((f) => f.id));

  const [tab, setTab] = useState('importar');

  // Tab importar
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [linking, setLinking] = useState(false);

  // Tab buscar
  const [q, setQ] = useState('');
  const [facturas, setFacturas] = useState(null);
  const [buscando, setBuscando] = useState(false);
  const [vinculandoId, setVinculandoId] = useState(null);

  function handleClose() {
    setTab('importar');
    setImporting(false);
    setImportResult(null);
    setLinking(false);
    setQ('');
    setFacturas(null);
    onClose();
  }

  async function handleFiles(files) {
    const file = files[0];
    setImporting(true);
    setImportResult(null);
    try {
      const formData = new FormData();
      formData.append('archivo', file);
      const token = sessionStorage.getItem('clf_token');
      const res = await fetch('/api/documentos/cfdi/importar', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const json = await res.json();
      if (!res.ok) {
        toast.error(json.detail ?? 'Error al importar');
        return;
      }
      setImportResult(json);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setImporting(false);
    }
  }

  async function handleVincularImportada() {
    if (!importResult) return;
    setLinking(true);
    try {
      await api.post(`/api/documentos/cfdi/${importResult.id}/vincular`, { cotizacion_id: cotizacionId });
      toast.success('Factura vinculada — cotización marcada como Facturada');
      onLinked();
      handleClose();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLinking(false);
    }
  }

  async function cargarFacturas(texto) {
    setBuscando(true);
    try {
      // Sin filtro sin_vincular: mostramos TODAS las tipo I para permitir
      // vincular una factura que ya tiene otras cotizaciones (caso N:1)
      const params = new URLSearchParams();
      params.set('tipo', 'I');
      if (texto.trim()) params.set('q', texto.trim());
      const data = await api.get(`/api/documentos/cfdi?${params}`);
      setFacturas(data.facturas ?? []);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setBuscando(false);
    }
  }

  async function buscar(texto) {
    setQ(texto);
    await cargarFacturas(texto);
  }

  async function buscarTodas() {
    if (facturas !== null) return;
    await cargarFacturas('');
  }

  async function handleVincularExistente(facturaId) {
    setVinculandoId(facturaId);
    try {
      await api.post(`/api/documentos/cfdi/${facturaId}/vincular`, { cotizacion_id: cotizacionId });
      toast.success('Factura vinculada — cotización marcada como Facturada');
      onLinked();
      handleClose();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setVinculandoId(null);
    }
  }

  const TAB_STYLE = (active) => ({
    padding: '7px 14px', fontSize: 12, fontWeight: active ? 600 : 400,
    border: 'none', background: 'none', cursor: 'pointer',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
    color: active ? 'var(--ink-900)' : 'var(--ink-500)',
  });

  return (
    <Modal open={open} onClose={handleClose} title="Vincular factura de venta" width={580}>
      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--ink-200)', marginBottom: 16, marginTop: -4 }}>
        <button style={TAB_STYLE(tab === 'importar')} onClick={() => setTab('importar')}>
          Importar XML
        </button>
        <button style={TAB_STYLE(tab === 'buscar')} onClick={() => { setTab('buscar'); buscarTodas(); }}>
          Buscar existente
        </button>
      </div>

      {tab === 'importar' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <FileZone onFiles={handleFiles} disabled={importing || !!importResult} />

          {importing && (
            <div style={{ fontSize: 12.5, color: 'var(--ink-500)', textAlign: 'center' }}>
              Procesando XML…
            </div>
          )}

          {importResult && (
            <div style={{
              padding: '12px 14px', borderRadius: 6,
              border: '1px solid #bbf7d0', background: '#f0fdf4',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-800)' }}>
                    {importResult.folio || '—'}
                    {importResult.already_exists && (
                      <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--warn)' }}>ya registrada</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ink-600)', marginTop: 2 }}>
                    {importResult.emisor}
                    {importResult.receptor && importResult.emisor !== importResult.receptor && (
                      <span style={{ color: 'var(--ink-400)', marginLeft: 6 }}>→ {importResult.receptor}</span>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--ink-800)' }}>
                  {importResult.total != null ? MXN.format(importResult.total) : '—'}
                </div>
              </div>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button className="btn btn-sm" onClick={() => setImportResult(null)}>Cambiar</button>
                <button className="btn btn-sm btn-primary" disabled={linking} onClick={handleVincularImportada}>
                  {linking ? 'Vinculando…' : 'Vincular a esta cotización'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'buscar' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <input
            className="input"
            placeholder="Buscar por folio, RFC, nombre…"
            value={q}
            onChange={(e) => buscar(e.target.value)}
            autoFocus
          />

          {buscando && (
            <div style={{ fontSize: 12, color: 'var(--ink-400)', textAlign: 'center', padding: '12px 0' }}>
              Buscando…
            </div>
          )}

          {!buscando && facturas !== null && facturas.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--ink-400)', textAlign: 'center', padding: '12px 0' }}>
              Sin facturas de ingreso registradas.
            </div>
          )}

          {!buscando && facturas && facturas.length > 0 && (
            <div style={{ maxHeight: 340, overflowY: 'auto', border: '1px solid var(--ink-200)', borderRadius: 6 }}>
              {facturas.map((f) => {
                const yaEsta = yaVinculadasIds.has(f.id);
                const nCots  = f.num_cotizaciones ?? 0;

                return (
                  <div key={f.id} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 12px', borderBottom: '1px solid var(--ink-100)', gap: 12,
                    background: yaEsta ? '#f0fdf4' : 'transparent',
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 12.5, fontWeight: 500, fontFamily: 'var(--mono)' }}>
                          {f.folio || '—'}
                        </span>
                        {yaEsta && (
                          <span style={{
                            fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 3,
                            background: '#dcfce7', color: '#166534',
                          }}>
                            Ya vinculada
                          </span>
                        )}
                        {!yaEsta && nCots > 0 && (
                          <span style={{
                            fontSize: 10, padding: '1px 6px', borderRadius: 3,
                            background: 'var(--ink-100)', color: 'var(--ink-500)',
                          }}>
                            {nCots} {nCots === 1 ? 'cotización' : 'cotizaciones'} vinculada{nCots !== 1 ? 's' : ''}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11.5, color: 'var(--ink-500)', marginTop: 3, display: 'flex', gap: 6 }}>
                        <span>{f.nombre_emisor ?? f.nombre_receptor ?? '—'}</span>
                        <span>·</span>
                        <span>{f.fecha ?? '—'}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>
                        {f.total != null ? MXN.format(f.total) : '—'}
                      </div>
                      {yaEsta ? (
                        <div style={{ fontSize: 10.5, color: '#166534', marginTop: 4 }}>
                          ✓ vinculada
                        </div>
                      ) : (
                        <button
                          className="btn btn-sm btn-primary"
                          style={{ fontSize: 10.5, marginTop: 4 }}
                          disabled={vinculandoId === f.id}
                          onClick={() => handleVincularExistente(f.id)}
                        >
                          {vinculandoId === f.id ? '…' : 'Vincular'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}
