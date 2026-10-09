"""Generate LOCAL research TLS files only. Never edits system trust, DNS or game files."""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
from pathlib import Path


def generate(directory: str | Path) -> Path:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from backend.application import SERVICES

    directory = Path(directory)
    # Fail closed rather than replacing the keys of an existing installation.
    if directory.exists():
        raise FileExistsError('TLS output directory already exists; refusing overwrite')
    now = dt.datetime.now(dt.timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Reawakened LOCAL Research CA')])

    def builder(subject, public_key):
        return (x509.CertificateBuilder().subject_name(subject).issuer_name(root_name)
                .public_key(public_key).serial_number(x509.random_serial_number())
                .not_valid_before(now - dt.timedelta(minutes=5))
                .not_valid_after(now + dt.timedelta(days=30)))

    def usage(ca):
        return x509.KeyUsage(digital_signature=True, content_commitment=False,
                             key_encipherment=not ca, data_encipherment=False,
                             key_agreement=False, key_cert_sign=ca, crl_sign=ca,
                             encipher_only=False, decipher_only=False)

    root = (builder(root_name, root_key.public_key())
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(usage(True), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    names = [x509.DNSName(s + '.steelyard.ca') for s in sorted(SERVICES)]
    names += [x509.DNSName('steelyard.online'), x509.DNSName('localhost'),
              x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
              x509.IPAddress(ipaddress.ip_address('::1'))]
    leaf = (builder(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]), leaf_key.public_key())
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(usage(False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(x509.SubjectAlternativeName(names), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    values = {
        'ca.pem': root.public_bytes(serialization.Encoding.PEM),
        'server.pem': leaf.public_bytes(serialization.Encoding.PEM),
        'server-key.pem': leaf_key.private_bytes(serialization.Encoding.PEM,
                                                serialization.PrivateFormat.PKCS8,
                                                serialization.NoEncryption()),
    }
    for name, value in values.items():
        fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(value)
    # Root private key is deliberately never written to disk.
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default='local-data/tls')
    args = parser.parse_args()
    generate(args.out)
    print('Local TLS files created. No system trust, hosts file or game files changed.')
    print('Do not publish local-data or any private keys. Do not import this CA into Windows.')
