# CLIProxyAPI + Antigravity Docker 薄层发行项目

> **🚧 项目未就绪，等待测试 / NOT READY — PENDING TESTS**
>
> 已发布实验镜像，但新增的容器集成测试发现阻塞：CPA v8.0.3 + 插件 v0.1.3
> 的聊天请求返回 `503 auth_not_found`，尚未调用到 agy。自动发布检查会阻止失败候选覆盖镜像。
> 真实 Google 登录、认证复用、流式响应和工具调用闭环也仍未完成验证。
> **不能作为已验证的一键可用方案，也不建议用于生产。**
> CI 通过不会自动改变此状态。验收记录见 [docs/TESTING.md](docs/TESTING.md)。

将 CLIProxyAPI、cliproxy-antigravity 插件和官方 `agy` 的安装流程集中到一个
Compose 服务中。只维护 Docker/启动脚本和配置，不 fork 或修改上游业务代码。

调用链：客户端 → CLIProxyAPI → cliproxy-antigravity 动态库 → 官方 agy 子进程 → Google。
客户端工具调用由上游插件模拟为 OpenAI `tool_calls`，工具结果由客户端传回；
本项目不另外实现 tool bridge。上游的原生工具权限仍然适用。

## 包含什么

- Debian 多阶段构建；CPA 开启 CGO，插件使用 `-buildmode=c-shared`。
- 固定上游提交，不随 `main` 自动漂移；构建时运行插件单测和上游 ABI mock 检查。
- 首次启动从 Google 官方地址安装 agy，镜像层不包含 Google 二进制或账号凭证。
- UID/GID 10001 非 root 运行；持久化整个用户目录与 CPA 配置。
- 自动生成随机客户端 API key；默认只将 API 暴露到宿主机 `127.0.0.1`。
- 显式登录、诊断、真实请求 smoke 脚本；本地 healthcheck 不调用 Google。
- GitHub Actions 构建与实验 GHCR 发布，每 6 小时检查上游正式 Release；不会生成 `latest`。

首版仅提供 `linux/amd64` 构建目标。ARM64、Windows/macOS Docker Desktop
均未验证；不要把上游的跨平台支持等同于本发行版已经验证。

## 首次本地试验

需要 Docker Engine / Docker Desktop、Compose v2，以及访问 GitHub、Go 模块源、
Debian 软件源和 Google 安装/认证服务的网络。以下命令在项目目录执行。

```bash
# 可选：复制环境配置；默认参数可以直接使用
cp .env.example .env

docker compose build --pull

# 推荐先在同一个持久卷中安装并登录，然后启动 API
docker compose run --rm cliproxy login

docker compose up -d
docker compose logs --tail=80 cliproxy
```

登录必须由你本人在 Google 官方流程中完成。`login` 直接启动官方 agy，
不会读取、导出或代填 OAuth token。无桌面容器是否自动进入授权码流程仍待测试；
如果它要求无法访问的 localhost 回调，先记录当前 agy 版本和提示，依据官方说明
处理远程登录，不要假定 `docker compose exec` 一定足以完成回调。

也支持先 `docker compose up -d --build`，再 `docker compose exec cliproxy agy`
登录。登录后运行 `docker compose restart cliproxy` 使插件重新发现模型。
如果服务启动失败，优先用 `docker compose run --rm cliproxy login` 诊断。

查看**客户端 API key**（不是 Google 凭证）：

```bash
docker compose exec cliproxy python3 -c 'import yaml; print(yaml.safe_load(open("/config/config.yaml"))["access"]["api-keys"][0])'
```

客户端 Base URL：`http://127.0.0.1:8317/v1`。先使用模型 `agy/default`；
其他模型名称以真实 `agy models` 和 API `/v1/models` 返回为准。

## 验证调用与持久化

下面命令会访问上游；真实推理会消耗账号额度。它们不会自动运行。

