# CLIProxyAPI + Antigravity Docker

> **正式版 / Stable**
>
> 2026-10-01，维护者 eveloki 已实机确认 `gemini-3.8-flash` 可用，并批准转为正式发布。
> 默认验证模型、命令示例及 CI mock 均已同步。实机反馈与 CI 结果分别记录在
> [测试记录](docs/TESTING.md)，不将模拟测试当作真实 Google 推理结果。

将 CLIProxyAPI、cliproxy-antigravity 插件和官方 Antigravity CLI 集中到一个 Compose 服务中。
调用链：客户端 → CLIProxyAPI → 插件动态库 → 官方 `agy` 子进程 → Google。

- CPA 和插件自动跟踪最新正式 Release，每 30 分钟检查一次，通过构建及集成测试后发布。
- 官方 CLI 固定为 `1.2.12`，构建时从官方 GitHub Release 下载并校验 SHA256。
- 当前正式发布版本：`v8.0.7-0.1.3-agy1.2.12-r2`。后续版本以 [Releases](https://github.com/eveloki/cliproxy-antigravity-docker/releases) 为准。
- 默认模型：`gemini-3.8-flash`；OpenAI 兼容 API 中使用 `agy/gemini-3.8-flash`。
- 非 root（UID/GID 10001）运行，持久化登录数据和 CPA 配置，默认仅监听宿主机 `127.0.0.1:8317`。
- 当前发布平台为 `linux/amd64`；ARM64 和 Docker Desktop 尚未单独验收。

CPA 源码不变。插件包含显式的 [兼容补丁](compat/README.md)，修复 `agy/*` 在调用执行器前
返回 `auth_not_found` 及 SSE 双重封装问题；不注入伪造 CPA 凭据，不修改 Google 登录流程。
客户端工具调用由上游插件模拟为 OpenAI `tool_calls`，工具结果由客户端传回。

## 部署、登录与验证

需要 Docker Engine、Compose v2，以及访问 GHCR 和 Google 认证/推理服务的网络。
将本仓库放到 `/www/cliproxy-antigravity-docker`（也可改用自己的目录）。

新部署可复制 `.env.example`；已有部署请保留原有端口和配置，将 `.env` 中的 `IMAGE` 改为：

```dotenv
IMAGE=ghcr.io/eveloki/cliproxy-antigravity-docker:latest
# 如需固定本次正式版：
# IMAGE=ghcr.io/eveloki/cliproxy-antigravity-docker:v8.0.7-0.1.3-agy1.2.12-r2
```

```bash
cd /www/cliproxy-antigravity-docker

# 首次部署才复制；保留已有 .env
[ -f .env ] || cp .env.example .env

# 拉取并启动正式镜像；已有服务也用此命令升级，保留命名卷
docker compose pull
docker compose up -d --no-build

# 1. 登录（走 Google 官方流程，项目不代填任何 token）
docker compose run --rm --no-build cliproxy login
# 登录完成后让插件重新发现模型
docker compose restart cliproxy

# 2. 查看客户端 API key（非 Google 凭证，仅供你自己查看）
docker compose exec cliproxy python3 -c 'import yaml; print(yaml.safe_load(open("/config/config.yaml"))["access"]["api-keys"][0])'

# 3. 验证真实推理（会消耗账号额度）
docker compose exec cliproxy /opt/cliproxy/scripts/doctor.sh
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools
```

登录由本人在 Google 官方流程中完成，`login` 直接启动官方 agy。若环境要求无法访问的
localhost 回调，依据官方远程登录说明处理。已有有效登录的部署可以跳过登录步骤。

客户端设置：

| 项目 | 值 |
| --- | --- |
| Base URL | `http://127.0.0.1:8317/v1` |
| API key | 上述命令读取的 CPA 客户端 key |
| 模型 | `agy/gemini-3.8-flash` |

`agy/` 前缀用于选择 CLI 插件，避免误走 CPA 内置 Antigravity provider。
模型统一配置在 `scripts/test-model.txt`；smoke 会检查精确模型是否存在，缺失时直接报错，不回退到其他模型。

## 更多验证与故障定位

```bash
# 查看组件版本和 CLI 模型列表
docker compose exec cliproxy /opt/cliproxy/scripts/doctor.sh
# 直接验证官方 CLI
docker compose exec cliproxy agy --model gemini-3.8-flash -p 'Reply only with OK'
# 验证 CPA 普通响应和 SSE 文本流
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --stream
# 查看服务日志
docker compose logs --tail=80 cliproxy
```

`--tools` 验证无副作用函数的名称、参数、调用 ID、结果回传和最终回复，不执行模型提供的代码。
流式工具调用、并发、取消和异常恢复的专项结果见测试记录。
`agy models`、Docker `healthy` 或 `/v1/models` 返回列表本身不等于一次真实推理成功。

## 登录数据与配置持久化

| 命名卷 | 容器路径 | 内容 |
| --- | --- | --- |
| `agy-home` | `/home/cliproxy` | CLI 登录数据、配置/缓存、CPA auth、工作目录 |
| `cpa-config` | `/config` | CPA 配置及随机生成的客户端 API key |

Compose 项目前缀固定为 `cliproxy-antigravity_`。升级时保留 project name 和命名卷。
`docker compose down` 保留卷；**`docker compose down -v` 会删除卷**。
卷备份、实际配置和 Google 凭据不要提交到 GitHub 或镜像。

`GEMINI_FORCE_FILE_STORAGE=true` 是依据上游用户报告保留的兼容设置，不是官方稳定认证契约。
HOME 挂载不能持久化内存中的 D-Bus/keyring 会话，也不能防止令牌撤销或到期。
维护者已确认当前环境可用；其他环境遇到 keyring 问题时仍需按官方认证流程诊断。

首次启动从 `config.example.yaml` 生成 `/config/config.yaml`，权限为 0600；以后保留配置和 key。
修改仓库模板不会覆盖已存在的配置。修改现有配置：

```bash
docker compose cp cliproxy:/config/config.yaml ./config.yaml
# 编辑 config.yaml（含客户端 key，已加入 .gitignore）
cat ./config.yaml | docker compose exec -T cliproxy sh -c 'cat > /config/config.yaml'
docker compose restart cliproxy
```

默认关闭管理 API/面板、请求日志和自动权限放行，未挂载宿主机源码或 Docker socket。
插件的 `sandbox: false` 对齐上游默认值；远程访问应配置认证和 TLS。

## CPA 导出凭据与官方 CLI

CPA 的 Antigravity JSON 供 CPA 内置 `antigravity` provider 使用。写入 CPA auth-dir
不会自动给官方 CLI 建立登录会话，本项目未验证直接导入或字段转换方案。
使用上述官方登录流程；Repository Secret `ANTIGRAVITY_JSON` 不被工作流引用。

认证依据：[官方 CLI 文档](https://antigravity.google/docs/cli/install/)、
[企业 ADC 文档](https://antigravity.google/docs/enterprise/)。CI 不读取账号凭据，不消耗真实推理额度。

## 版本与自动发布

| 标签 | 含义 | 更新规则 |
| --- | --- | --- |
| `v8.0.7-0.1.3-agy1.2.12-r2` | CPA、插件、CLI 版本及打包修订 | 发布后不覆盖 |
| `stable`、`latest` | 最近成功发布的正式版 | 与固定标签指向相同 digest |
| `sha-<完整发行层提交>` | 本次镜像的源码提交 | 随固定版本发布 |
| `rc`、`*-rc.*`、`experimental*` | 正式发布前的历史镜像 | 保留，不再更新 |

正式版仍使用三组件组合标签。相同组件版本的打包修改递增 `rN`，上游组件更新后重置为 `r1`。
注册表标签并非强制不可变；工作流通过串行发布和查询检查避免覆盖，严格固定可使用 `image@sha256:...`。

`Track stable upstream releases and publish stable images` 在 main push、手动触发及每小时 :17 / :47 运行：

1. 查询 CPA/插件最新正式 Release，解析完整 commit SHA；拒绝草稿、预发布、降级和同版本标签移动。
2. 有更新时先构建并测试候选；兼容补丁无法应用、单测或集成测试失败时停止。
3. 测试通过后记录 `upstream-versions.json` 和 Dockerfile，只允许 fast-forward 更新 main。
4. 对确切提交完成镜像构建、真实 CLI 离线版本检查和 mock JSON/SSE 集成测试。
5. 发布固定镜像与 GitHub 正式 Release，再更新 `stable` 和 `latest`，重新查询确认三个标签的 digest 一致。
6. 已完成发布则跳过；缺失镜像或中断的别名更新可重试，已有固定版本不覆盖。

这套自动化继续升级 CPA/插件，无需人工批准每次升版；CLI 保持 `1.2.12` 和固定 SHA256。
`upstream-versions.json` 是构建输入快照，用于追溯与回滚，不是禁止上游升级的配置。
每次自动构建仅执行 CI 检查，不宣称维护者逐一重新验证了每个未来版本的 Google 推理。
自动发布不会自动升级你的运行中容器，需要自行 `pull` 和 `up -d --no-build`。

手动发布：Actions → **Stable container release** → Run workflow → 勾选 `publish`。
PR 只构建验证。上游更新及创建正式 Release 需要 `contents: write`，镜像发布需要 `packages: write`。
公共仓库长期无活动时 GitHub 可能暂停定时任务；可在 Actions 中重新启用。

## 从源码构建

```bash
IMAGE=cliproxy-antigravity:local docker compose build --pull
IMAGE=cliproxy-antigravity:local docker compose up -d --no-build
```

需要访问 GitHub、Go 模块源和 Debian 软件源。官方 CLI 从
[Release 1.2.12](https://github.com/google-antigravity/antigravity-cli/releases/tag/1.2.12)
下载并校验归档哈希，位于 root 拥有的 `/opt/agy/agy`，运行用户不能改写。
`/usr/local/bin/agy` 始终调用该程序，旧 HOME 卷里的 `~/.local/bin/agy` 不会覆盖它。
运行时不下载 CLI，保留 `AGY_CLI_DISABLE_AUTO_UPDATE=true`。
Go 和基础镜像目前按版本系列跟踪，未固定 digest，因此不承诺逐字节可复现构建。

## 上游与许可

完整来源见 [docs/UPSTREAM.md](docs/UPSTREAM.md)，当前组件版本以构建输入快照为准。
发行层代码为 MIT，上游及 Google 软件遵循各自条款，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
本项目与 Google、CPA 及插件作者无隶属关系。
