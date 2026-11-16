# CLIProxyAPI + Antigravity Docker

[English](README.md) | **简体中文**

集成官方 Antigravity CLI 与执行器插件的 CPA 正式发行镜像。
镜像默认布局对齐 `eceasy/cli-proxy-api`，现有使用本地配置文件的 CPA 部署可以保留 Compose，直接替换镜像名。

> [!WARNING]
> **禁止在管理面板的插件商店安装、更新或重新安装 `cliproxy-antigravity`，即使面板提示有更新。**
> 本镜像内置插件保留 `agy/` 命名空间隔离，并检查 CLI 1.5.9 的提前终止状态。商店版可能热替换
> 内置版本，使这些保护丢失。**此插件只能通过升级本项目 Docker 镜像更新。**
> 此限制针对 `cliproxy-antigravity`；具体原因和误更新后的恢复方式见下文。

- CPA 和插件每 30 分钟检查最新正式 Release，在镜像构建中应用插件兼容补丁并通过测试后自动发布。
- 官方 CLI 固定为 `1.5.9`，构建时校验 SHA256。
- 默认测试模型：`gemini-3.8-flash`；插件 API 模型：`agy/gemini-3.8-flash`。
- 固定标签包含 CPA、插件、CLI 和打包修订版本；已发布版本见 [Releases](https://github.com/eveloki/cliproxy-antigravity-docker/releases)。
- 发布平台为 `linux/amd64`，ARM64 和 Docker Desktop 未单独验收。

## 替换现有 CPA 镜像

在**原部署目录**的 Compose 中，只修改这一行：

```yaml
image: ghcr.io/eveloki/cliproxy-antigravity-docker:latest
```

然后重建服务：

```bash
docker compose pull cli-proxy-api
docker compose up -d --no-build cli-proxy-api
```

保留原来的服务名、端口、配置、凭据、插件和数据。[compose.compat.yaml](compose.compat.yaml) 提供五个挂载的对照示例：

```yaml
services:
  cli-proxy-api:
    image: ghcr.io/eveloki/cliproxy-antigravity-docker:latest
    pull_policy: always
    container_name: cli-proxy-api
    ports:
      - "127.0.0.1:8317:8317"
    volumes:
      - ./config.yaml:/CLIProxyAPI/config.yaml
      - ./auths:/root/.cli-proxy-api
      - ./logs:/CLIProxyAPI/logs
      - ./plugins:/CLIProxyAPI/plugins
      - ./data:/CLIProxyAPI/data
    restart: unless-stopped
```

前提是已有真实的 `config.yaml`。不要把此文件复制到无关目录运行，否则相对路径会指向另一组数据。
初始化脚本不改写已有配置，不轮换已有客户端 key；CPA 自身的配置保存行为仍遵循上游。
单文件挂载可以读取，但上游原子保存配置的操作可能需要目录挂载。

镜像默认 root、`HOME=/root`、`WORKDIR=/CLIProxyAPI`、`CMD ["./CLIProxyAPI"]`。
入口支持 `./CLIProxyAPI`、`-config` 等 CPA 原生命令参数及 shell 命令。
发行层仍增加 tini、插件准备和健康检查，并非与上游逐字节一致。
旧 CPA 凭据继续服务于相应原生 provider；第三方插件仍需适配所选 CPA 版本和 Linux ABI。

## 启用官方 Antigravity CLI 路由

替换镜像会保留 CPA 配置，**不会强制启用被关闭的插件**、转换 CPA OAuth JSON，或改变管理面板设置。

要使用内置插件，将下面内容合并进现有 `plugins` 段，保留其他插件配置：

```yaml
plugins:
  enabled: true
  dir: /CLIProxyAPI/plugins
  configs:
    cliproxy-antigravity:
      enabled: true
      binary_path: /usr/local/bin/agy
      workdir: /CLIProxyAPI/data/agy-workspace
      print_timeout: 30m
      dangerously_skip_permissions: false
      sandbox: false
      reasoning_effort: high
```

```bash
docker compose restart cli-proxy-api
# Google 官方登录，项目不代填 token
docker compose run --rm --no-build cli-proxy-api login
docker compose restart cli-proxy-api
# 仅在自己终端查看 CPA 客户端 key（非 Google 凭据）
docker compose exec cli-proxy-api python3 /opt/cliproxy/scripts/runtime_config.py key
# 真实验证会消耗账号额度
docker compose exec cli-proxy-api /opt/cliproxy/scripts/doctor.sh
docker compose exec cli-proxy-api python3 /opt/cliproxy/scripts/smoke.py --tools
```

客户端 Base URL 为 `http://127.0.0.1:8317/v1`，模型使用 `agy/gemini-3.8-flash`。
`agy/` 前缀选择官方 CLI 插件，避免误走 CPA 原生 Antigravity provider。
文本 SSE 可单独运行 `smoke.py --stream`，不要与 `--tools` 合用。
测试模型在 `scripts/test-model.txt`；模型缺失时直接报错，不回退到其他模型。

默认只有 agy 子进程使用 `HOME=/root/.cli-proxy-api/agy-home`，登录数据随原有 `./auths/agy-home`
持久化，与 CPA 原生 JSON 分开，标准布局无需额外挂载。自定义布局或已有官方 CLI 登录目录可设置
`AGY_HOME` 指向持久化目录。CPA 的 HOME 仍是 `/root`，包装脚本不复制或转换账号 token。

CLI 本体位于 `/opt/agy/agy`，不被凭据或插件挂载遮住，关闭自动更新。
`GEMINI_FORCE_FILE_STORAGE=true` 是依据上游用户报告保留的兼容设置，不能视为所有环境的稳定 keyring 契约。

## 插件安装与数据持久化

### 为什么不能从商店更新内置插件

当前镜像使用上游插件 **v0.3.1** 和[公开的发行层补丁](compat/README.md)，
版本标识为 **`0.3.1+dist1`**，CPA 源码保持不变。

| 行为 | 当前实现 |
| --- | --- |
| CPA v8 路由和 SSE | 上游 v0.2.0 起已提供 ModelRouter 和标准 SSE；移除针对 v0.1.3 的旧路由/SSE 补丁。[作者已确认设计并修复](https://github.com/adeebahmad01/cliproxy-antigravity/issues/5#issuecomment-6903517407)。 |
| 命名空间隔离 | 发行层只发布和路由显式的 `agy/*` 模型，保持既有策略，不接管新版上游增加的裸模型名和 `antigravity/*` 别名。显式配置的原生 `agy` 凭据仍按上游方式调度。 |
| 提前终止检测 | 即使 CLI 返回 `status=SUCCESS`、退出码为 0，遇到 `finished_reason=print_timeout/interrupted/error` 或未知非空原因，也必须返回错误，避免把截断内容当作完整成功响应。 |

Google 登录仍由官方 CLI 负责。新版插件可能生成不含 Google access/refresh token 的 CPA
`agy` 账号元数据，用于调度和配额展示；这不等于导出或复用 Google OAuth 凭据。

商店二进制可能从其他路径热替换**相同插件 ID**，使上述隔离和终止保护丢失。
**旧 v0.1.3 的 `auth_not_found` 缺陷已由上游修复；当前商店更新限制的理由是剩余的发行层保护。**
启动哈希标记不会锁定活动插件，也不阻止商店热替换。商店副本会持久化在卷中，
所以仅重启或拉取镜像不一定恢复内置版本。

**正确更新方式：**拉取经过测试的本项目镜像并按上文 Compose 命令重建服务，不单独替换 `.so`。
未来源码版本仍须通过补丁应用检查和集成测试，禁止在补丁失败时静默跳过。

如果已经被商店版替换：

1. 根据 CPA 加载/热重载日志确认活动插件的路径和版本，并核对配置中的 `plugins.dir`。
2. 备份并移出冲突的未打补丁 `cliproxy-antigravity` 二进制，备份位置必须在**整个插件扫描目录树之外**，
   包括架构子目录；只移动到 `plugins.dir` 内的备份子目录，仍可能被扫描。保留其他插件、配置、凭据和数据。
3. 保留受管的内置兼容副本；如果该同名文件也被覆盖，应将冲突副本备份移出，让启动脚本重新播种镜像内的补丁库，然后重启对应服务。
4. 确认日志中**当前活动版本**为本次发行的 `0.3.1+dist1`，再显式验证一次推理。
   仅看到模型列表含 `agy/*`，不能证明执行器路由已恢复。

### 插件播种与持久化

启用 Antigravity 插件后，启动时将 `/opt/cliproxy/bundled-plugins` 中的内置库复制到配置指定的可写插件目录。
即使宿主挂载覆盖了镜像中的 `/CLIProxyAPI/plugins`，也能完成初始化。

- 保留其他插件文件和配置。
- 用哈希标记识别发行层安装的副本，只升级未被用户改动的受管副本；已有不同文件或被用户修改的副本会保留并提示。
- 因此，已有用户自行安装的 `cliproxy-antigravity.so` 不会被静默替换。如需改用发行层补丁版，应先备份并明确移除该文件，再重启。
- 默认 root 布局可以向插件挂载目录写入，满足商店安装权限；面板是否开放、管理密钥是什么仍由原配置决定。
  商店可写支持**不表示允许替换内置的 `cliproxy-antigravity` 插件**。
- 插件数据库应通过其自身配置放在挂载的 `/CLIProxyAPI/data` 下；本项目不搬运旧数据库、不改写第三方插件的数据路径。

内置插件包含公开的 [CLI 终止状态与命名空间补丁](compat/README.md)，CPA 源码不修改。
配置布局兼容不代表所有第三方插件都能兼容未来自动升级的每一个 CPA 版本。

## 本仓库原有的非 root 部署

`compose.yaml` 保留服务名 `cliproxy` 和原来的命名卷。**升级镜像时也要同步更新 Compose 文件**：
它现在显式设置 UID/GID `10001:10001`、`HOME=/home/cliproxy`、`AGY_HOME=/home/cliproxy`、
`CPA_CONFIG=/config/config.yaml` 和原工作目录，避免镜像的新 root 默认值改变文件属主或登录位置。
已有命名卷部署不要为了升级而直接换成 `compose.compat.yaml`。

RC 时代旧卷请升级到 `v8.0.8-0.1.3-agy1.2.12-r3` 或更高版本。旧卷可能没有
`/home/cliproxy/plugins`；启动脚本现在以 UID 10001 自动创建旧 `/opt/cliproxy/plugins`
符号链接的目标目录，无需在宿主机手动 mkdir/chown，也无需修改原配置。
此前 8.0.8 r1/r2 漏测了这一迁移场景。CI 现在用实际 8.0.6 RC 镜像创建卷，再测试升级、
重建和回滚，并检查合成配置、凭据、状态及数据文件的内容和属主保持不变。

```bash
cd /www/cliproxy-antigravity-docker
git pull --ff-only
# 保留原 .env；若 IMAGE 仍是 :rc，改为 :latest
[ -f .env ] || cp .env.example .env
docker compose pull
docker compose up -d --no-build
# 仅首次登录需要，已有有效会话可跳过
docker compose run --rm --no-build cliproxy login
docker compose restart cliproxy
docker compose exec cliproxy python3 /opt/cliproxy/scripts/runtime_config.py key
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools
```

| 设置 | 原 CPA 兼容布局 | 本仓库 Compose 布局 |
| --- | --- | --- |
| 用户 / CPA HOME | root / `/root` | 10001 / `/home/cliproxy` |
| 配置 | `/CLIProxyAPI/config.yaml` | `/config/config.yaml` |
| CPA 凭据 | `/root/.cli-proxy-api` | `/home/cliproxy/.cli-proxy-api` |
| 官方 CLI HOME | `/root/.cli-proxy-api/agy-home` | `/home/cliproxy` |
| 插件 | 配置指定，通常 `/CLIProxyAPI/plugins` | `/home/cliproxy/plugins`；旧 `/opt/cliproxy/plugins` 指向此处 |
| 数据 | `/CLIProxyAPI/data` 宿主挂载 | 选择已持久化 HOME 内的路径 |

仓库模板只在配置缺失时生成私有随机 key，不覆盖已有 key。辅助脚本同时识别旧平铺字段和 v8 分节，
支持自定义 HTTP 端口；显式 `-config` / `--config` 优先于 `CPA_CONFIG`，健康检查跟随实际配置路径。
重复指定原生 `-config` 时取最后一个值，遇到 `--` 或位置参数后停止解析。
`./CLIProxyAPI -help` 与 `./CLIProxyAPI discover ...` 直接透传，不执行配置初始化。
本地 HTTPS 健康检查跳过证书验证，真实 smoke 保留正常 TLS 校验。
原生远程配置后端、自定义 entrypoint 及全部 OAuth 回调流程不在本次五挂载兼容测试范围内，
请保留这些场景所需的上游配置和端口映射。

`docker compose down` 保留命名卷，`down -v` 会删除命名卷。升级时保持 Compose 项目名及原数据，
不要把账号凭据或卷备份提交到仓库。

## 发布与验证

固定标签采用 `v<CPA>-<插件>-agy<CLI>-r<修订>`，发布流程不覆盖。
管理面板的构建时间来自镜像内 CPA 二进制的 UTC 编译时间；Docker 复用编译缓存时保留原编译时间。
`stable` 和 `latest` 指向同一成功发布的镜像 digest；旧 RC 和 experimental 标签保留。
需要控制升级时使用固定标签或 digest；拉取镜像后仍需重建容器才会使用新版。

main push 和每小时 :17 / :47 查询 CPA/插件正式 Release，构建测试候选，记录完整 SHA，
然后发布 GHCR 和 GitHub Release。CLI 保持固定版本，失败时保留原有别名。
手动发布入口：Actions → **Stable container release**。Go/基础镜像按版本系列跟踪，不承诺逐字节可复现构建。

维护者于 2026-10-01 确认 `gemini-3.8-flash` 实际可用。CI 检查真实 CLI 离线启动、模拟 JSON/SSE 路由、
原生凭据枚举、只读旧配置、插件/数据目录可写以及容器重建后的持久化。
CI 不读取 Google 凭据，也不请求真实 Google 推理。实际结果及剩余范围见 [测试记录](docs/TESTING.md)。

## 来源与许可

本发行镜像集成以下三个上游项目：

| 上游项目 | 作用 |
| --- | --- |
| [router-for-me/CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | API 代理服务，自动跟踪正式版本。 |
| [adeebahmad01/cliproxy-antigravity](https://github.com/adeebahmad01/cliproxy-antigravity) | Antigravity CLI 执行器插件，自动跟踪正式版本并应用已公开的兼容补丁。 |
| [google-antigravity/antigravity-cli](https://github.com/google-antigravity/antigravity-cli) | Google 官方 Antigravity CLI，固定版本内置并校验 SHA256。 |

见 [上游记录](docs/UPSTREAM.md)、`upstream-versions.json` 和 [第三方声明](THIRD_PARTY_NOTICES.md)。
发行层代码为 MIT；Google CLI 和其他依赖保留各自条款。本项目与 Google、CPA 和插件作者无隶属关系。
