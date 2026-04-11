# -*- coding: utf-8 -*-
"""
core/cfdi.py
Parser canónico de archivos CFDI 3.3 / 4.0.
Sin dependencias de UI ni de frameworks web.
"""
import xml.etree.ElementTree as ET


def _attr(el, name, default=""):
    return el.get(name, default) if el is not None else default


def _parsear_root(root) -> dict:
    """Extrae todos los campos de un elemento raíz XML de CFDI ya parseado."""
    tag = root.tag
    if "cfd/4" in tag:
        ns_cfdi = "http://www.sat.gob.mx/cfd/4"
    elif "cfd/3" in tag:
        ns_cfdi = "http://www.sat.gob.mx/cfd/3"
    else:
        raise ValueError(
            "El archivo no parece ser un CFDI SAT válido. "
            "Se esperaba namespace cfdi/3 o cfdi/4."
        )

    def find(path):
        return root.find(path.replace("{cfdi}", f"{{{ns_cfdi}}}"))

    # ── Comprobante ───────────────────────────────────────────────────────────
    version     = root.get("Version", root.get("version", ""))
    serie       = root.get("Serie", "")
    folio       = root.get("Folio", "")
    fecha       = root.get("Fecha", "")
    subtotal    = float(root.get("SubTotal", 0) or 0)
    descuento   = float(root.get("Descuento", 0) or 0)
    total       = float(root.get("Total", 0) or 0)
    tipo        = root.get("TipoDeComprobante", "")
    metodo_pago = root.get("MetodoPago", "")
    forma_pago  = root.get("FormaPago", "")
    moneda      = root.get("Moneda", "MXN")

    # ── IVA ───────────────────────────────────────────────────────────────────
    iva = 0.0
    imp = find("{cfdi}Impuestos")
    if imp is not None:
        iva = float(imp.get("TotalImpuestosTrasladados", 0) or 0)

    # ── Emisor ────────────────────────────────────────────────────────────────
    emisor         = find("{cfdi}Emisor")
    rfc_emisor     = _attr(emisor, "Rfc")
    nombre_emisor  = _attr(emisor, "Nombre")
    regimen_fiscal = _attr(emisor, "RegimenFiscal")

    # ── Receptor ──────────────────────────────────────────────────────────────
    receptor        = find("{cfdi}Receptor")
    rfc_receptor    = _attr(receptor, "Rfc")
    nombre_receptor = _attr(receptor, "Nombre")
    uso_cfdi        = _attr(receptor, "UsoCFDI")

    # ── Timbre Fiscal Digital ─────────────────────────────────────────────────
    ns_tfd = "http://www.sat.gob.mx/TimbreFiscalDigital"
    complemento = find("{cfdi}Complemento")
    uuid = fecha_timbrado = no_cert_sat = ""
    if complemento is not None:
        tfd = complemento.find(f"{{{ns_tfd}}}TimbreFiscalDigital")
        if tfd is not None:
            uuid           = tfd.get("UUID", "")
            fecha_timbrado = tfd.get("FechaTimbrado", "")
            no_cert_sat    = tfd.get("NoCertificadoSAT", "")

    if not uuid:
        raise ValueError(
            "No se encontró el UUID (Timbre Fiscal Digital). "
            "El XML no está timbrado o no es un CFDI válido."
        )

    # ── Conceptos ─────────────────────────────────────────────────────────────
    conceptos = []
    for c in root.findall(f".//{{{ns_cfdi}}}Concepto"):
        conceptos.append({
            "clave_prod_serv":   c.get("ClaveProdServ", ""),
            "no_identificacion": c.get("NoIdentificacion", ""),
            "cantidad":          float(c.get("Cantidad", 0) or 0),
            "clave_unidad":      c.get("ClaveUnidad", ""),
            "unidad":            c.get("Unidad", ""),
            "descripcion":       c.get("Descripcion", ""),
            "valor_unitario":    float(c.get("ValorUnitario", 0) or 0),
            "importe":           float(c.get("Importe", 0) or 0),
            "descuento":         float(c.get("Descuento", 0) or 0),
        })

    return {
        "version":         version,
        "serie":           serie,
        "folio":           folio,
        "fecha":           fecha,
        "fecha_timbrado":  fecha_timbrado,
        "uuid":            uuid,
        "no_cert_sat":     no_cert_sat,
        "rfc_emisor":      rfc_emisor,
        "nombre_emisor":   nombre_emisor,
        "regimen_fiscal":  regimen_fiscal,
        "rfc_receptor":    rfc_receptor,
        "nombre_receptor": nombre_receptor,
        "uso_cfdi":        uso_cfdi,
        "subtotal":        subtotal,
        "descuento":       descuento,
        "iva":             iva,
        "total":           total,
        "tipo":            tipo,
        "metodo_pago":     metodo_pago,
        "forma_pago":      forma_pago,
        "moneda":          moneda,
        "conceptos":       conceptos,
    }


def parsear_cfdi(ruta_xml: str) -> dict:
    """
    Parsea un CFDI (3.3 o 4.0) desde ruta de archivo.
    Lanza ValueError si el XML no es válido o no está timbrado.
    """
    try:
        root = ET.parse(ruta_xml).getroot()
    except ET.ParseError as e:
        raise ValueError(f"El archivo no es un XML válido: {e}")
    return _parsear_root(root)


def parsear_cfdi_bytes(contenido: bytes) -> dict:
    """Igual que parsear_cfdi pero recibe bytes en lugar de ruta."""
    try:
        root = ET.fromstring(contenido)
    except ET.ParseError as e:
        raise ValueError(f"El archivo no es un XML válido: {e}")
    return _parsear_root(root)
