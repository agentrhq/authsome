# ADR 0003: Unmatched Proxy Requests Pass Through In Local Mode

## Status

Accepted for the current local design. Revisit before hosted mode or strict egress control.

## Context

Authsome's proxy is bundled inside the CLI to make credential passing easier for local agents. Agents run with `HTTP_PROXY` and `HTTPS_PROXY` pointed at the local Authsome proxy. When an outbound HTTPS request matches a connected provider route, the proxy asks the Server to resolve credentials and injects the returned auth headers.

Not every request made by an agent is a credentialed provider request. Language runtimes, package managers, SDKs, CLIs, telemetry clients, model APIs, GitHub, documentation sites, and provider OAuth endpoints may all share the same proxy path during one agent run.

The proxy can respond to unmatched requests in at least three ways:

- pass through unchanged;
- deny unmatched traffic;
- support selectable modes such as permissive, warn, strict, or proposal-driven access.

The broader proxy design remains open. This ADR records the current local-mode behavior so it is not mistaken for an accidental default.

Agent Vault is an important comparison point: its service model allows unmatched hosts to pass by default, supports strict deny mode for vaults, supports explicit passthrough services, and can return proposal hints for unknown hosts. Authsome is not adopting that full model now, but the comparison clarifies the design space.

## Decision

For the current local-first design, unmatched proxy requests pass through unchanged.

Matched provider requests receive injected credentials. Requests that do not match a provider route are forwarded without credentials. The proxy records misses where it can classify them, but it does not block those requests by default.

## Rationale

Pass-through keeps the CLI-bundled proxy usable as an ergonomic credential broker rather than a full network policy system. It avoids breaking ordinary local agent runs where only some outbound calls need Authsome-managed credentials.

Deny-by-default would be a stronger egress-control posture, but it would also turn the proxy into a policy enforcement layer before Authsome has a settled policy model, host allowlist UX, proposal flow, or hosted authorization story. That would mix credential brokering with network firewall behavior too early.

Pass-through is therefore the least surprising local behavior: Authsome only changes requests it can confidently associate with a connected provider route.

## Consequences

The proxy is not an egress firewall in the current local design. An agent can still make outbound requests that do not use Authsome-managed credentials.

Credential exfiltration protection applies to credentials stored in Authsome and injected by matched routes. It does not prevent an agent from sending data it already knows to arbitrary destinations.

Hosted mode or stricter deployments must revisit this decision. A hosted version likely needs authorization-aware credential resolution and may need explicit unmatched-host policy such as deny, proposal, or allowlist modes.

Tests and docs should refer to this as an explicit local-mode decision, not as a missing feature.

Before this decision is reused outside local mode, Authsome also needs a header-forwarding contract, proxy credential/session-token model, netguard policy for private IP ranges and cloud metadata endpoints, DNS rebinding protection, and per-identity rate limits.
