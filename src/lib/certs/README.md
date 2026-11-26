# Extra intermediate certificates

`extra_intermediates.pem` holds public intermediate CA certificates that some
public-body servers fail to send. Trust stores on macOS fetch a missing
intermediate on their own; OpenSSL on Linux and CI does not, so certificate
verification fails even though the server's chain is valid. Loading this file
as an extra verification certificate lets the chain build while verification
stays on.

## DigiCert Global G2 TLS RSA SHA256 2020 CA1

| Field | Value |
|---|---|
| Subject | `CN=DigiCert Global G2 TLS RSA SHA256 2020 CA1, OU=www.digicert.com, O=DigiCert Inc, C=US` |
| Issuer | `CN=DigiCert Global Root G2, OU=www.digicert.com, O=DigiCert Inc, C=US` |
| Valid from | 2021-03-30 |
| Valid to | 2031-03-29 |
| SHA-256 fingerprint | `C8:02:5F:9F:C6:5F:DF:C9:5B:3C:A8:CC:78:67:B9:A5:87:B5:27:79:73:95:79:17:46:3F:C8:13:D0:B6:25:A9` |
| Source | <https://cacerts.digicert.com/DigiCertGlobalG2TLSRSASHA2562020CA1-1.crt> (DER; converted with `openssl x509 -inform DER -outform PEM`) |

`www.meath.ie` serves its leaf certificate and the DigiCert Global Root G2 but
not this intermediate, so the pipeline supplies it (see
`openspec/changes/archive/2026-11-26-add-spc-minutes-pipeline/design.md` D10).

## Helper

`src/lib/certs/__init__.py` provides:

- `build_ssl_context()` — an `ssl.SSLContext` built from the certifi default
  trust store plus this file.
- `ca_bundle_path()` and `requests_verify()` — a combined CA bundle for
  `requests(..., verify=...)`.

`tests/test_certs.py` pins the fingerprint above, so replacing the file
without updating this README fails the suite.
