# 上游核对记录

核对日期：2026-09-28。此处是初始源码依据；当前版本以仓库根目录 `upstream-versions.json` 为准。
自动更新会同步版本锁和 Dockerfile，不改写此历史核对记录。

| 组件 | 固定版本 |
| --- | --- |
| CLIProxyAPI | `acdace936fa7df2905500c7f5e0a97d683138dea` |
| cliproxy-antigravity | `89d4a3ded47a375a446eac8739a03f6cbda00755`，源码 pluginVersion `0.1.3` |
| Go builder | `golang:1.26-bookworm`，CPA go.mod 声明 `1.26.0` |
| runtime | `debian:bookworm-slim` |
| agy | 不内置；首次运行下载，具体版本待安装后记录 |

- [CPA Dockerfile](https://github.com/router-for-me/CLIProxyAPI/blob/acdace936fa7df2905500c7f5e0a97d683138dea/Dockerfile)：CGO 开启、Debian 构建与运行。
- [CPA v8 配置](https://github.com/router-for-me/CLIProxyAPI/blob/acdace936fa7df2905500c7f5e0a97d683138dea/config.example.yaml)：server/access/oauth/plugins 字段。
- [插件说明](https://github.com/adeebahmad01/cliproxy-antigravity/blob/89d4a3ded47a375a446eac8739a03f6cbda00755/README.md)：C shared library、provider agy、配置字段、客户端 tool_calls 模拟。
- [插件 ABI smoke](https://github.com/adeebahmad01/cliproxy-antigravity/blob/89d4a3ded47a375a446eac8739a03f6cbda00755/scripts/abi_smoke.py)：构建阶段调用上游自己的 mock 检查。
- [官方安装和认证](https://antigravity.google/docs/cli/install/)：安装器、`~/.local/bin/agy`、安装 flags、SSH 授权码流程。
- [上游用户报告 #854](https://github.com/google-antigravity/antigravity-cli/issues/854)：报告者在强制文件存储环境中成功运行普通 agy 推理，但 daemon 认证失败。

官方安装文档与 issue 是不同证据等级。#854 的单一环境观察不能证明
所有 agy 版本或 Docker 环境均支持稳定文件凭证复用，因此将这项列为实机验收门槛。
本项目没有依赖未经核实的 token 文件格式或自行解析 Google OAuth 文件。
