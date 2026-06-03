import { useRef, useEffect, useState } from 'react';

export function MultiSelectDropdown({ options, values = [], onChange, counts, labelPlural = 'seleccionados' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function toggle(val) {
    if (values.includes(val)) {
      onChange(values.filter((v) => v !== val));
    } else {
      onChange([...values, val]);
    }
  }

  function selectAll() { onChange([]); setOpen(false); }

  const totalCount = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : null;

  let label;
  if (values.length === 0) {
    label = <span>Todos{totalCount != null ? <span className="n">{totalCount}</span> : null}</span>;
  } else if (values.length === 1) {
    const opt = options.find((o) => o.value === values[0]);
    const c = counts?.[values[0]];
    label = <span>{opt?.label ?? values[0]}{c != null ? <span className="n">{c}</span> : null}</span>;
  } else {
    label = <span>{values.length} {labelPlural}</span>;
  }

  return (
    <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
      <button
        type="button"
        className={`chip${values.length > 0 ? ' active' : ''}`}
        style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4 }}
        onClick={() => setOpen((o) => !o)}
      >
        {label}
        <span style={{ fontSize: 9, opacity: 0.6, marginLeft: 2 }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, zIndex: 200,
          background: 'var(--surface, #fff)', border: '1px solid var(--ink-200)',
          borderRadius: 6, boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          minWidth: 200, padding: '4px 0',
        }}>
          <div
            style={{
              padding: '7px 14px', cursor: 'pointer', fontSize: 13,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              background: values.length === 0 ? 'var(--ink-50, #f9fafb)' : 'transparent',
            }}
            onClick={selectAll}
          >
            <span style={{ fontWeight: values.length === 0 ? 600 : 400 }}>Todos</span>
            {totalCount != null && (
              <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>{totalCount}</span>
            )}
          </div>
          <div style={{ borderTop: '1px solid var(--ink-100)', margin: '2px 0' }} />
          {options.map((opt) => {
            const checked = values.includes(opt.value);
            const count = counts?.[opt.value];
            return (
              <label
                key={opt.value}
                style={{
                  padding: '7px 14px', cursor: 'pointer', fontSize: 13,
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: checked ? 'var(--ink-50, #f9fafb)' : 'transparent',
                }}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggle(opt.value)}
                  style={{ cursor: 'pointer' }}
                />
                <span style={{ flex: 1 }}>{opt.label}</span>
                {count != null && (
                  <span style={{ fontSize: 11, color: 'var(--ink-400)' }}>{count}</span>
                )}
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}
