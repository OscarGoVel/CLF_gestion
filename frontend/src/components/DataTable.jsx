import { useState, useMemo } from 'react';
import { LoadingRow, EmptyRow } from './TableStates';

export function DataTable({
  columns,
  data,
  loading,
  onRowClick,
  selectedId,
  keyField = 'id',
  footer,
  emptyLabel,
}) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');

  function handleSort(col) {
    if (!col.sortKey) return;
    if (sortKey === col.sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(col.sortKey);
      setSortDir('asc');
    }
  }

  const sorted = useMemo(() => {
    if (!sortKey || !data?.length) return data ?? [];
    return [...data].sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      if (av == null) return 1;
      if (bv == null) return -1;
      const cmp = typeof av === 'number'
        ? av - bv
        : String(av).localeCompare(String(bv), 'es');
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [data, sortKey, sortDir]);

  return (
    <>
      <table className="tbl">
        <thead>
          <tr>
            {columns.map((col, i) => (
              <th
                key={i}
                className={col.className}
                style={{
                  width: col.width,
                  cursor: col.sortKey ? 'pointer' : 'default',
                  userSelect: col.sortKey ? 'none' : 'auto',
                  ...col.headerStyle,
                }}
                onClick={() => handleSort(col)}
              >
                {col.header}
                {col.sortKey && (
                  <span style={{ marginLeft: 4, opacity: sortKey === col.sortKey ? 1 : 0.25, fontSize: 10 }}>
                    {sortKey === col.sortKey ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <LoadingRow colSpan={columns.length} />
          ) : !sorted.length ? (
            <EmptyRow colSpan={columns.length} label={emptyLabel} />
          ) : sorted.map((row) => (
            <tr
              key={row[keyField]}
              className={selectedId === row[keyField] ? 'sel' : ''}
              style={{ cursor: onRowClick ? 'pointer' : 'default' }}
              onClick={() => onRowClick?.(row)}
            >
              {columns.map((col, i) => (
                <td key={i} className={col.className} style={col.style}>
                  {col.render ? col.render(row) : (row[col.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {footer && (
        <div style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--ink-100)',
          fontSize: 11.5,
          color: 'var(--ink-500)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          {footer}
        </div>
      )}
    </>
  );
}
