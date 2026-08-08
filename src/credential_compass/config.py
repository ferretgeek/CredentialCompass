from __future__ import annotations

import ipaddress
import os
import secrets
import socket
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit


class ConfigError(ValueError):
    """Raised when a deployment setting would weaken the security boundary."""


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false")


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def _resolved_addresses(hostname: str, port: int) -> set[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ConfigError("The configured CLIProxyAPI host cannot be resolved") from exc
    addresses = {ipaddress.ip_address(record[4][0].split("%", 1)[0]) for record in records}
    if not addresses:
        raise ConfigError("The configured CLIProxyAPI host has no usable address")
    return addresses


def _normalized_base_url(raw: str, allow_private_http: bool) -> tuple[str, str, frozenset[str]]:
    value = raw.strip()
    if not value:
        raise ConfigError("COMPASS_CPA_URL is required outside demo mode")
    parsed: SplitResult = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ConfigError("COMPASS_CPA_URL must use http or https")
    if parsed.username or parsed.password:
        raise ConfigError("Credentials must not be embedded in COMPASS_CPA_URL")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ConfigError("COMPASS_CPA_URL must point to the server root")
    if not parsed.hostname:
        raise ConfigError("COMPASS_CPA_URL must include a hostname")

    default_port = 443 if parsed.scheme == "https" else 80
    port = parsed.port or default_port
    addresses = _resolved_addresses(parsed.hostname, port)
    if parsed.scheme == "http":
        loopback_only = all(address.is_loopback for address in addresses)
        private_only = all(
            (address.is_private or address.is_loopback)
            and not address.is_multicast
            and not address.is_unspecified
            for address in addresses
        )
        if not loopback_only and not (allow_private_http and private_only):
            raise ConfigError(
                "Plain HTTP is limited to loopback; use HTTPS or explicitly enable private-network HTTP"
            )

    host = parsed.hostname.lower().rstrip(".")
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    normalized = urlunsplit((parsed.scheme, netloc, "", "", ""))
    return normalized, host, frozenset(str(address) for address in addresses)


def _is_loopback_bind(host: str) -> bool:
    normalized = host.strip().lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _allowed_hosts(bind_host: str, configured: str) -> frozenset[str]:
    hosts = {item.strip().lower().rstrip(".") for item in configured.split(",") if item.strip()}
    if _is_loopback_bind(bind_host):
        hosts.update({"localhost", "127.0.0.1", "::1"})
    else:
        try:
            bind_address = ipaddress.ip_address(bind_host.split("%", 1)[0])
        except ValueError:
            bind_address = None
        if bind_address and not bind_address.is_unspecified:
            hosts.add(str(bind_address))
    if not hosts:
        raise ConfigError("COMPASS_ALLOWED_HOSTS is required for a non-loopback bind")
    if any(host in {"*", "0.0.0.0", "::"} for host in hosts):
        raise ConfigError("COMPASS_ALLOWED_HOSTS must list exact browser hostnames")
    return frozenset(hosts)


@dataclass(frozen=True, slots=True)
class AppConfig:
    bind_host: str
    port: int
    access_token: str
    generated_access_token: bool
    allowed_hosts: frozenset[str]
    cpa_url: str
    cpa_host: str
    cpa_addresses: frozenset[str]
    cpa_key: str
    demo: bool
    live_probe: bool
    allow_status_changes: bool
    max_accounts: int
    concurrency: int
    request_timeout: int
    allow_private_http: bool

    @classmethod
    def from_env(cls, *, demo_override: bool | None = None) -> AppConfig:
        demo = _bool("COMPASS_DEMO", False) if demo_override is None else demo_override
        bind_host = os.getenv("COMPASS_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = _integer("COMPASS_PORT", 8788, 1, 65535)
        allow_private_http = _bool("COMPASS_ALLOW_PRIVATE_HTTP", False)
        configured_hosts = os.getenv("COMPASS_ALLOWED_HOSTS", "")
        allowed_hosts = _allowed_hosts(bind_host, configured_hosts)

        access_token = os.getenv("COMPASS_ACCESS_TOKEN", "").strip()
        generated = False
        if not access_token:
            if not _is_loopback_bind(bind_host):
                raise ConfigError("COMPASS_ACCESS_TOKEN is required for a non-loopback bind")
            access_token = secrets.token_urlsafe(32)
            generated = True
        if len(access_token) < 32:
            raise ConfigError("COMPASS_ACCESS_TOKEN must contain at least 32 characters")

        if demo:
            cpa_url = "demo://local"
            cpa_host = "demo"
            cpa_addresses = frozenset()
            cpa_key = ""
        else:
            cpa_url, cpa_host, cpa_addresses = _normalized_base_url(
                os.getenv("COMPASS_CPA_URL", ""), allow_private_http
            )
            cpa_key = os.getenv("COMPASS_CPA_KEY", "").strip()
            if not cpa_key:
                raise ConfigError("COMPASS_CPA_KEY is required outside demo mode")

        return cls(
            bind_host=bind_host,
            port=port,
            access_token=access_token,
            generated_access_token=generated,
            allowed_hosts=allowed_hosts,
            cpa_url=cpa_url,
            cpa_host=cpa_host,
            cpa_addresses=cpa_addresses,
            cpa_key=cpa_key,
            demo=demo,
            live_probe=demo or _bool("COMPASS_ENABLE_LIVE_PROBE", False),
            allow_status_changes=demo or _bool("COMPASS_ALLOW_STATUS_CHANGES", False),
            max_accounts=_integer("COMPASS_MAX_ACCOUNTS", 1000, 1, 10_000),
            concurrency=_integer("COMPASS_CONCURRENCY", 4, 1, 8),
            request_timeout=_integer("COMPASS_REQUEST_TIMEOUT", 15, 3, 30),
            allow_private_http=allow_private_http,
        )
