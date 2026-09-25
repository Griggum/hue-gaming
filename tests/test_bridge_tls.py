"""Exercise actual TLS handshakes, without a Hue device or committed private keys."""

import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from hue_core.hue import Bridge, BridgeError
from hue_core.models import BridgeConfig

BRIDGE_ID = "001788fffe123abc"


def certificate(name, key, issuer=None, issuer_key=None, *, expired=False):
    now = datetime.now(UTC)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    ca = issuer is None
    signer = issuer_key or key
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer.subject if issuer else subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=2))
        .not_valid_after(now + timedelta(days=-1 if expired else 30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, ca, ca, False, False),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(signer.public_key()), False
        )
    )
    if not ca:
        # Deliberately CN-only, like Hue certificates; no IP SAN.
        builder = builder.add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False
        )
    return builder.sign(signer, hashes.SHA256())


@pytest.fixture
def tls_bridge(tmp_path, monkeypatch, request):
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca = certificate("Test Hue CA", ca_key)
    key = ec.generate_private_key(ec.SECP256R1())
    leaf = certificate(
        BRIDGE_ID, key, ca, ca_key, expired=getattr(request, "param", None) == "expired"
    )
    ca_path = tmp_path / "ca.pem"
    cert_path = tmp_path / "bridge.pem"
    key_path = tmp_path / "key.pem"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(
                (self.path, self.headers.get("Host"), self.headers.get("hue-application-key"))
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"data": [], "errors": []}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connect = socket.create_connection

    def local_connection(address, *args, **kwargs):
        assert address == ("192.168.10.128", 443)
        return connect(server.server_address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", local_connection)
    try:
        yield ca_path, received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_hue_ca_and_bridge_id_verify_cn_certificate(tls_bridge):
    ca_path, received = tls_bridge
    bridge = Bridge(
        "192.168.10.128",
        "test-key",
        BridgeConfig(ca_file=str(ca_path), bridge_id=BRIDGE_ID.upper()),
    )
    try:
        assert bridge.lights() == []
    finally:
        bridge.close()
    assert received == [("/clip/v2/resource/light", BRIDGE_ID, "test-key")]


@pytest.mark.parametrize("failure", ["wrong_id", "untrusted", "ip_name"])
def test_tls_failure_sends_no_credentials_and_never_falls_back(tls_bridge, failure):
    ca_path, received = tls_bridge
    config = BridgeConfig(
        ca_file=None if failure == "untrusted" else str(ca_path),
        bridge_id=None
        if failure == "ip_name"
        else ("001788fffe000000" if failure == "wrong_id" else BRIDGE_ID),
    )
    bridge = Bridge("192.168.10.128", "test-key", config)
    try:
        with pytest.raises(BridgeError, match="TLS configuration"):
            bridge.lights()
    finally:
        bridge.close()
    assert received == []


@pytest.mark.parametrize("tls_bridge", ["expired"], indirect=True)
def test_expired_certificate_is_rejected(tls_bridge):
    ca_path, received = tls_bridge
    bridge = Bridge(
        "192.168.10.128", "test-key", BridgeConfig(ca_file=str(ca_path), bridge_id=BRIDGE_ID)
    )
    try:
        with pytest.raises(BridgeError):
            bridge.lights()
    finally:
        bridge.close()
    assert received == []


@pytest.mark.parametrize("bridge_id", ["", "bridge.local", "001788", "g" * 16, "a" * 16 + "\n"])
def test_invalid_bridge_id_rejected(bridge_id):
    with pytest.raises(ValueError):
        BridgeConfig(bridge_id=bridge_id)
