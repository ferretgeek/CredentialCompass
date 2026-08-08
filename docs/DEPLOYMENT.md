# Deployment

Recommended order: learn the interface in demo mode, use loopback plus an SSH tunnel for real operation, and add an HTTPS reverse proxy only when a public hostname is necessary.

## Local demo

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m credential_compass --demo
```

The terminal prints the local address and an ephemeral access token. The token is not written to disk and expires when the process stops.

## Local real mode

Confirm that the CLIProxyAPI management endpoint is reachable only through a trusted network.

```bash
export COMPASS_CPA_URL="https://cliproxyapi.example.com"
export COMPASS_CPA_KEY="<set-the-management-key-locally>"
export COMPASS_ACCESS_TOKEN="$(python -m credential_compass token)"
python -m credential_compass
```

Live quota probing and status changes remain off. Enable them only after reading the compatibility and security-boundary documents:

```bash
export COMPASS_ENABLE_LIVE_PROBE=true
export COMPASS_ALLOW_STATUS_CHANGES=true
```

The application does not auto-load `.env`. Never commit real values or place them in screenshots, issues, or shell history. For a service, use a mode-`0600` environment file or a secret manager.

## Docker Compose

Create an untracked `.env` and set `COMPASS_ACCESS_TOKEN` to at least 32 characters. Compose starts in synthetic demo mode by default:

```bash
docker compose up --build
```

The port is published only on host loopback. The container is read-only, drops Linux capabilities, and has process, memory, and CPU limits. Real mode also needs `COMPASS_DEMO=false`, `COMPASS_CPA_URL`, and `COMPASS_CPA_KEY`. Private-network plain HTTP requires explicit `COMPASS_ALLOW_PRIVATE_HTTP=true`; prefer HTTPS whenever available.

## Linux + systemd

1. Create a dedicated system user and install the virtual environment at `/opt/credential-compass/.venv`.
2. Copy [`deploy/credential-compass.service`](../deploy/credential-compass.service) to `/etc/systemd/system/`.
3. Create `/etc/credential-compass.env` from [`deploy/credential-compass.env.example`](../deploy/credential-compass.env.example), fill values locally, and run `chmod 600 /etc/credential-compass.env`.
4. Adjust the service user and paths, then run `systemctl daemon-reload && systemctl enable --now credential-compass`.

Keep the service on `127.0.0.1:8788`; do not expose it directly to the public internet.

## HTTPS reverse proxy

Start from [`deploy/nginx.conf.example`](../deploy/nginx.conf.example). Replace the reserved hostname, add the same hostname to `COMPASS_ALLOWED_HOSTS`, terminate TLS at a trusted proxy, and preserve the original `Host`. Do not disable the application Host or Origin checks.

For personal remote access, an SSH tunnel is safer and simpler:

```bash
ssh -L 8788:127.0.0.1:8788 your-server
```

Then browse only to `http://127.0.0.1:8788`.

## Go-live checks

- A signed-out browser can load the static shell, while every state API returns 401.
- Invalid Hosts, cross-origin requests, and cross-port origins are rejected.
- Browser storage contains only the theme name; reload requires the access token again.
- Management keys, accounts, and upstream bodies do not appear in source, responses, logs, or screenshots.
- Live probing and status changes are enabled only when genuinely required.