```bash
docker compose exec cliproxy /opt/cliproxy/scripts/doctor.sh
docker compose exec cliproxy agy -p 'Reply only with OK'
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --stream
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools

# 删除容器，保留命名卷
docker compose down
docker compose up -d

# 新进程 + 新容器中的真实推理才是关键验证
docker compose exec cliproxy agy -p 'Reply only with OK'
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools
```

`agy models` 或 Docker 的 `healthy` 不能证明 Google 登录和推理一定正常。
`--tools` 验证一个无副作用函数的名称、参数、调用 ID、结果回传和最终回复，
不会执行模型提供的代码。流式工具调用仍需在真实客户端中另行验收。

## 凭证到底保存在哪

| 命名卷 | 容器路径 | 内容 |
| --- | --- | --- |
| `agy-home` | `/home/cliproxy` | agy 本体、`~/.gemini`、CPA auth、CLI 配置/缓存、工作目录 |
| `cpa-config` | `/config` | CPA 配置及自动生成的客户端 API key |

实际卷名带固定 Compose 项目前缀 `cliproxy-antigravity_`。
不要随意改变 Compose project name；改变后会创建另一组卷，看起来像“凭证丢失”。
运行用户、HOME、安装位置在 `serve`、`login`、`exec agy` 中保持一致。

本项目默认设置 `GEMINI_FORCE_FILE_STORAGE=true`。这是依据上游用户报告采用的
**实验性兼容方案**，不是经过本项目验证的稳定认证契约。挂载整个 HOME 可覆盖
常见文件存储路径，但不会持久化内存中的 D-Bus/keyring 会话。
若当前 agy 仍依赖 keyring、不能复用文件凭证，验收应判为失败并保持未就绪。
保留文件也不能防止 Google 撤销会话、令牌过期或上游认证逻辑变更。

`docker compose down` 保留卷；**`docker compose down -v` 会删除卷**。
不要将卷备份、Google 凭证或实际配置提交到 GitHub、上传到 GHCR。
实验阶段建议单实例访问这组凭证，先验证串行请求再测试并发。

## 修改配置

首次启动从 `config.example.yaml` 生成 `/config/config.yaml`，以后保留原内容和 key。
编辑仓库中的模板不会覆盖已存在的配置。需要修改时：

```bash
docker compose cp cliproxy:/config/config.yaml ./config.yaml
# 编辑 config.yaml；它含 API key，已加入 .gitignore
cat ./config.yaml | docker compose exec -T cliproxy sh -c 'cat > /config/config.yaml'
docker compose restart cliproxy
```

上面通过服务用户写入，保留文件归属与私有权限。模板关闭管理 API/面板、请求日志和自动权限放行；工作目录仅为容器专用 workspace。
没有挂载宿主机源码、用户 session 或 Docker socket。`sandbox: false` 对齐插件默认值，
并不代表 CLI 已受到完整沙箱隔离。不要直接把此服务公开给不可信用户。
如需远程使用，自行设置带认证和 TLS 的访问入口。

## 安装与升级

安装器地址固定为 `https://antigravity.google/cli/install.sh`，使用官方文档中的
`--skip-aliases --skip-path`。安装脚本采用 HTTPS 下载，可用 `.env` 中
`AGY_INSTALLER_SHA256` 校验已审阅版本；它仅验证安装脚本，不锁定下载的 agy 二进制。
安装失败会退出，不会吞掉错误继续运行。并行安装由文件锁串行化。

已安装 agy 会直接复用，重建 CPA 镜像不会主动重装。
`AGY_CLI_DISABLE_AUTO_UPDATE=true` 请求关闭 CLI 自动更新，具体版本是否遵循仍待测。
安装器哈希和 CLI 版本记录在 HOME 的 `.agy-installer-sha256` / `.agy-version.txt`。
官方首次安装取什么版本由上游决定，因此**目前不承诺完整可复现构建/运行**。

CPA/插件版本记录在 `upstream-versions.json`，自动更新会同步 Dockerfile 的版本和完整 commit SHA。
手动改动时必须保持两者一致，并重新完成验收。
Go/基础镜像目前锁到版本系列，未锁 digest。正式版还需要固定这些依赖。
不要以“用了同一个 Go 编译器”为由假定兼容；插件使用 C ABI，其协议兼容性仍需验证。

