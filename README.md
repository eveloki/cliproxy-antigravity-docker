# CLIProxyAPI + Antigravity Docker 薄层发行项目

> **🚧 项目未就绪，等待测试 / NOT READY — PENDING TESTS**
>
> CPA → 插件的 `auth_not_found` 已由兼容补丁修复；指定模型的无网络 mock 测试
> 已通过普通响应、SSE、客户端认证及路由边界检查。
> 真实 Google 登录、凭据复用、实际模型可用性和工具调用闭环仍未验证。
> **不能作为已验证的一键可用方案，也不建议用于生产。**
> CI 通过不会自动改变此状态。验收记录见 [docs/TESTING.md](docs/TESTING.md)。

将 CLIProxyAPI、cliproxy-antigravity 插件和固定版本的官方 `agy`集中到一个
Compose 服务中。维护 Docker/启动脚本、配置，以及一个显式的
[插件路由兼容补丁](compat/README.md)。CPA 源码不变；插件打包版本为 `0.1.3+cpa8-route1`。
补丁只将 `agy/*` 请求交给插件自身执行器，不添加 CPA 上游凭据，也不改变官方 CLI 的登录方式。

调用链：客户端 → CLIProxyAPI → cliproxy-antigravity 动态库 → 官方 agy 子进程 → Google。
客户端工具调用由上游插件模拟为 OpenAI `tool_calls`，工具结果由客户端传回；
本项目不另外实现 tool bridge。上游的原生工具权限仍然适用。

当前打包修订为 `v8.0.3-0.1.3-agy1.2.12-r1`，包含上述路由修复；旧 `experimental` 镜像不变。

## 包含什么

- Debian 多阶段构建；CPA 开启 CGO，插件使用 `-buildmode=c-shared`。
- 自动跟踪 CPA/插件最新正式 Release，记录每次构建的准确提交；构建时运行插件单测和上游 ABI mock 检查。
- 构建时下载官方 agy 1.2.12，校验固定 SHA256 后内置；镜像不包含账号凭证。
- UID/GID 10001 非 root 运行；持久化整个用户目录与 CPA 配置。
- 自动生成随机客户端 API key；默认只将 API 暴露到宿主机 `127.0.0.1`。
- 显式登录、诊断、真实请求 smoke 脚本；本地 healthcheck 不调用 Google。
- GitHub Actions 每 30 分钟检查上游正式 Release；门禁通过后自动发布 RC 镜像，`rc` 和 `latest` 跟随最近成功发布。

首版仅提供 `linux/amd64` 构建目标。ARM64、Windows/macOS Docker Desktop
均未验证；不要把上游的跨平台支持等同于本发行版已经验证。

## 首次本地试验

需要 Docker Engine / Docker Desktop、Compose v2，以及访问 GitHub、Go 模块源、
Debian 软件源和 Google 认证服务的网络。以下命令在项目目录执行。

```bash
# 可选：复制环境配置；默认参数可以直接使用
cp .env.example .env

docker compose build --pull

# 推荐先登录并保存会话到持久卷，然后启动 API
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

客户端 Base URL：`http://127.0.0.1:8317/v1`。当前测试模型固定为 `gemini-3.5-flash-lite`，
通过插件请求时使用 `agy/gemini-3.5-flash-lite`。统一配置在 `scripts/test-model.txt`。
CLI 和 API 的模型列表必须包含目标模型；缺失直接失败，不回退到默认或其他模型。
这个固定值来自测试要求，不代表已经验证该账号或当前 agy 提供此模型。

## 验证调用与持久化

下面命令会访问上游；真实推理会消耗账号额度。它们不会自动运行。

```bash
docker compose exec cliproxy /opt/cliproxy/scripts/doctor.sh
docker compose exec cliproxy agy --model gemini-3.5-flash-lite -p 'Reply only with OK'
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --stream
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools

# 删除容器，保留命名卷
docker compose down
docker compose up -d

# 新进程 + 新容器中的真实推理才是关键验证
docker compose exec cliproxy agy --model gemini-3.5-flash-lite -p 'Reply only with OK'
docker compose exec cliproxy python3 /opt/cliproxy/scripts/smoke.py --tools
```

`agy models` 或 Docker 的 `healthy` 不能证明 Google 登录和推理一定正常。
`--tools` 验证一个无副作用函数的名称、参数、调用 ID、结果回传和最终回复，
不会执行模型提供的代码。流式工具调用仍需在真实客户端中另行验收。

## 凭证到底保存在哪

| 命名卷 | 容器路径 | 内容 |
| --- | --- | --- |
| `agy-home` | `/home/cliproxy` | `~/.gemini`、CPA auth、CLI 配置/缓存、工作目录（CLI 本体不在卷内） |
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

