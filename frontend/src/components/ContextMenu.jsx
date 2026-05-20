import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

function SubMenu({ items, parentRect, onClose }) {
  const ref = useRef(null);
  const [style, setStyle] = useState({ visibility: 'hidden' });

  useEffect(() => {
    if (!ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    const spaceRight = window.innerWidth - parentRect.right;
    const spaceBottom = window.innerHeight - parentRect.top;
    const left = spaceRight >= width ? parentRect.width : -width;
    const top = spaceBottom >= height ? 0 : Math.max(-(height - parentRect.height), -parentRect.top);
    setStyle({ left, top, visibility: 'visible' });
  }, [parentRect]);

  return (
    <ul className="ctx-menu ctx-submenu" ref={ref} style={style}>
      {items.map((item, i) => renderItem(item, i, onClose))}
    </ul>
  );
}

function MenuItem({ item, onClose }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const [wrapRect, setWrapRect] = useState(null);

  function handleMouseEnter() {
    if (item.submenu) {
      setWrapRect(wrapRef.current?.getBoundingClientRect());
      setOpen(true);
    }
  }

  function handleClick(e) {
    if (item.disabled || item.submenu) return;
    e.stopPropagation();
    item.onClick?.();
    onClose();
  }

  const cls = [
    'ctx-item',
    item.disabled ? 'disabled' : '',
    item.danger ? 'danger' : '',
    item.submenu ? 'has-sub' : '',
  ].filter(Boolean).join(' ');

  return (
    <li
      ref={wrapRef}
      className={cls}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => setOpen(false)}
    >
      {item.icon && <span className="ctx-icon">{item.icon}</span>}
      <span className="ctx-label">{item.label}</span>
      {item.submenu && <span className="ctx-arrow">›</span>}
      {open && wrapRect && item.submenu && (
        <SubMenu items={item.submenu} parentRect={wrapRect} onClose={onClose} />
      )}
    </li>
  );
}

function renderItem(item, i, onClose) {
  if (item.type === 'divider') return <li key={i} className="ctx-divider" />;
  return <MenuItem key={i} item={item} onClose={onClose} />;
}

export function ContextMenu({ x, y, items, onClose }) {
  const ref = useRef(null);
  const [style, setStyle] = useState({ visibility: 'hidden', left: x, top: y });

  useEffect(() => {
    if (!ref.current) return;
    const { width, height } = ref.current.getBoundingClientRect();
    const left = x + width > window.innerWidth ? x - width : x;
    const top = y + height > window.innerHeight ? y - height : y;
    setStyle({ left, top, visibility: 'visible' });
  }, [x, y]);

  useEffect(() => {
    function handleKey(e) { if (e.key === 'Escape') onClose(); }
    function handleClick() { onClose(); }
    function handleScroll() { onClose(); }
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    window.addEventListener('scroll', handleScroll, true);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
      window.removeEventListener('scroll', handleScroll, true);
    };
  }, [onClose]);

  return createPortal(
    <ul
      ref={ref}
      className="ctx-menu"
      style={{ position: 'fixed', zIndex: 9999, ...style }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {items.map((item, i) => renderItem(item, i, onClose))}
    </ul>,
    document.body
  );
}
