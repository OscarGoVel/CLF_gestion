#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/generar_cert.py
Genera un certificado SSL autofirmado para uso interno en la red local.

Uso:
    cd "c:/Users/oscar/OneDrive/Documentos/CLF Sistema/Gestion-CLF"
    python tools/generar_cert.py

Genera:
    ssl/server.key  → clave privada RSA 2048
    ssl/server.crt  → certificado X.509 valido 2 anos

El certificado incluye el IP del servidor (192.168.0.40) y localhost
como Subject Alternative Names para que los navegadores lo acepten.
"""

import ipaddress
import datetime
import sys
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
except ImportError:
    print("ERROR: instala cryptography:  pip install cryptography")
    sys.exit(1)

# ── Configuracion ─────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
SSL_DIR  = ROOT / "ssl"
CERT_CRT = SSL_DIR / "server.crt"
CERT_KEY = SSL_DIR / "server.key"

# IPs y nombres que el certificado cubrira
SERVER_IP   = "192.168.0.40"
EXTRA_IPS   = ["127.0.0.1"]
EXTRA_NAMES = ["localhost"]
ORG_NAME    = "CLF Sistema"
COMMON_NAME = "CLF Gestion"
VALIDITY_DAYS = 730   # 2 anos


def generar():
    SSL_DIR.mkdir(exist_ok=True)

    print("Generando clave privada RSA 2048...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # SANs: IPs
    san_ips   = [x509.IPAddress(ipaddress.IPv4Address(SERVER_IP))]
    san_ips  += [x509.IPAddress(ipaddress.IPv4Address(ip)) for ip in EXTRA_IPS]
    san_names = [x509.DNSName(n) for n in EXTRA_NAMES]

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME,         COMMON_NAME),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME,   ORG_NAME),
        x509.NameAttribute(NameOID.COUNTRY_NAME,        "MX"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)

    print(f"Generando certificado (valido {VALIDITY_DAYS} dias)...")
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(san_ips + san_names),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    # Guardar clave privada
    CERT_KEY.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    # Guardar certificado
    CERT_CRT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    print(f"\n  Clave:        {CERT_KEY}")
    print(f"  Certificado:  {CERT_CRT}")
    print(f"  Valido hasta: {(now + datetime.timedelta(days=VALIDITY_DAYS)).strftime('%Y-%m-%d')}")
    print(f"  SANs:         {SERVER_IP}, {', '.join(EXTRA_IPS + EXTRA_NAMES)}")
    print()
    print("Para que el navegador confie en el certificado:")
    print("  Chrome/Edge: abre https://192.168.0.40:8443 > 'Avanzado' > 'Continuar'")
    print("  O importa ssl/server.crt en: Configuracion > Certificados > Entidades de confianza")


if __name__ == "__main__":
    generar()