## CPA 导出凭据与官方 CLI

CPA 的 Antigravity JSON（如 `type: antigravity`、`access_token`、`refresh_token`、
`expired`）供 CPA 内置 `antigravity` provider 使用，不是官方 agy 的凭据导入格式。
放进 CPA 的 auth-dir 不会给 `agy` provider 或官方 CLI 建立登录会话。

官方 [安装与认证文档](https://antigravity.google/docs/cli/install/)说明 CLI 自身的
keyring/远程 OAuth 登录，以及 Gemini API key 模式；[企业文档](https://antigravity.google/docs/enterprise/)
另提供 ADC。没有据此确认 CPA JSON 可以直接导入，也没有验证字段转换方案。
Repository Secret `ANTIGRAVITY_JSON` 暂不被工作流引用，未将它写入 CLI 目录、镜像或日志。
真实 CLI 测试仍需可复用的官方登录会话或选定的受支持认证方式。

当前 CI 包含真实 CLI 的离线版本检查，以及无网络的 mock agy 集成测试，不消费真实账号额度。固定模型同时用于 mock 和手动实测；
mock 会检查插件传入的 `--model` 参数，但不能证明真实服务提供该模型。
CPA → 插件的路由阻塞已通过兼容补丁独立修复；该结果不依赖导入 CPA 内置 provider 的凭据。

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

官方 CLI 固定为 `1.2.12`，来自
[官方 GitHub Release](https://github.com/google-antigravity/antigravity-cli/releases/tag/1.2.12)。
`upstream-versions.json` 记录版本、资产名和 SHA256；Dockerfile 固定对应下载地址与哈希。
下载或校验失败会中止构建，禁止回退到 latest 或运行时安装。

CLI 位于镜像内 `/opt/agy/agy`，由 root 拥有，运行用户不能改写；
`/usr/local/bin/agy` 始终调用它，旧持久卷里的 `~/.local/bin/agy` 不会覆盖固定版本。
`AGY_CLI_DISABLE_AUTO_UPDATE=true` 同时保留。升级通过更换镜像完成，登录数据留在 HOME 卷。
`AGY_AUTO_INSTALL` 和 `AGY_INSTALLER_SHA256` 已移除，不再参与启动。
自动更新只追踪 CPA/插件；CLI 版本与哈希需显式修改，不会自动升级。

CPA/插件不固定在某个发行版：updater 每次查询最新正式 Release，检测到更新后自动构建、测试和发布 RC，无须人工批准升版。
`upstream-versions.json` 是已通过候选测试的构建输入快照，自动同步 Dockerfile 的版本和完整 commit SHA，
用于复现、审计与回滚，不是禁止升级的配置。单次构建仍使用准确 SHA，避免测试与发布期间源码漂移。
Go/基础镜像目前锁到版本系列，未锁 digest。正式版还需要固定这些依赖。
不要以“用了同一个 Go 编译器”为由假定兼容；插件使用 C ABI，其协议兼容性仍需验证。

## GitHub 与 GHCR

项目仓库：[eveloki/cliproxy-antigravity-docker](https://github.com/eveloki/cliproxy-antigravity-docker)。
历史实验镜像：`ghcr.io/eveloki/cliproxy-antigravity-docker:experimental`（保留，不再更新）。
新发布采用 `v<CPA版本>-<插件版本>-agy<CLI版本>-rc.<打包修订>`，并更新滚动标签 `rc` 和兼容别名 `latest`。
历史版本的发布记录：[Actions 36388336156](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36388336156)。
所有镜像都保留 **NOT READY — PENDING TESTS** 状态；发布成功不等于真实账号验收通过。

在 `.env` 中设置下面这一行，然后拉取镜像：

```dotenv
IMAGE=ghcr.io/eveloki/cliproxy-antigravity-docker:rc
# pull 时跟随最新通过门禁的 RC；需要回滚时使用带版本的 RC 标签或 digest
```

```bash
docker compose pull
docker compose run --rm --no-build cliproxy login
docker compose up -d --no-build
```

已有登录只需 `pull` 和 `up -d --no-build`，无需删除命名卷。自动发布不会自动更新你的运行中容器。
发布标签规则：

| 标签 | 含义 | 是否移动 |
| --- | --- | --- |
| `v8.0.4-0.1.3-agy1.2.12-rc.1`（示例） | CPA 8.0.4 + 插件 0.1.3 + CLI 1.2.12 的第一个 RC | 发布流程不覆盖 |
| `v8.0.4-0.1.3-agy1.2.12-rc.2`（示例） | 相同三组件版本的第 2 次打包修订 | 发布流程不覆盖 |
| `rc` | 最近成功发布的 RC，与版本标签 digest 一致 | 新版本通过检查后移动 |
| `latest` | `rc` 的兼容别名，不代表稳定版 | 与 `rc` 一起更新 |
| `sha-<完整发行层提交>` | 首次发布该版本所用的源码提交 | 随固定版本一并发布 |
| `experimental` 及已有 `experimental-*` | 历史实验镜像 | 保留，不再更新 |
| 已有 `*-r1` 等旧版标签 | RC 策略启用前的历史镜像 | 保留，不覆盖 |

`latest` 不代表项目已就绪；镜像标签和文档仍标记 **NOT READY — PENDING TESTS**。
带版本的 RC 标签是三个上游版本及打包修订的组合标识，不按单个 SemVer 的预发布规则排序。

版本标签本身不是注册表强制不可变：本仓库通过串行发布和发布前检查保证不覆盖，
若标签已存在则保留其 digest，仅修复 `rc` / `latest` 指向。鉴权或网络查询失败会终止发布，
不会当成“标签不存在”。有权限的人员仍可在流程外改动标签；严格锁定请使用 `image@sha256:...`。

同一上游组合需要修改 Dockerfile、启动脚本或基础镜像时，将 `upstream-versions.json`
中的 `packaging_revision` 递增到 2、3……，生成 `-rc.2`、`-rc.3` 标签。
任何上游版本更新时自动重置为 1，采用新组合的 `-rc.1` 标签；不需要人工修改版本。
若新版上游不能应用兼容补丁或路由测试失败，自动更新停止，必须先审阅适配或移除补丁。
仅修改文档不产生新的打包版本；重复执行不会重建并覆盖已经发布的版本标签。

### 自动跟踪上游

`Track stable upstream releases and publish RC` 每 30 分钟运行一次（每小时的 :17 和 :47）。
GitHub 调度可能延迟，也可在 Actions 手动 Run workflow。

1. 查询 CPA 与插件的最新正式 GitHub Release，解析标签到完整 commit SHA。
2. 拒绝草稿、预发布、版本回退和同版本标签被移动；包括跨主版本更新在内，都必须通过后续构建与集成检查。
3. 有更新时，先执行脚本测试、完整镜像构建、上游插件单测/ABI mock 测试，
   验证镜像内真实 `agy --version` 与锁定版本一致，再用无网络的 mock agy 检查 CPA → 插件调用是否正常。
4. 上述检查通过后才提交 `upstream-versions.json` 和 Dockerfile 到 main；只允许 fast-forward，
   其他人同时修改 main 时失败退出，不覆盖他人提交。
5. 显式调用可复用发布工作流，对该确切提交重新检查后发布 GHCR。
   不依赖机器人 push 触发另一个工作流，因此只需 `GITHUB_TOKEN`，无须 PAT。
6. 带版本的 RC 已存在且 `rc`、`latest` 与其 digest 均一致时跳过。缺失版本或任意别名更新中断时，下次检查重试；
   已存在的版本不会覆盖，两个别名从其现有 digest 创建，并从注册表重新读取验证三个标签一致。

任何构建/测试失败均不会发布候选镜像或移动 `rc` / `latest`。已有镜像保留；这不表示其功能已验证。
发布任务串行执行，并拒绝覆盖已被新 main 提交取代的版本。
这套自动化只升级 CPA 和插件；CLI 固定为锁定版本，不下载 Google 账号凭证。

### 手动发布与权限

- main push 自动检查最新上游、构建并发布缺失版本；PR 只检查并构建。
- Actions → **Experimental container (NOT READY)** → Run workflow → 勾选 `publish` 可发布当前 main。
  Git tag push 不再单独触发发布，镜像版本统一取自构建输入快照，避免产生任意标签。
- 上游检测流程需要 `contents: write` 记录通过测试的上游快照；发布任务需要 `packages: write`。
  若以后启用分支保护或组织限制，需要允许该机器人更新，或改用 PR 流程；不会绕过规则。
- 公共仓库并不自动保证 GHCR 包公开；包可见性应设为 Public，才能匿名拉取。
- 公共仓库长期无活动时，GitHub 可能暂停定时工作流；在 Actions 中重新启用即可。

CI 的 mock agy 不使用 Google 账号，不能替代真实认证、推理和工具调用验收。
稳定发布必须依据 [测试清单](docs/TESTING.md) 人工更新状态与版本策略。

## 上游与证据

核对日期：2026-09-28。完整来源与固定提交见 [docs/UPSTREAM.md](docs/UPSTREAM.md)。
本项目 MIT；上游与第三方软件遵循各自许可证，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
本项目与 Google、CLIProxyAPI 及插件作者无隶属关系；不承诺账号使用不会受到限制。
