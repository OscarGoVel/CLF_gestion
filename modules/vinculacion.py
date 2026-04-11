# -*- coding: utf-8 -*-
"""
Centro de Vinculacion
Detecta entidades de facturas XML no registradas/vinculadas
y ofrece un dialogo split-panel para confirmar o crear el vinculo.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3

from core.vinculacion import (  # noqa: F401
    CLF_RFC,
    detectar_pendientes,
    cargar_clientes as _cargar_clientes,
    cargar_proveedores as _cargar_proveedores,
    cargar_productos as _cargar_productos,
    cargar_cotizaciones as _cargar_cotizaciones,
)


# ══════════════════════════════════════════════════════════════════════════════
class PanelVinculacion:

    CATS = [
        ("clientes",    "👥", "Clientes sin registrar",
         "RFC receptor de facturas sin cliente en catalogo.",
         "#1e3a5f", "#dbeafe"),
        ("proveedores", "🏭", "Proveedores sin registrar",
         "RFC emisor de facturas sin proveedor en catalogo.",
         "#92400e", "#fef3c7"),
        ("productos",   "📦", "Productos sin vincular",
         "No. Identificacion de conceptos XML sin producto en catalogo.",
         "#065f46", "#dcfce7"),
        ("cotizaciones","📄", "Facturas sin vincular",
         "🧾 Venta: sin cotización vinculada  ·  🛒 Compra: sin registro en compras.",
         "#0e7490", "#cffafe"),
    ]

    def __init__(self, sistema):
        self.sistema = sistema
        self.root    = sistema.root
        self.conn    = sistema.conn
        self.cursor  = sistema.cursor

    def abrir(self):
        self._pendientes = detectar_pendientes(self.cursor)
        total = sum(len(v) for v in self._pendientes.values())

        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("🔗  Centro de Vinculacion")
        win.geometry("820x680")
        win.configure(bg="#f1f5f9")
        win.transient(self.root)
        self._win_panel = win

        hdr = tk.Frame(win, bg="#1e2d45", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔗  Centro de Vinculacion",
                 font=("Arial", 12, "bold"), bg="#1e2d45", fg="white").pack(side="left", padx=14)
        bdg_bg = "#dc2626" if total > 0 else "#16a34a"
        tk.Label(hdr, text=f"  {total} pendiente{'s' if total!=1 else ''}  ",
                 font=("Arial", 9, "bold"), bg=bdg_bg, fg="white").pack(side="right", padx=14)

        tk.Label(win,
                 text="Detecta entidades de facturas importadas sin registro o vinculo.",
                 font=("Arial", 8), bg="#f1f5f9", fg="#6b7280").pack(anchor="w", padx=14, pady=(5, 0))

        tb = tk.Frame(win, bg="#f1f5f9", pady=4)
        tb.pack(fill="x", padx=14)
        tk.Button(tb, text="🔄 Re-escanear", font=("Arial", 8), cursor="hand2",
                  bg="#e2e8f0", fg="#374151", padx=10, pady=3,
                  command=lambda: [win.destroy(), self.abrir()]).pack(side="left")
        tk.Button(tb, text="🔓 Desvincular factura", font=("Arial", 8, "bold"), cursor="hand2",
                  bg="#7c3aed", fg="white", padx=10, pady=3,
                  command=lambda: self._abrir_desvincular(win)).pack(side="left", padx=8)
        tk.Button(tb, text="Cerrar", font=("Arial", 8), cursor="hand2",
                  bg="#e2e8f0", fg="#374151", padx=10, pady=3,
                  command=win.destroy).pack(side="right")
        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x")

        canvas = tk.Canvas(win, bg="#f1f5f9", highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        inner = tk.Frame(canvas, bg="#f1f5f9")
        wid = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))

        for key, icono, titulo, desc, color, bg_card in self.CATS:
            items = self._pendientes[key]
            self._tarjeta(inner, key, icono, titulo, desc, color, bg_card, items, win)
        win.after(0, win.deiconify)

    def _abrir_desvincular(self, win_padre):
        """Diálogo para desvincular una factura de su cotización."""
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("🔓 Desvincular Factura de Cotización")
        win.geometry("980x580")
        win.configure(bg="#f1f5f9")
        win.transient(self.root)
        win.grab_set()

        # Header
        hdr = tk.Frame(win, bg="#7c3aed", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  🔓  Desvincular Factura de Cotización",
                 font=("Arial", 11, "bold"), bg="#7c3aed", fg="white").pack(side="left", padx=12)
        tk.Label(hdr, text="Solo se deshace el vínculo — los datos del catálogo no se modifican",
                 font=("Arial", 8, "italic"), bg="#7c3aed", fg="#e9d5ff").pack(side="left", padx=6)

        # Búsqueda
        sf = tk.Frame(win, bg="#f1f5f9", pady=6)
        sf.pack(fill="x", padx=12)
        tk.Label(sf, text="🔍 Buscar:", font=("Arial", 9, "bold"),
                 bg="#f1f5f9", fg="#374151").pack(side="left")
        entry_bus = tk.Entry(sf, font=("Arial", 9), width=30)
        entry_bus.pack(side="left", padx=6)
        lbl_conteo = tk.Label(sf, text="", font=("Arial", 8),
                               bg="#f1f5f9", fg="#6b7280")
        lbl_conteo.pack(side="right")

        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x", padx=12)

        # Tree de vínculos existentes
        tree_f = tk.Frame(win, bg="#f1f5f9")
        tree_f.pack(fill="both", expand=True, padx=12, pady=6)
        tree_f.grid_rowconfigure(0, weight=1)
        tree_f.grid_columnconfigure(0, weight=1)

        cols = ("fac_id", "cot_id", "Serie-Folio", "UUID", "Fecha Fac",
                "Receptor", "Total", "Cotización", "Cliente Cot", "Estado Cot")
        widths = [0, 0, 90, 145, 80, 180, 80, 100, 150, 90]

        tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                             selectmode="browse", height=14)
        for col, w in zip(cols, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, minwidth=w if w > 0 else 1,
                        stretch=(w > 0))
        # Ocultar columnas de IDs
        tree.column("fac_id", width=0, minwidth=0, stretch=False)
        tree.column("cot_id", width=0, minwidth=0, stretch=False)

        sc_y = ttk.Scrollbar(tree_f, orient="vertical",   command=tree.yview)
        sc_x = ttk.Scrollbar(tree_f, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        tree.grid(row=0, column=0, sticky="nsew")
        sc_y.grid(row=0, column=1, sticky="ns")
        sc_x.grid(row=1, column=0, sticky="ew")

        _todos = []

        def _cargar(buscar=""):
            tree.delete(*tree.get_children())
            like = f"%{buscar}%"
            self.cursor.execute("""
                SELECT f.id, fc.cotizacion_id,
                       f.serie, f.folio_factura, f.uuid, f.fecha,
                       f.rfc_receptor, f.nombre_receptor, f.total,
                       c.folio AS cot_folio,
                       cl.nombre_comercial, c.estado
                FROM factura_cotizaciones fc
                JOIN facturas f   ON f.id  = fc.factura_id
                JOIN cotizaciones c  ON c.id  = fc.cotizacion_id
                JOIN clientes cl  ON cl.id = c.cliente_id
                WHERE (f.uuid            LIKE ? OR f.nombre_receptor LIKE ?
                    OR f.folio_factura   LIKE ? OR c.folio           LIKE ?
                    OR cl.nombre_comercial LIKE ?)
                ORDER BY f.fecha DESC, f.fecha_registro DESC
            """, (like, like, like, like, like))
            rows = self.cursor.fetchall()
            _todos.clear()
            _todos.extend(rows)
            for r in rows:
                (fid, cid, serie, folio_f, uuid, fecha,
                 rfc_rec, nombre_rec, total, cot_folio, cli_cot, estado_cot) = r
                serie_folio = f"{serie}-{folio_f}" if serie else (folio_f or "—")
                tree.insert("", "end", values=(
                    fid, cid,
                    serie_folio, (uuid or "")[:22] + "…" if uuid and len(uuid) > 22 else (uuid or "—"),
                    (fecha or "")[:10],
                    (nombre_rec or rfc_rec or "—")[:28],
                    f"${total:,.2f}" if total else "—",
                    cot_folio or "—",
                    (cli_cot or "—")[:22],
                    estado_cot or "—"
                ))
            n = len(rows)
            lbl_conteo.config(text=f"{n} vínculo{'s' if n!=1 else ''} activo{'s' if n!=1 else ''}")

        entry_bus.bind("<KeyRelease>", lambda e: _cargar(entry_bus.get().strip()))
        _cargar()

        # Pie con botón desvincular
        foot = tk.Frame(win, bg="#1e2d45", pady=8)
        foot.pack(fill="x", side="bottom")

        lbl_sel = tk.Label(foot,
                            text="Selecciona un vínculo de la lista y presiona Desvincular",
                            font=("Arial", 8), bg="#1e2d45", fg="#94a3b8")
        lbl_sel.pack(side="left", padx=12)

        def _desvincular():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Sin selección",
                    "Selecciona un vínculo de la lista.", parent=win)
                return
            vals = tree.item(sel[0])["values"]
            fac_id = int(vals[0])
            cot_id = int(vals[1])
            serie_folio = vals[2]
            cot_folio   = vals[7]
            cli_cot     = vals[8]

            if not messagebox.askyesno(
                "Confirmar desvinculación",
                f"¿Desvincular la factura  {serie_folio}\n"
                f"de la cotización  {cot_folio}  ({cli_cot})?\n\n"
                f"Los datos del catálogo no se modifican.\n"
                f"La cotización volverá a aparecer como pendiente de vincular.",
                parent=win):
                return

            try:
                # 1. Borrar de junction table
                self.cursor.execute(
                    "DELETE FROM factura_cotizaciones WHERE factura_id=? AND cotizacion_id=?",
                    (fac_id, cot_id))
                # 2. Limpiar columna legacy si aún apunta a esta cotización
                self.cursor.execute(
                    "UPDATE facturas SET cotizacion_id=NULL WHERE id=? AND cotizacion_id=?",
                    (fac_id, cot_id))
                # 3. Revertir etapa "Facturada" en seguimiento_etapas
                self.cursor.execute("""
                    UPDATE seguimiento_etapas
                    SET completada=0, referencia=NULL, notas='Desvinculado manualmente'
                    WHERE cotizacion_id=? AND etapa='Facturada'
                """, (cot_id,))
                # 4. Limpiar numero_factura en cotización
                self.cursor.execute("""
                    UPDATE cotizaciones
                    SET numero_factura=NULL, fecha_factura=NULL
                    WHERE id=?
                      AND numero_factura=(SELECT uuid FROM facturas WHERE id=?)
                """, (cot_id, fac_id))
                self.conn.commit()
                messagebox.showinfo("Desvinculado",
                    f"✅ Vínculo eliminado.\n\n"
                    f"Factura {serie_folio} ← desvinculada de → {cot_folio}\n"
                    f"La factura aparecerá nuevamente en 'Sin vincular'.",
                    parent=win)
                _cargar(entry_bus.get().strip())
                # Refrescar badge
                try:
                    self.sistema._actualizar_badge_vinculacion()
                except Exception:
                    pass

            except sqlite3.Error as e:
                self.conn.rollback()
                messagebox.showerror("Error", str(e), parent=win)

        tk.Button(foot, text="  🔓  Desvincular seleccionado  ",
                  font=("Arial", 10, "bold"), bg="#dc2626", fg="white",
                  cursor="hand2", padx=14, pady=6, relief="flat",
                  command=_desvincular).pack(side="right", padx=12)
        tk.Button(foot, text="Cerrar", font=("Arial", 9),
                  bg="#6b7280", fg="white", cursor="hand2",
                  padx=12, pady=6, relief="flat",
                  command=win.destroy).pack(side="right", padx=4)
        win.after(0, win.deiconify)

    def _tarjeta(self, parent, key, icono, titulo, desc, color, bg_card, items, win):
        card = tk.Frame(parent, bg=bg_card, highlightbackground=color, highlightthickness=2)
        card.pack(fill="x", padx=14, pady=6)

        ch = tk.Frame(card, bg=color, pady=5)
        ch.pack(fill="x")
        tk.Label(ch, text=f"  {icono}  {titulo}",
                 font=("Arial", 10, "bold"), bg=color, fg="white").pack(side="left", padx=8)
        n = len(items)
        bdg = f"{n} pendiente{'s' if n!=1 else ''}" if n > 0 else "Todo vinculado"
        tk.Label(ch, text=f"  {bdg}  ", font=("Arial", 8, "bold"),
                 bg="#dc2626" if n > 0 else "#16a34a", fg="white").pack(side="right", padx=8)

        tk.Label(card, text=f"  {desc}", font=("Arial", 8),
                 bg=bg_card, fg="#6b7280").pack(anchor="w", pady=(4, 0))

        if not items:
            tk.Label(card, text="  Sin pendientes en esta categoria.",
                     font=("Arial", 8, "italic"), bg=bg_card, fg="#9ca3af").pack(
                anchor="w", padx=10, pady=(2, 8))
            return

        resolver_fn = {
            "clientes":    self._resolver_cliente,
            "proveedores": self._resolver_proveedor,
            "productos":   self._resolver_producto,
            "cotizaciones":self._resolver_cotizacion,
        }[key]

        max_visible = 6
        altura_item = 34
        lista_outer = tk.Frame(card, bg=bg_card)
        lista_outer.pack(fill="x", padx=10, pady=6)

        altura_canvas = min(len(items), max_visible) * altura_item
        c_lista = tk.Canvas(lista_outer, bg=bg_card, height=altura_canvas, highlightthickness=0)
        sb_lista = ttk.Scrollbar(lista_outer, orient="vertical", command=c_lista.yview)
        c_lista.configure(yscrollcommand=sb_lista.set)
        if len(items) > max_visible:
            sb_lista.pack(side="right", fill="y")
        c_lista.pack(fill="x", expand=True)

        inner_lista = tk.Frame(c_lista, bg=bg_card)
        wid = c_lista.create_window((0, 0), window=inner_lista, anchor="nw")
        inner_lista.bind("<Configure>", lambda e, cv=c_lista: cv.configure(scrollregion=cv.bbox("all")))
        c_lista.bind("<Configure>", lambda e, cv=c_lista, w=wid: cv.itemconfig(w, width=e.width))

        for item in items:
            rf = tk.Frame(inner_lista, bg="white", highlightbackground="#e2e8f0", highlightthickness=1)
            rf.pack(fill="x", pady=2)
            txt = self._label_item(item, key)
            tk.Label(rf, text=txt, font=("Arial", 8), bg="white",
                     fg="#374151", anchor="w").pack(side="left", padx=8, pady=5)
            def _btn_cmd(i=item, fn=resolver_fn, wp=win):
                fn(i, wp)
            tk.Button(rf, text="🔗 Resolver", font=("Arial", 8, "bold"),
                      bg=color, fg="white", cursor="hand2", padx=8, pady=2, relief="flat",
                      command=_btn_cmd).pack(side="right", padx=6, pady=4)

    def _label_item(self, item, key):
        if key in ("clientes", "proveedores"):
            _, uuid, rfc, nombre = item
            return f"RFC: {rfc or '—'}   •   {(nombre or 'Sin nombre')[:48]}   •   UUID: {str(uuid)[:18]}…"
        elif key == "productos":
            _, uuid, no_id, desc, clave = item
            ident = no_id or (f"SAT:{clave}" if clave else "—")
            return f"Codigo: {ident}   •   {(desc or '')[:45]}   •   Clave SAT: {clave or '—'}"
        else:
            # cotizacion: (fid, uuid, total, rfc_contraparte, fecha, tipo_fac, nombre_contraparte)
            fid, uuid, total, rfc, fecha, tipo_fac, nombre = item
            icono = "🧾" if tipo_fac == "venta" else "🛒"
            total_txt = f"${total:,.2f}" if total else "—"
            return f"{icono} {tipo_fac.capitalize()}   •   {(nombre or rfc or '—')[:35]}   •   {total_txt}   •   {(fecha or '')[:10]}"

    # ── Resolvers ──────────────────────────────────────────────────────────────

    def _resolver_cliente(self, item, win_padre):
        fid, uuid, rfc, nombre = item
        self.cursor.execute("""
            SELECT uuid, rfc_receptor, nombre_receptor, uso_cfdi, total, fecha
            FROM facturas WHERE id=?
        """, (fid,))
        row = self.cursor.fetchone()
        if not row:
            return
        origen = {
            "tipo":      "cliente",
            "icono":     "👥",
            "color":     "#1e3a5f",
            "titulo":    "Cliente sin registrar",
            "subtitulo": f"RFC: {row[1]}  •  {row[2]}",
            "campos": [
                ("UUID",          row[0] or "—"),
                ("RFC Receptor",  row[1] or "—"),
                ("Nombre",        row[2] or "—"),
                ("Uso CFDI",      row[3] or "—"),
                ("Total factura", f"${row[4]:,.2f}" if row[4] else "—"),
                ("Fecha",         (row[5] or "")[:10]),
            ],
            "datos_registro": {
                "nombre_comercial": row[2] or "",
                "razon_social":     row[2] or "",
                "rfc":              row[1] or "",
                "uso_cfdi":         row[3] or "",
                "tipo":             "Empresa",
            },
            "factura_id": fid,
        }
        DialogoVinculacion(self, origen, win_padre).abrir()

    def _resolver_proveedor(self, item, win_padre):
        fid, uuid, rfc, nombre = item
        self.cursor.execute("""
            SELECT rfc_emisor, nombre_emisor, fecha, uuid, total, metodo_pago
            FROM facturas WHERE id=?
        """, (fid,))
        row = self.cursor.fetchone()
        if not row:
            return
        origen = {
            "tipo":      "proveedor",
            "icono":     "🏭",
            "color":     "#92400e",
            "titulo":    "Proveedor sin registrar",
            "subtitulo": f"RFC: {row[0]}  •  {row[1]}",
            "campos": [
                ("UUID",          row[3] or "—"),
                ("RFC Emisor",    row[0] or "—"),
                ("Nombre Emisor", row[1] or "—"),
                ("Fecha",         (row[2] or "")[:10]),
                ("Total factura", f"${row[4]:,.2f}" if row[4] else "—"),
                ("Metodo Pago",   row[5] or "—"),
            ],
            "datos_registro": {
                "nombre":         row[1] or "",
                "razon_social":   row[1] or "",
                "rfc":            row[0] or "",
                "regimen_fiscal": "",
            },
            "factura_id": fid,
        }
        DialogoVinculacion(self, origen, win_padre).abrir()

    def _resolver_producto(self, item, win_padre):
        fid, uuid, no_id, desc, clave_sat_xml = item
        # Buscar concepto por no_identificacion si existe, si no por clave_prod_serv
        if no_id:
            self.cursor.execute("""
                SELECT fc.cantidad, fc.valor_unitario, fc.importe,
                       fc.clave_unidad, fc.unidad, fc.clave_prod_serv
                FROM factura_conceptos fc
                WHERE fc.factura_id=? AND UPPER(fc.no_identificacion)=UPPER(?) LIMIT 1
            """, (fid, no_id))
        else:
            self.cursor.execute("""
                SELECT fc.cantidad, fc.valor_unitario, fc.importe,
                       fc.clave_unidad, fc.unidad, fc.clave_prod_serv
                FROM factura_conceptos fc
                WHERE fc.factura_id=? AND fc.clave_prod_serv=? LIMIT 1
            """, (fid, clave_sat_xml))
        cr = self.cursor.fetchone()
        # El identificador principal: no_id si existe, si no la clave SAT
        ident_display = no_id or f"SAT:{clave_sat_xml}" or "—"
        origen = {
            "tipo":      "producto",
            "icono":     "📦",
            "color":     "#065f46",
            "titulo":    "Producto sin vincular",
            "subtitulo": f"Código: {ident_display}  •  {(desc or '')[:40]}",
            "campos": [
                ("No. Identificacion", no_id or "—"),
                ("Clave SAT (XML)",    clave_sat_xml or "—"),
                ("Descripcion",        (desc or "—")[:60]),
                ("Cantidad",           f"{cr[0]:g}" if cr else "—"),
                ("Valor Unitario",     f"${cr[1]:,.2f}" if cr else "—"),
                ("Importe Total",      f"${cr[2]:,.2f}" if cr else "—"),
                ("Clave Unidad",       cr[3] if cr else "—"),
                ("Unidad",             cr[4] if cr else "—"),
            ],
            "datos_registro": {
                "codigo":           no_id or "",
                "nombre":           desc or "",
                "clave_sat":        clave_sat_xml or "",
                "clave_unidad_sat": cr[3] if cr else "",
                "precio_venta":     cr[1] if cr else 0,
            },
            "factura_id": fid,
            "no_id":      no_id,
            "clave_prod_serv": clave_sat_xml,
        }
        DialogoVinculacion(self, origen, win_padre).abrir()

    def _resolver_cotizacion(self, item, win_padre):
        # item = (fid, uuid, total, rfc_contraparte, fecha, tipo_fac, nombre_contraparte)
        fid, uuid, total, rfc_contraparte, fecha, tipo_fac, nombre_contraparte = item

        self.cursor.execute("""
            SELECT uuid, rfc_emisor, nombre_emisor, rfc_receptor, nombre_receptor,
                   total, subtotal, iva, fecha, serie, folio_factura,
                   metodo_pago, forma_pago, tipo
            FROM facturas WHERE id=?
        """, (fid,))
        row = self.cursor.fetchone()
        if not row:
            return
        (uuid_, rfc_em, nom_em, rfc_rec, nom_rec,
         total_, sub_, iva_, fecha_, serie_, folio_,
         met_pago, forma_pago, tipo_cfdi) = row

        sf = f"{serie_}-{folio_}" if serie_ else (folio_ or "—")

        es_compra = (tipo_fac == 'compra')

        if es_compra:
            # Factura de COMPRA: proveedor → CLF
            # Opciones: (a) abrir _confirmar_stock_compra para registrarla como compra
            #            (b) vincular a una cotización si fue compra exclusiva para ella
            self._resolver_compra_xml(fid, row, sf, win_padre)
        else:
            # Factura de VENTA: CLF → cliente
            origen = {
                "tipo":      "cotizacion",
                "icono":     "🧾",
                "color":     "#0e7490",
                "titulo":    "Factura de VENTA sin cotización vinculada",
                "subtitulo": f"Serie-Folio: {sf}  •  ${total_:,.2f}  •  {nom_rec or rfc_rec}",
                "campos": [
                    ("Tipo",        "🧾 Factura de Venta (tú eres el emisor)"),
                    ("UUID",        uuid_ or "—"),
                    ("Serie-Folio", sf),
                    ("RFC Receptor", rfc_rec or "—"),
                    ("Cliente",     nom_rec or "—"),
                    ("Total",       f"${total_:,.2f}" if total_ else "—"),
                    ("Subtotal",    f"${sub_:,.2f}"   if sub_   else "—"),
                    ("IVA",         f"${iva_:,.2f}"   if iva_   else "—"),
                    ("Fecha",       (fecha_ or "")[:10]),
                    ("Método Pago", met_pago or "—"),
                ],
                "factura_id": fid,
            }
            DialogoVinculacion(self, origen, win_padre).abrir()

    def _resolver_compra_xml(self, fid, row, sf, win_padre):
        """
        Diálogo para facturas de COMPRA (proveedor → CLF) sin registro.
        Ofrece dos acciones:
          A) Registrar como compra para STOCK GENERAL
          B) Registrar como compra vinculada a una COTIZACIÓN específica
        """
        (uuid_, rfc_em, nom_em, rfc_rec, nom_rec,
         total_, sub_, iva_, fecha_, serie_, folio_,
         met_pago, forma_pago, tipo_cfdi) = row

        # Cargar conceptos del XML para mostrar detalle
        self.cursor.execute("""
            SELECT fc.no_identificacion, fc.descripcion, fc.cantidad,
                   fc.valor_unitario, fc.importe, fc.clave_prod_serv,
                   p.nombre AS nombre_catalogo, p.codigo
            FROM factura_conceptos fc
            LEFT JOIN productos p ON (
                (fc.no_identificacion IS NOT NULL AND fc.no_identificacion != ''
                 AND UPPER(p.codigo) = UPPER(fc.no_identificacion))
                OR
                (fc.clave_prod_serv IS NOT NULL AND fc.clave_prod_serv != ''
                 AND p.clave_sat IS NOT NULL
                 AND UPPER(p.clave_sat) = UPPER(fc.clave_prod_serv))
            )
            WHERE fc.factura_id = ?
            ORDER BY fc.id
        """, (fid,))
        conceptos = self.cursor.fetchall()

        win = tk.Toplevel(self._win_panel)
        win.title(f"🛒 Factura de Compra — {sf}")
        win.geometry("980x720")
        win.configure(bg="#f1f5f9")
        win.transient(self._win_panel)
        win.grab_set()

        # ── Cabecera ──────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg="#92400e", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="🛒  Factura de Compra sin registro",
                 font=("Arial", 11, "bold"), bg="#92400e", fg="white").pack(side="left", padx=12)
        tk.Label(hdr, text=f"{sf}  ·  {nom_em or rfc_em}  ·  ${total_:,.2f}",
                 font=("Arial", 9), bg="#92400e", fg="#fef3c7").pack(side="left", padx=6)

        # ── Info factura (fila compacta) ───────────────────────────────────────
        info_f = tk.Frame(win, bg="white", pady=6, padx=16)
        info_f.pack(fill="x", padx=12, pady=(8, 0))
        campos_inf = [
            ("Proveedor (Emisor):", nom_em or "—"), ("RFC Emisor:", rfc_em or "—"),
            ("Fecha:", (fecha_ or "")[:10]),         ("Total:", f"${total_:,.2f}"),
            ("IVA:", f"${iva_:,.2f}"),               ("Método Pago:", met_pago or "—"),
        ]
        for i, (lbl, val) in enumerate(campos_inf):
            col = (i % 2) * 2
            row_n = i // 2
            tk.Label(info_f, text=lbl, font=("Arial", 8, "bold"),
                     bg="white", fg="#6b7280").grid(row=row_n, column=col, sticky="w", padx=(0, 4), pady=1)
            tk.Label(info_f, text=val, font=("Arial", 8),
                     bg="white", fg="#1e2d45").grid(row=row_n, column=col+1, sticky="w", padx=(0, 20), pady=1)

        # ── Productos / Conceptos del XML ─────────────────────────────────────
        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x", padx=12, pady=(8, 0))

        sec_prod = tk.Frame(win, bg="#f1f5f9")
        sec_prod.pack(fill="x", padx=12, pady=(4, 0))

        hdr_prod = tk.Frame(sec_prod, bg="#f1f5f9")
        hdr_prod.pack(fill="x", pady=(0, 3))
        tk.Label(hdr_prod, text="📦  Productos en esta factura",
                 font=("Arial", 9, "bold"), bg="#f1f5f9", fg="#374151").pack(side="left")
        n_vinc_prod  = sum(1 for c in conceptos if c[6])
        n_total_prod = len(conceptos)
        color_badge = ("#d1fae5" if n_vinc_prod == n_total_prod else
                       "#fef3c7" if n_vinc_prod > 0 else "#fee2e2")
        fg_badge    = ("#065f46" if n_vinc_prod == n_total_prod else
                       "#92400e" if n_vinc_prod > 0 else "#991b1b")
        tk.Label(hdr_prod,
                 text=f"  {n_vinc_prod}/{n_total_prod} vinculados al catálogo  ",
                 font=("Arial", 8, "bold"), bg=color_badge, fg=fg_badge).pack(side="left", padx=8)
        if n_vinc_prod < n_total_prod:
            tk.Label(hdr_prod,
                     text="⚠ Los productos en amarillo no están en catálogo — ve al Centro de Vinculación → Productos.",
                     font=("Arial", 8, "italic"), bg="#f1f5f9", fg="#92400e").pack(side="left", padx=4)

        tree_prod_f = tk.Frame(sec_prod, bg="#f1f5f9")
        tree_prod_f.pack(fill="x")
        tree_prod_f.grid_columnconfigure(0, weight=1)

        cols_p  = ("Código / Clave SAT", "Descripción XML", "Cant.", "P.Unit.", "Importe", "En catálogo")
        widths_p = [120, 255, 55, 88, 90, 235]
        tree_p = ttk.Treeview(tree_prod_f, columns=cols_p, show="headings",
                               height=min(n_total_prod, 5), selectmode="none")
        for col, w in zip(cols_p, widths_p):
            tree_p.heading(col, text=col)
            tree_p.column(col, width=w, minwidth=40)
        tree_p.tag_configure("vinculado",    background="#d1fae5", foreground="#065f46")
        tree_p.tag_configure("sin_vincular", background="#fef3c7", foreground="#92400e")

        for c in conceptos:
            no_id, desc, cant, vu, importe, clave_sat, nom_cat, cod_cat = c
            ident  = no_id or (f"SAT:{clave_sat}" if clave_sat else "—")
            en_cat = f"✅ {cod_cat} — {nom_cat}" if nom_cat else "⚠️ Sin vincular al catálogo"
            tag    = "vinculado" if nom_cat else "sin_vincular"
            tree_p.insert("", "end", tags=(tag,), values=(
                ident, (desc or "")[:50],
                f"{cant:g}", f"${vu:,.2f}", f"${importe:,.2f}", en_cat))

        sc_p = ttk.Scrollbar(tree_prod_f, orient="vertical", command=tree_p.yview)
        tree_p.configure(yscrollcommand=sc_p.set)
        tree_p.grid(row=0, column=0, sticky="nsew")
        sc_p.grid(row=0, column=1, sticky="ns")

        # ── Pregunta principal ────────────────────────────────────────────────
        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x", padx=12, pady=(8, 4))
        tk.Label(win,
                 text="¿Esta compra fue para stock general o para satisfacer una cotización específica?",
                 font=("Arial", 10, "bold"), bg="#f1f5f9", fg="#374151").pack(padx=16, anchor="w")
        tk.Label(win,
                 text="Selecciona una cotización si los productos se compraron exclusivamente para ella. "
                      "De lo contrario, registra como compra para stock.",
                 font=("Arial", 8), bg="#f1f5f9", fg="#6b7280",
                 wraplength=900, justify="left").pack(padx=16, anchor="w", pady=(1, 6))

        # ── Selector de cotización + detalle lado a lado ──────────────────────
        body = tk.Frame(win, bg="#f1f5f9")
        body.pack(fill="both", expand=True, padx=12)
        body.grid_columnconfigure(0, weight=2)   # lista cotizaciones
        body.grid_columnconfigure(1, weight=3)   # detalle cotización
        body.grid_rowconfigure(1, weight=1)

        # Búsqueda encima de la lista
        ff = tk.Frame(body, bg="#f1f5f9")
        ff.grid(row=0, column=0, sticky="ew", pady=(0, 4), padx=(0, 6))
        tk.Label(ff, text="Buscar cotización (opcional):",
                 font=("Arial", 9), bg="#f1f5f9").pack(side="left", padx=(0, 4))
        entry_bus = tk.Entry(ff, font=("Arial", 9), width=22)
        entry_bus.pack(side="left")

        lbl_sel_cot = tk.Label(body,
                                text="← Selecciona una cotización para ver su detalle",
                                font=("Arial", 8, "italic"), bg="#f1f5f9", fg="#6b7280")
        lbl_sel_cot.grid(row=0, column=1, sticky="w", padx=(8, 0))

        # ── Lista de cotizaciones (izquierda) ──────────────────────────────
        ft = tk.Frame(body, bg="#f1f5f9")
        ft.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
        ft.grid_rowconfigure(0, weight=1)
        ft.grid_columnconfigure(0, weight=1)

        cols_c = ("ID", "Folio", "Fecha", "Cliente", "Total", "Estado")
        tree_c = ttk.Treeview(ft, columns=cols_c, show="headings",
                               selectmode="browse", height=10)
        for col, w in zip(cols_c, [0, 110, 80, 170, 85, 105]):
            tree_c.heading(col, text=col)
            tree_c.column(col, width=w)
        tree_c.column("ID", stretch=False)
        sc = ttk.Scrollbar(ft, orient="vertical", command=tree_c.yview)
        tree_c.configure(yscrollcommand=sc.set)
        tree_c.grid(row=0, column=0, sticky="nsew")
        sc.grid(row=0, column=1, sticky="ns")

        # ── Panel de detalle cotización (derecha) ──────────────────────────
        det_frame = tk.Frame(body, bg="white",
                             highlightbackground="#e2e8f0", highlightthickness=1)
        det_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 0))

        def _limpiar_detalle():
            for w in det_frame.winfo_children():
                w.destroy()
            tk.Label(det_frame,
                     text="Selecciona una cotización de la lista\npara ver sus productos aquí.",
                     font=("Arial", 9, "italic"), bg="white", fg="#9ca3af",
                     justify="center").pack(expand=True)

        def _mostrar_detalle_cot(cot_id, folio, cliente, estado, fecha, total, entregado):
            for w in det_frame.winfo_children():
                w.destroy()

            estado_colors = {
                "Pendiente":"#f39c12","Programada":"#3498db","Entregada":"#27ae60",
                "Facturada":"#9b59b6","Pagada":"#16a085","Cancelada":"#e74c3c"
            }
            ec = estado_colors.get(estado, "#64748b")

            # Header
            hc = tk.Frame(det_frame, bg=ec, pady=5, padx=10)
            hc.pack(fill="x")
            tk.Label(hc, text=folio, font=("Arial", 10, "bold"),
                     bg=ec, fg="white").pack(side="left")
            tk.Label(hc, text=estado, font=("Arial", 8, "bold"),
                     bg="white", fg=ec, padx=6, pady=2).pack(side="right")

            # Meta
            meta = tk.Frame(det_frame, bg="#f8fafc", pady=4, padx=8)
            meta.pack(fill="x")
            for txt in [f"👤 {cliente}", f"📅 {(fecha or '')[:10]}"]:
                tk.Label(meta, text=txt, font=("Arial", 8),
                         bg="#f8fafc", fg="#374151").pack(side="left", padx=(0,14))

            # Tabla productos
            tk.Frame(det_frame, bg="#e2e8f0", height=1).pack(fill="x")
            tf = tk.Frame(det_frame, bg="white")
            tf.pack(fill="both", expand=True)
            tf.grid_columnconfigure(0, weight=1)
            tf.grid_rowconfigure(0, weight=1)

            self.cursor.execute("""
                SELECT p.codigo, p.nombre, cd.cantidad,
                       cd.precio_unitario, cd.subtotal, cd.tiene_stock
                FROM cotizacion_detalle cd
                JOIN productos p ON p.id = cd.producto_id
                WHERE cd.cotizacion_id = ?
            """, (cot_id,))
            prods = self.cursor.fetchall()

            cols_p = ("Código", "Producto", "Cant.", "P.Unit.", "Subtotal", "Stock")
            w_p    = [65, 175, 45, 75, 78, 45]
            tree_p = ttk.Treeview(tf, columns=cols_p, show="headings",
                                   height=min(len(prods), 8), selectmode="none")
            for col, w in zip(cols_p, w_p):
                tree_p.heading(col, text=col)
                tree_p.column(col, width=w, minwidth=30)
            tree_p.tag_configure("nostock", background="#fef3c7")
            sc_p = ttk.Scrollbar(tf, orient="vertical", command=tree_p.yview)
            tree_p.configure(yscrollcommand=sc_p.set)
            for p in prods:
                cod, nom, cant, pu, sub_, ts = p
                tag = "nostock" if not ts else ""
                tree_p.insert("", "end", tags=(tag,), values=(
                    cod, nom, f"{cant:g}", f"${pu:,.0f}", f"${sub_:,.0f}",
                    "✓" if ts else "✗"))
            tree_p.grid(row=0, column=0, sticky="nsew")
            sc_p.grid(row=0, column=1, sticky="ns")

            # Footer totales
            tf2 = tk.Frame(det_frame, bg="#1e2d45", pady=4, padx=10)
            tf2.pack(fill="x", side="bottom")
            tk.Label(tf2, text=f"Total: ${total:,.2f}",
                     font=("Arial", 9, "bold"), bg="#1e2d45", fg="white").pack(side="right")
            tk.Label(tf2, text=f"Entregado: ${entregado:,.2f}",
                     font=("Arial", 8), bg="#1e2d45", fg="#94a3b8").pack(side="right", padx=12)
            tk.Label(tf2, text=f"{len(prods)} producto(s)",
                     font=("Arial", 8), bg="#1e2d45", fg="#94a3b8").pack(side="left")

        _limpiar_detalle()

        _sel_cot = {"id": None, "folio": None}

        def _cargar_cots(buscar=""):
            tree_c.delete(*tree_c.get_children())
            like = f"%{buscar}%"
            self.cursor.execute("""
                SELECT c.id, c.folio, c.fecha, cl.nombre_comercial, c.total, c.estado,
                       c.monto_entregado
                FROM cotizaciones c
                JOIN clientes cl ON cl.id = c.cliente_id
                WHERE c.estado NOT IN ('Cancelada', 'Pagada')
                  AND (c.folio LIKE ? OR cl.nombre_comercial LIKE ?)
                ORDER BY c.folio DESC
            """, (like, like))
            for r in self.cursor.fetchall():
                cid, folio, fec, cli, tot, est, entregado = r
                tree_c.insert("", "end", iid=str(cid),
                              values=(cid, folio, (fec or "")[:10], cli, f"${tot:,.2f}", est))

        def _on_sel(event):
            sel = tree_c.selection()
            if not sel:
                return
            vals = tree_c.item(sel[0])["values"]
            cot_id   = int(vals[0])
            folio_s  = vals[1]
            cliente_s = vals[3]
            estado_s = vals[5]

            # Obtener datos completos para el detalle
            self.cursor.execute("""
                SELECT c.fecha, c.total, c.monto_entregado
                FROM cotizaciones c WHERE c.id=?
            """, (cot_id,))
            row_c = self.cursor.fetchone()
            fecha_c, total_c, entregado_c = row_c if row_c else ("", 0, 0)

            _sel_cot["id"]    = cot_id
            _sel_cot["folio"] = folio_s
            lbl_sel_cot.config(
                text=f"✅ {folio_s} — {cliente_s}",
                fg="#0f7b5e", font=("Arial", 8, "bold"))
            _mostrar_detalle_cot(cot_id, folio_s, cliente_s, estado_s,
                                  fecha_c, total_c or 0, entregado_c or 0)

        tree_c.bind("<<TreeviewSelect>>", _on_sel)
        entry_bus.bind("<KeyRelease>", lambda e: _cargar_cots(entry_bus.get().strip()))
        _cargar_cots()

        # ═══════════════════════════════════════════════════════════════════
        # ── PANEL DE ASIGNACIÓN DE COSTOS POR PRODUCTO ─────────────────────
        # ═══════════════════════════════════════════════════════════════════

        tk.Frame(win, bg="#e2e8f0", height=1).pack(fill="x", padx=12, pady=(8, 0))

        asig_hdr = tk.Frame(win, bg="#1e3a5f", pady=6)
        asig_hdr.pack(fill="x")
        tk.Label(asig_hdr, text="📋  Asignación de costos por producto",
                 font=("Arial", 10, "bold"), bg="#1e3a5f", fg="white").pack(side="left", padx=12)
        tk.Label(asig_hdr,
                 text="Asigna cada producto a una cotización o deja en Stock general",
                 font=("Arial", 8), bg="#1e3a5f", fg="#93c5fd").pack(side="left")

        # Canvas scrollable para las filas de asignación
        asig_outer = tk.Frame(win, bg="#f8fafc")
        asig_outer.pack(fill="both", expand=True, padx=12, pady=4)
        asig_outer.grid_rowconfigure(0, weight=1)
        asig_outer.grid_columnconfigure(0, weight=1)

        asig_canvas = tk.Canvas(asig_outer, bg="#f8fafc", highlightthickness=0, height=200)
        asig_sc = ttk.Scrollbar(asig_outer, orient="vertical", command=asig_canvas.yview)
        asig_canvas.configure(yscrollcommand=asig_sc.set)
        asig_canvas.grid(row=0, column=0, sticky="nsew")
        asig_sc.grid(row=0, column=1, sticky="ns")

        asig_inner = tk.Frame(asig_canvas, bg="#f8fafc")
        asig_wid = asig_canvas.create_window((0, 0), window=asig_inner, anchor="nw")
        asig_inner.bind("<Configure>",
            lambda e: asig_canvas.configure(scrollregion=asig_canvas.bbox("all")))
        asig_canvas.bind("<Configure>",
            lambda e: asig_canvas.itemconfig(asig_wid, width=e.width))

        # Cargar lista de cotizaciones (todas excepto canceladas)
        self.cursor.execute("""
            SELECT c.id, c.folio, cl.nombre_comercial, c.estado
            FROM cotizaciones c
            JOIN clientes cl ON cl.id = c.cliente_id
            WHERE c.estado NOT IN ('Cancelada')
            ORDER BY c.folio DESC
        """)
        cots_lista = self.cursor.fetchall()
        cot_opciones = ["— Stock general —"] + [
            f"{row[1]} | {row[2][:20]} | {row[3]}" for row in cots_lista
        ]
        cot_ids_map = {cot_opciones[i+1]: cots_lista[i][0] for i in range(len(cots_lista))}

        # asig_data: lista de dicts por concepto con sus filas de asignación
        # asig_data[i] = {'prod_id': X, 'nombre': Y, 'cant_total': Z,
        #                 'costo_unit': W, 'asignaciones': [{'cot_id': ..., 'cant': ..., 'var': ..., 'combo': ...}]}
        asig_data = []

        def _rebuild_asig_ui():
            for w in asig_inner.winfo_children():
                w.destroy()

            # Header de columnas
            hdr_cols = ["Producto (XML)", "Cant. total", "Costo u.", "", "Cotización", "Cant.", "Subtotal", ""]
            hdr_ws   = [220, 70, 80, 30, 220, 65, 80, 50]
            for ci, (ch, cw) in enumerate(zip(hdr_cols, hdr_ws)):
                tk.Label(asig_inner, text=ch, font=("Arial", 8, "bold"),
                         bg="#e2e8f0", fg="#374151", width=cw//7,
                         anchor="w", padx=4, pady=3
                         ).grid(row=0, column=ci, sticky="ew", padx=1, pady=(0,2))

            row_idx = 1
            for di, data in enumerate(asig_data):
                cant_asig = sum(float(a['var'].get() or 0) for a in data['asignaciones'])
                cant_libre = data['cant_total'] - cant_asig
                bg_prod = "#f0fdf4" if abs(cant_libre) < 0.001 else "#fff7ed"

                # Fila de producto (nombre + totales)
                pf = tk.Frame(asig_inner, bg=bg_prod)
                pf.grid(row=row_idx, column=0, columnspan=8, sticky="ew", pady=(4,0))
                estado_txt = "✅" if abs(cant_libre) < 0.001 else f"⚠ {cant_libre:g} sin asignar"
                estado_col = "#16a34a" if abs(cant_libre) < 0.001 else "#d97706"
                tk.Label(pf, text=f"  {data['nombre'][:35]}",
                         font=("Arial", 8, "bold"), bg=bg_prod, fg="#1e2d45",
                         anchor="w").pack(side="left")
                tk.Label(pf, text=f"  {data['cant_total']:g} pzas × ${data['costo_unit']:,.2f}",
                         font=("Arial", 8), bg=bg_prod, fg="#6b7280").pack(side="left", padx=8)
                tk.Label(pf, text=estado_txt, font=("Arial", 8, "bold"),
                         bg=bg_prod, fg=estado_col).pack(side="right", padx=8)
                row_idx += 1

                # Filas de asignación existentes
                for ai, asig in enumerate(data['asignaciones']):
                    af = tk.Frame(asig_inner, bg="#ffffff",
                                  highlightbackground="#e2e8f0", highlightthickness=1)
                    af.grid(row=row_idx, column=0, columnspan=8, sticky="ew", padx=16, pady=1)

                    tk.Label(af, text="", width=30, bg="#ffffff").pack(side="left")  # indent

                    combo = ttk.Combobox(af, values=cot_opciones, state="readonly",
                                         font=("Arial", 8), width=32)
                    combo.set(asig.get('combo_val', cot_opciones[0]))
                    combo.pack(side="left", padx=4, pady=3)
                    asig['combo'] = combo

                    tk.Label(af, text="Cant:", font=("Arial", 8), bg="#ffffff",
                             fg="#6b7280").pack(side="left")
                    var = asig['var']
                    entry_c = tk.Entry(af, textvariable=var, width=7,
                                       font=("Arial", 8), relief="solid", bd=1)
                    entry_c.pack(side="left", padx=(2, 6), pady=3)

                    def _upd(e=None, _di=di, _ai=ai):
                        asig_data[_di]['asignaciones'][_ai]['combo_val'] =                             asig_data[_di]['asignaciones'][_ai]['combo'].get()
                        _rebuild_asig_ui()

                    combo.bind("<<ComboboxSelected>>", _upd)
                    var.trace_add("write", lambda *a, _di=di, _ai=ai: _rebuild_asig_ui())

                    # Subtotal
                    try:
                        cant_a = float(var.get() or 0)
                    except Exception:
                        cant_a = 0
                    sub = cant_a * data['costo_unit']
                    tk.Label(af, text=f"${sub:,.2f}", font=("Arial", 8),
                             bg="#ffffff", fg="#065f46", width=9).pack(side="left")

                    # Botón quitar fila
                    def _del_row(_di=di, _ai=ai):
                        asig_data[_di]['asignaciones'].pop(_ai)
                        _rebuild_asig_ui()
                    tk.Button(af, text="✕", font=("Arial", 8), bg="#ffffff",
                              fg="#dc2626", relief="flat", cursor="hand2",
                              command=_del_row).pack(side="left", padx=4)

                    row_idx += 1

                # Botón agregar fila
                add_f = tk.Frame(asig_inner, bg="#f8fafc")
                add_f.grid(row=row_idx, column=0, columnspan=8, sticky="w", padx=16)
                def _add_row(_di=di):
                    libre = asig_data[_di]['cant_total'] - sum(
                        float(a['var'].get() or 0)
                        for a in asig_data[_di]['asignaciones'])
                    asig_data[_di]['asignaciones'].append({
                        'var': tk.StringVar(value=f"{max(0, libre):g}"),
                        'combo_val': cot_opciones[0],
                        'combo': None,
                    })
                    _rebuild_asig_ui()
                tk.Button(add_f, text="＋ Agregar asignación",
                          font=("Arial", 7), bg="#f8fafc", fg="#1a4b8c",
                          relief="flat", cursor="hand2",
                          command=_add_row).pack(side="left", pady=2)
                row_idx += 1

        # Inicializar asig_data desde conceptos vinculados al catálogo
        for c in conceptos:
            no_id, desc, cant, vu, importe, clave_sat_c, nom_cat, cod_cat = c
            prod_id = None
            if cod_cat:
                self.cursor.execute(
                    "SELECT id FROM productos WHERE UPPER(codigo)=UPPER(?) LIMIT 1",
                    (cod_cat,))
                r = self.cursor.fetchone()
                if r: prod_id = r[0]
            if not prod_id and clave_sat_c:
                self.cursor.execute(
                    "SELECT id FROM productos WHERE UPPER(clave_sat)=UPPER(?) LIMIT 1",
                    (clave_sat_c,))
                r = self.cursor.fetchone()
                if r: prod_id = r[0]

            nombre_display = nom_cat or desc or no_id or "—"
            asig_data.append({
                'prod_id':     prod_id,
                'no_id':       no_id,
                'clave_sat':   clave_sat_c,
                'nombre':      nombre_display,
                'cant_total':  float(cant or 0),
                'costo_unit':  float(vu or 0),
                'asignaciones': [{
                    'var':       tk.StringVar(value=f"{float(cant or 0):g}"),
                    'combo_val': cot_opciones[0],
                    'combo':     None,
                }],
            })

        _rebuild_asig_ui()

        # ── Pie ───────────────────────────────────────────────────────────────
        foot = tk.Frame(win, bg="#1e2d45", pady=8)
        foot.pack(fill="x", side="bottom")

        def _registrar():
            """Registra la compra con asignación granular de costos."""
            from datetime import datetime as _dt

            # Validar asignaciones — verificar sobreasignación
            errores = []
            for data in asig_data:
                cant_asig = sum(float(a['var'].get() or 0)
                                for a in data['asignaciones'])
                if cant_asig > data['cant_total'] + 0.001:
                    errores.append(
                        f"• {data['nombre'][:30]}: asignado {cant_asig:g} > disponible {data['cant_total']:g}")
            if errores:
                messagebox.showerror("Sobreasignación",
                    "Hay productos con más cantidad asignada que disponible:\n\n" +
                    "\n".join(errores), parent=win)
                return

            # Verificar si hay cantidades sin asignar → pedir confirmación
            sin_asignar = []
            for data in asig_data:
                cant_asig = sum(float(a['var'].get() or 0)
                                for a in data['asignaciones'])
                libre = data['cant_total'] - cant_asig
                if libre > 0.001:
                    sin_asignar.append((data, libre))

            if sin_asignar:
                msgs = [f"• {d['nombre'][:30]}: {lib:g} pzas" for d, lib in sin_asignar]
                resp = messagebox.askyesno(
                    "Cantidades sin asignar",
                    "Los siguientes productos tienen cantidades sin asignar:\n\n" +
                    "\n".join(msgs) +
                    "\n\n¿Asignar automáticamente a Stock general?",
                    parent=win)
                if resp:
                    # Añadir fila de stock general con la cantidad libre
                    for data, libre in sin_asignar:
                        data['asignaciones'].append({
                            'var': tk.StringVar(value=f"{libre:g}"),
                            'combo_val': cot_opciones[0],
                            'combo': None,
                        })
                else:
                    return  # usuario quiere asignar manualmente

            # Buscar proveedor
            self.cursor.execute(
                "SELECT id FROM proveedores WHERE UPPER(rfc)=UPPER(?) LIMIT 1",
                (rfc_em or "",))
            prov_row = self.cursor.fetchone()
            prov_id  = prov_row[0] if prov_row else None

            # Generar folio (usa MAX para evitar duplicados si hay registros eliminados)
            año = (fecha_ or _dt.now().strftime("%Y-%m-%d"))[:4]
            self.cursor.execute(
                "SELECT MAX(CAST(SPLIT_PART(folio, '-', 3) AS INTEGER)) FROM compras "
                "WHERE folio LIKE ?", (f"COMP-{año}-%",))
            max_num = self.cursor.fetchone()[0] or 0
            folio_compra = f"COMP-{año}-{max_num+1:04d}"

            try:
                # Insertar compra principal
                self.cursor.execute("""
                    INSERT INTO compras
                    (folio, proveedor_id, fecha_compra, subtotal, iva, total,
                     notas, ticket_referencia, factura_xml_id)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (folio_compra, prov_id,
                      (fecha_ or _dt.now().strftime("%Y-%m-%d"))[:10],
                      sub_ or 0, iva_ or 0, total_ or 0,
                      f"Importado desde XML {sf}", sf, fid))
                compra_id = self.cursor.lastrowid

                n_stock = 0
                n_cot   = 0

                for data in asig_data:
                    prod_id = data['prod_id']

                    # Resolver prod_id si no lo teníamos
                    if not prod_id:
                        if data.get('no_id'):
                            self.cursor.execute(
                                "SELECT id FROM productos WHERE UPPER(codigo)=UPPER(?) LIMIT 1",
                                (data['no_id'],))
                            r = self.cursor.fetchone()
                            if r: prod_id = r[0]
                        if not prod_id and data.get('clave_sat'):
                            self.cursor.execute(
                                "SELECT id FROM productos WHERE UPPER(clave_sat)=UPPER(?) LIMIT 1",
                                (data['clave_sat'],))
                            r = self.cursor.fetchone()
                            if r: prod_id = r[0]

                    cant_total = data['cant_total']
                    costo_unit = data['costo_unit']

                    # Insertar compra_detalle (1 por producto, cantidad total)
                    self.cursor.execute("""
                        INSERT INTO compra_detalle
                        (compra_id, producto_id, cantidad, costo_unitario, costo_total)
                        VALUES (?,?,?,?,?)
                    """, (compra_id, prod_id, cant_total, costo_unit,
                          cant_total * costo_unit))
                    detalle_id = self.cursor.lastrowid

                    # Actualizar stock (todo sube porque pasa por bodega)
                    if prod_id:
                        self.cursor.execute(
                            "SELECT stock_actual FROM productos WHERE id=?", (prod_id,))
                        stock_antes = (self.cursor.fetchone() or (0,))[0] or 0
                        self.cursor.execute(
                            "UPDATE productos SET stock_actual = stock_actual + ? WHERE id=?",
                            (cant_total, prod_id))
                        self.cursor.execute("""
                            INSERT INTO movimientos_stock
                            (producto_id, tipo, motivo, cantidad,
                             stock_antes, stock_despues, referencia, notas)
                            VALUES (?, 'entrada', 'Compra XML', ?, ?, ?, ?, ?)
                        """, (prod_id, cant_total, stock_antes,
                              stock_antes + cant_total, folio_compra,
                              f"XML {sf} — {nom_em or rfc_em or ''}"))

                    # Insertar asignaciones de costo
                    for asig in data['asignaciones']:
                        cant_a = float(asig['var'].get() or 0)
                        if cant_a <= 0:
                            continue
                        combo_val = asig.get('combo_val') or (
                            asig['combo'].get() if asig.get('combo') else cot_opciones[0])
                        cot_id_a = cot_ids_map.get(combo_val)  # None = stock general

                        self.cursor.execute("""
                            INSERT INTO compra_detalle_cotizacion
                            (compra_detalle_id, cotizacion_id, cantidad)
                            VALUES (?,?,?)
                        """, (detalle_id, cot_id_a, cant_a))

                        if cot_id_a:
                            n_cot += 1
                        else:
                            n_stock += 1

                self.conn.commit()

                # Feedback en barra de estado
                try:
                    self.sistema._set_status(
                        f'Compra {folio_compra} registrada — stock actualizado', 'ok')
                except Exception:
                    pass

                resumen = f"✅ Folio: {folio_compra}\n"
                resumen += f"Total: ${total_:,.2f}\n"
                resumen += f"Asignaciones a cotizaciones: {n_cot}\n"
                resumen += f"Asignaciones a stock general: {n_stock}"
                messagebox.showinfo("Compra registrada", resumen, parent=win)
                win.destroy()
                win_padre.destroy()
                try:
                    self.sistema._actualizar_badge_vinculacion()
                except Exception:
                    pass
                self.abrir()

            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Error BD", str(e), parent=win)

        tk.Button(foot, text="✅  Registrar compra",
                  command=_registrar,
                  bg="#065f46", fg="white", font=("Arial", 10, "bold"),
                  cursor="hand2", padx=16, pady=6, relief="flat").pack(side="left", padx=12)
        tk.Label(foot,
                 text="El stock sube para todos los productos (pasan por bodega)",
                 font=("Arial", 8), bg="#1e2d45", fg="#94a3b8").pack(side="left", padx=6)
        tk.Button(foot, text="Cancelar", command=win.destroy,
                  bg="#6b7280", fg="white", font=("Arial", 9),
                  cursor="hand2", padx=10, pady=6).pack(side="right", padx=12)



