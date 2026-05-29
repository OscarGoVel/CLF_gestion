import { useEffect, useRef, useState } from 'react';
import { Html5Qrcode } from 'html5-qrcode';

const CONTAINER_ID = 'clf-barcode-reader';

export function BarcodeScanner({ open, onDetected, onClose }) {
  const scannerRef = useRef(null);
  const firedRef   = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!open) {
      if (scannerRef.current) {
        scannerRef.current.stop().catch(() => {});
        scannerRef.current = null;
      }
      setError('');
      return;
    }

    firedRef.current = false;
    setError('');

    const scanner = new Html5Qrcode(CONTAINER_ID);
    scannerRef.current = scanner;

    const config = { fps: 10, qrbox: { width: 260, height: 140 } };

    const onSuccess = (code) => {
      if (firedRef.current) return;
      firedRef.current = true;
      scanner.stop()
        .catch(() => {})
        .finally(() => {
          scannerRef.current = null;
          onDetected(code);
        });
    };

    // Intenta cámara trasera (móvil). Si falla, intenta cualquier cámara (desktop).
    scanner
      .start({ facingMode: 'environment' }, config, onSuccess, () => {})
      .catch(() =>
        scanner.start({ facingMode: 'user' }, config, onSuccess, () => {})
      )
      .catch((err) => {
        const msg = typeof err === 'string' ? err : (err?.message ?? 'No se pudo acceder a la cámara');
        setError(msg);
      });

    return () => {
      if (scannerRef.current) {
        scannerRef.current.stop().catch(() => {});
        scannerRef.current = null;
      }
    };
  }, [open]);

  function handleClose() {
    firedRef.current = true;
    if (scannerRef.current) {
      scannerRef.current.stop().catch(() => {});
      scannerRef.current = null;
    }
    onClose();
  }

  // display:none en lugar de return null — el div con id siempre debe estar
  // en el DOM mientras html5-qrcode lo está usando, si se desmonta React crashea
  return (
    <div
      style={{
        display: open ? 'flex' : 'none',
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.82)',
        flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        padding: 20,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) handleClose(); }}
    >
      <div style={{
        background: '#fff', borderRadius: 10, overflow: 'hidden',
        width: '100%', maxWidth: 380,
        boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', borderBottom: '1px solid var(--ink-200)',
        }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Escanear código de barras</span>
          <button
            onClick={handleClose}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 18, color: 'var(--ink-500)', lineHeight: 1, padding: 4,
            }}
          >×</button>
        </div>

        <div style={{ padding: '16px 16px 8px' }}>
          {error ? (
            <div style={{
              padding: '12px 16px', background: '#fff5f5',
              border: '1px solid #fecaca', borderRadius: 6,
              fontSize: 13, color: '#991b1b',
            }}>
              {error}
            </div>
          ) : (
            <p style={{ fontSize: 12.5, color: 'var(--ink-500)', margin: '0 0 12px', textAlign: 'center' }}>
              Apunta la cámara al código de barras
            </p>
          )}
          <div
            id={CONTAINER_ID}
            style={{ width: '100%', minHeight: error ? 0 : 200, borderRadius: 6, overflow: 'hidden' }}
          />
        </div>

        <div style={{ padding: '8px 16px 16px', display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn" onClick={handleClose}>Cancelar</button>
        </div>
      </div>
    </div>
  );
}
