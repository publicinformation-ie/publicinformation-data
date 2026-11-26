"""TLS verification that also accepts public intermediate certificates.

Some public-body servers (notably ``www.meath.ie``) omit an intermediate CA
from the chain they send. macOS completes the chain itself; OpenSSL on Linux
and CI does not, so verification fails. The fix is to load the public
intermediate as an extra verification certificate, never to disable
verification. See ``extra_intermediates.pem`` and its README.

Use:

    requests.get(url, verify=str(requests_verify()))

or, with the standard library:

    urllib.request.urlopen(url, context=build_ssl_context())
"""
from __future__ import annotations

import atexit
import os
import ssl
import tempfile
from pathlib import Path

import certifi

CERT_DIR = Path(__file__).resolve().parent
EXTRA_INTERMEDIATES = CERT_DIR / "extra_intermediates.pem"

_bundle_path: Path | None = None


def build_ssl_context() -> ssl.SSLContext:
    """A verifying SSL context: the default trust store plus our intermediates."""
    context = ssl.create_default_context(cafile=certifi.where())
    context.load_verify_locations(cafile=str(EXTRA_INTERMEDIATES))
    return context


def ca_bundle_path() -> Path:
    """Path to a combined PEM bundle of certifi's roots and our intermediates.

    The bundle is built once per process and removed at exit. ``requests``
    takes a single CA file, so the roots and the intermediate must be
    concatenated.
    """
    global _bundle_path
    if _bundle_path is None:
        fd, name = tempfile.mkstemp(prefix="publicinformation-ca-", suffix=".pem")
        with os.fdopen(fd, "w", encoding="ascii") as handle:
            handle.write(Path(certifi.where()).read_text(encoding="ascii"))
            handle.write("\n")
            handle.write(EXTRA_INTERMEDIATES.read_text(encoding="ascii"))
        _bundle_path = Path(name)
        atexit.register(_remove_bundle)
    return _bundle_path


def requests_verify() -> str:
    """The ``verify=`` value for ``requests`` calls that need the extra chain."""
    return str(ca_bundle_path())


def _remove_bundle() -> None:
    if _bundle_path is not None:
        try:
            _bundle_path.unlink()
        except FileNotFoundError:
            pass
