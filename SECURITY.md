# Security Policy

## Supported version

Security fixes are provided for the latest release and the `main` branch.

## Report privately

Use GitHub **Private vulnerability reporting**. Do not open a public issue containing real accounts, credential files, tokens, management keys, private API addresses, deployment hostnames, raw upstream bodies, logs, or screenshots. Reproduce with reserved synthetic data only.

## Security boundary

Credential Compass keeps the CLIProxyAPI management key in server-process memory, exposes no web editor for upstream settings, replaces raw identifiers with process-local opaque handles, masks accounts by default, and discards upstream bodies after classification. It does not store credentials, create credential archives, or provide deletion.

The default listener is loopback-only. A non-loopback listener requires a strong access token and exact Host allowlist, but that does not replace HTTPS. The optional compatibility probe and reversible status controls are both disabled by default.

The project cannot protect a compromised browser, extension, operating system, reverse proxy, CLIProxyAPI instance, upstream account, or operator environment.

## 中文说明

请通过仓库的私密漏洞报告功能提交安全问题。报告中不得包含真实账号、凭证文件、Token、管理密钥、私有 API 地址、服务器身份、原始响应、日志或截图，只能使用保留域名下的合成数据。若秘密曾进入公开历史，仅删除当前文件不算修复：仍须撤销或轮换秘密，清理所有可达 Git 历史与发布资产，并从未登录视角复核。
