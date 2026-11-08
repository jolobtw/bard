"""Bard: Arcane Terminal YouTube Music Player."""

from __future__ import annotations

import os

# On macOS, Python often lacks trusted root certificates unless Install Certificates.command
# was manually executed. Point SSL_CERT_FILE and REQUESTS_CA_BUNDLE to certifi's bundle so
# HTTPS requests to Google OAuth and YouTube Music succeed seamlessly out of the box.
try:
    import certifi

    _ca_bundle = certifi.where()
    if os.path.exists(_ca_bundle):
        os.environ.setdefault("SSL_CERT_FILE", _ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca_bundle)
except Exception:
    pass

__version__ = "0.1.0"
