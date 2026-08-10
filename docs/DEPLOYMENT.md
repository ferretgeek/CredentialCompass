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

Start from [`deploy/nginx.conf.example`](../deploy/nginx.conf.example). Replace the reserved hostname, add the same hostname to `COMPASS_ALLOWED_HOSTS`, terminate TLS at a trusted proxy, and preserve the original `Host`. Set `COMPASS_TRUSTED_PROXY_IPS` to the proxy's exact IP literals (normally `127.0.0.1,::1`) so rate limits use the real client. The example overwrites `X-Forwarded-For`; never trust forwarding headers from an unlisted peer. Do not disable the application Host or Origin checks.

CLIProxyAPI hostnames are resolved once during startup. Each authenticated connection is pinned to and peer-checked against that approved address set, preventing DNS changes from redirecting the management key. Restart Credential Compass intentionally after a legitimate upstream address change.

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

## Architecture and lifecycle

Credential Compass is a stateless browser panel over a Python HTTP service. The service holds the upstream management key and the panel access token in process memory, reduces upstream credential data to masked records, and does not create an application database. Browser storage contains only the selected theme.

For upgrades, keep the previous source/image and secret configuration, deploy the new version on a separate loopback port, run the go-live checks, then switch the proxy or service. Roll back by restoring the previous source/image; do not reuse an access token that was exposed during testing.

There is no application data to back up. Back up only the private environment/service configuration through your encrypted infrastructure process. Never place management keys in repository backups, screenshots, or generic log archives.

## Uninstall and troubleshooting

- Stop and disable the systemd unit or run `docker compose down`; remove the virtual environment/image only after confirming rollback is unnecessary.
- Delete `/etc/credential-compass.env` through the host's secret-removal process and clear browser site data if the saved theme is no longer wanted.
- `401`: re-enter the panel access token; it is intentionally not persisted by the page.
- `403` Host/Origin error: use the configured hostname and same-origin page; do not disable the checks.
- Inventory unavailable: verify the CLIProxyAPI management URL/key from the service account without printing either value.
- Probe unavailable while inventory works: keep probing disabled and recheck [`COMPATIBILITY.md`](./COMPATIBILITY.md); the probe path is optional and less stable.
- Health endpoint failure: inspect the service status and private logs, then redact endpoints, account handles, keys, and upstream bodies before sharing diagnostics.

Stop/disable the service before removal, delete secrets through the host's secret-management process, and clear browser site data only if desired. Preserve Host/Origin and authentication checks when troubleshooting; never solve connectivity by exposing the panel or logging secrets.
