<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/authsome-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/authsome-logo-light.svg">
    <img alt="Authsome" src="assets/authsome-logo-light.svg" height="60">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/authsome/"><img src="https://img.shields.io/pypi/v/authsome.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/authsome/"><img src="https://img.shields.io/pypi/pyversions/authsome.svg" alt="Python 3.13+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://pypi.org/project/authsome/"><img src="https://img.shields.io/pypi/dm/authsome.svg" alt="PyPI downloads"></a>
  <a href="https://github.com/agentrhq/authsome/actions/workflows/python-test.yml"><img src="https://github.com/agentrhq/authsome/actions/workflows/python-test.yml/badge.svg" alt="Tests"></a>
  <a href="https://codecov.io/gh/agentrhq/authsome"><img src="https://codecov.io/gh/agentrhq/authsome/branch/main/graph/badge.svg" alt="codecov"></a>
  <a href="https://discord.gg/9YP2C9tvMp"><img src="https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
</p>

<p align="center">
  <b>Credential Gateway for AI Agents</b>
</p>

<p align="center">
  <a href="https://authsome.ai/docs">Docs</a> ·
  <a href="https://authsome.ai">Website</a> ·
  <a href="https://discord.gg/9YP2C9tvMp">Discord</a> ·
  <a href="https://github.com/agentrhq/authsome/issues">Issues</a>
</p>

---

An open-source credential gateway that sits between your agents and the services they call. Instead of sharing credentials with every agent, log in once via OAuth2 or API keys. Authsome stores credentials securely and injects them via an HTTP proxy. You get one place to manage access, rotate keys, and see what every agent is doing.

Bundled providers out of the box — OAuth2 and API key. [See the full list](https://authsome.ai/docs/reference/bundled-providers).

---

## Demo

https://github.com/user-attachments/assets/27f9b229-baf4-4889-be9a-378a133654dc

---

## Why Agents Need Authsome

Agents run beyond interactive sessions. They live in CI, over SSH, in cron jobs, in background workers, and in parallel pipelines. They need API access that survives without a human in the loop.

Hardcoded environment tokens leak or go stale, and building auth flow logic, token storage, refresh handling, and per-provider config into every project rebuilds the same plumbing every time.

Authsome is the credential broker agents call at runtime.

- **No credential sprawl.** One encrypted store. Every provider, every agent, one place.
- **Agents never see credentials.** Auth is handled outside the agent process — no exfiltration risk, no secrets in environment variables.
- **No browser required at runtime.** Setup can use browser PKCE, device code, or a browser bridge for secure API key entry. After that, agents run headlessly.

---

## How It Works

The CLI is the agent's interface: setup once, then inject fresh credentials whenever a tool runs.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/authsome-how-it-works-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="assets/authsome-how-it-works-light.svg">
  <img alt="Authsome Architecture" src="assets/authsome-how-it-works-light.svg" width="100%">
</picture>

Authenticate once:

```bash
authsome login github
# This opens a browser on user's machine
# user completes login without sharing the creds with the agent.
```

Then agents get valid credentials on demand when they try to access external services.
All they need to do is use `authsome run --` before the command they want to run:

```bash
authsome run -- curl -s "https://api.github.com/user/repos?per_page=10"
# runs behind an auth proxy that injects headers at request time
# without exposing secrets in the child process environment.
# matched automatically via provider api_url (e.g. api.openai.com)
```

Credentials are encrypted at rest and refreshed before expiry.

---

## Why Authsome

| | authsome | Hardcoded env tokens | DIY |
|--|:--------:|:--------------------:|:---:|
| Automatic token refresh | ✅ | ❌ | build it |
| OAuth2 + API keys | ✅ | ❌ | build it |
| Runtime headless use | ✅ | ✅ | varies |
| Built-in providers, zero config | ✅ | ❌ | ❌ |
| Multi-account per provider | ✅ | ❌ | build it |
| Agents never see credentials | ✅ | ❌ | build it |

Authsome gives agents one command for a valid token, without scattering long-lived secrets across every project.

---

## Install

Requires Python 3.13+.

```bash
uv tool install authsome
```

## Self-hosting

Run a persistent daemon in Docker — no Python required on the host:

```bash
export AUTHSOME_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
export AUTHSOME_MASTER_KEY="$(openssl rand -base64 32)"
export AUTHSOME_UI_SESSION_KEY="$(openssl rand -base64 32)"
docker compose up -d
curl http://localhost:7998/health
```

For a hosted daemon, set `AUTHSOME_BASE_URL` to the public HTTPS URL before starting the stack. See the [self-hosting guide](docs/guides/self-hosting.md) for first-run setup, volume backup, TLS termination, and environment variable reference.

## Quick Start

Install and run first-time setup (identity, claim, and API key import from `.env`):

```bash
authsome onboard
```

For a remote daemon, pass `--base-url` once — it is saved in client config for later commands:

```bash
authsome onboard --base-url https://authsome.example.com
```

Add the authsome skill to your agent (claude, codex, cursor, hermes, etc.):

```bash
npx skills add agentrhq/authsome
```

And try a sample task that requires access to external services:

```
Star the repo agentrhq/authsome
```
```
Get my last 5 emails from gmail
```
```
Check my stripe balance
```

The agent will use authsome to login into external services and perform the task.

## Agent Integrations

Authsome ships with adapters for the most common agent frameworks and CLIs:

- [Claude Code](https://authsome.ai/docs/integrations/agents/claude-code)
- [Codex](https://authsome.ai/docs/integrations/agents/codex)
- [Cursor](https://authsome.ai/docs/integrations/agents/cursor)
- [OpenCode](https://authsome.ai/docs/integrations/agents/opencode)
- [LangChain](https://authsome.ai/docs/integrations/agents/langchain)
- [LlamaIndex](https://authsome.ai/docs/integrations/agents/llamaindex)
- [OpenAI Agents SDK](https://authsome.ai/docs/integrations/agents/openai-agents-sdk)
- [Anthropic SDK](https://authsome.ai/docs/integrations/agents/anthropic-sdk)

Full list at [authsome.ai/docs/integrations](https://authsome.ai/docs/integrations/agents/index).

## Community

- **[Discord](https://discord.gg/9YP2C9tvMp)** for questions, help, and showing what you're building.
- **[GitHub Issues](https://github.com/agentrhq/authsome/issues)** for bugs and feature requests.

## Roadmap

See [authsome.ai/docs/roadmap](https://authsome.ai/docs/roadmap) for what's shipped, what's next, and what's out of scope.

## Contributing

- **Found a bug?** [Open an issue](https://github.com/agentrhq/authsome/issues/new?template=bug_report.md)
- **Have an idea?** [Start a discussion](https://github.com/agentrhq/authsome/discussions/new?category=ideas)
- **Want to contribute?** Read [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and the engineering principles we follow.

## Links

- **Website:** [authsome.ai](https://authsome.ai)
- **Docs:** [authsome.ai/docs](https://authsome.ai/docs)
- **Discord:** [discord.gg/9YP2C9tvMp](https://discord.gg/9YP2C9tvMp)
- **Issues:** [github.com/agentrhq/authsome/issues](https://github.com/agentrhq/authsome/issues)

## Star History

<a href="https://star-history.com/#agentrhq/authsome&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=agentrhq/authsome&type=Date&theme=dark">
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=agentrhq/authsome&type=Date">
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=agentrhq/authsome&type=Date">
  </picture>
</a>

## License

MIT. See [LICENSE](LICENSE).
