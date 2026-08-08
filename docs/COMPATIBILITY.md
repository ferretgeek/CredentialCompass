# Compatibility

Credential Compass targets Codex credential pools managed by CLIProxyAPI. It is neither an OpenAI product nor a Codex sign-in tool.

## Two capability layers

- **Inventory layer (default):** reads the CLIProxyAPI credential inventory and enablement state, then creates masked accounts and opaque handles.
- **Probe layer (optional):** asks CLIProxyAPI's management `api-call` feature to reach one fixed ChatGPT usage endpoint, then reduces the response to health and quota signals.

The probe depends on a compatibility path that is not promised as a stable public API. It may break as upstream services evolve, so `COMPASS_ENABLE_LIVE_PROBE=false` is the default. Inventory remains useful when probing is off.

Reversible enable/disable controls also depend on CLIProxyAPI management behavior and are disabled by `COMPASS_ALLOW_STATUS_CHANGES=false`. After a CLIProxyAPI upgrade, validate inventory, probing, and status changes with isolated synthetic or low-risk accounts before production use.

Codex officially supports ChatGPT sign-in and API-key authentication. Follow the [official OpenAI Codex authentication documentation](https://learn.chatgpt.com/docs/auth). Never submit an OpenAI API key, ChatGPT cookie, or login token to Credential Compass.

## Tested runtime range

- Python 3.10–3.13
- Current Chromium-family browsers, Firefox, and Safari
- A CLIProxyAPI management endpoint reachable from the Credential Compass server process

CLIProxyAPI and compatibility endpoints evolve. Treat CI, release notes, and your own isolated deployment validation as the final compatibility check.
