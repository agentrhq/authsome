"""Proxy-local configuration types."""

from __future__ import annotations

from typing import Literal

ProxyMode = Literal[
    "connected_allow",
    "connected_deny",
    "configured_allow",
    "configured_deny",
]
