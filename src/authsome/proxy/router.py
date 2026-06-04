"""Route match result type for proxy routing."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RouteMatch:
    """Result of a successful route resolution."""

    provider: str
    connection: str | None = None


@dataclass(frozen=True)
class RouteResolution:
    """Outcome of routing one proxied HTTPS request to a provider connection."""

    match: RouteMatch | None
    miss_reason: Literal["no_match", "ambiguous"] | None = None
