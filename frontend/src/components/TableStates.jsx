export function LoadingRow({ colSpan = 1 }) {
  return (
    <tr>
      <td colSpan={colSpan} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>
        Cargando…
      </td>
    </tr>
  );
}

export function EmptyRow({ colSpan = 1, label = 'Sin resultados' }) {
  return (
    <tr>
      <td colSpan={colSpan} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-400)' }}>
        {label}
      </td>
    </tr>
  );
}
