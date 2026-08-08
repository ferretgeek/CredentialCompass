<div align="center">

# 凭证罗盘 · Credential Compass

让散落的凭证，回到一张清楚的航图。

[![CI](https://github.com/ferretgeek/CredentialCompass/actions/workflows/ci.yml/badge.svg)](https://github.com/ferretgeek/CredentialCompass/actions/workflows/ci.yml)
[![CodeQL](https://github.com/ferretgeek/CredentialCompass/actions/workflows/codeql.yml/badge.svg)](https://github.com/ferretgeek/CredentialCompass/actions/workflows/codeql.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-287f87)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-5f7f55.svg)](LICENSE)

[English](README_EN.md) · [部署](docs/部署说明.md) · [安全边界](docs/安全边界.md) · [兼容性](docs/兼容性.md)

![凭证罗盘界面预览](docs/images/dashboard.png)

</div>

凭证罗盘是一间安静的 CLIProxyAPI 凭证池健康工作台：它盘点启用状态，在明确开启后探测额度轮廓，并只把经过归类的健康信号交给浏览器。

## 它刻意做少一点

- 管理密钥只存在于服务端进程内存，网页不能查看或修改上游地址与密钥。
- 账号默认遮罩；原始 Token、上游响应正文、凭证文件与真实 ID 不进入浏览器、日志或磁盘。
- 默认只读；停用与恢复需由部署者开启，并要求逐次输入精确确认短语。
- 不提供删除、凭证 ZIP 下载、任意请求代理或第三方前端资源。
- 天青、青玉、夕照与深灰四套全局主题；深灰背景为 `#17191d`。

## 三分钟看见它

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m credential_compass --demo
```

打开终端显示的本地地址，输入一次性访问令牌。演示模式只使用 `example.com`、`example.net` 与 `example.org` 保留域名，不连接真实账号。

真实模式、Docker、反向代理与 systemd 示例见[部署说明](docs/部署说明.md)。实时额度探测依赖兼容性接口，默认关闭；启用前请阅读[兼容性说明](docs/兼容性.md)。

## 适用边界

这是独立社区项目，与 OpenAI 无隶属或背书关系。它不负责登录 Codex，也不接收 OpenAI API Key 或 ChatGPT 登录凭据；只连接由部署者固定配置的 CLIProxyAPI 管理端点。

## 开发验证

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

安全问题请使用 GitHub Private vulnerability reporting，勿在公开 Issue 中提交真实账号、Token、管理地址、日志或截图。
