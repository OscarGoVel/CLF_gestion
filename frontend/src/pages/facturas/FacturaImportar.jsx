import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/apiClient';

const MXN = new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' });

const TIPO_COLOR = {
  I: { bg: '#dcfce7', color: '#166534' },
  E: { bg: '#fee2e2', color: '#991b1b' },
  P: { bg: '#e0f2fe', color: '#075985' },
  N: { bg: '#f3f4f6', color: '#374151' },
  T: { bg: '#fef9c3', color: '#854d0e' },
};

function FileZone({ onFiles }) {
  const [over, setOver] = useState(false);
  const inputRef = useRef(null);

  function handleDrop(e) {
    e.preventDefault();
    setOver(false);
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
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={handleDrop}
      style={{
        border: `2px dashed ${over ? 'var(--accent)' : 'var(--ink-300)'}`,
        borderRadius: 8, padding: '40px 24px', textAlign: 'center',
        cursor: 'pointer', transition: 'border-color 0.15s',
        background: over ? '#f0f9ff' : '#fafafa',
      }}
    >
      <div style={{ fontSize: 32, marginBottom: 8 }}>📄</div>
      <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink-700)' }}>
        Arrastra archivos XML aquí o haz clic para seleccionar
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink-400)', marginTop: 4 }}>
        Solo archivos .xml de CFDI 4.0 / 3.3
      </div>
      <input ref={inputRef} type="file" accept=".xml" multiple onChange={handleChange} style={{ display: 'none' }} />
    </div>
  );
}

function ResultCard({ result }) {
  const navigate = useNavigate();
  if (result.error) {
    return (
      <div style={{
        padding: '12px 16px', borderRadius: 6, border: '1px solid #fecaca',
        background: '#fef2f2', marginBottom: 8,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <div style={{ fontWeight: 500, fontSize: 13, color: '#991b1b' }}>
              {result.filename}
            </div>
            <div style={{ fontSize: 12, color: '#b91c1c', marginTop: 2 }}>{result.error}</div>
          </div>
          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3, background: '#fee2e2', color: '#991b1b', whiteSpace: 'nowrap' }}>
            Error
          </span>
        </div>
      </div>
    );
  }

  const tipo = result.tipo ?? 'I';
  const tc = TIPO_COLOR[tipo] ?? TIPO_COLOR.I;

  return (
    <div style={{
      padding: '12px 16px', borderRadius: 6, border: '1px solid #bbf7d0',
      background: '#f0fdf4', marginBottom: 8,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 3, ...tc }}>
              {result.tipo_label}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 13, fontWeight: 600 }}>
              {result.folio || '—'}
            </span>
          </div>
          <div style={{ fontSize: 12.5, marginTop: 4, color: 'var(--ink-700)' }}>
            {result.emisor}
            {result.receptor && result.emisor !== result.receptor && (
              <span style={{ color: 'var(--ink-400)', marginLeft: 6 }}>→ {result.receptor}</span>
            )}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-400)', marginTop: 2 }}>
            {result.uuid}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, marginLeft: 12 }}>
          <span style={{ fontFamily: 'var(--serif)', fontSize: 18, letterSpacing: '-0.02em' }}>
            {result.total != null ? MXN.format(result.total) : '—'}
          </span>
          <button
            className="btn btn-sm"
            onClick={() => navigate(`/facturas?highlight=${result.id}`)}
            style={{ fontSize: 11 }}
          >
            Ver factura →
          </button>
        </div>
      </div>
    </div>
  );
}

export default function FacturaImportar() {
  const navigate = useNavigate();
  const [queue, setQueue] = useState([]);
  const [results, setResults] = useState([]);
  const [processing, setProcessing] = useState(false);

  async function processFiles(files) {
    const newItems = files.map((f) => ({ file: f, filename: f.name, status: 'pending' }));
    setQueue((q) => [...q, ...newItems]);
    setProcessing(true);

    const newResults = [];
    for (const item of newItems) {
      const formData = new FormData();
      formData.append('archivo', item.file);
      try {
        const token = sessionStorage.getItem('clf_token');
        const res = await fetch('/api/facturas/importar', {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        const json = await res.json();
        if (!res.ok) {
          newResults.push({ filename: item.filename, error: json.detail ?? 'Error desconocido' });
        } else {
          newResults.push({ filename: item.filename, ...json });
        }
      } catch (e) {
        newResults.push({ filename: item.filename, error: e.message });
      }
    }

    setResults((r) => [...r, ...newResults]);
    setQueue([]);
    setProcessing(false);
  }

  const ok = results.filter((r) => !r.error).length;
  const errors = results.filter((r) => r.error).length;

  return (
    <div className="page">
      <div className="crumbs">
        <a onClick={() => navigate('/facturas')}>Facturas</a>
        <span className="sep">/</span>
        <span>Importar XML</span>
      </div>

      <div className="page-header">
        <div>
          <div className="page-title">Importar facturas CFDI</div>
          <div className="page-sub">Sube uno o varios archivos XML para registrarlos en el sistema</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {results.length > 0 && (
            <button className="btn btn-primary" onClick={() => navigate('/facturas')}>
              Ver todas las facturas
            </button>
          )}
          <button className="btn" onClick={() => navigate('/facturas')}>Cancelar</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: results.length > 0 ? '1fr 1fr' : '1fr', gap: 24 }}>
        <div>
          <FileZone onFiles={processFiles} />

          {processing && (
            <div style={{ marginTop: 16, padding: '12px 16px', background: '#eff6ff',
              border: '1px solid #bfdbfe', borderRadius: 6, fontSize: 13, color: '#1d4ed8' }}>
              Procesando archivos…
            </div>
          )}

          {queue.length > 0 && (
            <div style={{ marginTop: 12 }}>
              {queue.map((item, i) => (
                <div key={i} style={{ padding: '8px 0', fontSize: 12, color: 'var(--ink-500)',
                  borderBottom: '1px solid var(--ink-100)', display: 'flex', gap: 8 }}>
                  <span>⏳</span>
                  <span>{item.filename}</span>
                </div>
              ))}
            </div>
          )}

          {results.length > 0 && (
            <div style={{ marginTop: 16, padding: '10px 14px', borderRadius: 6,
              background: 'var(--ink-50)', border: '1px solid var(--ink-200)',
              fontSize: 12.5, display: 'flex', gap: 16 }}>
              <span style={{ color: '#166534' }}>✓ {ok} importada(s)</span>
              {errors > 0 && <span style={{ color: '#991b1b' }}>✗ {errors} error(es)</span>}
            </div>
          )}
        </div>

        {results.length > 0 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Resultados ({results.length})</div>
            <div style={{ maxHeight: '65vh', overflowY: 'auto' }}>
              {results.map((r, i) => <ResultCard key={i} result={r} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
