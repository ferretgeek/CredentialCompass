# Security boundary

Credential Compass is designed under two assumptions: the browser may be hostile, and a public repository will be scanned byte by byte.

## Data flow

1. The operator fixes the CLIProxyAPI root URL and management key in the process environment.
2. The server calls fixed management routes only, never follows redirects, and reads at most 512 KiB per response.
3. Raw credential-file identifiers become process-local HMAC handles immediately; accounts are masked by default.
4. Optional probe responses are reduced in memory to health, plan, usage, and reset signals; raw bodies are discarded.
5. The browser receives only opaque handles, an account view, and classified results. Its access token stays in page memory.

## Default gates

- Loopback listener. A non-loopback bind requires an access token of at least 32 characters and an exact Host allowlist.
- Host, Origin (including port), and `Sec-Fetch-Site` checks; no CORS; CSP, anti-framing headers, and rate limits.
- 32 KiB request bodies, 512 KiB upstream responses, at most 10,000 accounts, concurrency at most 8, and timeout at most 30 seconds.
- Plain HTTP is loopback-only by default. Private-network HTTP requires explicit opt-in; public traffic should use HTTPS.
- Live probing and status changes are both off by default. Status changes are reversible, limited to 50 records, and require exact `DISABLE N` or `ENABLE N` confirmation.

## Intentionally absent

- Reading or exporting raw tokens, credential files, upstream bodies, real file identifiers, or the management key.
- Arbitrary URL proxying, browser-editable upstream settings, redirect following, bulk ZIP export, or irreversible deletion.
- Access tokens in cookies or browser storage, telemetry, third-party scripts, fonts, or CDNs.

`localStorage` stores only the theme name. HTTP request logging is disabled; the quiet event feed contains no account or token.

## Operator responsibilities

Protect the operating system, browser and extensions, reverse proxy, CLIProxyAPI, upstream accounts, and environment variables. Restrict environment-file permissions, provide TLS for remote access, and rotate any secret that was ever exposed. Credential Compass cannot repair a compromised dependency system.
