/**
 * Descarga los datos de una tabla como archivo CSV.
 *
 * @param {string[]} keys   - Claves de campo a exportar (en orden de columnas)
 * @param {object[]} rows   - Filas de datos
 * @param {string}   name   - Nombre base del archivo (sin extensión)
 */
export function exportCSV(keys, rows, name = 'export') {
  const header = keys.join(',');
  const body = rows.map((row) =>
    keys.map((k) => {
      const v = row[k] ?? '';
      const s = String(v);
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    }).join(',')
  );

  const csv = [header, ...body].join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const date = new Date().toISOString().slice(0, 10);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name}_${date}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
