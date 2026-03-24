# -*- coding: utf-8 -*-
"""
ui/utils.py
Helpers de UI compartidos por todos los módulos y vistas.
"""


def centrar_ventana(win, padre=None, ancho=None, alto=None):
    """Centra una ventana respecto a su padre o pantalla."""
    win.withdraw()
    if ancho and alto:
        win.geometry(f"{ancho}x{alto}")
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    if padre:
        x = padre.winfo_rootx() + (padre.winfo_width()  - w) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - h) // 2
    else:
        x = (win.winfo_screenwidth()  - w) // 2
        y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"+{max(0,x)}+{max(0,y)}")
    win.after(0, win.deiconify)


def campo_error(entry, msg_label, mensaje):
    """Marca un Entry con borde rojo y muestra mensaje de error en msg_label.
    Devuelve False para usar en: if not campo_error(...): return
    """
    entry.configure(highlightbackground='#dc2626', highlightcolor='#dc2626',
                    highlightthickness=2)
    if msg_label:
        msg_label.configure(text=mensaje, fg='#dc2626')
    entry.focus()
    return False


def campo_ok(entry, msg_label=None):
    """Limpia el estado de error de un Entry."""
    entry.configure(highlightthickness=0)
    if msg_label:
        msg_label.configure(text='')
