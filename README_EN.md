<div align="center">

# Credential Compass · 凭证罗盘

Bring scattered credentials back onto one clear chart.

[![CI](https://github.com/ferretgeek/CredentialCompass/actions/workflows/ci.yml/badge.svg)](https://github.com/ferretgeek/CredentialCompass/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ferretgeek/CredentialCompass/actions/workflows/codeql.yml/badge.svg)](https://github.com/ferretgeek/CredentialCompass/actions/workflows/codeql.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-287f87)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-5f7f55.svg)](LICENSE)

[简体中文](README.md) · [Deployment](docs/DEPLOYMENT.md) · [Security boundary](docs/SECURITY-BOUNDARY.md) · [Compatibility](docs/COMPATIBILITY.md)

![Credential Compass dashboard](docs/images/dashboard.png)

</div>

Credential Compass is a quiet health workbench for CLIProxyAPI-managed credential pools. It inventories enablement, optionally observes a narrow quota outline, and gives the browser only classified health signals.

## Deliberately less powerful

- The management key stays in server-process memory. The browser cannot read or edit the upstream address or key.
- Accounts are masked by default. Raw tokens, upstream bodies, credential files, and real identifiers never enter the browser, logs, or disk.
- Read-only by default. Reversible enable/disable controls require operator opt-in and an exact confirmation phrase for every action.
- No deletion, credential ZIP export, arbitrary request proxy, telemetry, or third-party front-end assets.
- Four global themes: Sky, Jade, Sunset, and Graphite. Graphite uses a deep-gray `#17191d` background.

## See it in three minutes

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m credential_compass --demo
```

Open the local address printed in the terminal and enter the one-time access token. Demo mode uses only reserved `example.com`, `example.net`, and `example.org` identities and never touches a real account.

See [Deployment](docs/DEPLOYMENT.md) for real mode, Docker, reverse proxy, and systemd examples. The optional live quota probe uses a compatibility endpoint and is off by default; read [Compatibility](docs/COMPATIBILITY.md) before enabling it.

## Scope

This is an independent community project and is not affiliated with or endorsed by OpenAI. It does not sign in to Codex and does not accept OpenAI API keys or ChatGPT login credentials. It only connects to the CLIProxyAPI management endpoint fixed by the operator at startup.

## Development checks

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Use GitHub Private vulnerability reporting for security issues. Never place real accounts, tokens, management URLs, logs, or screenshots in a public issue.
