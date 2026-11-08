"""Bard: Arcane Terminal YouTube Music Player."""

from __future__ import annotations

import os

# 1. On macOS and Windows, hook into the operating system's native certificate store
# (Keychain on macOS, CryptoAPI on Windows). This avoids SSL verification failures
# regardless of how Python was installed (Homebrew, python.org, Xcode, or pyenv).
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

# 2. Point SSL_CERT_FILE and REQUESTS_CA_BUNDLE to certifi's bundle as a fallback.
try:
    import certifi

    _ca_bundle = certifi.where()
    if os.path.exists(_ca_bundle):
        os.environ.setdefault("SSL_CERT_FILE", _ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle)
except Exception:
    pass

__version__ = "0.2.0"
