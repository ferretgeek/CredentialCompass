<div align="center">

  <img src="docs/images/social-preview.png" alt="CLIProxyAPI 凭证体检" width="100%">

  # CLIProxyAPI 凭证体检

  中文 · [English](README_EN.md)

  [![CI](https://github.com/ferretgeek/cliproxyapi-credential-check/actions/workflows/ci.yml/badge.svg)](https://github.com/ferretgeek/cliproxyapi-credential-check/actions/workflows/ci.yml)
  [![CodeQL](https://github.com/ferretgeek/cliproxyapi-credential-check/actions/workflows/codeql.yml/badge.svg)](https://github.com/ferretgeek/cliproxyapi-credential-check/actions/workflows/codeql.yml)
  [![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-287f87)](https://www.python.org/)
  [![License: MIT](https://img.shields.io/badge/License-MIT-5f7f55.svg)](LICENSE)

  [部署](docs/部署说明.md) · [安全边界](docs/安全边界.md) · [兼容性](docs/兼容性.md)

</div>

> CLIProxyAPI 里那一堆账号，哪个还能用、哪个该换了？

## 为什么会需要它

用 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 管一个凭证池，时间长了就会变成一堆你不敢动的文件：三十个凭证，你只记得大概哪几个是好的，剩下的既不敢删也不敢用。

要判断状态，得挨个翻配置文件、看日志、试请求。而且这中间任何一步都有风险——手滑删掉一个还在用的凭证，或者把 Token 打进终端历史里。

这个面板做的事很窄：**盘点凭证池的启用状态和健康信号，用完整的遮罩呈现给你。** 想停用哪个、想恢复哪个，也在这里做，但要逐次输入精确的确认短语。

它**默认只读**。停用和恢复是部署者必须显式打开的能力，不是默认送你的按钮。

## 界面

![面板界面](docs/images/dashboard.png)

## 它刻意做少一点

这个项目最重要的特点是"没做什么"，所以先说这部分：

- **管理密钥只存在于服务端进程内存。** 网页看不到、也改不了上游地址与密钥。
- **账号默认遮罩。** 原始 Token、上游响应正文、凭证文件和真实 ID **不进入浏览器、日志或磁盘**。
- **默认只读。** 停用与恢复需要部署者开启 `COMPASS_ALLOW_STATUS_CHANGES`，并要求逐次输入精确确认短语。
- **不提供删除。** 也不提供凭证 ZIP 下载、任意请求代理，或任何第三方前端资源。
- 天青、青玉、夕照与深灰四套全局主题；深灰背景为 `#17191d`。

## 三分钟看见它

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m credential_compass --demo
```

打开终端显示的本地地址，输入一次性访问令牌。

演示模式只使用 `example.com`、`example.net` 与 `example.org` 这些保留域名，**不连接任何真实账号**——可以先看界面再决定要不要接真实环境。

真实模式、Docker、反向代理与 systemd 示例见[部署说明](docs/部署说明.md)。

## 两层能力，第二层默认关闭

这一点值得单独说清楚：

**清单层（默认开启）** — 读取 CLIProxyAPI 的凭证清单和启用状态，只形成遮罩后的账号和匿名句柄。这一层用的是稳定接口。

**探测层（默认关闭）** — 通过 CLIProxyAPI 管理端的 `api-call` 能力，请求一个固定的 ChatGPT 使用量接口，再把响应缩减为健康和额度轮廓。

探测层依赖的是**没有被承诺为稳定公共 API 的兼容路径**，随上游变化随时可能失效。所以 `COMPASS_ENABLE_LIVE_PROBE=false` 是默认值——而不是默认打开、坏了再说。关闭探测时，清单盘点仍然完整可用。

同理，状态停用 / 恢复也依赖管理接口，由 `COMPASS_ALLOW_STATUS_CHANGES=false` 默认关闭。

> **升级 CLIProxyAPI 之后**，请先在隔离的合成或低风险账户上验证清单、探测和状态变更，再投入正式使用。

详见[兼容性说明](docs/兼容性.md)。

## 它不做什么

- **不负责登录 Codex。** 不接收 OpenAI API Key、ChatGPT Cookie 或登录 Token。
- 只连接由部署者固定配置的 CLIProxyAPI 管理端点，不做任意请求代理。
- 不提供删除凭证的能力，也不提供凭证文件下载。
- 不绕过、不放宽任何额度限制。

Codex 本身支持 ChatGPT 登录和 API Key 两类官方认证方式，请按 [OpenAI 官方 Codex 认证文档](https://learn.chatgpt.com/docs/auth)完成认证。

## 开发验证

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

## 更多文档

[部署说明](docs/部署说明.md) · [安全边界](docs/安全边界.md) · [兼容性](docs/兼容性.md) · [发布审计](docs/发布审计.md) · [版本变更](CHANGELOG.md) · [参与开发](CONTRIBUTING.md) · [安全策略](SECURITY.md)

安全问题请使用 GitHub Private vulnerability reporting。**不要在公开 Issue 中提交真实账号、Token、管理地址、日志或截图。**

## 许可与声明

MIT License，见 [LICENSE](LICENSE)。

这是独立的社区项目，与 OpenAI 及 CLIProxyAPI 上游项目均无隶属、授权或背书关系，也不绕过任何额度限制。
