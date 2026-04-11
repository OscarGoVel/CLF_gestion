# -*- coding: utf-8 -*-
"""
Módulo de Facturación
Maneja la importación de XMLs CFDI, vinculación con cotizaciones
y visualización de información de facturación.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import sqlite3
import os
from datetime import datetime
from ui.utils import centrar_ventana as _centrar
from app_config import FACTURAS_XML_DIR


from core.cfdi import parsear_cfdi, _attr  # noqa: F401


# ══════════════════════════════════════════════════════════════════════════════
class SeccionFacturacion:
    """Sección completa de Facturación integrada al sistema."""

    def __init__(self, sistema):
        self.sistema = sistema
        self.root    = sistema.root
        self.conn    = sistema.conn
        self.cursor  = sistema.cursor
        self.C       = sistema.C

        self._init_db()
        self._crear_seccion()

    # ── Base de datos ──────────────────────────────────────────────────────────
    def _init_db(self):
        """Crea tablas y migraciones necesarias."""
        import db_connection
        if db_connection.motor_activo() == 'postgresql':
            return  # Esquema ya existe en PostgreSQL (creado por db_init.py)
        # Tabla principal de facturas
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                cotizacion_id    INTEGER,
                uuid             TEXT UNIQUE NOT NULL,
                serie            TEXT,
                folio_factura    TEXT,
                fecha            TEXT,
                fecha_timbrado   TEXT,
                no_cert_sat      TEXT,
                rfc_emisor       TEXT,
                nombre_emisor    TEXT,
                rfc_receptor     TEXT,
                nombre_receptor  TEXT,
                uso_cfdi         TEXT,
                tipo             TEXT,
                metodo_pago      TEXT,
                forma_pago       TEXT,
                moneda           TEXT DEFAULT 'MXN',
                subtotal         REAL DEFAULT 0,
                descuento        REAL DEFAULT 0,
                iva              REAL DEFAULT 0,
                total            REAL DEFAULT 0,
                ruta_xml         TEXT,
                notas            TEXT,
                fecha_registro   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id)
            )
        ''')

        # Tabla de conceptos de factura
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS factura_conceptos (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_id       INTEGER NOT NULL,
                clave_prod_serv  TEXT,
                no_identificacion TEXT,
                cantidad         REAL,
                clave_unidad     TEXT,
                unidad           TEXT,
                descripcion      TEXT,
                valor_unitario   REAL,
                importe          REAL,
                descuento        REAL DEFAULT 0,
                FOREIGN KEY (factura_id) REFERENCES facturas(id)
            )
        ''')

        # Migraciones: clave SAT en productos
        for col, tipo in [('clave_sat', 'TEXT'), ('clave_unidad_sat', 'TEXT'),
                          ('precio_base_fecha', 'TEXT')]:
            try:
                self.cursor.execute(f'ALTER TABLE productos ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass

        # Migraciones: datos fiscales SAT en clientes
        for col, tipo in [('regimen_fiscal', 'TEXT'), ('uso_cfdi', 'TEXT'),
                          ('cp_fiscal', 'TEXT')]:
            try:
                self.cursor.execute(f'ALTER TABLE clientes ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass

        # Migraciones: datos fiscales SAT en proveedores
        for col, tipo in [('regimen_fiscal', 'TEXT'), ('cp_fiscal', 'TEXT')]:
            try:
                self.cursor.execute(f'ALTER TABLE proveedores ADD COLUMN {col} {tipo}')
            except sqlite3.OperationalError:
                pass

        self.conn.commit()

    # ── UI Principal ───────────────────────────────────────────────────────────
    def _crear_seccion(self):
        sec = tk.Frame(self.sistema._content_area, bg=self.C['content_bg'])
        self.sistema._secciones['facturacion'] = sec

        # Toolbar
        tb = tk.Frame(sec, bg=self.C['toolbar_bg'], relief='flat', bd=0)
        tb.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        self.sistema._toolbar_btn(tb, '📥 Importar XML',
                                  self.importar_xml, color='#0f7b5e',
                                  tip='Importar factura CFDI desde archivo .xml')
        self.sistema._toolbar_btn(tb, '🔗 Vincular Cotización',
                                  self.vincular_cotizacion,
                                  tip='Vincular la factura seleccionada a una o más cotizaciones')
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '🔍 Ver Detalle',
                                  self.ver_detalle_factura,
                                  tip='Ver datos completos del CFDI seleccionado')
        self.sistema._toolbar_btn(tb, '📄 Abrir XML',
                                  self.abrir_xml)
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '🗑️ Eliminar',
                                  self.eliminar_factura, peligro=True)
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '🔗 Centro de Vinculación',
                                  self.sistema._abrir_centro_vinculacion, color='#dc2626')
        self.sistema._toolbar_btn(tb, '🔄', self.cargar_facturas, tip='Recargar lista de facturas')
        self.sistema._toolbar_sep(tb)
        self.sistema._toolbar_btn(tb, '📊 Exportar CSV', self.exportar_csv,
                                  color='#065f46')

        # Barra de búsqueda / filtros
        ff = tk.Frame(sec, bg=self.C['toolbar_bg'], pady=4)
        ff.pack(fill='x')
        tk.Frame(sec, bg=self.C['toolbar_border'], height=1).pack(fill='x')

        tk.Label(ff, text='Buscar:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(8, 2))
        self._entry_buscar = tk.Entry(ff, font=('Arial', 9), width=28)
        self._entry_buscar.pack(side='left', padx=4)
        self._entry_buscar.bind('<KeyRelease>', lambda e: self.cargar_facturas())
        self._entry_buscar.bind('<Return>', lambda e: self.cargar_facturas())

        tk.Label(ff, text='Vinculadas:', bg=self.C['toolbar_bg'],
                 font=('Arial', 9)).pack(side='left', padx=(10, 2))
        self._filtro_vinc = ttk.Combobox(ff, values=['Todas', 'Vinculadas', 'Sin vincular'],
                                          state='readonly', width=14, font=('Arial', 9))
        self._filtro_vinc.set('Todas')
        self._filtro_vinc.pack(side='left', padx=4)
        self._filtro_vinc.bind('<<ComboboxSelected>>', lambda e: self.cargar_facturas())

        # Tabla
        ft = tk.Frame(sec, bg=self.C['content_bg'])
        ft.pack(fill='both', expand=True, padx=8, pady=8)

        cols = ('ID', 'UUID', 'Serie-Folio', 'Fecha', 'RFC Receptor',
                'Receptor', 'Subtotal', 'IVA', 'Total', 'Moneda',
                'Tipo', 'Cotización', 'Estado')
        self.tree = ttk.Treeview(ft, columns=cols, show='headings',
                                  selectmode='browse')
        wcfg = {
            'ID': 0, 'UUID': 110, 'Serie-Folio': 95, 'Fecha': 90,
            'RFC Receptor': 115, 'Receptor': 190,
            'Subtotal': 90, 'IVA': 70, 'Total': 90,
            'Moneda': 52, 'Tipo': 58, 'Cotización': 120, 'Estado': 88,
        }
        anchors = {'Subtotal':'e','IVA':'e','Total':'e'}
        for col in cols:
            self.tree.heading(col, text=col, anchor=anchors.get(col,'w'))
            self.tree.column(col, width=wcfg[col], minwidth=wcfg[col],
                             stretch=(col not in ('ID','Moneda','Tipo','UUID')),
                             anchor=anchors.get(col,'w'))
        self.tree.column('ID', stretch=False)

        # Sin fondo de color — indicadores en columna Estado y Tipo
        self.tree.tag_configure('vinculada',    foreground='#16a34a')
        self.tree.tag_configure('sin_vincular', foreground='#d97706')
        self.tree.tag_configure('ingreso',      foreground='#1a4b8c')
        self.tree.tag_configure('egreso',       foreground='#c0392b')
        self.tree.tag_configure('fila_par',     background='#ffffff')
        self.tree.tag_configure('fila_impar',   background='#f8fafc')

        sc_y = ttk.Scrollbar(ft, orient='vertical',   command=self.tree.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        self.tree.bind('<Double-1>', lambda e: self.ver_detalle_factura())
        self.sistema._configurar_sorting_treeview(
            self.tree, columnas_numericas=['Subtotal', 'IVA', 'Total'])

        # Barra de estado
        self._status_fac = tk.Label(sec, text='',
            font=('Arial', 8), bg='#dde3ec', fg='#6b7280',
            anchor='w', padx=8, pady=3)
        self._status_fac.pack(fill='x', side='bottom')

        self.cargar_facturas()

    # ── Cargar tabla ───────────────────────────────────────────────────────────
    def exportar_csv(self):
        """Exporta la vista actual de facturas a CSV.
        Columnas: Folio, OC Relacionada, Fecha Emisión, Monto Total.
        Respeta los filtros activos (búsqueda y estado de vinculación).
        """
        import csv as _csv
        from tkinter import filedialog as _fd
        from datetime import datetime as _dt

        # Construir query con los mismos filtros que cargar_facturas
        buscar = self._entry_buscar.get().strip()
        vinc   = self._filtro_vinc.get()

        where_parts = []
        params      = []

        if vinc == 'Vinculadas':
            where_parts.append("""(
                f.cotizacion_id IS NOT NULL
                OR EXISTS (SELECT 1 FROM factura_cotizaciones fc WHERE fc.factura_id = f.id)
                OR EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
            )""")
        elif vinc == 'Sin vincular':
            where_parts.append("""(
                f.cotizacion_id IS NULL
                AND NOT EXISTS (
                    SELECT 1 FROM factura_cotizaciones fc WHERE fc.factura_id = f.id)
                AND NOT EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
            )""")

        if buscar:
            where_parts.append(
                '(f.uuid LIKE ? OR f.rfc_receptor LIKE ? '
                'OR f.nombre_receptor LIKE ? OR f.folio_factura LIKE ?)')
            p = f'%{buscar}%'
            params += [p, p, p, p]

        where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        self.cursor.execute(f"""
            SELECT
                CASE WHEN f.serie IS NOT NULL AND f.serie != ''
                     THEN f.serie || '-' || f.folio_factura
                     ELSE f.folio_factura
                END                                    AS folio,
                f.uuid                                 AS folio_fiscal,
                GROUP_CONCAT(DISTINCT c.orden_compra)  AS oc_relacionada,
                f.fecha                                AS fecha_emision,
                f.total                                AS monto,
                f.moneda
            FROM facturas f
            LEFT JOIN factura_cotizaciones fc ON fc.factura_id = f.id
            LEFT JOIN cotizaciones c          ON c.id = fc.cotizacion_id
            LEFT JOIN compras comp            ON comp.factura_xml_id = f.id
            {where_sql}
            GROUP BY f.id
            ORDER BY f.fecha DESC, f.fecha_registro DESC
        """, params)

        filas = self.cursor.fetchall()

        if not filas:
            messagebox.showinfo('Sin datos',
                'No hay facturas que exportar con los filtros actuales.',
                parent=self.root)
            return

        # Pedir ruta de guardado
        fecha_hoy = _dt.now().strftime('%Y-%m-%d')
        ruta = _fd.asksaveasfilename(
            title='Guardar exportación como...',
            defaultextension='.csv',
            initialfile=f'facturas_{fecha_hoy}.csv',
            filetypes=[('CSV', '*.csv'), ('Todos los archivos', '*.*')],
            parent=self.root,
        )
        if not ruta:
            return

        try:
            with open(ruta, 'w', newline='', encoding='utf-8-sig') as f:
                writer = _csv.writer(f)
                # Encabezado
                writer.writerow(['Folio', 'Folio Fiscal (UUID)', 'OC Relacionada',
                                  'Fecha Emisión', 'Monto', 'Moneda'])
                # Datos
                for folio, uuid, oc, fecha, monto, moneda in filas:
                    writer.writerow([
                        folio or '',
                        uuid or '',
                        oc or '',
                        (fecha or '')[:10],
                        f'{monto:,.2f}' if monto else '0.00',
                        moneda or 'MXN',
                    ])

            n = len(filas)
            messagebox.showinfo(
                '✅ Exportación completa',
                f'{n} factura{"s" if n != 1 else ""} exportada{"s" if n != 1 else ""}\n\n'
                f'Archivo: {ruta}',
                parent=self.root)

        except Exception as e:
            messagebox.showerror('Error al exportar', str(e), parent=self.root)

    def cargar_facturas(self):
        self.tree.delete(*self.tree.get_children())

        buscar = self._entry_buscar.get().strip()
        vinc   = self._filtro_vinc.get()

        # ── Verificar si existe factura_cotizaciones ───────────────────────
        import db_connection as _dbc
        if _dbc.motor_activo() == 'postgresql':
            tiene_junction = True  # Siempre existe en PostgreSQL
        else:
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='factura_cotizaciones'")
            tiene_junction = bool(self.cursor.fetchone())

        # ── WHERE con filtros ──────────────────────────────────────────────
        where_parts = []
        params      = []

        if vinc == 'Vinculadas':
            if tiene_junction:
                where_parts.append("""(
                    EXISTS (SELECT 1 FROM factura_cotizaciones fc2 WHERE fc2.factura_id = f.id)
                    OR f.cotizacion_id IS NOT NULL
                    OR EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
                )""")
            else:
                where_parts.append("""(
                    f.cotizacion_id IS NOT NULL
                    OR EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
                )""")
        elif vinc == 'Sin vincular':
            if tiene_junction:
                where_parts.append("""(
                    NOT EXISTS (SELECT 1 FROM factura_cotizaciones fc2 WHERE fc2.factura_id = f.id)
                    AND f.cotizacion_id IS NULL
                    AND NOT EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
                )""")
            else:
                where_parts.append("""(
                    f.cotizacion_id IS NULL
                    AND NOT EXISTS (SELECT 1 FROM compras co WHERE co.factura_xml_id = f.id)
                )""")

        if buscar:
            where_parts.append(
                '(f.uuid LIKE ? OR f.rfc_receptor LIKE ? '
                'OR f.nombre_receptor LIKE ? OR f.folio_factura LIKE ? '
                'OR f.serie LIKE ?)')
            p = f'%{buscar}%'
            params += [p, p, p, p, p]

        where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

        # ── Query principal ────────────────────────────────────────────────
        if tiene_junction:
            self.cursor.execute(f"""
                SELECT f.id, f.uuid, f.serie, f.folio_factura, f.fecha,
                       f.rfc_receptor, f.nombre_receptor,
                       f.subtotal, f.iva, f.total, f.moneda, f.tipo,
                       COALESCE(
                           STRING_AGG(DISTINCT c_junc.folio, ','),
                           MAX(c_leg.folio)
                       )                        AS cot_folios,
                       COUNT(DISTINCT fc.cotizacion_id) +
                           CASE WHEN f.cotizacion_id IS NOT NULL
                                 AND NOT EXISTS (
                                     SELECT 1 FROM factura_cotizaciones fc3
                                     WHERE fc3.factura_id = f.id)
                                THEN 1 ELSE 0 END AS n_cotizaciones,
                       COUNT(DISTINCT comp.id)  AS n_compras
                FROM facturas f
                LEFT JOIN factura_cotizaciones fc ON fc.factura_id = f.id
                LEFT JOIN cotizaciones c_junc     ON c_junc.id = fc.cotizacion_id
                LEFT JOIN cotizaciones c_leg      ON c_leg.id = f.cotizacion_id
                LEFT JOIN compras comp            ON comp.factura_xml_id = f.id
                {where_sql}
                GROUP BY f.id
                ORDER BY f.fecha DESC, f.fecha_registro DESC
            """, params)
        else:
            # Fallback: solo usa la columna legacy cotizacion_id
            self.cursor.execute(f"""
                SELECT f.id, f.uuid, f.serie, f.folio_factura, f.fecha,
                       f.rfc_receptor, f.nombre_receptor,
                       f.subtotal, f.iva, f.total, f.moneda, f.tipo,
                       c.folio                 AS cot_folios,
                       CASE WHEN f.cotizacion_id IS NOT NULL THEN 1 ELSE 0 END AS n_cotizaciones,
                       COUNT(DISTINCT comp.id)  AS n_compras
                FROM facturas f
                LEFT JOIN cotizaciones c   ON c.id = f.cotizacion_id
                LEFT JOIN compras comp     ON comp.factura_xml_id = f.id
                {where_sql}
                GROUP BY f.id
                ORDER BY f.fecha DESC, f.fecha_registro DESC
            """, params)

        for row in self.cursor.fetchall():
            (fid, uuid, serie, folio_f, fecha, rfc_rec, nombre_rec,
             subtotal, iva, total, moneda, tipo, cot_folios, n_cots, n_compras) = row

            serie_folio = f"{serie}-{folio_f}" if serie else (folio_f or '—')
            tipo_txt    = {'I': 'Ingreso', 'E': 'Egreso', 'P': 'Pago',
                           'N': 'Nómina',  'T': 'Traslado'}.get(tipo, tipo or '—')

            # Estado y referencia de vínculo
            if n_cots and n_cots > 0:
                vinculada = cot_folios or '—'
                estado    = 'Vinculada'
            elif n_compras and n_compras > 0:
                vinculada = '🛒 Compra'
                estado    = 'Vinculada'
            else:
                vinculada = '—'
                estado    = 'Sin vincular'

            # Alternación de filas
            idx      = len(self.tree.get_children())
            fila_tag = 'fila_par' if idx % 2 == 0 else 'fila_impar'
            est_tag  = 'vinculada' if estado == 'Vinculada' else 'sin_vincular'
            tipo_tag = 'ingreso' if tipo == 'I' else ('egreso' if tipo == 'E' else '')
            tags     = [fila_tag, est_tag] + ([tipo_tag] if tipo_tag else [])

            uuid_short = (uuid or '')[:13] + '…' if len(uuid or '') > 13 else (uuid or '')

            self.tree.insert('', 'end', tags=tuple(tags), values=(
                fid, uuid_short, serie_folio, (fecha or '')[:10],
                rfc_rec, nombre_rec,
                f'${subtotal:,.2f}' if subtotal else '$0.00',
                f'${iva:,.2f}'      if iva      else '$0.00',
                f'${total:,.2f}'    if total    else '$0.00',
                moneda, tipo_txt, vinculada, estado,
            ))

        # Actualizar barra de estado
        n      = len(self.tree.get_children())
        vinc_n = sum(1 for iid in self.tree.get_children()
                     if 'vinculada' in self.tree.item(iid, 'tags'))
        if hasattr(self, '_status_fac'):
            self._status_fac.config(
                text=f'{n} factura{"s" if n!=1 else ""}  ·  '
                     f'{vinc_n} vinculada{"s" if vinc_n!=1 else ""}  ·  '
                     f'doble clic para ver detalle')

        # Actualizar badge vinculación
        try:
            self.sistema._actualizar_badge_vinculacion()
        except Exception:
            pass
    # ── Importar XML ───────────────────────────────────────────────────────────
        # Actualizar badge de pendientes en cotizaciones
        try:
            self.sistema._actualizar_badge_vinculacion()
        except Exception:
            pass

    def importar_xml(self):
        """Importa uno o varios XMLs CFDI y los guarda en la BD."""
        rutas = filedialog.askopenfilenames(
            title='Seleccionar XML(s) CFDI',
            filetypes=[('XML CFDI', '*.xml'), ('Todos', '*.*')],
            parent=self.root
        )
        if not rutas:
            return

        importados = 0
        errores    = []

        for ruta in rutas:
            nombre = os.path.basename(ruta)
            try:
                datos = parsear_cfdi(ruta)
            except ValueError as e:
                errores.append(f"{nombre}:\n  {e}")
                continue

            # Copiar XML a carpeta de facturas del sistema
            carpeta_dest = FACTURAS_XML_DIR
            os.makedirs(carpeta_dest, exist_ok=True)
            dest = os.path.join(carpeta_dest, nombre)
            base, ext = os.path.splitext(nombre)
            cnt = 1
            while os.path.exists(dest) and dest != ruta:
                dest = os.path.join(carpeta_dest, f"{base}_{cnt}{ext}")
                cnt += 1
            if ruta != dest:
                import shutil
                try:
                    shutil.copy2(ruta, dest)
                except Exception:
                    dest = ruta  # usar ruta original si falla la copia

            try:
                self.cursor.execute("""
                    INSERT INTO facturas
                    (uuid, serie, folio_factura, fecha, fecha_timbrado, no_cert_sat,
                     rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                     uso_cfdi, tipo, metodo_pago, forma_pago, moneda,
                     subtotal, descuento, iva, total, ruta_xml)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    datos['uuid'], datos['serie'], datos['folio'],
                    datos['fecha'][:19] if datos['fecha'] else None,
                    datos['fecha_timbrado'][:19] if datos['fecha_timbrado'] else None,
                    datos['no_cert_sat'],
                    datos['rfc_emisor'], datos['nombre_emisor'],
                    datos['rfc_receptor'], datos['nombre_receptor'],
                    datos['uso_cfdi'], datos['tipo'],
                    datos['metodo_pago'], datos['forma_pago'], datos['moneda'],
                    datos['subtotal'], datos['descuento'],
                    datos['iva'], datos['total'], dest,
                ))
                factura_id = self.cursor.lastrowid

                # Insertar conceptos
                for c in datos['conceptos']:
                    self.cursor.execute("""
                        INSERT INTO factura_conceptos
                        (factura_id, clave_prod_serv, no_identificacion,
                         cantidad, clave_unidad, unidad, descripcion,
                         valor_unitario, importe, descuento)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        factura_id, c['clave_prod_serv'], c['no_identificacion'],
                        c['cantidad'], c['clave_unidad'], c['unidad'],
                        c['descripcion'], c['valor_unitario'],
                        c['importe'], c['descuento'],
                    ))

                self.conn.commit()
                importados += 1

                # Intentar vincular automáticamente por RFC receptor
                self._intentar_autovinculo(factura_id, datos)

                # Si CLF es receptor → es una factura de compra → confirmar stock
                # Si el RFC receptor coincide con la empresa activa → es factura de compra
                rfc_empresa = (self.sistema.empresa.get('rfc', '') or '').upper()
                if rfc_empresa and datos.get('rfc_receptor', '').upper() == rfc_empresa:
                    self._confirmar_stock_compra(factura_id, datos)

            except sqlite3.IntegrityError:
                self.conn.rollback()
                errores.append(f"{nombre}:\n  UUID duplicado — ya existe en el sistema.")
            except sqlite3.Error as e:
                self.conn.rollback()
                errores.append(f"{nombre}:\n  Error BD: {e}")

        # Resultado
        msg = f"✅ {importados} factura(s) importada(s) correctamente."
        if errores:
            msg += f"\n\n⚠️ {len(errores)} con error:\n" + "\n".join(errores)
        if importados > 0:
            messagebox.showinfo("Importación completada", msg, parent=self.root)
        else:
            messagebox.showwarning("Sin importaciones", msg, parent=self.root)

        self.cargar_facturas()

    def _intentar_autovinculo(self, factura_id, datos):
        """
        Intenta vincular automáticamente la factura a una cotización
        cuyo cliente tenga el mismo RFC que el receptor de la factura.
        Solo vincula si hay exactamente UNA cotización Entregada sin factura
        para ese RFC.
        """
        rfc = datos['rfc_receptor']
        if not rfc:
            return
        self.cursor.execute("""
            SELECT c.id FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE cl.rfc = ?
              AND c.estado IN ('Entregada', 'Parcialmente Entregada',
                               'Programada')
              AND c.id NOT IN (SELECT cotizacion_id FROM facturas
                               WHERE cotizacion_id IS NOT NULL)
        """, (rfc,))
        rows = self.cursor.fetchall()
        if len(rows) == 1:
            self._vincular_factura_a_cotizacion(factura_id, rows[0][0],
                                                 datos['uuid'], datos.get('fecha', ''),
                                                 auto=True)

    # ── Confirmación de stock al importar XML de compra ────────────────────────
    def _confirmar_stock_compra(self, factura_id, datos):
        """
        Muestra diálogo de confirmación para actualizar stock y precio_base
        a partir de un XML de compra (CLF como receptor).
        Busca productos por clave_prod_serv (clave_sat) primero,
        luego por no_identificacion (codigo).
        """
        conceptos = datos.get('conceptos', [])
        if not conceptos:
            return

        hoy = datetime.now().strftime('%Y-%m-%d')
        serie_folio = (f"{datos.get('serie','')}-" if datos.get('serie') else '') + \
                      (datos.get('folio', '') or datos.get('uuid', '')[:8])
        emisor = datos.get('nombre_emisor', '') or datos.get('rfc_emisor', '')

        # ── Resolver productos ────────────────────────────────────────────────
        items = []
        for c in conceptos:
            clave_sat_xml = c.get('clave_prod_serv', '')
            no_id         = c.get('no_identificacion', '')
            descripcion   = c.get('descripcion', '')
            cantidad      = c.get('cantidad', 0)
            precio_xml    = c.get('valor_unitario', 0)

            prod   = None
            metodo = ''

            # 1° buscar por clave_sat
            if clave_sat_xml:
                self.cursor.execute(
                    "SELECT id, codigo, nombre, precio_base, stock_actual, precio_base_fecha "
                    "FROM productos WHERE UPPER(clave_sat)=UPPER(?) LIMIT 1",
                    (clave_sat_xml,))
                row = self.cursor.fetchone()
                if row:
                    prod   = row
                    metodo = 'clave_sat'

            # 2° buscar por no_identificacion / codigo
            if not prod and no_id:
                self.cursor.execute(
                    "SELECT id, codigo, nombre, precio_base, stock_actual, precio_base_fecha "
                    "FROM productos WHERE UPPER(codigo)=UPPER(?) LIMIT 1",
                    (no_id,))
                row = self.cursor.fetchone()
                if row:
                    prod   = row
                    metodo = 'codigo'

            precio_ant = prod[3] if prod else 0
            sube       = precio_xml > precio_ant if prod else False

            items.append({
                'descripcion': descripcion,
                'clave_sat':   clave_sat_xml,
                'no_id':       no_id,
                'cantidad':    cantidad,
                'precio_xml':  precio_xml,
                'prod':        prod,   # (id, codigo, nombre, precio_base, stock_actual, precio_base_fecha)
                'metodo':      metodo,
                'sube_precio': sube,
            })

        n_vinc   = sum(1 for i in items if i['prod'])
        n_novinc = len(items) - n_vinc

        # ── Ventana ───────────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title('📦 Confirmar actualización de Stock')
        win.geometry('1000x620')
        _centrar(win, self.sistema.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)
        win.grab_set()

        # Cabecera
        hdr = tk.Frame(win, bg='#065f46', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='📦  Actualización de Stock desde Factura de Compra',
                 font=('Arial', 11, 'bold'), bg='#065f46', fg='white').pack(side='left', padx=12)
        tk.Label(hdr, text=f'{serie_folio}  ·  {emisor}',
                 font=('Arial', 9), bg='#065f46', fg='#a7f3d0').pack(side='left', padx=6)

        # Resumen rápido
        sf = tk.Frame(win, bg='#ecfdf5', pady=6)
        sf.pack(fill='x', padx=14, pady=(8, 0))
        def _badge(parent, txt, bg, fg):
            tk.Label(parent, text=f'  {txt}  ', font=('Arial', 9, 'bold'),
                     bg=bg, fg=fg).pack(side='left', padx=4)
        _badge(sf, f'✅ {n_vinc} vinculados al catálogo', '#d1fae5', '#065f46')
        if n_novinc:
            _badge(sf, f'⚠️ {n_novinc} sin vincular (no se registrarán)', '#fef3c7', '#92400e')
        _badge(sf, f'{len(items)} conceptos totales', '#dbeafe', '#1e3a5f')

        tk.Label(win,
                 text='Los productos vinculados actualizarán su stock. '
                      'El precio base se actualiza solo si el precio del XML es mayor al registrado.',
                 font=('Arial', 8), bg='#f1f5f9', fg='#6b7280').pack(anchor='w', padx=14, pady=(2, 4))

        # ── Tabla ─────────────────────────────────────────────────────────────
        cols = ('Descripción XML', 'Clave SAT', 'Cant.', 'Producto en Catálogo',
                'Stock Actual', 'Precio Ant.', 'Precio XML', 'Acción Precio', 'Método')
        widths = [200, 90, 55, 180, 80, 90, 90, 110, 80]

        ft = tk.Frame(win, bg='#f1f5f9')
        ft.pack(fill='both', expand=True, padx=14, pady=6)
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        tree = ttk.Treeview(ft, columns=cols, show='headings', selectmode='none', height=14)
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w)

        tree.tag_configure('sat',     background='#d1fae5', foreground='#065f46')
        tree.tag_configure('codigo',  background='#dbeafe', foreground='#1e3a5f')
        tree.tag_configure('novinc',  background='#fef3c7', foreground='#92400e')

        sc_y = ttk.Scrollbar(ft, orient='vertical',   command=tree.yview)
        sc_x = ttk.Scrollbar(ft, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        tree.grid(row=0, column=0, sticky='nsew')
        sc_y.grid(row=0, column=1, sticky='ns')
        sc_x.grid(row=1, column=0, sticky='ew')

        for it in items:
            if it['prod']:
                pid, cod, nom, p_ant, stock, p_fecha = it['prod']
                nom_cat    = f'{cod} — {nom}'
                stock_txt  = f'{stock:g}'
                p_ant_txt  = f'${p_ant:,.2f}' if p_ant else '$0.00'
                p_xml_txt  = f'${it["precio_xml"]:,.2f}'
                if it['sube_precio']:
                    accion = f'↑ ${it["precio_xml"]:,.2f}  (actualizar)'
                elif it['precio_xml'] == p_ant:
                    accion = '= Sin cambio'
                else:
                    accion = '↓ No aplica'
                metodo_txt = '🔑 Clave SAT' if it['metodo'] == 'clave_sat' else '📦 Código'
                tag = 'sat' if it['metodo'] == 'clave_sat' else 'codigo'
            else:
                nom_cat = '⚠️ Sin vincular'
                stock_txt = '—'
                p_ant_txt = '—'
                p_xml_txt = f'${it["precio_xml"]:,.2f}'
                accion    = '—'
                metodo_txt = '—'
                tag = 'novinc'

            tree.insert('', 'end', tags=(tag,), values=(
                (it['descripcion'] or '')[:45],
                it['clave_sat'] or '—',
                f'{it["cantidad"]:g}',
                nom_cat,
                stock_txt,
                p_ant_txt,
                p_xml_txt,
                accion,
                metodo_txt,
            ))

        # ── Pie ───────────────────────────────────────────────────────────────
        foot = tk.Frame(win, bg='#1e2d45', pady=8)
        foot.pack(fill='x', side='bottom')

        def _confirmar():
            if n_vinc == 0:
                messagebox.showinfo(
                    'Sin productos vinculados',
                    'No hay productos vinculados al catálogo. '
                    'Ve al Centro de Vinculación para asignarlos primero.',
                    parent=win)
                win.destroy()
                return

            try:
                actualizados   = 0
                precios_subidos = 0
                for it in items:
                    if not it['prod']:
                        continue
                    pid, cod, nom, p_ant, stock_act, p_fecha = it['prod']

                    nuevo_stock = stock_act + it['cantidad']
                    upd = {'stock_actual': nuevo_stock}

                    # Actualizar precio si sube
                    if it['sube_precio']:
                        self.cursor.execute(
                            "UPDATE productos SET stock_actual=?, precio_base=?, "
                            "precio_base_fecha=? WHERE id=?",
                            (nuevo_stock, it['precio_xml'], hoy, pid))
                        precios_subidos += 1
                    else:
                        self.cursor.execute(
                            "UPDATE productos SET stock_actual=? WHERE id=?",
                            (nuevo_stock, pid))

                    # Registrar movimiento en stock
                    folio_ref = serie_folio or datos.get('uuid', '')[:16]
                    self.cursor.execute("""
                        INSERT INTO movimientos_stock
                        (producto_id, tipo, motivo, cantidad,
                         stock_antes, stock_despues, referencia, notas, fecha)
                        VALUES (?, 'entrada', 'Compra XML', ?, ?, ?, ?, ?, ?)
                    """, (pid, it['cantidad'], stock_act, nuevo_stock,
                          folio_ref,
                          f'Importado desde XML — {emisor}',
                          hoy))
                    actualizados += 1

                self.conn.commit()

                # ── Registrar entrada en tabla compras ────────────────────────
                # Buscar proveedor por RFC emisor
                rfc_emisor = datos.get('rfc_emisor', '')
                self.cursor.execute(
                    "SELECT id FROM proveedores WHERE UPPER(rfc)=UPPER(?) LIMIT 1",
                    (rfc_emisor,))
                prov_row = self.cursor.fetchone()
                prov_id  = prov_row[0] if prov_row else None

                # Buscar id de la factura recién importada (por uuid)
                self.cursor.execute(
                    "SELECT id FROM facturas WHERE uuid=? LIMIT 1",
                    (datos.get('uuid', ''),))
                fac_row    = self.cursor.fetchone()
                factura_id = fac_row[0] if fac_row else None

                # Generar folio — usa MAX del sufijo para evitar duplicados por gaps
                año_c = hoy[:4]
                self.cursor.execute(
                    "SELECT COALESCE(MAX(CAST(SUBSTR(folio, 11) AS INTEGER)), 0) + 1 "
                    "FROM compras WHERE folio LIKE ?",
                    (f"COMP-{año_c}-%",))
                consec_c = self.cursor.fetchone()[0]
                folio_compra = f"COMP-{año_c}-{consec_c:04d}"

                # Totales
                subtotal_c = datos.get('subtotal', 0) or 0
                iva_c      = datos.get('iva', 0) or 0
                total_c    = datos.get('total', 0) or 0

                # Verificar que no exista ya (evitar duplicado si se llama dos veces)
                if factura_id:
                    self.cursor.execute(
                        "SELECT id FROM compras WHERE factura_xml_id=?", (factura_id,))
                    ya_existe = self.cursor.fetchone()
                else:
                    ya_existe = None

                if not ya_existe:
                    # Retry hasta 5 veces si el folio colisiona (race condition o gap)
                    for _intento in range(5):
                        try:
                            self.cursor.execute("""
                                INSERT INTO compras
                                (folio, proveedor_id, fecha_compra, subtotal, iva, total,
                                 notas, ticket_referencia, factura_xml_id)
                                VALUES (?,?,?,?,?,?,?,?,?)
                            """, (folio_compra, prov_id, hoy,
                                  subtotal_c, iva_c, total_c,
                                  f"Importado desde XML {serie_folio}",
                                  serie_folio, factura_id))
                            break
                        except Exception as _dup:
                            if 'unique' in str(_dup).lower() or 'duplicad' in str(_dup).lower():
                                consec_c += 1
                                folio_compra = f"COMP-{año_c}-{consec_c:04d}"
                            else:
                                raise
                    compra_id_nuevo = self.cursor.lastrowid

                    # Detalle de compra: solo productos vinculados al catálogo
                    for it in items:
                        if not it['prod']:
                            continue
                        pid, cod, nom, p_ant, stock_ant_i, p_fecha = it['prod']
                        self.cursor.execute("""
                            INSERT INTO compra_detalle
                            (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                            VALUES (?,?,?,?,?)
                        """, (compra_id_nuevo, pid,
                              it['cantidad'], it['precio_xml'],
                              it['cantidad'] * it['precio_xml']))

                    self.conn.commit()

                msg = f'✅ Stock actualizado para {actualizados} producto(s).'
                msg += f'\n📦 Compra registrada con folio {folio_compra}.'
                if precios_subidos:
                    msg += f'\n💰 {precios_subidos} precio(s) base actualizados al costo máximo histórico.'
                if n_novinc:
                    msg += (f'\n⚠️ {n_novinc} concepto(s) no se registraron por no estar '
                            'vinculados al catálogo.\n   Usa el Centro de Vinculación para asignarlos.')
                messagebox.showinfo('Stock actualizado', msg, parent=win)
                win.destroy()

                # Refrescar dashboard
                try:
                    self.sistema.actualizar_dashboard()
                except Exception:
                    pass

            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror('Error BD', str(e), parent=win)

        tk.Button(foot, text='✅  Confirmar y Registrar Stock',
                  font=('Arial', 10, 'bold'), bg='#16a34a', fg='white',
                  cursor='hand2', padx=16, pady=6, relief='flat',
                  command=_confirmar).pack(side='left', padx=12)
        tk.Button(foot, text='Cancelar — no registrar',
                  font=('Arial', 9), bg='#6b7280', fg='white',
                  cursor='hand2', padx=12, pady=6, relief='flat',
                  command=win.destroy).pack(side='right', padx=12)
        tk.Label(foot,
                 text='Los productos sin vincular se omiten. El stock solo sube en productos del catálogo.',
                 font=('Arial', 8), bg='#1e2d45', fg='#94a3b8').pack(side='left', padx=6)

    # ── Vincular cotización ────────────────────────────────────────────────────
    def vincular_cotizacion(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Advertencia', 'Selecciona una factura', parent=self.root)
            return
        vals      = self.tree.item(sel[0])['values']
        factura_id = vals[0]
        uuid       = vals[1]

        # Obtener datos actuales
        self.cursor.execute(
            'SELECT cotizacion_id, fecha FROM facturas WHERE id=?', (factura_id,))
        row = self.cursor.fetchone()
        cot_actual, fecha_fac = row if row else (None, '')

        # ── Ventana de vinculación ──────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title('Vincular Factura a Cotización')
        win.geometry('700x500')
        _centrar(win, self.sistema.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)
        win.grab_set()

        hdr = tk.Frame(win, bg='#0f7b5e', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🔗  Vincular Factura a Cotización',
                 font=('Arial', 11, 'bold'), bg='#0f7b5e', fg='white').pack()
        tk.Label(hdr, text=uuid, font=('Arial', 8), bg='#0f7b5e',
                 fg='#a7f3d0').pack()

        # Barra de búsqueda de cotizaciones
        ff = tk.Frame(win, bg='#f1f5f9', pady=6)
        ff.pack(fill='x', padx=12)
        tk.Label(ff, text='Buscar cotización:', bg='#f1f5f9',
                 font=('Arial', 9)).pack(side='left', padx=(0, 4))
        entry_bus = tk.Entry(ff, font=('Arial', 9), width=30)
        entry_bus.pack(side='left')

        # Layout: tabla izquierda | preview derecho
        body = tk.Frame(win, bg='#f1f5f9')
        body.pack(fill='both', expand=True, padx=12, pady=4)

        # Tabla izquierda
        ft = tk.Frame(body, bg='#f1f5f9')
        ft.pack(side='left', fill='both', expand=True, padx=(0, 6))

        cols_c = ('ID', 'Folio', 'Fecha', 'Cliente', 'Total', 'Estado')
        tree_c = ttk.Treeview(ft, columns=cols_c, show='headings',
                               selectmode='browse', height=14)
        for col, w in zip(cols_c, [0, 120, 82, 190, 90, 120]):
            tree_c.heading(col, text=col)
            tree_c.column(col, width=w)
        tree_c.column('ID', stretch=False)
        sc = ttk.Scrollbar(ft, orient='vertical', command=tree_c.yview)
        tree_c.configure(yscrollcommand=sc.set)
        tree_c.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')

        for estado, bg in [('Pendiente', '#fff3cd'), ('Programada', '#cce5ff'),
                            ('Parcialmente Entregada', '#e8d5ff'),
                            ('Entregada', '#d4edda'),
                            ('Facturada', '#cffafe'), ('Pagada', '#d1fae5')]:
            tree_c.tag_configure(estado, background=bg)

        # Preview derecho
        pv = tk.Frame(body, bg='#f8fafc', width=240, relief='flat', bd=0,
                      highlightbackground='#cbd5e1', highlightthickness=1)
        pv.pack(side='right', fill='y')
        pv.pack_propagate(False)

        tk.Frame(pv, bg='#1e3a5f', height=30).pack(fill='x')
        tk.Label(pv.winfo_children()[-1], text='📋 Detalle',
                 font=('Arial', 8, 'bold'), bg='#1e3a5f', fg='white').place(relx=0.5, rely=0.5, anchor='center')

        pv_folio   = tk.Label(pv, text='—', font=('Arial', 9, 'bold'),
                               bg='#f8fafc', fg='#1e3a5f', anchor='w', padx=8)
        pv_folio.pack(fill='x', pady=(6, 0))
        pv_cliente = tk.Label(pv, text='Selecciona una cotización',
                               font=('Arial', 8), bg='#f8fafc', fg='#6b7280',
                               anchor='w', padx=8, wraplength=220, justify='left')
        pv_cliente.pack(fill='x')
        pv_estado  = tk.Label(pv, text='', font=('Arial', 8, 'bold'),
                               bg='#f8fafc', fg='#374151', anchor='w', padx=8)
        pv_estado.pack(fill='x')

        tk.Frame(pv, bg='#e2e8f0', height=1).pack(fill='x', pady=4)

        # Mini tabla productos
        cols_pv = ('Producto', 'Cant.', 'Total')
        pv_tree = ttk.Treeview(pv, columns=cols_pv, show='headings',
                                selectmode='none', height=9)
        for col_pv, w_pv in zip(cols_pv, [130, 40, 60]):
            pv_tree.heading(col_pv, text=col_pv)
            pv_tree.column(col_pv, width=w_pv, minwidth=w_pv)
        pv_tree.tag_configure('par',   background='#f8fafc')
        pv_tree.tag_configure('impar', background='#ffffff')
        pv_tree.pack(fill='x', padx=4)

        tk.Frame(pv, bg='#e2e8f0', height=1).pack(fill='x', pady=(4, 0))

        pv_total_lbl = tk.Label(pv, text='', font=('Arial', 9, 'bold'),
                                 bg='#f8fafc', fg='#0f7b5e', anchor='e', padx=10)
        pv_total_lbl.pack(fill='x', pady=4)

        def _actualizar_pv(cot_id):
            self.cursor.execute("""
                SELECT p.nombre, cd.cantidad, cd.total
                FROM cotizacion_detalle cd
                JOIN productos p ON p.id = cd.producto_id
                WHERE cd.cotizacion_id = ? ORDER BY cd.id
            """, (cot_id,))
            pv_tree.delete(*pv_tree.get_children())
            for i, (nombre, cant, tot_p) in enumerate(self.cursor.fetchall()):
                tag = 'par' if i % 2 == 0 else 'impar'
                pv_tree.insert('', 'end', tags=(tag,), values=(
                    nombre[:20] + ('…' if len(nombre) > 20 else ''),
                    f'{cant:g}', f'${tot_p:,.0f}'))

        def _on_select_pv(event):
            sel_pv = tree_c.selection()
            if not sel_pv:
                return
            vals_pv = tree_c.item(sel_pv[0])['values']
            cot_id_pv  = vals_pv[0]
            folio_pv   = str(vals_pv[1]).replace(' ◀', '')
            cliente_pv = vals_pv[3]
            total_pv   = vals_pv[4]
            estado_pv  = vals_pv[5]
            colores_pv = {
                'Pendiente': '#d97706', 'Programada': '#1d4ed8',
                'Parcialmente Entregada': '#7c3aed', 'Entregada': '#166534',
            }
            pv_folio.config(text=folio_pv)
            pv_cliente.config(text=f'👤 {cliente_pv}')
            pv_estado.config(text=f'● {estado_pv}',
                             fg=colores_pv.get(estado_pv, '#374151'))
            pv_total_lbl.config(text=f'Total: {total_pv}')
            _actualizar_pv(cot_id_pv)

        tree_c.bind('<<TreeviewSelect>>', _on_select_pv)

        def _cargar_cots(buscar=''):
            tree_c.delete(*tree_c.get_children())
            like = f'%{buscar}%'
            # Get cotizaciones already linked to this factura
            self.cursor.execute(
                "SELECT cotizacion_id FROM factura_cotizaciones WHERE factura_id=?",
                (factura_id,))
            ya_vinculadas = {r[0] for r in self.cursor.fetchall()}
            # Also check legacy
            if cot_actual:
                ya_vinculadas.add(cot_actual)

            self.cursor.execute("""
                SELECT c.id, c.folio, c.fecha, cl.nombre_comercial, c.total, c.estado
                FROM cotizaciones c
                JOIN clientes cl ON cl.id = c.cliente_id
                WHERE (c.folio LIKE ? OR cl.nombre_comercial LIKE ?)
                ORDER BY c.folio DESC
            """, (like, like))
            for r in self.cursor.fetchall():
                cid, folio, fecha, cli, total, estado = r
                vinculada_marca = ' 🔗' if cid in ya_vinculadas else ''
                tag = estado if estado in ('Pendiente', 'Programada',
                                           'Parcialmente Entregada', 'Entregada',
                                           'Facturada', 'Pagada') else ''
                tree_c.insert('', 'end', tags=(tag,), values=(
                    cid, folio + vinculada_marca, (fecha or '')[:10],
                    cli, f'${total:,.2f}', estado))

        _cargar_cots()
        entry_bus.bind('<Return>', lambda e: _cargar_cots(entry_bus.get().strip()))

        # Botón buscar inline
        tk.Button(ff, text='🔍', command=lambda: _cargar_cots(entry_bus.get().strip()),
                  bg=self.C['toolbar_bg'], font=('Arial', 9),
                  cursor='hand2', padx=6, pady=2).pack(side='left', padx=4)

        # Pie de ventana
        foot = tk.Frame(win, bg='#e2e8f0', pady=8)
        foot.pack(fill='x', side='bottom')

        def _vincular():
            sel_c = tree_c.selection()
            if not sel_c:
                messagebox.showwarning('Advertencia', 'Selecciona una cotización',
                                       parent=win)
                return
            cot_id  = tree_c.item(sel_c[0])['values'][0]
            cot_folio = tree_c.item(sel_c[0])['values'][1].replace(' ◀', '')
            self._vincular_factura_a_cotizacion(factura_id, cot_id,
                                                 uuid, fecha_fac, auto=False)
            win.destroy()
            self.cargar_facturas()
            self.sistema.actualizar_dashboard()

        def _desvincular():
            # Check both legacy column and junction table
            self.cursor.execute(
                "SELECT COUNT(*) FROM factura_cotizaciones WHERE factura_id=?", (factura_id,))
            n_junc = self.cursor.fetchone()[0]
            if not cot_actual and n_junc == 0:
                messagebox.showinfo('Info', 'La factura no tiene cotización vinculada.',
                                    parent=win)
                return
            if messagebox.askyesno('Confirmar', '¿Desvincular la factura de todas sus cotizaciones?',
                                   parent=win):
                # Limpiar junction table
                self.cursor.execute(
                    "DELETE FROM factura_cotizaciones WHERE factura_id=?", (factura_id,))
                # Limpiar legacy
                self.cursor.execute(
                    "UPDATE facturas SET cotizacion_id=NULL WHERE id=?", (factura_id,))
                self.conn.commit()
                win.destroy()
                self.cargar_facturas()

        tk.Button(foot, text='✅ Vincular seleccionada', command=_vincular,
                  bg='#0f7b5e', fg='white', font=('Arial', 10, 'bold'),
                  cursor='hand2', padx=14, pady=6).pack(side='left', padx=12)
        tk.Button(foot, text='🔓 Desvincular', command=_desvincular,
                  bg='#d97706', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=10, pady=6).pack(side='left')
        tk.Button(foot, text='Cancelar', command=win.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 10),
                  cursor='hand2', padx=10, pady=6).pack(side='right', padx=12)

    def _vincular_factura_a_cotizacion(self, factura_id, cot_ids, uuid, fecha_fac,
                                        auto=False):
        """Vincula una factura a una o varias cotizaciones.
        cot_ids puede ser un int o una lista de ints.
        """
        if isinstance(cot_ids, int):
            cot_ids = [cot_ids]
        try:
            fecha_etapa = (fecha_fac or '')[:10] or datetime.now().strftime('%Y-%m-%d')

            for cot_id in cot_ids:
                # 1. Junction table — crear si no existe (solo SQLite; en PG ya existe)
                import db_connection as _dbc
                if _dbc.motor_activo() != 'postgresql':
                    self.cursor.execute('''
                        CREATE TABLE IF NOT EXISTS factura_cotizaciones (
                            id            INTEGER PRIMARY KEY AUTOINCREMENT,
                            factura_id    INTEGER NOT NULL,
                            cotizacion_id INTEGER NOT NULL,
                            fecha_vinculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (factura_id)    REFERENCES facturas(id),
                            FOREIGN KEY (cotizacion_id) REFERENCES cotizaciones(id),
                            UNIQUE(factura_id, cotizacion_id)
                        )
                    ''')
                self.cursor.execute("""
                    INSERT OR IGNORE INTO factura_cotizaciones (factura_id, cotizacion_id)
                    VALUES (?, ?)
                """, (factura_id, cot_id))

                # 2. Columna legacy (compatibilidad)
                if cot_ids.index(cot_id) == 0:
                    self.cursor.execute(
                        'UPDATE facturas SET cotizacion_id=? WHERE id=?',
                        (cot_id, factura_id))

                # 3. Seguimiento: marcar etapa Facturada
                self.cursor.execute("""
                    INSERT INTO seguimiento_etapas
                        (cotizacion_id, etapa, completada, referencia, fecha_etapa, notas)
                    VALUES (?, 'Facturada', 1, ?, ?, ?)
                    ON CONFLICT(cotizacion_id, etapa) DO UPDATE SET
                        completada  = 1,
                        referencia  = excluded.referencia,
                        fecha_etapa = excluded.fecha_etapa,
                        notas       = COALESCE(excluded.notas, seguimiento_etapas.notas)
                """, (cot_id, uuid, fecha_etapa,
                      'Vinculado automáticamente desde XML' if auto else None))

                # 4. Sincronizar numero_factura en cotización
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET numero_factura = ?,
                        fecha_factura  = COALESCE(?, fecha_factura)
                    WHERE id = ?
                """, (uuid, fecha_etapa or None, cot_id))

            self.conn.commit()

            if not auto:
                n = len(cot_ids)
                messagebox.showinfo('Éxito',
                    f'Factura vinculada a {n} cotización{"es" if n > 1 else ""}\n'
                    f'Etapa "Facturada" marcada como completada.',
                    parent=self.root)

        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror('Error', str(e), parent=self.root)

    # ── Ver detalle ────────────────────────────────────────────────────────────
    def ver_detalle_factura(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Advertencia', 'Selecciona una factura', parent=self.root)
            return
        factura_id = self.tree.item(sel[0])['values'][0]
        self._mostrar_detalle_por_id(factura_id)

    def _mostrar_detalle_por_id(self, factura_id):
        """Abre la ventana de detalle de una factura dado su ID. Llamable desde otros módulos."""

        self.cursor.execute("""
            SELECT f.*, c.folio AS cot_folio
            FROM facturas f
            LEFT JOIN cotizaciones c ON c.id = f.cotizacion_id
            WHERE f.id = ?
        """, (factura_id,))
        cols_f = [d[0] for d in self.cursor.description]
        row    = self.cursor.fetchone()
        if not row:
            return
        f = dict(zip(cols_f, row))

        # Conceptos
        self.cursor.execute("""
            SELECT clave_prod_serv, no_identificacion, cantidad,
                   clave_unidad, unidad, descripcion, valor_unitario,
                   importe, descuento
            FROM factura_conceptos WHERE factura_id=?
        """, (factura_id,))
        conceptos = self.cursor.fetchall()

        # ── Ventana ───────────────────────────────────────────────────────────
        win = tk.Toplevel(self.root)
        win.title(f"Detalle Factura — {f['uuid']}")
        win.geometry('960x700')
        win.minsize(860, 620)
        _centrar(win, self.sistema.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)

        tipo_map_hdr = {'I': '📥 Ingreso', 'E': '📤 Egreso', 'P': '💳 Pago',
                        'N': '📋 Nómina', 'T': '🔄 Traslado'}
        tipo_map     = {'I': 'Ingreso', 'E': 'Egreso', 'P': 'Pago de Complemento',
                        'N': 'Nómina',  'T': 'Traslado'}

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg='#1a4b8c', pady=8)
        hdr.pack(fill='x')

        serie_folio_disp = ''
        if f.get('serie') and f.get('folio_factura'):
            serie_folio_disp = f"{f['serie']}-{f['folio_factura']}"
        elif f.get('folio_factura'):
            serie_folio_disp = str(f['folio_factura'])

        tipo_txt = tipo_map_hdr.get(f.get('tipo', ''), '🧾 CFDI')
        top_row  = tk.Frame(hdr, bg='#1a4b8c')
        top_row.pack(fill='x', padx=14)
        lbl_tipo_hdr = tk.Label(top_row, text=f"{tipo_txt}  {serie_folio_disp}",
                                font=('Arial', 11, 'bold'), bg='#1a4b8c', fg='white')
        lbl_tipo_hdr.pack(side='left')
        total_disp  = f.get('total', 0) or 0
        moneda_disp = f.get('moneda', 'MXN') or 'MXN'
        tk.Label(top_row, text=f"${total_disp:,.2f} {moneda_disp}",
                 font=('Arial', 11, 'bold'), bg='#1a4b8c', fg='#6ee7b7').pack(side='right')

        info_row = tk.Frame(hdr, bg='#1a4b8c')
        info_row.pack(fill='x', padx=14, pady=(2, 0))
        tk.Label(info_row,
                 text=f"Emisor: {f.get('rfc_emisor','')}  {f.get('nombre_emisor','')[:40]}",
                 font=('Arial', 8), bg='#1a4b8c', fg='#bfdbfe').pack(side='left')
        tk.Label(info_row,
                 text=f"Receptor: {f.get('rfc_receptor','')}  {f.get('nombre_receptor','')[:40]}",
                 font=('Arial', 8), bg='#1a4b8c', fg='#bfdbfe').pack(side='right')
        tk.Label(hdr, text=f"UUID: {(f.get('uuid',''))[:36]}",
                 font=('Arial', 8), bg='#1a4b8c', fg='#7dd3fc').pack(anchor='w', padx=14)

        # ── Footer (fijo, fuera del contenido) ───────────────────────────────
        foot = tk.Frame(win, bg='#e8edf4', pady=8)
        foot.pack(side='bottom', fill='x')

        tk.Button(foot, text='📄 Abrir XML',
                  command=lambda: self._abrir_archivo(f['ruta_xml']),
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=12)

        def _on_tipo_cambiado(nuevo_tipo):
            f['tipo'] = nuevo_tipo
            lbl_tipo_hdr.config(text=f"{tipo_map_hdr.get(nuevo_tipo, '🧾 CFDI')}  {serie_folio_disp}")

        tk.Button(foot, text='✏️ Cambiar Tipo',
                  command=lambda: self._cambiar_tipo_factura(
                      f['id'], f.get('tipo', ''), _on_tipo_cambiado, win),
                  bg='#d97706', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=4).pack(side='left', padx=4)

        tk.Button(foot, text='Cerrar', command=win.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=4).pack(side='right', padx=12)

        # ── Helpers ───────────────────────────────────────────────────────────
        def card(parent, titulo):
            lf = tk.LabelFrame(parent, text=f'  {titulo}  ',
                               font=('Arial', 9, 'bold'),
                               bg='#f1f5f9', fg='#1e2d45',
                               relief='flat', bd=1)
            lf.pack(fill='x', padx=8, pady=(5, 0))
            return lf

        def fila(parent, label, valor, color='#1e2d45'):
            r = tk.Frame(parent, bg='#f1f5f9')
            r.pack(fill='x', padx=8, pady=1)
            tk.Label(r, text=label, font=('Arial', 9, 'bold'), bg='#f1f5f9',
                     fg='#6b7e99', width=20, anchor='w').pack(side='left')
            tk.Label(r, text=str(valor) if valor else '—', font=('Arial', 9),
                     bg='#f1f5f9', fg=color, anchor='w').pack(side='left', fill='x', expand=True)

        # ── Cuerpo: dos columnas ──────────────────────────────────────────────
        body = tk.Frame(win, bg='#f1f5f9')
        body.pack(fill='both', expand=True, padx=6, pady=6)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)

        # Columna izquierda: Datos Generales
        col_izq = tk.Frame(body, bg='#f1f5f9')
        col_izq.grid(row=0, column=0, sticky='nsew', padx=(0, 4))

        c1 = card(col_izq, '📄  Datos Generales')
        fila(c1, 'UUID:', f['uuid'])
        fila(c1, 'Versión CFDI:', f.get('version') or '—')
        fila(c1, 'Serie - Folio:',
             f"{f['serie']}-{f['folio_factura']}" if f.get('serie') else (f.get('folio_factura') or '—'))
        fila(c1, 'Fecha:', (f.get('fecha') or '')[:19])
        fila(c1, 'Fecha timbrado:', (f.get('fecha_timbrado') or '')[:19])
        fila(c1, 'Tipo:', tipo_map.get(f.get('tipo', ''), f.get('tipo') or '—'))
        fila(c1, 'Método de pago:', f.get('metodo_pago') or '—')
        fila(c1, 'Forma de pago:', f.get('forma_pago') or '—')
        fila(c1, 'Moneda:', f.get('moneda') or '—')
        fila(c1, 'Cotización:', f.get('cot_folio') or '—',
             '#1a6b3a' if f.get('cot_folio') else '#d97706')
        fila(c1, 'Archivo XML:', os.path.basename(f['ruta_xml']) if f.get('ruta_xml') else '—')

        # Columna derecha: Emisor + Receptor + Totales
        col_der = tk.Frame(body, bg='#f1f5f9')
        col_der.grid(row=0, column=1, sticky='nsew', padx=(4, 0))

        c2 = card(col_der, '🏢  Emisor')
        fila(c2, 'RFC:', f.get('rfc_emisor') or '—')
        fila(c2, 'Nombre:', f.get('nombre_emisor') or '—')
        fila(c2, 'Régimen fiscal:', f.get('regimen_fiscal') or '—')

        c3 = card(col_der, '🏛️  Receptor')
        fila(c3, 'RFC:', f.get('rfc_receptor') or '—')
        fila(c3, 'Nombre:', f.get('nombre_receptor') or '—')
        fila(c3, 'Uso CFDI:', f.get('uso_cfdi') or '—')

        c4 = card(col_der, '💰  Totales')
        fila(c4, 'Subtotal:', f'${f["subtotal"]:,.2f}' if f.get('subtotal') else '$0.00')
        if f.get('descuento'):
            fila(c4, 'Descuento:', f'${f["descuento"]:,.2f}', '#c0392b')
        fila(c4, 'IVA:', f'${f["iva"]:,.2f}' if f.get('iva') is not None else '$0.00')
        fila(c4, 'TOTAL:', f'${f["total"]:,.2f}' if f.get('total') is not None else '$0.00',
             '#1a4b8c')

        # ── Conceptos (fila completa) ─────────────────────────────────────────
        if conceptos:
            frm_conc = tk.LabelFrame(win, text='  📦  Conceptos  ',
                                     font=('Arial', 9, 'bold'),
                                     bg='#f1f5f9', fg='#1e2d45',
                                     relief='flat', bd=1)
            frm_conc.pack(fill='x', padx=14, pady=(0, 4))

            cols_conc = ('Clave SAT', 'No. ID', 'Cantidad', 'Clave Unidad',
                         'Descripción', 'Valor Unit.', 'Importe')
            tree_conc = ttk.Treeview(frm_conc, columns=cols_conc, show='headings', height=4)
            for col, w in zip(cols_conc, [85, 85, 60, 85, 260, 95, 95]):
                tree_conc.heading(col, text=col)
                tree_conc.column(col, width=w, minwidth=40)
            for conc in conceptos:
                tree_conc.insert('', 'end', values=(
                    conc[0], conc[1], f'{conc[2]:g}', conc[3],
                    conc[5], f'${conc[6]:,.2f}', f'${conc[7]:,.2f}',
                ))
            sc_c   = ttk.Scrollbar(frm_conc, orient='vertical',   command=tree_conc.yview)
            sc_x_c = ttk.Scrollbar(frm_conc, orient='horizontal', command=tree_conc.xview)
            tree_conc.configure(yscrollcommand=sc_c.set, xscrollcommand=sc_x_c.set)
            sc_c.pack(side='right', fill='y')
            sc_x_c.pack(side='bottom', fill='x')
            tree_conc.pack(fill='x', padx=4, pady=4)

    # ── Cambiar tipo de comprobante ────────────────────────────────────────────
    def _cambiar_tipo_factura(self, factura_id, tipo_actual, on_cambio=None, parent_win=None):
        """Diálogo para cambiar el TipoDeComprobante de una factura ya importada."""
        dlg = tk.Toplevel(parent_win or self.root)
        dlg.title('Cambiar Tipo de Comprobante')
        dlg.geometry('300x270')
        _centrar(dlg, parent_win or self.root)
        dlg.configure(bg='#f1f5f9')
        dlg.transient(parent_win or self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text='Selecciona el tipo de comprobante:',
                 font=('Arial', 10, 'bold'), bg='#f1f5f9', fg='#1e2d45').pack(pady=(16, 8))

        tipos = [('I', '📥 Ingreso'), ('E', '📤 Egreso'), ('P', '💳 Pago'),
                 ('N', '📋 Nómina'),  ('T', '🔄 Traslado')]
        var = tk.StringVar(value=tipo_actual)
        for codigo, etiqueta in tipos:
            tk.Radiobutton(dlg, text=etiqueta, variable=var, value=codigo,
                           font=('Arial', 10), bg='#f1f5f9', fg='#1e2d45',
                           activebackground='#f1f5f9').pack(anchor='w', padx=36, pady=2)

        def guardar():
            nuevo_tipo = var.get()
            try:
                self.cursor.execute('UPDATE facturas SET tipo=? WHERE id=?',
                                    (nuevo_tipo, factura_id))
                self.conn.commit()
                self.cargar_facturas()
                if on_cambio:
                    on_cambio(nuevo_tipo)
                dlg.destroy()
            except sqlite3.Error as e:
                messagebox.showerror('Error', str(e), parent=dlg)

        btn_frame = tk.Frame(dlg, bg='#f1f5f9')
        btn_frame.pack(pady=14)
        tk.Button(btn_frame, text='Guardar', command=guardar,
                  bg='#1a4b8c', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=16, pady=5).pack(side='left', padx=8)
        tk.Button(btn_frame, text='Cancelar', command=dlg.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=12, pady=5).pack(side='left', padx=8)

    # ── Abrir XML ─────────────────────────────────────────────────────────────
    def abrir_xml(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Advertencia', 'Selecciona una factura', parent=self.root)
            return
        factura_id = self.tree.item(sel[0])['values'][0]
        self.cursor.execute('SELECT ruta_xml FROM facturas WHERE id=?', (factura_id,))
        row = self.cursor.fetchone()
        if row:
            self._abrir_archivo(row[0])

    def _abrir_archivo(self, ruta):
        if not ruta or not os.path.exists(ruta):
            messagebox.showerror('Archivo no encontrado',
                                 f'No se encontró el archivo:\n{ruta}', parent=self.root)
            return
        import subprocess, platform
        try:
            if platform.system() == 'Windows':
                os.startfile(ruta)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', ruta])
            else:
                subprocess.Popen(['xdg-open', ruta])
        except Exception as e:
            messagebox.showerror('Error', str(e), parent=self.root)

    # ── Eliminar ──────────────────────────────────────────────────────────────
    def eliminar_factura(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning('Advertencia', 'Selecciona una factura', parent=self.root)
            return
        vals       = self.tree.item(sel[0])['values']
        factura_id = vals[0]
        uuid       = vals[1]

        resp = messagebox.askyesno(
            'Eliminar factura',
            f'¿Eliminar el registro de la factura?\n\nUUID: {uuid}\n\n'
            'Esto solo elimina el registro en el sistema.\n'
            'El archivo XML no se eliminará del disco.',
            parent=self.root)
        if not resp:
            return
        try:
            self.cursor.execute('DELETE FROM factura_conceptos WHERE factura_id=?', (factura_id,))
            self.cursor.execute('DELETE FROM facturas WHERE id=?', (factura_id,))
            self.conn.commit()
            self.cargar_facturas()
        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror('Error', str(e), parent=self.root)

    # ── Gestionar Claves SAT ───────────────────────────────────────────────────
    def gestionar_claves_sat(self):
        """Ventana para gestionar datos fiscales SAT de productos, clientes y proveedores."""
        win = tk.Toplevel(self.root)
        win.title('🏷️  Datos Fiscales SAT')
        win.geometry('960x600')
        _centrar(win, self.sistema.root)
        win.configure(bg='#f1f5f9')
        win.transient(self.root)
        win.grab_set()

        hdr = tk.Frame(win, bg='#7c3aed', pady=8)
        hdr.pack(fill='x')
        tk.Label(hdr, text='🏷️  Vinculación de Datos Fiscales SAT',
                 font=('Arial', 11, 'bold'), bg='#7c3aed', fg='white').pack()
        tk.Label(hdr,
                 text='Gestiona claves SAT de productos, régimen fiscal de clientes y proveedores.',
                 font=('Arial', 8), bg='#7c3aed', fg='#ddd6fe').pack()

        nb = ttk.Notebook(win)
        nb.pack(fill='both', expand=True, padx=8, pady=6)

        # ══════════════ TAB 1: PRODUCTOS ══════════════════════════════════
        tab_prod = tk.Frame(nb, bg='#f1f5f9')
        nb.add(tab_prod, text='📦  Productos')

        # ── Búsqueda de productos ─────────────────────────────────────────
        ff = tk.Frame(tab_prod, bg='#f1f5f9', pady=6)
        ff.pack(fill='x', padx=12)
        tk.Label(ff, text='Buscar:', bg='#f1f5f9', font=('Arial', 9)).pack(side='left')
        entry_b = tk.Entry(ff, font=('Arial', 9), width=30)
        entry_b.pack(side='left', padx=6)

        # Tabla de productos
        ft = tk.Frame(tab_prod, bg='#f1f5f9')
        ft.pack(fill='both', expand=True, padx=12, pady=4)

        cols = ('ID', 'Código', 'Nombre', 'Clave SAT', 'Clave Unidad SAT')
        tree_p = ttk.Treeview(ft, columns=cols, show='headings', selectmode='browse')
        wcfg   = {'ID': 0, 'Código': 90, 'Nombre': 280,
                  'Clave SAT': 120, 'Clave Unidad SAT': 120}
        for col in cols:
            tree_p.heading(col, text=col)
            tree_p.column(col, width=wcfg[col])
        tree_p.column('ID', stretch=False)

        tree_p.tag_configure('con_clave',   background='#d4edda')
        tree_p.tag_configure('sin_clave',   background='#fff3cd')
        tree_p.tag_configure('clave_parc',  background='#cffafe')

        sc = ttk.Scrollbar(ft, orient='vertical', command=tree_p.yview)
        tree_p.configure(yscrollcommand=sc.set)
        tree_p.pack(side='left', fill='both', expand=True)
        sc.pack(side='right', fill='y')

        def _cargar(buscar=''):
            tree_p.delete(*tree_p.get_children())
            like = f'%{buscar}%'
            self.cursor.execute("""
                SELECT id, codigo, nombre, clave_sat, clave_unidad_sat
                FROM productos
                WHERE codigo LIKE ? OR nombre LIKE ?
                ORDER BY nombre
            """, (like, like))
            for r in self.cursor.fetchall():
                pid, codigo, nombre, csat, cunidad = r
                tiene_sat    = bool(csat)
                tiene_unidad = bool(cunidad)
                if tiene_sat and tiene_unidad:
                    tag = 'con_clave'
                elif tiene_sat or tiene_unidad:
                    tag = 'clave_parc'
                else:
                    tag = 'sin_clave'
                tree_p.insert('', 'end', tags=(tag,), values=(
                    pid, codigo, nombre, csat or '—', cunidad or '—'))

        _cargar()
        entry_b.bind('<Return>', lambda e: _cargar(entry_b.get().strip()))
        tk.Button(ff, text='🔍', command=lambda: _cargar(entry_b.get().strip()),
                  bg='#e2e8f0', font=('Arial', 9), cursor='hand2',
                  padx=6, pady=2).pack(side='left', padx=2)

        # Leyenda
        ley = tk.Frame(tab_prod, bg='#f1f5f9', pady=4)
        ley.pack(fill='x', padx=12)
        for txt, bg, fg in [('✅ Ambas claves', '#d4edda', '#1a6b3a'),
                             ('🔵 Solo una clave', '#cffafe', '#0e7490'),
                             ('⚠️ Sin claves', '#fff3cd', '#856404')]:
            lf = tk.Frame(ley, bg=bg, padx=8, pady=2)
            lf.pack(side='left', padx=3)
            tk.Label(lf, text=txt, font=('Arial', 7), bg=bg, fg=fg).pack()

        # Botones acción productos
        foot = tk.Frame(tab_prod, bg='#e2e8f0', pady=6)
        foot.pack(fill='x', side='bottom')

        def _editar_clave():
            sel = tree_p.selection()
            if not sel:
                messagebox.showwarning('Advertencia', 'Selecciona un producto', parent=win)
                return
            vals = tree_p.item(sel[0])['values']
            pid  = vals[0]
            nombre = vals[2]
            csat_act    = vals[3] if vals[3] != '—' else ''
            cunidad_act = vals[4] if vals[4] != '—' else ''

            dlg = tk.Toplevel(win)
            dlg.title(f'Claves SAT — {nombre}')
            dlg.geometry('420x220')
            _centrar(dlg, self.sistema.root)
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            dlg.configure(bg='#f8fafc')

            tk.Label(dlg, text=nombre, font=('Arial', 10, 'bold'),
                     bg='#f8fafc', wraplength=380).pack(pady=(14, 8), padx=16)

            form = tk.Frame(dlg, bg='#f8fafc')
            form.pack(fill='x', padx=24)
            form.grid_columnconfigure(1, weight=1)

            tk.Label(form, text='Clave Prod/Serv SAT:', font=('Arial', 9, 'bold'),
                     bg='#f8fafc', anchor='e').grid(row=0, column=0, sticky='e',
                                                    padx=(0, 8), pady=6)
            e_sat = tk.Entry(form, font=('Arial', 10), width=22)
            e_sat.insert(0, csat_act)
            e_sat.grid(row=0, column=1, sticky='w')
            tk.Label(form, text='ej. 43211500', font=('Arial', 7),
                     bg='#f8fafc', fg='#9ca3af').grid(row=1, column=1, sticky='w')

            tk.Label(form, text='Clave Unidad SAT:', font=('Arial', 9, 'bold'),
                     bg='#f8fafc', anchor='e').grid(row=2, column=0, sticky='e',
                                                    padx=(0, 8), pady=6)
            e_unidad = tk.Entry(form, font=('Arial', 10), width=22)
            e_unidad.insert(0, cunidad_act)
            e_unidad.grid(row=2, column=1, sticky='w')
            tk.Label(form, text='ej. H87 (pieza), KGM (kg), LTR (litro)',
                     font=('Arial', 7), bg='#f8fafc',
                     fg='#9ca3af').grid(row=3, column=1, sticky='w')

            def _guardar(event=None):
                nuevo_sat    = e_sat.get().strip() or None
                nuevo_unidad = e_unidad.get().strip() or None
                try:
                    self.cursor.execute("""
                        UPDATE productos SET clave_sat=?, clave_unidad_sat=? WHERE id=?
                    """, (nuevo_sat, nuevo_unidad, pid))
                    self.conn.commit()
                    _cargar(entry_b.get().strip())
                    dlg.destroy()
                except sqlite3.Error as e2:
                    messagebox.showerror('Error', str(e2), parent=dlg)

            e_sat.bind('<Return>', _guardar)
            e_unidad.bind('<Return>', _guardar)

            fb = tk.Frame(dlg, bg='#f8fafc')
            fb.pack(pady=12)
            tk.Button(fb, text='💾 Guardar', command=_guardar,
                      bg='#7c3aed', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=14, pady=5).pack(side='left', padx=6)
            tk.Button(fb, text='Cancelar', command=dlg.destroy,
                      bg='#6b7280', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=5).pack(side='left')

        def _autocompletar_desde_facturas():
            """
            Intenta asociar claves SAT a productos a partir de los conceptos
            de facturas importadas, haciendo match por NoIdentificacion = codigo.
            """
            self.cursor.execute("""
                SELECT DISTINCT fc.no_identificacion,
                       fc.clave_prod_serv, fc.clave_unidad
                FROM factura_conceptos fc
                WHERE fc.no_identificacion IS NOT NULL
                  AND fc.no_identificacion != ''
                  AND fc.clave_prod_serv IS NOT NULL
                  AND fc.clave_prod_serv != ''
            """)
            conceptos_fac = self.cursor.fetchall()
            if not conceptos_fac:
                messagebox.showinfo('Sin datos',
                    'No hay conceptos en facturas importadas con No. Identificación.\n'
                    'Importa facturas primero para usar esta función.',
                    parent=win)
                return

            actualizados = 0
            for no_id, clave_sat, clave_unidad in conceptos_fac:
                self.cursor.execute("""
                    UPDATE productos
                    SET clave_sat = COALESCE(clave_sat, ?),
                        clave_unidad_sat = COALESCE(clave_unidad_sat, ?)
                    WHERE codigo = ?
                      AND (clave_sat IS NULL OR clave_unidad_sat IS NULL)
                """, (clave_sat, clave_unidad, no_id))
                actualizados += self.cursor.rowcount

            self.conn.commit()
            _cargar(entry_b.get().strip())
            messagebox.showinfo('Listo',
                f'Se actualizaron {actualizados} producto(s) con claves SAT '
                'desde los conceptos de facturas importadas.',
                parent=win)

        tk.Button(foot, text='✏️ Editar clave seleccionada', command=_editar_clave,
                  bg='#7c3aed', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5).pack(side='left', padx=12)
        tk.Button(foot, text='⚡ Auto-completar desde facturas',
                  command=_autocompletar_desde_facturas,
                  bg='#0e7490', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5).pack(side='left')

        tree_p.bind('<Double-1>', lambda e: _editar_clave())

        # ══════════════ TAB 2: CLIENTES ════════════════════════════════════
        REGIMENES_SAT = [
            ('601','General de Ley Personas Morales'),
            ('603','Personas Morales con Fines no Lucrativos'),
            ('605','Sueldos y Salarios e Ingresos Asimilados'),
            ('606','Arrendamiento'),
            ('607','Enajenación o Adquisición de Bienes'),
            ('608','Demás ingresos'),
            ('610','Residentes Extranjero sin EP en México'),
            ('611','Ingresos por Dividendos'),
            ('612','PF con Actividades Empresariales y Profesionales'),
            ('614','Ingresos por intereses'),
            ('616','Sin obligaciones fiscales'),
            ('620','Sociedades Cooperativas de Producción'),
            ('621','Incorporación Fiscal'),
            ('622','Actividades Agrícolas, Ganaderas, Silvícolas'),
            ('623','Opcional para Grupos de Sociedades'),
            ('624','Coordinados'),
            ('625','Actividades Empresariales vía Plataformas Tecnológicas'),
            ('626','RESICO – Simplificado de Confianza'),
        ]
        USOS_CFDI_SAT = [
            ('G01','Adquisición de mercancias'),
            ('G02','Devoluciones, descuentos o bonificaciones'),
            ('G03','Gastos en general'),
            ('I01','Construcciones'),
            ('I02','Mobiliario y equipo de oficina'),
            ('I03','Equipo de transporte'),
            ('I04','Equipo de cómputo y accesorios'),
            ('I08','Otra maquinaria y equipo'),
            ('D01','Honorarios médicos y gastos hospitalarios'),
            ('D10','Pagos por servicios educativos'),
            ('S01','Sin efectos fiscales'),
            ('CP01','Pagos'),
            ('CN01','Nómina'),
        ]
        reg_opts_all  = [''] + [f"{c} – {n}" for c, n in REGIMENES_SAT]
        uso_opts_all  = [''] + [f"{c} – {n}" for c, n in USOS_CFDI_SAT]

        tab_cli = tk.Frame(nb, bg='#f1f5f9')
        nb.add(tab_cli, text='👥  Clientes')

        ff_cli = tk.Frame(tab_cli, bg='#f1f5f9', pady=6)
        ff_cli.pack(fill='x', padx=12)
        tk.Label(ff_cli, text='Buscar:', bg='#f1f5f9', font=('Arial', 9)).pack(side='left')
        entry_cli = tk.Entry(ff_cli, font=('Arial', 9), width=28)
        entry_cli.pack(side='left', padx=6)
        tk.Button(ff_cli, text='🔍', bg='#e2e8f0', font=('Arial', 9), cursor='hand2',
                  padx=6, pady=2,
                  command=lambda: _cargar_cli(entry_cli.get().strip())).pack(side='left')

        ft_cli2 = tk.Frame(tab_cli, bg='#f1f5f9')
        ft_cli2.pack(fill='both', expand=True, padx=12, pady=4)
        cols_cli_sat = ('ID', 'Nombre Comercial', 'RFC', 'Régimen Fiscal', 'Uso CFDI', 'C.P. Fiscal')
        tree_cli = ttk.Treeview(ft_cli2, columns=cols_cli_sat, show='headings', selectmode='browse')
        for col_c, w_c in zip(cols_cli_sat, [0, 200, 110, 180, 90, 80]):
            tree_cli.heading(col_c, text=col_c)
            tree_cli.column(col_c, width=w_c, minwidth=w_c)
        tree_cli.column('ID', stretch=False)
        tree_cli.tag_configure('completo',  background='#d4edda')
        tree_cli.tag_configure('parcial',   background='#cffafe')
        tree_cli.tag_configure('sin_datos', background='#fff3cd')
        sc_cli2 = ttk.Scrollbar(ft_cli2, orient='vertical', command=tree_cli.yview)
        tree_cli.configure(yscrollcommand=sc_cli2.set)
        tree_cli.pack(side='left', fill='both', expand=True)
        sc_cli2.pack(side='right', fill='y')

        def _cargar_cli(buscar=''):
            tree_cli.delete(*tree_cli.get_children())
            like = f'%{buscar}%'
            self.cursor.execute("""
                SELECT id, nombre_comercial, rfc, regimen_fiscal, uso_cfdi, cp_fiscal
                FROM clientes WHERE nombre_comercial LIKE ? OR rfc LIKE ?
                ORDER BY nombre_comercial
            """, (like, like))
            for r in self.cursor.fetchall():
                cid, nombre, rfc, reg, uso, cp = r
                cnt = sum(1 for v in (reg, uso, cp) if v)
                tag = 'completo' if cnt == 3 else ('parcial' if cnt > 0 else 'sin_datos')
                tree_cli.insert('', 'end', tags=(tag,), values=(
                    cid, nombre, rfc or '—', reg or '—', uso or '—', cp or '—'))
        _cargar_cli()
        entry_cli.bind('<Return>', lambda e: _cargar_cli(entry_cli.get().strip()))

        ley_cli = tk.Frame(tab_cli, bg='#f1f5f9', pady=3)
        ley_cli.pack(fill='x', padx=12)
        for txt_l, bg_l, fg_l in [('✅ Completo','#d4edda','#1a6b3a'),
                                    ('🔵 Parcial','#cffafe','#0e7490'),
                                    ('⚠️ Sin datos','#fff3cd','#856404')]:
            lf2 = tk.Frame(ley_cli, bg=bg_l, padx=8, pady=2)
            lf2.pack(side='left', padx=3)
            tk.Label(lf2, text=txt_l, font=('Arial', 7), bg=bg_l, fg=fg_l).pack()

        def _editar_cli():
            sel_c = tree_cli.selection()
            if not sel_c:
                messagebox.showwarning('Advertencia', 'Selecciona un cliente', parent=win)
                return
            vals_c = tree_cli.item(sel_c[0])['values']
            cli_id = vals_c[0]
            self.cursor.execute(
                'SELECT regimen_fiscal, uso_cfdi, cp_fiscal FROM clientes WHERE id=?', (cli_id,))
            row_c = self.cursor.fetchone()
            cur_reg_c = row_c[0] or '' if row_c else ''
            cur_uso_c = row_c[1] or '' if row_c else ''
            cur_cp_c  = row_c[2] or '' if row_c else ''

            dlg = tk.Toplevel(win)
            dlg.title(f'Datos Fiscales SAT — {vals_c[1]}')
            dlg.geometry('500x230')
            _centrar(dlg, self.sistema.root)
            dlg.resizable(False, False)
            dlg.transient(win)
            dlg.grab_set()
            dlg.configure(bg='#f8fafc')

            hdr_d = tk.Frame(dlg, bg='#1e3a5f', pady=6)
            hdr_d.pack(fill='x')
            tk.Label(hdr_d, text=f'👥  {vals_c[1]}  •  RFC: {vals_c[2]}',
                     font=('Arial', 9, 'bold'), bg='#1e3a5f', fg='white').pack(padx=12, anchor='w')

            form_c = tk.Frame(dlg, bg='#f8fafc')
            form_c.pack(fill='x', padx=20, pady=10)
            form_c.grid_columnconfigure(1, weight=1)

            def frow_c(r, lbl, wdg):
                tk.Label(form_c, text=lbl, font=('Arial', 9, 'bold'),
                         bg='#f8fafc', fg='#374151', anchor='e').grid(
                    row=r, column=0, sticky='e', padx=(0, 8), pady=5)
                wdg.grid(row=r, column=1, sticky='ew', pady=5)

            c_reg_c = ttk.Combobox(form_c, values=reg_opts_all, state='readonly',
                                    width=40, font=('Arial', 9))
            c_reg_c.set(next((o for o in reg_opts_all if o.startswith(cur_reg_c)), ''))
            frow_c(0, 'Régimen Fiscal:', c_reg_c)

            c_uso_c = ttk.Combobox(form_c, values=uso_opts_all, state='readonly',
                                    width=40, font=('Arial', 9))
            c_uso_c.set(next((o for o in uso_opts_all if o.startswith(cur_uso_c)), ''))
            frow_c(1, 'Uso de CFDI:', c_uso_c)

            e_cp_c = tk.Entry(form_c, font=('Arial', 9), width=12, relief='solid', bd=1)
            e_cp_c.insert(0, cur_cp_c)
            frow_c(2, 'C.P. Fiscal:', e_cp_c)

            def _guardar_cli(event=None):
                reg_v = c_reg_c.get().split(' – ')[0] if c_reg_c.get() else None
                uso_v = c_uso_c.get().split(' – ')[0] if c_uso_c.get() else None
                cp_v  = e_cp_c.get().strip() or None
                try:
                    self.cursor.execute(
                        'UPDATE clientes SET regimen_fiscal=?, uso_cfdi=?, cp_fiscal=? WHERE id=?',
                        (reg_v, uso_v, cp_v, cli_id))
                    self.conn.commit()
                    _cargar_cli(entry_cli.get().strip())
                    dlg.destroy()
                except Exception as ex:
                    messagebox.showerror('Error', str(ex), parent=dlg)

            fb_c = tk.Frame(dlg, bg='#f8fafc')
            fb_c.pack(pady=10)
            tk.Button(fb_c, text='💾 Guardar', command=_guardar_cli,
                      bg='#1e3a5f', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=14, pady=5).pack(side='left', padx=6)
            tk.Button(fb_c, text='Cancelar', command=dlg.destroy,
                      bg='#6b7280', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=5).pack(side='left')
            e_cp_c.bind('<Return>', _guardar_cli)

        def _autocompletar_cli():
            self.cursor.execute("""
                SELECT DISTINCT f.rfc_receptor, f.uso_cfdi
                FROM facturas f
                WHERE f.rfc_receptor IS NOT NULL AND f.rfc_receptor != ''
                  AND f.uso_cfdi IS NOT NULL AND f.uso_cfdi != ''
            """)
            actualizados_c = 0
            for rfc_f, uso_f in self.cursor.fetchall():
                self.cursor.execute("""
                    UPDATE clientes SET uso_cfdi = COALESCE(uso_cfdi, ?)
                    WHERE rfc = ? AND (uso_cfdi IS NULL OR uso_cfdi = '')
                """, (uso_f, rfc_f))
                actualizados_c += self.cursor.rowcount
            self.conn.commit()
            _cargar_cli(entry_cli.get().strip())
            messagebox.showinfo('Listo',
                f'Se actualizaron {actualizados_c} cliente(s) desde facturas importadas.',
                parent=win)

        foot_cli = tk.Frame(tab_cli, bg='#e2e8f0', pady=6)
        foot_cli.pack(fill='x', side='bottom')
        tk.Button(foot_cli, text='✏️ Editar datos SAT', command=_editar_cli,
                  bg='#1e3a5f', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5).pack(side='left', padx=12)
        tk.Button(foot_cli, text='⚡ Auto-completar desde facturas',
                  command=_autocompletar_cli,
                  bg='#0e7490', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5).pack(side='left')
        tree_cli.bind('<Double-1>', lambda e: _editar_cli())

        # ══════════════ TAB 3: PROVEEDORES ═════════════════════════════════
        tab_prov2 = tk.Frame(nb, bg='#f1f5f9')
        nb.add(tab_prov2, text='🏭  Proveedores')

        ff_prov2 = tk.Frame(tab_prov2, bg='#f1f5f9', pady=6)
        ff_prov2.pack(fill='x', padx=12)
        tk.Label(ff_prov2, text='Buscar:', bg='#f1f5f9', font=('Arial', 9)).pack(side='left')
        entry_prov2 = tk.Entry(ff_prov2, font=('Arial', 9), width=28)
        entry_prov2.pack(side='left', padx=6)
        tk.Button(ff_prov2, text='🔍', bg='#e2e8f0', font=('Arial', 9), cursor='hand2',
                  padx=6, pady=2,
                  command=lambda: _cargar_prov(entry_prov2.get().strip())).pack(side='left')

        ft_prov2 = tk.Frame(tab_prov2, bg='#f1f5f9')
        ft_prov2.pack(fill='both', expand=True, padx=12, pady=4)
        cols_prov_sat = ('ID', 'Nombre', 'RFC', 'Régimen Fiscal', 'C.P. Fiscal')
        tree_prov2 = ttk.Treeview(ft_prov2, columns=cols_prov_sat, show='headings', selectmode='browse')
        for col_p, w_p in zip(cols_prov_sat, [0, 240, 120, 210, 90]):
            tree_prov2.heading(col_p, text=col_p)
            tree_prov2.column(col_p, width=w_p, minwidth=w_p)
        tree_prov2.column('ID', stretch=False)
        tree_prov2.tag_configure('completo',  background='#d4edda')
        tree_prov2.tag_configure('parcial',   background='#cffafe')
        tree_prov2.tag_configure('sin_datos', background='#fff3cd')
        sc_prov2 = ttk.Scrollbar(ft_prov2, orient='vertical', command=tree_prov2.yview)
        tree_prov2.configure(yscrollcommand=sc_prov2.set)
        tree_prov2.pack(side='left', fill='both', expand=True)
        sc_prov2.pack(side='right', fill='y')

        def _cargar_prov(buscar=''):
            tree_prov2.delete(*tree_prov2.get_children())
            like = f'%{buscar}%'
            self.cursor.execute("""
                SELECT id, nombre, rfc, regimen_fiscal, cp_fiscal
                FROM proveedores WHERE nombre LIKE ? OR rfc LIKE ?
                ORDER BY nombre
            """, (like, like))
            for r in self.cursor.fetchall():
                pid, nombre, rfc, reg, cp = r
                cnt = sum(1 for v in (reg, cp) if v)
                tag = 'completo' if cnt == 2 else ('parcial' if cnt > 0 else 'sin_datos')
                tree_prov2.insert('', 'end', tags=(tag,), values=(
                    pid, nombre, rfc or '—', reg or '—', cp or '—'))
        _cargar_prov()
        entry_prov2.bind('<Return>', lambda e: _cargar_prov(entry_prov2.get().strip()))

        ley_prov2 = tk.Frame(tab_prov2, bg='#f1f5f9', pady=3)
        ley_prov2.pack(fill='x', padx=12)
        for txt_l, bg_l, fg_l in [('✅ Completo','#d4edda','#1a6b3a'),
                                    ('🔵 Parcial','#cffafe','#0e7490'),
                                    ('⚠️ Sin datos','#fff3cd','#856404')]:
            lf3 = tk.Frame(ley_prov2, bg=bg_l, padx=8, pady=2)
            lf3.pack(side='left', padx=3)
            tk.Label(lf3, text=txt_l, font=('Arial', 7), bg=bg_l, fg=fg_l).pack()

        def _editar_prov():
            sel_p = tree_prov2.selection()
            if not sel_p:
                messagebox.showwarning('Advertencia', 'Selecciona un proveedor', parent=win)
                return
            vals_p = tree_prov2.item(sel_p[0])['values']
            prov_id2 = vals_p[0]
            self.cursor.execute(
                'SELECT regimen_fiscal, cp_fiscal FROM proveedores WHERE id=?', (prov_id2,))
            row_p = self.cursor.fetchone()
            cur_reg_p = row_p[0] or '' if row_p else ''
            cur_cp_p  = row_p[1] or '' if row_p else ''

            dlg_p = tk.Toplevel(win)
            dlg_p.title(f'Datos Fiscales SAT — {vals_p[1]}')
            dlg_p.geometry('480x185')
            _centrar(ventana, self.sistema.root)
            dlg_p.resizable(False, False)
            dlg_p.transient(win)
            dlg_p.grab_set()
            dlg_p.configure(bg='#f8fafc')

            hdr_p = tk.Frame(dlg_p, bg='#92400e', pady=6)
            hdr_p.pack(fill='x')
            tk.Label(hdr_p, text=f'🏭  {vals_p[1]}  •  RFC: {vals_p[2]}',
                     font=('Arial', 9, 'bold'), bg='#92400e', fg='white').pack(padx=12, anchor='w')

            form_p = tk.Frame(dlg_p, bg='#f8fafc')
            form_p.pack(fill='x', padx=20, pady=10)
            form_p.grid_columnconfigure(1, weight=1)

            def frow_p(r, lbl, wdg):
                tk.Label(form_p, text=lbl, font=('Arial', 9, 'bold'),
                         bg='#f8fafc', fg='#374151', anchor='e').grid(
                    row=r, column=0, sticky='e', padx=(0, 8), pady=5)
                wdg.grid(row=r, column=1, sticky='ew', pady=5)

            c_reg_p = ttk.Combobox(form_p, values=reg_opts_all, state='readonly',
                                    width=40, font=('Arial', 9))
            c_reg_p.set(next((o for o in reg_opts_all if o.startswith(cur_reg_p)), ''))
            frow_p(0, 'Régimen Fiscal:', c_reg_p)
            e_cp_p = tk.Entry(form_p, font=('Arial', 9), width=12, relief='solid', bd=1)
            e_cp_p.insert(0, cur_cp_p)
            frow_p(1, 'C.P. Fiscal:', e_cp_p)

            def _guardar_prov(event=None):
                reg_v = c_reg_p.get().split(' – ')[0] if c_reg_p.get() else None
                cp_v  = e_cp_p.get().strip() or None
                try:
                    self.cursor.execute(
                        'UPDATE proveedores SET regimen_fiscal=?, cp_fiscal=? WHERE id=?',
                        (reg_v, cp_v, prov_id2))
                    self.conn.commit()
                    _cargar_prov(entry_prov2.get().strip())
                    dlg_p.destroy()
                except Exception as ex:
                    messagebox.showerror('Error', str(ex), parent=dlg_p)

            fb_p = tk.Frame(dlg_p, bg='#f8fafc')
            fb_p.pack(pady=10)
            tk.Button(fb_p, text='💾 Guardar', command=_guardar_prov,
                      bg='#92400e', fg='white', font=('Arial', 9, 'bold'),
                      cursor='hand2', padx=14, pady=5).pack(side='left', padx=6)
            tk.Button(fb_p, text='Cancelar', command=dlg_p.destroy,
                      bg='#6b7280', fg='white', font=('Arial', 9),
                      cursor='hand2', padx=10, pady=5).pack(side='left')
            e_cp_p.bind('<Return>', _guardar_prov)

        foot_prov2 = tk.Frame(tab_prov2, bg='#e2e8f0', pady=6)
        foot_prov2.pack(fill='x', side='bottom')
        tk.Button(foot_prov2, text='✏️ Editar datos SAT', command=_editar_prov,
                  bg='#92400e', fg='white', font=('Arial', 9, 'bold'),
                  cursor='hand2', padx=12, pady=5).pack(side='left', padx=12)
        tree_prov2.bind('<Double-1>', lambda e: _editar_prov())

        # ── Botón cerrar global ────────────────────────────────────────────
        tk.Button(win, text='✕  Cerrar', command=win.destroy,
                  bg='#6b7280', fg='white', font=('Arial', 9),
                  cursor='hand2', padx=14, pady=5).pack(pady=6)

