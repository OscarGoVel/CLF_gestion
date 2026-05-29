import { useState, useMemo, useRef } from 'react';
import { LoadingRow, EmptyRow } from './TableStates';
import { ContextMenu } from './ContextMenu';
import { useMobile } from '../hooks/useMobile';

export function DataTable({
  columns,
  data,
  loading,
  onRowClick,
  selectedId,
  keyField = 'id',
  footer,
  emptyLabel,
  getContextMenuItems,
}) {
  const isMobile = useMobile();
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [ctxMenu, setCtxMenu] = useState(null);
  const longPressTimer = useRef(null);

  function openCtxMenu(x, y, row) {
    setCtxMenu({ x, y, row });
  }

  function startLongPress(e, row) {
    const touch = e.touches[0];
    longPressTimer.current = setTimeout(() => {
      openCtxMenu(touch.clientX, touch.clientY, row);
    }, 500);
  }

  function cancelLongPress() {
    clearTimeout(longPressTimer.current);
  }

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

  if (isMobile) {
    const visibleCols = columns.filter((c) => !c.mobileHide);
    return (
      <>
        {loading ? (
          <div className="mob-cards"><div className="mob-card" style={{ color: 'var(--ink-400)', textAlign: 'center' }}>Cargando…</div></div>
        ) : !sorted.length ? (
          <div className="mob-cards"><div className="mob-card" style={{ color: 'var(--ink-400)', textAlign: 'center' }}>{emptyLabel ?? 'Sin registros'}</div></div>
        ) : (
          <div className="mob-cards">
            {sorted.map((row) => (
              <div
                key={row[keyField]}
                className={`mob-card${selectedId === row[keyField] ? ' sel' : ''}`}
                onClick={() => onRowClick?.(row)}
              >
                {visibleCols.map((col, i) => (
                  <div key={i} className="mob-card__field">
                    <span className="mob-card__label">{col.header}</span>
                    <span className="mob-card__val">{col.render ? col.render(row) : (row[col.key] ?? '—')}</span>
                  </div>
                ))}
                {getContextMenuItems && (
                  <button
                    className="btn btn-sm mob-card__actions"
                    onClick={(e) => { e.stopPropagation(); openCtxMenu(e.clientX, e.clientY, row); }}
                  >
                    Acciones ⋮
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {ctxMenu && (
          <ContextMenu
            x={ctxMenu.x}
            y={ctxMenu.y}
            items={getContextMenuItems(ctxMenu.row)}
            onClose={() => setCtxMenu(null)}
          />
        )}
        {footer && (
          <div style={{ padding: '10px 16px', borderTop: '1px solid var(--ink-100)', fontSize: 11.5, color: 'var(--ink-500)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            {footer}
          </div>
        )}
      </>
    );
  }

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
            {getContextMenuItems && <th className="ctx-col" />}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <LoadingRow colSpan={columns.length + (getContextMenuItems ? 1 : 0)} />
          ) : !sorted.length ? (
            <EmptyRow colSpan={columns.length + (getContextMenuItems ? 1 : 0)} label={emptyLabel} />
          ) : sorted.map((row) => (
            <tr
              key={row[keyField]}
              className={selectedId === row[keyField] ? 'sel' : ''}
              style={{ cursor: onRowClick ? 'pointer' : 'default' }}
              onClick={() => onRowClick?.(row)}
              onContextMenu={getContextMenuItems ? (e) => { e.preventDefault(); openCtxMenu(e.clientX, e.clientY, row); } : undefined}
              onTouchStart={getContextMenuItems ? (e) => startLongPress(e, row) : undefined}
              onTouchMove={getContextMenuItems ? cancelLongPress : undefined}
              onTouchEnd={getContextMenuItems ? cancelLongPress : undefined}
            >
              {columns.map((col, i) => (
                <td key={i} className={col.className} style={col.style}>
                  {col.render ? col.render(row) : (row[col.key] ?? '—')}
                </td>
              ))}
              {getContextMenuItems && (
                <td
                  className="ctx-col"
                  onClick={(e) => { e.stopPropagation(); openCtxMenu(e.clientX, e.clientY, row); }}
                >
                  <button className="ctx-kebab" aria-label="Acciones">⋮</button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          items={getContextMenuItems(ctxMenu.row)}
          onClose={() => setCtxMenu(null)}
        />
      )}
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