## GitHub 与 GHCR

项目仓库：[eveloki/cliproxy-antigravity-docker](https://github.com/eveloki/cliproxy-antigravity-docker)。
镜像地址：`ghcr.io/eveloki/cliproxy-antigravity-docker:experimental`。
所有镜像都保留 **NOT READY — PENDING TESTS** 状态；发布成功不等于真实账号验收通过。

在 `.env` 中设置下面这一行，然后拉取镜像：

```dotenv
IMAGE=ghcr.io/eveloki/cliproxy-antigravity-docker:experimental
```

```bash
docker compose pull
docker compose run --rm --no-build cliproxy login
docker compose up -d --no-build
```

已有登录只需 `pull` 和 `up -d --no-build`，无需删除命名卷。自动发布不会自动更新你的运行中容器。
发布标签包括：

- `experimental`：最近成功发布的实验镜像。
- `experimental-sha-<完整发行层提交>`：定位发行层源码版本。
- `experimental-cpa-<版本>-plugin-<版本>-<发行层短提交>`：同时标明两项上游版本。
- 匹配 `v*-alpha*` 的手工发行标签。不会生成 `latest`。

回滚或严格锁定部署时，使用 Actions 发布摘要里的 `image@sha256:...` digest。

### 自动跟踪上游

`Update upstream releases and publish (experimental)` 每 6 小时运行一次：
UTC 00:17 / 06:17 / 12:17 / 18:17，即北京时间 08:17 / 14:17 / 20:17 / 02:17。
GitHub 调度可能延迟，也可在 Actions 手动 Run workflow。

1. 查询 CPA 与插件的最新正式 GitHub Release，解析标签到完整 commit SHA。
2. 拒绝草稿、预发布、版本回退和同版本标签被移动；跨主版本变化停止并报错，等待兼容性确认。
3. 有更新时，先执行脚本测试、完整镜像构建、上游插件单测/ABI mock 测试，
   再用无网络的 mock agy 检查 CPA → 插件调用是否正常。
4. 上述检查通过后才提交 `upstream-versions.json` 和 Dockerfile 到 main；只允许 fast-forward，
   其他人同时修改 main 时失败退出，不覆盖他人提交。
5. 显式调用可复用发布工作流，对该确切提交重新检查后发布 GHCR。
   不依赖机器人 push 触发另一个工作流，因此只需 `GITHUB_TOKEN`，无须 PAT。
6. 没有新版本且对应提交的镜像已存在时跳过。提交已更新但发布失败时，下次检查会重试缺失镜像。

任何构建/测试失败均不会发布候选镜像，已有 `experimental` 镜像继续可用。
发布任务串行执行，并拒绝覆盖已被新 main 提交取代的版本。
这套自动化只升级 CPA 和插件；不下载 Google 账号凭证、不打包或自动升级持久卷中的 agy。

### 手动发布与权限

- main push / PR 默认只检查并构建。
- Actions → **Experimental container (NOT READY)** → Run workflow → 勾选 `publish` 可发布当前 main。
- 上游检测流程需要 `contents: write` 更新版本锁；发布任务需要 `packages: write`。
  若以后启用分支保护或组织限制，需要允许该机器人更新，或改用 PR 流程；不会绕过规则。
- 公共仓库并不自动保证 GHCR 包公开；包可见性应设为 Public，才能匿名拉取。
- 公共仓库长期无活动时，GitHub 可能暂停定时工作流；在 Actions 中重新启用即可。

CI 的 mock agy 不使用 Google 账号，不能替代真实认证、推理和工具调用验收。
稳定发布必须依据 [测试清单](docs/TESTING.md) 人工更新状态与版本策略。

## 上游与证据

核对日期：2026-09-28。完整来源与固定提交见 [docs/UPSTREAM.md](docs/UPSTREAM.md)。
本项目 MIT；上游与第三方软件遵循各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
本项目与 Google、CLIProxyAPI 及插件作者无隶属关系；不承诺账号使用不会受到限制。
