"""Proxy-local configuration types."""

from typing import Literal

ProxyMode = Literal[
    "connected_allow",
    "connected_deny",
    "configured_allow",
    "configured_deny",
]