# ── Helpers de UI para preview cards ──────────────────────────────────────────

def _card_header(parent, titulo, bg_color):
    """Encabezado coloreado para una card de preview."""
    hf = tk.Frame(parent, bg=bg_color, pady=6, padx=10)
    hf.pack(fill="x")
    tk.Label(hf, text=titulo, font=("Arial", 10, "bold"),
             bg=bg_color, fg="white", anchor="w").pack(fill="x")


def _card_fields(parent, campos):
    """Lista de campos clave-valor alternando fondo."""
    for i, (lbl, val) in enumerate(campos):
        bg_c = "#f8fafc" if i % 2 == 0 else "white"
        rf = tk.Frame(parent, bg=bg_c, pady=4)
        rf.pack(fill="x")
        tk.Label(rf, text=f"  {lbl}:", font=("Arial", 8, "bold"),
                 bg=bg_c, fg="#6b7280", width=20, anchor="w").pack(side="left")
        tk.Label(rf, text=str(val) if val else "—", font=("Arial", 8),
                 bg=bg_c, fg="#1e2d45", anchor="w",
                 wraplength=280, justify="left").pack(
            side="left", fill="x", expand=True, padx=(0, 8))


# ══════════════════════════════════════════════════════════════════════════════
class DialogoVinculacion:
    """
    Dialogo split-panel:
      Izquierda — datos del XML (informacion de origen)
      Derecha   — lista completa con busqueda en vivo + preview del seleccionado
    El boton Vincular aplica directamente sobre el registro seleccionado.
    """

    def __init__(self, panel, origen, win_padre):
        self.panel     = panel
        self.cursor    = panel.cursor
        self.conn      = panel.conn
        self.sistema   = panel.sistema
        self.origen    = origen
        self.win_padre = win_padre
        self._sel_row  = None   # fila seleccionada actualmente
        self._todos    = []     # lista completa cargada de BD
        self._idx_map  = []     # mapeo posicion visible -> fila real

    # ── Apertura ───────────────────────────────────────────────────────────────

    def abrir(self):
        tipo  = self.origen["tipo"]
        color = self.origen["color"]
        icono = self.origen["icono"]
        titulo= self.origen["titulo"]

        # Cargar todos los registros del catalogo segun tipo
        if tipo == "cliente":
            self._todos = _cargar_clientes(self.cursor)
        elif tipo == "proveedor":
            self._todos = _cargar_proveedores(self.cursor)
        elif tipo in ("producto", "clave_sat"):
            self._todos = _cargar_productos(self.cursor)
        elif tipo == "cotizacion":
            self._todos = _cargar_cotizaciones(self.cursor, self.origen["factura_id"])

        win = tk.Toplevel(self.panel.root)
        win.withdraw()
        win.title(f"Vincular — {titulo}")
        # Cotizaciones necesitan más espacio para las tablas de productos
        geo = "1300x720" if tipo in ("cotizacion",) else "1060x680"
        win.geometry(geo)
        win.configure(bg="#f1f5f9")
        win.transient(self.panel.root)
        win.grab_set()
        self._win = win

        # Cabecera
        hdr = tk.Frame(win, bg=color, pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"  {icono}  {titulo}",
                 font=("Arial", 11, "bold"), bg=color, fg="white").pack(side="left", padx=10)
        sub = self.origen.get("subtitulo", "")
        if sub:
            tk.Label(hdr, text=sub, font=("Arial", 9), bg=color,
                     fg="#e2e8f0").pack(side="left", padx=6)
        tk.Label(hdr, text=f"  {len(self._todos)} registro(s) en catalogo  ",
                 font=("Arial", 8), bg="#2d4a6e", fg="white").pack(side="right", padx=10)

        # Body split
        body = tk.PanedWindow(win, orient="horizontal", sashwidth=6,
                               bg="#cbd5e1", sashrelief="flat")
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg="white")
        body.add(left, minsize=290, width=310)
        self._build_left(left, color)

        right = tk.Frame(body, bg="#f1f5f9")
        body.add(right, minsize=440)
        self._build_right(right, color)

        # Pie
        foot = tk.Frame(win, bg="#1e2d45", pady=8)
        foot.pack(fill="x", side="bottom")

        if tipo == "cotizacion":
            self._btn_vincular = tk.Button(
                foot, text="  ✅  Vincular cotizaciones seleccionadas (0)  ",
                font=("Arial", 10, "bold"), bg="#16a34a", fg="white",
                cursor="hand2", padx=14, pady=6, relief="flat",
                command=self._accion_vincular)
            self._btn_vincular.pack(side="left", padx=12)
            self._lbl_pie = tk.Label(foot,
                text="Marca una o más cotizaciones con ☑ y pulsa Vincular",
                font=("Arial", 8), bg="#1e2d45", fg="#94a3b8")
            self._lbl_pie.pack(side="left", padx=6)
        else:
            self._btn_vincular = tk.Button(
                foot, text="  ✅  Vincular con seleccionado  ",
                font=("Arial", 10, "bold"), bg="#16a34a", fg="white",
                cursor="hand2", padx=14, pady=6, relief="flat",
                command=self._accion_vincular)
            self._btn_vincular.pack(side="left", padx=12)
            tk.Label(foot,
                     text="Selecciona un registro de la lista y pulsa Vincular",
                     font=("Arial", 8), bg="#1e2d45", fg="#94a3b8").pack(side="left", padx=6)

        tk.Button(foot, text="Cancelar", font=("Arial", 9),
                  bg="#6b7280", fg="white", cursor="hand2",
                  padx=12, pady=6, relief="flat",
                  command=win.destroy).pack(side="right", padx=12)
        win.after(0, win.deiconify)

    # ── Panel izquierdo ────────────────────────────────────────────────────────

    def _build_left(self, parent, color):
        tipo = self.origen["tipo"]
        tk.Frame(parent, bg=color, height=5).pack(fill="x")
        th = tk.Frame(parent, bg="#f8fafc", pady=7)
        th.pack(fill="x")
        tk.Label(th, text="  📌  Datos desde el XML",
                 font=("Arial", 9, "bold"), bg="#f8fafc", fg=color).pack(side="left")
        tk.Frame(parent, bg="#e2e8f0", height=1).pack(fill="x")

        # Para cotizaciones, los campos son pocos — mostrarlos en modo compacto
        max_fields = 6 if tipo == "cotizacion" else 999
        for i, (lbl, val) in enumerate(self.origen["campos"][:max_fields]):
            bg_c = "#f8fafc" if i % 2 == 0 else "white"
            rf = tk.Frame(parent, bg=bg_c, pady=4)
            rf.pack(fill="x")
            tk.Label(rf, text=f"  {lbl}", font=("Arial", 8, "bold"),
                     bg=bg_c, fg="#6b7280", width=18, anchor="w").pack(side="left")
            tk.Label(rf, text=str(val), font=("Arial", 8),
                     bg=bg_c, fg="#1e2d45", anchor="w",
                     wraplength=160, justify="left").pack(
                side="left", fill="x", expand=True, padx=(0, 8))

        # Para cotizaciones: tabla de conceptos del XML (lo que se está facturando)
        if tipo == "cotizacion":
            fac_id = self.origen.get("factura_id")
            if fac_id:
                tk.Frame(parent, bg="#e2e8f0", height=1).pack(fill="x", pady=(6, 0))
                sh = tk.Frame(parent, bg="#ecf4ff", pady=5, padx=8)
                sh.pack(fill="x")
                tk.Label(sh, text="📋 Conceptos en la Factura",
                         font=("Arial", 8, "bold"), bg="#ecf4ff", fg="#1e3a5f").pack(anchor="w")
                self.cursor.execute("""
                    SELECT fc.no_identificacion, fc.descripcion,
                           fc.cantidad, fc.valor_unitario, fc.importe
                    FROM factura_conceptos fc WHERE fc.factura_id=?
                    ORDER BY fc.id
                """, (fac_id,))
                conceptos_fac = self.cursor.fetchall()
                if conceptos_fac:
                    cf_frame = tk.Frame(parent, bg="white")
                    cf_frame.pack(fill="x", padx=4, pady=(2, 0))
                    cols_cf = ("Código", "Descripción", "Cant.", "P.Unit.", "Importe")
                    widths_cf = [55, 100, 38, 68, 68]
                    tree_cf = ttk.Treeview(cf_frame, columns=cols_cf, show="headings",
                                           height=min(len(conceptos_fac), 6),
                                           selectmode="none")
                    for col, w in zip(cols_cf, widths_cf):
                        tree_cf.heading(col, text=col)
                        tree_cf.column(col, width=w, minwidth=30)
                    sc_cf = ttk.Scrollbar(cf_frame, orient="vertical", command=tree_cf.yview)
                    tree_cf.configure(yscrollcommand=sc_cf.set)
                    for c in conceptos_fac:
                        no_id, desc, cant, vu, imp = c
                        tree_cf.insert("", "end", values=(
                            no_id or "—", (desc or "")[:28],
                            f"{cant:g}", f"${vu:,.0f}", f"${imp:,.0f}"))
                    tree_cf.pack(side="left", fill="x", expand=True)
                    sc_cf.pack(side="right", fill="y")
                else:
                    tk.Label(parent, text="Sin conceptos registrados.",
                             font=("Arial", 8, "italic"), bg="white", fg="#9ca3af").pack(anchor="w", padx=8, pady=4)

        # Boton crear nuevo (no aplica a clave_sat, ahi solo se asigna)
        if self.origen["tipo"] != "clave_sat":
            tk.Frame(parent, bg="#e2e8f0", height=1).pack(fill="x", pady=(12, 0))
            nf = tk.Frame(parent, bg="#f0fdf4", pady=10, padx=12)
            nf.pack(fill="x")
            tk.Label(nf, text="No encuentras el registro?",
                     font=("Arial", 9, "bold"), bg="#f0fdf4", fg="#15803d").pack(anchor="w")
            tk.Label(nf,
                     text="Crea uno nuevo con los datos del XML como punto de partida.",
                     font=("Arial", 8), bg="#f0fdf4", fg="#6b7280",
                     wraplength=265, justify="left").pack(anchor="w", pady=(2, 6))
            tk.Button(nf, text="  Crear nuevo y vincular",
                      font=("Arial", 9, "bold"), bg=color, fg="white",
                      cursor="hand2", padx=10, pady=6, relief="flat",
                      command=self._accion_crear).pack(fill="x")

    # ── Panel derecho: lista + busqueda + preview ──────────────────────────────

    def _build_right(self, parent, color):
        tipo = self.origen["tipo"]

        # ── Cotizaciones: layout especial con checkboxes + panel de seleccionadas ──
        if tipo == "cotizacion":
            self._checked_ids  = {}   # cot_id -> row tuple
            self._check_vars   = {}   # cot_id -> BooleanVar
            self._check_btns   = {}   # cot_id -> Button widget

            parent.grid_columnconfigure(0, weight=3)  # lista + búsqueda
            parent.grid_columnconfigure(1, weight=2)  # detalle + seleccionadas
            parent.grid_rowconfigure(2, weight=1)

            # ── Columna izq: búsqueda + lista checkboxes ──────────────────────
            sb_f = tk.Frame(parent, bg="#f1f5f9", pady=6)
            sb_f.grid(row=0, column=0, sticky="ew", padx=(10, 4))
            tk.Label(sb_f, text="🔍 Buscar:", font=("Arial", 9, "bold"),
                     bg="#f1f5f9", fg="#374151").pack(side="left")
            self._entry_buscar = tk.Entry(sb_f, font=("Arial", 9), width=24)
            self._entry_buscar.pack(side="left", padx=6)
            self._entry_buscar.bind("<KeyRelease>", lambda e: self._filtrar())
            self._lbl_conteo = tk.Label(sb_f, text="", font=("Arial", 8),
                                         bg="#f1f5f9", fg="#6b7280")
            self._lbl_conteo.pack(side="right", padx=4)

            tk.Frame(parent, bg="#e2e8f0", height=1).grid(
                row=1, column=0, sticky="ew", padx=(10, 4), pady=(0, 2))

            # Canvas scrollable para la lista de checkboxes
            lista_outer = tk.Frame(parent, bg="#f1f5f9")
            lista_outer.grid(row=2, column=0, sticky="nsew", padx=(10, 4))
            lista_outer.grid_rowconfigure(0, weight=1)
            lista_outer.grid_columnconfigure(0, weight=1)

            self._canvas_lista = tk.Canvas(lista_outer, bg="#f1f5f9", highlightthickness=0)
            sc_lista = ttk.Scrollbar(lista_outer, orient="vertical",
                                      command=self._canvas_lista.yview)
            self._canvas_lista.configure(yscrollcommand=sc_lista.set)
            self._canvas_lista.grid(row=0, column=0, sticky="nsew")
            sc_lista.grid(row=0, column=1, sticky="ns")

            self._inner_lista = tk.Frame(self._canvas_lista, bg="#f1f5f9")
            self._wid_lista = self._canvas_lista.create_window(
                (0, 0), window=self._inner_lista, anchor="nw")
            self._inner_lista.bind("<Configure>",
                lambda e: self._canvas_lista.configure(
                    scrollregion=self._canvas_lista.bbox("all")))
            self._canvas_lista.bind("<Configure>",
                lambda e: self._canvas_lista.itemconfig(self._wid_lista, width=e.width))

            # ── Columna der: detalle arriba + seleccionadas abajo ─────────────
            right_col = tk.Frame(parent, bg="#f1f5f9")
            right_col.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(4, 10), pady=0)
            right_col.grid_rowconfigure(1, weight=2)   # detalle
            right_col.grid_rowconfigure(3, weight=1)   # seleccionadas
            right_col.grid_columnconfigure(0, weight=1)

            # Header detalle
            ph = tk.Frame(right_col, bg="#f1f5f9", pady=3)
            ph.grid(row=0, column=0, sticky="ew")
            tk.Label(ph, text="Detalle de la cotización:", font=("Arial", 9, "bold"),
                     bg="#f1f5f9", fg="#374151").pack(side="left")

            self._preview_frame = tk.Frame(right_col, bg="white",
                                            highlightbackground="#e2e8f0",
                                            highlightthickness=1)
            self._preview_frame.grid(row=1, column=0, sticky="nsew")
            tk.Label(self._preview_frame,
                     text="Haz clic en una cotización\npara ver su detalle.",
                     font=("Arial", 8, "italic"), bg="white",
                     fg="#9ca3af", justify="center").pack(expand=True)

            # Header seleccionadas
            tk.Frame(right_col, bg="#e2e8f0", height=1).grid(
                row=2, column=0, sticky="ew", pady=(6, 0))
            sh = tk.Frame(right_col, bg="#ecf4ff", pady=4, padx=8)
            sh.grid(row=2, column=0, sticky="ew")
            self._lbl_seleccionadas = tk.Label(
                sh, text="☑ Cotizaciones a vincular (0):",
                font=("Arial", 9, "bold"), bg="#ecf4ff", fg="#1e3a5f")
            self._lbl_seleccionadas.pack(side="left")

            # Lista de seleccionadas
            sel_outer = tk.Frame(right_col, bg="white",
                                  highlightbackground="#e2e8f0", highlightthickness=1)
            sel_outer.grid(row=3, column=0, sticky="nsew")
            sel_outer.grid_rowconfigure(0, weight=1)
            sel_outer.grid_columnconfigure(0, weight=1)
            self._sel_canvas = tk.Canvas(sel_outer, bg="white", highlightthickness=0)
            sel_sc = ttk.Scrollbar(sel_outer, orient="vertical",
                                    command=self._sel_canvas.yview)
            self._sel_canvas.configure(yscrollcommand=sel_sc.set)
            self._sel_canvas.grid(row=0, column=0, sticky="nsew")
            sel_sc.grid(row=0, column=1, sticky="ns")
            self._sel_inner = tk.Frame(self._sel_canvas, bg="white")
            wid_sel = self._sel_canvas.create_window((0, 0), window=self._sel_inner, anchor="nw")
            self._sel_inner.bind("<Configure>",
                lambda e: self._sel_canvas.configure(
                    scrollregion=self._sel_canvas.bbox("all")))
            self._sel_canvas.bind("<Configure>",
                lambda e: self._sel_canvas.itemconfig(wid_sel, width=e.width))

            self._filtrar()
            return

        # ── Otros tipos: layout original ──────────────────────────────────────
        parent.grid_rowconfigure(2, weight=2)   # tree
        parent.grid_rowconfigure(5, weight=1)   # preview
        parent.grid_columnconfigure(0, weight=1)

        # Barra de busqueda
        sb_f = tk.Frame(parent, bg="#f1f5f9", pady=6)
        sb_f.grid(row=0, column=0, sticky="ew", padx=10)
        tk.Label(sb_f, text="🔍 Buscar:", font=("Arial", 9, "bold"),
                 bg="#f1f5f9", fg="#374151").pack(side="left")
        self._entry_buscar = tk.Entry(sb_f, font=("Arial", 9), width=32)
        self._entry_buscar.pack(side="left", padx=6)
        self._entry_buscar.bind("<KeyRelease>", lambda e: self._filtrar())
        self._lbl_conteo = tk.Label(sb_f, text="", font=("Arial", 8),
                                     bg="#f1f5f9", fg="#6b7280")
        self._lbl_conteo.pack(side="right", padx=4)

        tk.Frame(parent, bg="#e2e8f0", height=1).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 2))

        # Treeview
        cols   = self._cols()
        widths = self._widths()
        tree_f = tk.Frame(parent, bg="#f1f5f9")
        tree_f.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 4))
        tree_f.grid_rowconfigure(0, weight=1)
        tree_f.grid_columnconfigure(0, weight=1)

        self._tree = ttk.Treeview(tree_f, columns=cols, show="headings",
                                   selectmode="browse", height=9)
        for col, w in zip(cols, widths):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, minwidth=w)

        sc_y = ttk.Scrollbar(tree_f, orient="vertical",   command=self._tree.yview)
        sc_x = ttk.Scrollbar(tree_f, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=sc_y.set, xscrollcommand=sc_x.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        sc_y.grid(row=0, column=1, sticky="ns")
        sc_x.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", lambda e: self._accion_vincular())

        # Separador + etiqueta preview
        tk.Frame(parent, bg="#e2e8f0", height=1).grid(
            row=3, column=0, sticky="ew", padx=10, pady=(4, 0))
        ph = tk.Frame(parent, bg="#f1f5f9", pady=3)
        ph.grid(row=4, column=0, sticky="ew", padx=10)
        tipo_sel = self.origen["tipo"]
        lbl_preview = ("Detalle de la cotización seleccionada:" if tipo_sel == "cotizacion"
                       else "Detalle del registro seleccionado:")
        tk.Label(ph, text=lbl_preview,
                 font=("Arial", 9, "bold"), bg="#f1f5f9", fg="#374151").pack(side="left")
        tk.Label(ph, text="← doble clic para vincular directamente",
                 font=("Arial", 8, "italic"), bg="#f1f5f9", fg="#9ca3af").pack(side="right")

        # Frame preview — más alto para cotizaciones
        self._preview_frame = tk.Frame(parent, bg="white",
                                        highlightbackground="#e2e8f0",
                                        highlightthickness=1)
        self._preview_frame.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 6))
        tk.Label(self._preview_frame,
                 text="Selecciona un registro de la lista para ver detalle.",
                 font=("Arial", 8, "italic"), bg="white", fg="#9ca3af", pady=12).pack()

        # Poblar el tree al inicio
        self._filtrar()

    # ── Filtrado en vivo ───────────────────────────────────────────────────────

    def _filtrar(self):
        buscar = self._entry_buscar.get().strip().lower()
        tipo   = self.origen["tipo"]

        # ── Cotizaciones: lista de checkboxes ─────────────────────────────────
        if tipo == "cotizacion":
            for w in self._inner_lista.winfo_children():
                w.destroy()
            visible = 0
            for row in self._todos:
                vals = self._vals(row)
                if buscar and not any(buscar in str(v).lower() for v in vals):
                    continue
                cot_id = row[0]
                is_checked = cot_id in self._checked_ids

                rf = tk.Frame(self._inner_lista,
                               bg="#e0f2fe" if is_checked else "white",
                               highlightbackground="#93c5fd" if is_checked else "#e2e8f0",
                               highlightthickness=1)
                rf.pack(fill="x", pady=1, padx=2)

                # Checkbox
                var = self._check_vars.get(cot_id) or tk.BooleanVar(value=is_checked)
                self._check_vars[cot_id] = var

                def _toggle(r=row, v=var, frame=rf):
                    cid = r[0]
                    if v.get():
                        self._checked_ids[cid] = r
                    else:
                        self._checked_ids.pop(cid, None)
                    self._actualizar_seleccionadas()
                    self._actualizar_preview(r)

                cb = tk.Checkbutton(rf, variable=var, command=_toggle,
                                     bg="#e0f2fe" if is_checked else "white",
                                     activebackground="#bfdbfe",
                                     cursor="hand2", relief="flat",
                                     padx=4)
                cb.pack(side="left")
                self._check_btns[cot_id] = cb

                # Info compacta
                cid, folio, fecha, cliente, rfc_c, total_c, estado, _ = row
                estado_colors = {
                    "Pendiente":"#f39c12","Programada":"#3498db","Entregada":"#27ae60",
                    "Facturada":"#9b59b6","Pagada":"#16a085","Cancelada":"#e74c3c"
                }
                ec = estado_colors.get(estado, "#64748b")
                info_f = tk.Frame(rf, bg="#e0f2fe" if is_checked else "white",
                                   cursor="hand2")
                info_f.pack(side="left", fill="x", expand=True, pady=3)
                info_f.bind("<Button-1>", lambda e, r=row, v=var, t=_toggle: (
                    v.set(not v.get()), t()))

                tk.Label(info_f, text=folio, font=("Arial", 9, "bold"),
                         bg="#e0f2fe" if is_checked else "white",
                         fg="#1e2d45", cursor="hand2").pack(side="left", padx=(0, 8))
                tk.Label(info_f, text=(cliente or rfc_c or "—")[:28],
                         font=("Arial", 8),
                         bg="#e0f2fe" if is_checked else "white",
                         fg="#374151", cursor="hand2").pack(side="left", padx=(0, 8))
                tk.Label(info_f, text=(fecha or "")[:10], font=("Arial", 8),
                         bg="#e0f2fe" if is_checked else "white",
                         fg="#6b7280").pack(side="left", padx=(0, 8))
                tk.Label(info_f, text=f"${total_c:,.0f}" if total_c else "—",
                         font=("Arial", 8, "bold"),
                         bg="#e0f2fe" if is_checked else "white",
                         fg="#065f46").pack(side="left", padx=(0, 8))
                tk.Label(info_f, text=estado, font=("Arial", 7, "bold"),
                         bg=ec, fg="white", padx=4, pady=1).pack(side="left")

                # Botón ver detalle (ojo)
                def _ver(r=row): self._actualizar_preview(r)
                tk.Button(rf, text="👁", font=("Arial", 9), cursor="hand2",
                           bg="#e0f2fe" if is_checked else "white",
                           relief="flat", padx=4, command=_ver).pack(side="right", padx=4)

                visible += 1

            n = visible
            self._lbl_conteo.config(text=f"{n} cotización{'es' if n!=1 else ''}")
            return

        # ── Otros tipos: Treeview original ────────────────────────────────────
        self._tree.delete(*self._tree.get_children())
        self._sel_row = None
        self._idx_map = []

        for row in self._todos:
            vals = self._vals(row)
            if buscar and not any(buscar in str(v).lower() for v in vals):
                continue
            self._tree.insert("", "end", values=vals)
            self._idx_map.append(row)

        n = len(self._idx_map)
        self._lbl_conteo.config(text=f"{n} resultado{'s' if n!=1 else ''}")

        # Limpiar preview
        for w in self._preview_frame.winfo_children():
            w.destroy()
        tk.Label(self._preview_frame,
                 text="Selecciona un registro de la lista para ver detalle.",
                 font=("Arial", 8, "italic"), bg="white", fg="#9ca3af", pady=8).pack()

    def _actualizar_seleccionadas(self):
        """Refresca el panel de cotizaciones marcadas y el botón de acción."""
        for w in self._sel_inner.winfo_children():
            w.destroy()
        n = len(self._checked_ids)
        self._lbl_seleccionadas.config(text=f"☑ Cotizaciones a vincular ({n}):")
        self._btn_vincular.config(
            text=f"  ✅  Vincular {n} cotización{'es' if n!=1 else ''} seleccionada{'s' if n!=1 else ''}  ",
            state="normal" if n > 0 else "disabled",
            bg="#16a34a" if n > 0 else "#9ca3af")
        if not self._checked_ids:
            tk.Label(self._sel_inner,
                     text="Ninguna seleccionada aún.",
                     font=("Arial", 8, "italic"), bg="white", fg="#9ca3af",
                     pady=6).pack(anchor="w", padx=8)
            return
        for cot_id, row in self._checked_ids.items():
            _, folio, fecha, cliente, _, total_c, estado, _ = row
            rf = tk.Frame(self._sel_inner, bg="#f0fdf4",
                           highlightbackground="#86efac", highlightthickness=1)
            rf.pack(fill="x", pady=1, padx=2)
            tk.Label(rf, text=f"✓ {folio}", font=("Arial", 8, "bold"),
                     bg="#f0fdf4", fg="#15803d").pack(side="left", padx=6, pady=3)
            tk.Label(rf, text=(cliente or "—")[:22], font=("Arial", 8),
                     bg="#f0fdf4", fg="#374151").pack(side="left")
            tk.Label(rf, text=f"${total_c:,.0f}" if total_c else "—",
                     font=("Arial", 8), bg="#f0fdf4", fg="#065f46").pack(side="right", padx=6)
            # Botón quitar
            def _quitar(cid=cot_id):
                self._checked_ids.pop(cid, None)
                if cid in self._check_vars:
                    self._check_vars[cid].set(False)
                self._actualizar_seleccionadas()
                self._filtrar()
            tk.Button(rf, text="✕", font=("Arial", 7), cursor="hand2",
                       bg="#f0fdf4", fg="#dc2626", relief="flat", padx=2,
                       command=_quitar).pack(side="right", padx=2)

    # ── Seleccion en tree (solo tipos no-cotizacion) ───────────────────────────

    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        idx = self._tree.index(sel[0])
        if idx >= len(self._idx_map):
            return
        self._sel_row = self._idx_map[idx]
        self._actualizar_preview(self._sel_row)

    def _actualizar_preview(self, row):
        for w in self._preview_frame.winfo_children():
            w.destroy()
        tipo = self.origen["tipo"]

        # ── Cotización: card completa con tabla de productos ───────────────────
        if tipo == "cotizacion":
            cid, folio, fecha, cliente, rfc_c, total_c, estado, entregado = row
            self.cursor.execute("""
                SELECT p.codigo, p.nombre, cd.cantidad, cd.precio_unitario,
                       cd.subtotal, cd.iva, cd.total, cd.tiene_stock
                FROM cotizacion_detalle cd
                JOIN productos p ON p.id = cd.producto_id
                WHERE cd.cotizacion_id = ?
            """, (cid,))
            prods_cot = self.cursor.fetchall()

            # Header card
            estado_colors = {
                "Pendiente":"#f39c12","Programada":"#3498db","Entregada":"#27ae60",
                "Facturada":"#9b59b6","Pagada":"#16a085","Cancelada":"#e74c3c"
            }
            hc = tk.Frame(self._preview_frame,
                          bg=estado_colors.get(estado, "#64748b"), pady=6, padx=10)
            hc.pack(fill="x")
            tk.Label(hc, text=folio, font=("Arial", 11, "bold"),
                     bg=estado_colors.get(estado, "#64748b"), fg="white").pack(side="left")
            tk.Label(hc, text=estado, font=("Arial", 9, "bold"),
                     bg="white", fg=estado_colors.get(estado, "#64748b"),
                     padx=8, pady=2).pack(side="right")

            # Meta row
            meta = tk.Frame(self._preview_frame, bg="#f8fafc", pady=5, padx=10)
            meta.pack(fill="x")
            for txt in [f"👤 {cliente}", f"RFC: {rfc_c or '—'}", f"📅 {(fecha or '')[:10]}"]:
                tk.Label(meta, text=txt, font=("Arial", 8), bg="#f8fafc",
                         fg="#374151").pack(side="left", padx=(0, 16))

            # Tabla de productos
            tk.Frame(self._preview_frame, bg="#e2e8f0", height=1).pack(fill="x")
            tf = tk.Frame(self._preview_frame, bg="white")
            tf.pack(fill="both", expand=True)
            tf.grid_columnconfigure(0, weight=1)
            tf.grid_rowconfigure(0, weight=1)

            cols_cp = ("Código", "Producto", "Cant.", "P.Unit.", "Subtotal", "Stock")
            w_cp    = [70, 190, 48, 80, 80, 50]
            tree_cp = ttk.Treeview(tf, columns=cols_cp, show="headings",
                                    height=min(len(prods_cot), 7), selectmode="none")
            for col, w in zip(cols_cp, w_cp):
                tree_cp.heading(col, text=col)
                tree_cp.column(col, width=w, minwidth=30)
            tree_cp.tag_configure("nostock", background="#fef3c7")
            sc_cp = ttk.Scrollbar(tf, orient="vertical", command=tree_cp.yview)
            tree_cp.configure(yscrollcommand=sc_cp.set)
            for p in prods_cot:
                cod, nom, cant, pu, sub_, iva_, tot_, ts = p
                tag = "nostock" if not ts else ""
                tree_cp.insert("", "end", tags=(tag,), values=(
                    cod, nom, f"{cant:g}", f"${pu:,.0f}", f"${sub_:,.0f}",
                    "✓" if ts else "✗"))
            tree_cp.grid(row=0, column=0, sticky="nsew")
            sc_cp.grid(row=0, column=1, sticky="ns")

            # Totales footer
            tf2 = tk.Frame(self._preview_frame, bg="#1e2d45", pady=5, padx=10)
            tf2.pack(fill="x", side="bottom")
            tk.Label(tf2, text=f"Total: ${total_c:,.2f}", font=("Arial", 10, "bold"),
                     bg="#1e2d45", fg="white").pack(side="right")
            tk.Label(tf2, text=f"Entregado: ${entregado:,.2f}",
                     font=("Arial", 9), bg="#1e2d45", fg="#94a3b8").pack(side="right", padx=16)
            tk.Label(tf2, text=f"{len(prods_cot)} productos",
                     font=("Arial", 8), bg="#1e2d45", fg="#94a3b8").pack(side="left")
            return

        # ── Cliente ───────────────────────────────────────────────────────────
        if tipo == "cliente":
            cid, nom, razon, rfc, tip, reg, uso, cp, cont, email = row
            _card_header(self._preview_frame, f"👥 {nom}", "#1e3a5f")
            campos = [("Razón Social", razon), ("RFC", rfc), ("Tipo", tip),
                      ("Régimen Fiscal", reg), ("Uso CFDI", uso), ("C.P. Fiscal", cp),
                      ("Contacto", cont), ("Email", email)]
            _card_fields(self._preview_frame, campos)
            return

        # ── Proveedor ─────────────────────────────────────────────────────────
        if tipo == "proveedor":
            pid, nom, razon, rfc, reg, cp, cont, email = row
            _card_header(self._preview_frame, f"🏭 {nom}", "#92400e")
            campos = [("Razón Social", razon), ("RFC", rfc),
                      ("Régimen Fiscal", reg), ("C.P. Fiscal", cp),
                      ("Contacto", cont), ("Email", email)]
            _card_fields(self._preview_frame, campos)
            # Últimas compras a este proveedor
            self.cursor.execute("""
                SELECT folio, fecha_compra, total FROM compras
                WHERE proveedor_id=? ORDER BY fecha_compra DESC LIMIT 4
            """, (pid,))
            compras_prev = self.cursor.fetchall()
            if compras_prev:
                tk.Frame(self._preview_frame, bg="#e2e8f0", height=1).pack(fill="x", pady=(6,0))
                tk.Label(self._preview_frame, text="  Últimas compras:",
                         font=("Arial", 8, "bold"), bg="white", fg="#6b7280").pack(anchor="w", pady=(4,0))
                for folio_c, fec_c, tot_c in compras_prev:
                    rf = tk.Frame(self._preview_frame, bg="#f8fafc", pady=2)
                    rf.pack(fill="x")
                    tk.Label(rf, text=f"  {folio_c}", font=("Arial", 8),
                             bg="#f8fafc", fg="#374151").pack(side="left")
                    tk.Label(rf, text=(fec_c or "")[:10], font=("Arial", 8),
                             bg="#f8fafc", fg="#6b7280").pack(side="left", padx=8)
                    tk.Label(rf, text=f"${tot_c:,.2f}", font=("Arial", 8, "bold"),
                             bg="#f8fafc", fg="#065f46").pack(side="right", padx=8)
            return

        # ── Producto ──────────────────────────────────────────────────────────
        if tipo in ("producto", "clave_sat"):
            pid, codigo, nombre, precio, unidad, clave_sat = row
            # Obtener stock actual y datos extra
            self.cursor.execute(
                "SELECT stock_actual, stock_minimo, precio_base FROM productos WHERE id=?",
                (pid,))
            pr = self.cursor.fetchone()
            stock_act = pr[0] if pr else 0
            stock_min = pr[1] if pr else 0
            costo_b   = pr[2] if pr else 0

            # Obtener todas las claves SAT históricas
            self.cursor.execute("""
                SELECT clave_sat, fuente, fecha_registro
                FROM producto_claves_sat
                WHERE producto_id=?
                ORDER BY fecha_registro
            """, (pid,))
            todas_claves = self.cursor.fetchall()

            _card_header(self._preview_frame, f"📦 {nombre}", "#065f46")
            stock_color = "#16a34a" if stock_act > stock_min else "#dc2626"
            campos = [("Código", codigo),
                      ("Clave SAT principal", clave_sat or "—"),
                      ("Unidad", unidad),
                      ("Precio Venta", f"${precio:,.2f}" if precio else "—"),
                      ("Costo base", f"${costo_b:,.2f}" if costo_b else "—")]
            _card_fields(self._preview_frame, campos)

            # Stock
            sf = tk.Frame(self._preview_frame, bg="#f8fafc", pady=5, padx=10)
            sf.pack(fill="x")
            tk.Label(sf, text="Stock actual:", font=("Arial", 9, "bold"),
                     bg="#f8fafc", fg="#374151").pack(side="left")
            tk.Label(sf, text=f"{stock_act:g}  (mín: {stock_min:g})",
                     font=("Arial", 10, "bold"), bg="#f8fafc", fg=stock_color).pack(side="left", padx=8)

            # Bloque de claves SAT históricas
            if todas_claves:
                tk.Frame(self._preview_frame, bg="#e2e8f0", height=1).pack(fill="x", pady=(6,0))
                hsat = tk.Frame(self._preview_frame, bg="#ecf4ff", pady=4, padx=10)
                hsat.pack(fill="x")
                badge_txt = f"🏷 Claves SAT registradas ({len(todas_claves)})"
                if len(todas_claves) > 1:
                    badge_txt += "  ⚠️ múltiples"
                tk.Label(hsat, text=badge_txt,
                         font=("Arial", 8, "bold"), bg="#ecf4ff",
                         fg="#dc2626" if len(todas_claves) > 1 else "#1e3a5f").pack(anchor="w")
                for clave_h, fuente_h, fecha_h in todas_claves:
                    es_principal = (clave_h == clave_sat)
                    rf = tk.Frame(self._preview_frame, bg="#fffbeb" if es_principal else "white", pady=2)
                    rf.pack(fill="x")
                    tk.Label(rf, text=f"  {'★ ' if es_principal else '  '}{clave_h}",
                             font=("Arial", 8, "bold" if es_principal else "normal"),
                             bg="#fffbeb" if es_principal else "white",
                             fg="#92400e" if es_principal else "#374151").pack(side="left")
                    tk.Label(rf, text=f"{fuente_h}  {(fecha_h or '')[:10]}",
                             font=("Arial", 7), bg="#fffbeb" if es_principal else "white",
                             fg="#9ca3af").pack(side="right", padx=8)
            return

        # ── Fallback genérico ─────────────────────────────────────────────────
        for i, (lbl, val) in enumerate(self._campos_preview(row)):
            bg_c = "#f8fafc" if i % 2 == 0 else "white"
            rf = tk.Frame(self._preview_frame, bg=bg_c, pady=3)
            rf.pack(fill="x")
            tk.Label(rf, text=f"  {lbl}:", font=("Arial", 8, "bold"),
                     bg=bg_c, fg="#6b7280", width=18, anchor="w").pack(side="left")
            tk.Label(rf, text=str(val) if val else "—", font=("Arial", 8),
                     bg=bg_c, fg="#1e2d45", anchor="w").pack(
                side="left", fill="x", expand=True, padx=(0, 8))


    # ── Columnas / valores del tree ────────────────────────────────────────────

    def _cols(self):
        t = self.origen["tipo"]
        if t == "cliente":
            return ("Nombre Comercial", "RFC", "Tipo", "Uso CFDI", "Contacto")
        elif t == "proveedor":
            return ("Nombre", "RFC", "Regimen Fiscal", "Contacto")
        elif t in ("producto", "clave_sat"):
            return ("Codigo", "Nombre", "Precio Venta", "Unidad", "Clave SAT")
        elif t == "cotizacion":
            return ("Folio", "Cliente", "Fecha", "Total", "Estado")
        else:
            return ("Tipo", "Contraparte", "Fecha", "Total")

    def _widths(self):
        t = self.origen["tipo"]
        if t == "cliente":
            return [185, 110, 75, 80, 110]
        elif t == "proveedor":
            return [215, 120, 155, 120]
        elif t in ("producto", "clave_sat"):
            return [105, 205, 95, 70, 95]
        elif t == "cotizacion":
            return [110, 200, 85, 90, 100]
        else:
            return [80, 240, 85, 95]

    def _vals(self, row):
        t = self.origen["tipo"]
        if t == "cliente":
            cid, nom, razon, rfc, tipo, reg, uso, cp, cont, email = row
            return (nom, rfc or "—", tipo or "—", uso or "—", cont or "—")
        elif t == "proveedor":
            pid, nom, razon, rfc, reg, cp, cont, email = row
            return (nom, rfc or "—", reg or "—", cont or "—")
        elif t in ("producto", "clave_sat"):
            pid, codigo, nombre, precio, unidad, clave_sat = row
            return (codigo or "—", nombre,
                    f"${precio:,.2f}" if precio else "—",
                    unidad or "—",
                    clave_sat or "—")
        elif t == "cotizacion":
            # (id, folio, fecha, nombre_comercial, rfc, total, estado, monto_entregado)
            cid, folio, fecha, cliente, rfc_c, total_c, estado, entregado = row
            return (folio, cliente or rfc_c or "—",
                    (fecha or "")[:10],
                    f"${total_c:,.2f}" if total_c else "—",
                    estado or "—")
        else:
            # facturas pendientes: (fid, uuid, total, rfc_contraparte, fecha, tipo_fac, nombre_contraparte)
            fid, uuid_f, total_f, rfc_c, fecha_f, tipo_fac, nombre_c = row
            icono = "🧾" if tipo_fac == "venta" else "🛒"
            tipo_label = "Venta" if tipo_fac == "venta" else "Compra"
            return (f"{icono} {tipo_label}", nombre_c or rfc_c,
                    (fecha_f or "")[:10], f"${total_f:,.2f}" if total_f else "—")

    def _campos_preview(self, row):
        t = self.origen["tipo"]
        if t == "cliente":
            cid, nom, razon, rfc, tipo, reg, uso, cp, cont, email = row
            return [("ID", cid), ("Nombre Comercial", nom), ("Razon Social", razon),
                    ("RFC", rfc), ("Tipo", tipo), ("Regimen Fiscal", reg),
                    ("Uso CFDI", uso), ("C.P. Fiscal", cp),
                    ("Contacto", cont), ("Email", email)]
        elif t == "proveedor":
            pid, nom, razon, rfc, reg, cp, cont, email = row
            return [("ID", pid), ("Nombre", nom), ("Razon Social", razon),
                    ("RFC", rfc), ("Regimen Fiscal", reg), ("C.P. Fiscal", cp),
                    ("Contacto", cont), ("Email", email)]
        elif t in ("producto", "clave_sat"):
            pid, codigo, nombre, precio, unidad, clave_sat = row
            return [("ID", pid), ("Codigo", codigo), ("Nombre", nombre),
                    ("Precio Venta", f"${precio:,.2f}" if precio else "—"),
                    ("Unidad", unidad), ("Clave SAT actual", clave_sat or "—")]
        else:
            fid2, uuid_f, total_f, rfc_c, fecha_f, tipo_fac, nombre_c = row
            tipo_label = ("Factura de Venta (tú eres el emisor)" if tipo_fac == "venta"
                          else "Factura de Compra (proveedor → CLF)")
            return [("ID Factura", fid2), ("Tipo", tipo_label),
                    ("UUID", uuid_f), ("RFC Contraparte", rfc_c),
                    ("Nombre", nombre_c), ("Total", f"${total_f:,.2f}" if total_f else "—"),
                    ("Fecha", (fecha_f or "")[:10])]

    # ── Vincular ───────────────────────────────────────────────────────────────

    def _accion_vincular(self):
        tipo = self.origen["tipo"]
        if tipo == "cotizacion":
            if not self._checked_ids:
                messagebox.showwarning(
                    "Sin selección",
                    "Marca al menos una cotización de la lista para vincular.",
                    parent=self._win)
                return
            # Pasar lista de IDs directamente al branch de cotizacion en _ejecutar_vinculo
            self._ejecutar_vinculo_cotizacion(list(self._checked_ids.keys()))
            return
        if self._sel_row is None:
            messagebox.showwarning(
                "Sin seleccion",
                "Selecciona un registro de la lista para vincular.",
                parent=self._win)
            return
        self._ejecutar_vinculo(self._sel_row)

    def _ejecutar_vinculo_cotizacion(self, cot_ids):
        """Vincula una factura a múltiples cotizaciones vía factura_cotizaciones."""
        factura_id = self.origen["factura_id"]
        cd         = dict(self.origen["campos"])
        uuid       = cd.get("UUID", "")
        fecha_fac  = cd.get("Fecha", "")
        fac_obj    = getattr(self.sistema, "_facturacion", None)
        if not fac_obj:
            messagebox.showerror("Error",
                "No se pudo acceder al módulo de facturación.", parent=self._win)
            return
        try:
            fac_obj._vincular_factura_a_cotizacion(
                factura_id, cot_ids, uuid, fecha_fac, auto=False)
            self._cerrar_y_refrescar()
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self._win)

    def _ejecutar_vinculo(self, row):
        tipo = self.origen["tipo"]
        try:
            if tipo == "cliente":
                cli_id  = row[0]
                rfc_xml = self.origen["datos_registro"].get("rfc", "")
                uso_xml = self.origen["datos_registro"].get("uso_cfdi", "")
                self.cursor.execute("""
                    UPDATE clientes
                    SET rfc      = COALESCE(NULLIF(rfc,''),      ?),
                        uso_cfdi = COALESCE(NULLIF(uso_cfdi,''), ?)
                    WHERE id=?
                """, (rfc_xml, uso_xml, cli_id))
                self.conn.commit()
                messagebox.showinfo(
                    "Vinculado",
                    f"Cliente '{row[1]}' vinculado.\nRFC y Uso CFDI actualizados desde el XML.",
                    parent=self._win)

            elif tipo == "proveedor":
                prov_id = row[0]
                rfc_xml = self.origen["datos_registro"].get("rfc", "")
                reg_xml = self.origen["datos_registro"].get("regimen_fiscal", "")
                self.cursor.execute("""
                    UPDATE proveedores
                    SET rfc            = COALESCE(NULLIF(rfc,''),            ?),
                        regimen_fiscal = COALESCE(NULLIF(regimen_fiscal,''), ?)
                    WHERE id=?
                """, (rfc_xml, reg_xml, prov_id))
                self.conn.commit()
                messagebox.showinfo(
                    "Vinculado",
                    f"Proveedor '{row[1]}' vinculado con RFC actualizado.",
                    parent=self._win)

            elif tipo == "producto":
                prod_id      = row[0]
                no_id        = self.origen.get("no_id", "")
                clave_xml    = self.origen.get("clave_prod_serv", "") or                                self.origen["datos_registro"].get("clave_sat", "")
                uni          = self.origen["datos_registro"].get("clave_unidad_sat", "")

                if no_id:
                    # Asignar código al producto; clave_sat principal solo si aún no tiene
                    self.cursor.execute("""
                        UPDATE productos
                        SET codigo           = ?,
                            clave_sat        = COALESCE(NULLIF(clave_sat,''), ?),
                            clave_unidad_sat = COALESCE(NULLIF(clave_unidad_sat,''), ?)
                        WHERE id=?
                    """, (no_id, clave_xml, uni, prod_id))
                    detalle = f"Código '{no_id}' asignado al producto."
                else:
                    # Solo viene clave SAT — asignar como principal si el producto no tiene
                    self.cursor.execute("""
                        UPDATE productos
                        SET clave_sat        = COALESCE(NULLIF(clave_sat,''), ?),
                            clave_unidad_sat = COALESCE(NULLIF(clave_unidad_sat,''), ?)
                        WHERE id=?
                    """, (clave_xml, uni, prod_id))
                    detalle = f"Clave SAT '{clave_xml}' registrada para el producto."

                # Registrar clave SAT en tabla histórica (permite múltiples claves por producto)
                if clave_xml:
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO producto_claves_sat (producto_id, clave_sat, fuente)
                        VALUES (?, ?, 'xml_import')
                    """, (prod_id, clave_xml))

                self.conn.commit()
                # Contar cuántas claves SAT tiene ahora este producto
                self.cursor.execute(
                    "SELECT COUNT(*) FROM producto_claves_sat WHERE producto_id=?", (prod_id,))
                n_claves = self.cursor.fetchone()[0]
                extra = f"\nClaves SAT registradas para este producto: {n_claves}" if n_claves > 1 else ""
                messagebox.showinfo(
                    "Vinculado",
                    f"Producto '{row[2]}' vinculado.\n{detalle}{extra}",
                    parent=self._win)

            elif tipo == "clave_sat":
                prod_id = self.origen.get("prod_id") or row[0]
                clave   = self.origen["datos_registro"].get("clave_sat", "")
                # Asignar como principal solo si el producto no tiene ninguna
                self.cursor.execute("""
                    UPDATE productos
                    SET clave_sat = COALESCE(NULLIF(clave_sat,''), ?)
                    WHERE id=?
                """, (clave, prod_id))
                # Registrar en tabla histórica
                if clave:
                    self.cursor.execute("""
                        INSERT OR IGNORE INTO producto_claves_sat (producto_id, clave_sat, fuente)
                        VALUES (?, ?, 'xml_import')
                    """, (prod_id, clave))
                self.conn.commit()
                self.cursor.execute(
                    "SELECT COUNT(*) FROM producto_claves_sat WHERE producto_id=?", (prod_id,))
                n_claves = self.cursor.fetchone()[0]
                extra = f"\nClaves SAT registradas para este producto: {n_claves}" if n_claves > 1 else ""
                messagebox.showinfo(
                    "Clave SAT asignada",
                    f"Clave SAT '{clave}' registrada para el producto '{row[2]}'.{extra}",
                    parent=self._win)

            elif tipo == "cotizacion":
                cot_id     = row[0]
                factura_id = self.origen["factura_id"]
                cd         = dict(self.origen["campos"])
                uuid       = cd.get("UUID", "")
                fecha_fac  = cd.get("Fecha", "")
                fac_obj    = getattr(self.sistema, "_facturacion", None)
                if fac_obj:
                    fac_obj._vincular_factura_a_cotizacion(
                        factura_id, cot_id, uuid, fecha_fac, auto=False)
                    self._cerrar_y_refrescar()
                    return
                else:
                    messagebox.showerror(
                        "Error",
                        "No se pudo acceder al modulo de facturacion.",
                        parent=self._win)
                    return

            self._cerrar_y_refrescar()

        except sqlite3.Error as e:
            self.conn.rollback()
            messagebox.showerror("Error de BD", str(e), parent=self._win)

    def _cerrar_y_refrescar(self):
        panel_win = self.win_padre
        self._win.destroy()
        try:
            panel_win.destroy()
        except Exception:
            pass
        try:
            self.sistema._actualizar_badge_vinculacion()
        except Exception:
            pass
        # Refrescar tabla de facturas si el módulo está abierto
        try:
            fac_obj = getattr(self.sistema, "_facturacion", None)
            if fac_obj:
                fac_obj.cargar_facturas()
        except Exception:
            pass
        self.panel.abrir()

    # ── Crear nuevo ────────────────────────────────────────────────────────────

    def _accion_crear(self):
        tipo  = self.origen["tipo"]
        datos = self.origen.get("datos_registro", {})
        if tipo == "cliente":
            self._win.destroy()
            self.sistema.ventana_cliente(
                modo="nuevo", _prefill=datos,
                _callback=lambda cid: self._post_crear("cliente", cid))
        elif tipo == "proveedor":
            self._win.destroy()
            self.sistema._ventana_proveedor(
                modo="nuevo", _prefill=datos,
                _callback=lambda pid: self._post_crear("proveedor", pid))
        elif tipo == "producto":
            self._win.destroy()
            self.sistema._ventana_producto_prefill(
                datos,
                callback=lambda pid: self._post_crear("producto", pid))
        elif tipo == "cotizacion":
            messagebox.showinfo(
                "Crear cotizacion",
                "No es posible crear una cotizacion automaticamente desde aqui.\n"
                "Si existe, buscala en la lista y usa Vincular con seleccionado.\n"
                "Si necesitas crearla, hazlo desde la seccion Cotizaciones.",
                parent=self._win)

    def _post_crear(self, tipo, nuevo_id):
        try:
            self.sistema._actualizar_badge_vinculacion()
        except Exception:
            pass
        msgs = {
            "cliente":   "Cliente creado. Ahora aparece en escaneos de vinculacion.",
            "proveedor": "Proveedor creado correctamente.",
            "producto":  "Producto creado con las claves SAT del XML.",
        }
        messagebox.showinfo("Creado", msgs.get(tipo, "Registro creado."))
        try:
            self.win_padre.destroy()
        except Exception:
            pass
        self.panel.abrir()
