"""Local certificate trust helpers for the auth proxy."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from loguru import logger

from authsome.cli.config import load_client_config, save_client_config


def ensure_local_proxy_ca(home: Path) -> None:
    """Ensure local proxy trust setup has run at most once per client home."""
    config = load_client_config(home)
    if config.proxy_ca_installed:
        return

    if _ensure_macos_keychain_ca():
        config.proxy_ca_installed = True
        save_client_config(home, config)


def _ensure_macos_keychain_ca() -> bool:
    """Ensure the mitmproxy CA is generated and trusted in the macOS login keychain.

    Go's crypto/x509 on macOS uses the native Security framework and ignores
    ``SSL_CERT_FILE``, so Go-based tools only trust the proxy CA once it is
    added to the login keychain on the local machine.
    """
    if sys.platform != "darwin":
        return True

    keychain = Path.home() / "Library/Keychains/login.keychain-db"
    if not keychain.exists():
        return True

    check = subprocess.run(
        ["security", "find-certificate", "-c", "mitmproxy", str(keychain)],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        logger.debug("mitmproxy CA already present in macOS login keychain; skipping add")
        return True

    confdir = Path.home() / ".mitmproxy"
    ca_cert_path = confdir / "mitmproxy-ca-cert.pem"
    if not ca_cert_path.exists():
        try:
            from mitmproxy.certs import CertStore

            CertStore.from_store(confdir, "mitmproxy", 2048)
            logger.debug("Generated mitmproxy CA certificate at {}", ca_cert_path)
        except Exception as exc:
            logger.debug("Failed to generate mitmproxy CA certificate: {}", exc)
            return False

    if not ca_cert_path.exists():
        return False

    result = subprocess.run(
        [
            "security",
            "add-trusted-cert",
            "-d",
            "-r",
            "trustRoot",
            "-k",
            str(keychain),
            str(ca_cert_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode == 0:
        logger.debug("Added mitmproxy CA to macOS login keychain")
        return True

    logger.warning(
        "Could not add mitmproxy CA to macOS login keychain"
        " (Go-based tools like gh/terraform/kubectl may fail with TLS errors): {}",
        result.stderr.strip() or result.stdout.strip(),
    )
    return False
