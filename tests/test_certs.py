import hashlib
import socket
import ssl
import urllib.request

import pytest

from src.lib.certs import (
    EXTRA_INTERMEDIATES,
    build_ssl_context,
    ca_bundle_path,
    requests_verify,
)

EXPECTED_FINGERPRINT = (
    "C8:02:5F:9F:C6:5F:DF:C9:5B:3C:A8:CC:78:67:B9:A5:"
    "87:B5:27:79:73:95:79:17:46:3F:C8:13:D0:B6:25:A9"
)
MEATH_SPC_PAGE = (
    "https://www.meath.ie/council/your-council/your-elected-council/"
    "strategic-policy-committees/transportation-and-urban-regeneration-spc"
)


def _pem_fingerprint(path) -> str:
    pem = path.read_text(encoding="ascii")
    der = ssl.PEM_cert_to_DER_cert(pem)
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i:i + 2] for i in range(0, len(digest), 2))


def test_extra_intermediate_fingerprint_is_pinned():
    """The committed intermediate is the DigiCert Global G2 TLS RSA SHA256 2020 CA1."""
    assert _pem_fingerprint(EXTRA_INTERMEDIATES) == EXPECTED_FINGERPRINT


def test_build_ssl_context_still_verifies():
    context = build_ssl_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_combined_bundle_contains_roots_and_intermediate():
    bundle = ca_bundle_path()
    text = bundle.read_text(encoding="ascii")
    assert "BEGIN CERTIFICATE" in text
    # The intermediate's fingerprint proves it is in the combined file.
    der = ssl.PEM_cert_to_DER_cert(EXTRA_INTERMEDIATES.read_text(encoding="ascii"))
    assert ssl.DER_cert_to_PEM_cert(der).strip() in text
    assert requests_verify() == str(bundle)


def _online() -> bool:
    try:
        with socket.create_connection(("www.meath.ie", 443), timeout=5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _online(), reason="offline: cannot reach www.meath.ie")
def test_meath_page_fetches_with_verification_on():
    with urllib.request.urlopen(MEATH_SPC_PAGE, context=build_ssl_context(), timeout=30) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8", "replace")
    assert "Transportation and Urban Regeneration" in body
