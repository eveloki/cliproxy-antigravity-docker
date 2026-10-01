# 测试状态：正式版 / Stable

## RC 卷迁移与兼容性复查（2026-10-01，r3 已发布）

生产侧报告正确指出：先前非 root smoke 使用新容器，没有挂载 RC 创建的旧命名卷。
旧卷缺少 `plugins/`，使 `/opt/cliproxy/plugins` 成为悬空目录链接，`Path.mkdir` 报 EEXIST。
这属于发行层兼容缺陷，不能将此前 CI 通过解释为旧卷升级已通过。

- 本地先复现失败，再验证修复：解析目录链接后创建目标，保留用户自管插件链接。
- 26 项本地测试通过；同时修复重复 `-config` 的最后值/终止符解析，透传原生 help/discover。
- 对照 CPA v8.0.8 Dockerfile 检查 Version、Commit、BuildDate 三项 ldflags；均已注入。
  管理接口回归现在同时核对版本、提交和 UTC 日期，系统时区文件也与上游对齐。
- `tests/upgrade-smoke.sh` 使用实际 `v8.0.6-0.1.3-agy1.2.12-rc.1` 镜像创建命名卷，
  固定 digest `sha256:1d8432eb6bc1f202adc15c38f45fe075b01f04f3f82ba1880feb9c0b08611f39`。
  不预建 plugins，使用仓库 Compose 升级、重建、回滚；检查旧文件哈希/权限/属主、
  插件播种、模型发现、模拟普通/SSE 请求及 CLI HOME 持久化。
- 同时保留原有非 root 新部署、上游五挂载测试，增加只读根文件系统下原生帮助命令比对。

[Actions 36821300972](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36821300972)
全部成功，源码提交 `b113d7e7628c961a73fef0b2e670648fc610e1d9`。
26 项单测、非 root 新部署、上游五挂载、真实 RC 旧卷升级/重建/回滚三组容器测试通过。
管理接口版本和提交与镜像内来源记录一致，构建时间为 `2026-10-01T05:25:34Z`：
本次复用 r2 的 CPA 二进制编译缓存，保留其实际编译时间。

正式版 `v8.0.8-0.1.3-agy1.2.12-r3`、`stable`、`latest` 已发布并核对为同一 digest：
`sha256:d33cfce40ba2f51f4551fe00a5e213da304766ec5f05d775b8b34ed345f49347`。
更新仓库 Compose 后，RC 旧卷升级无需生产侧报告中临时提出的手动建目录/改配置步骤。

全部使用合成状态，不读取生产卷或真实 Google 凭据；
原生 provider 的在线认证、任意第三方插件、远程配置后端和 ARM64 不在本次验收范围。

## Deployment compatibility (2026-10-01)

Version `v8.0.8-0.1.3-agy1.2.12-r1` aligns the default root image with the upstream
`/CLIProxyAPI` working directory and five bind mounts. The repository Compose explicitly
retains the existing non-root HOME and named volumes. English/Chinese READMEs document both modes.

23 Python tests pass locally and in CI. New CI coverage passes legacy read-only config,
root user/workdir, native synthetic Codex credential enumeration, plugin seeding, writable plugin/data
mounts, file logs, isolated agy HOME and recreation persistence. The existing non-root JSON/SSE
integration also passes. No Google credentials are used. The update job in
[Actions 36817926461](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36817926461)
verified both deployment modes before committing the CPA 8.0.8 snapshot. The CLI remains pinned to 1.2.12.

The publish job repeated the integration checks and published the non-prerelease
[GitHub Release](https://github.com/eveloki/cliproxy-antigravity-docker/releases/tag/v8.0.8-0.1.3-agy1.2.12-r1).
Source: `6128ecf623c7c087dcedf9b7dcd5d1b12e0f1cbd`.
The fixed tag, `stable` and `latest` were checked to have the same digest:
`sha256:c2a29a35b19bd4e3a854d87a0187ec1ef41eeeb6c19323580a493202b6cb1634`.

## 2026-10-01 正式发布验收

维护者 eveloki 在实机环境确认 `gemini-3.8-flash` 可用，并明确要求升级为正式版。
这是维护者提供的验收结论；本次维护没有读取 Google 凭据，也没有代跑真实账号推理。

- 已发布正式版：`v8.0.7-0.1.3-agy1.2.12-r2`（CPA 8.0.7 / 插件 0.1.3 / CLI 1.2.12）。
- 默认测试模型和所有当前命令示例更新为 `gemini-3.8-flash`；API 使用 `agy/gemini-3.8-flash`。
- README 纳入官方登录、重启发现模型、读取客户端 API key、doctor 和 `smoke.py --tools` 操作。
- STATUS、启动提示、镜像标签和工作流转为 STABLE；发布固定版本、stable、latest 和 GitHub 正式 Release。
- CI 验证真实 CLI 的离线启动，以及模拟 JSON/SSE、认证和路由边界；不执行 Google 推理。

| 范围 | 证据及状态 |
| --- | --- |
| gemini-3.8-flash 实际可用性 | 维护者于 2026-10-01 确认通过 |
| 官方登录与调用操作 | README 已按维护者提供的流程整理 |
| 本次发布构建与离线集成 | [Actions 36808623835](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36808623835) 全部通过 |
| 工具闭环的独立日志、流式工具调用、并发与异常恢复 | 本次未提供逐项结果，不据此宣称专项验收通过 |
| ARM64 / Docker Desktop | 未单独验收，当前发布 linux/amd64 |

发布状态依据维护者验收与发布决定更新。后续自动升级仍以 CI 为发布门槛，
不把本次模型实测结论扩展成对所有账号、环境或未来上游版本的保证。

## 本次正式发布证据

- 源码提交：`37a6e63740375f0729efe188cbf64962c5f36760`。
- 18 项 Python 单测、脚本/Compose 检查、完整构建、插件 Go 单测和 ABI 测试通过。
- 真实 agy 1.2.12 在非 root、断网容器中启动成功；gemini-3.8-flash mock 普通响应、SSE、401 和路由边界检查通过。
- [GitHub 正式 Release](https://github.com/eveloki/cliproxy-antigravity-docker/releases/tag/v8.0.7-0.1.3-agy1.2.12-r2) 已发布，非草稿、非预发布。
- 固定标签 `v8.0.7-0.1.3-agy1.2.12-r2`、`stable`、`latest` 均已发布，工作流重新查询确认 digest 一致：
  `sha256:80f6c2a34a263df54e17bbd07b6de4bcbe79963a78ee84b889e261d3e5e42f85`。

## 历史记录（以下保留当时状态）

以下内容中的“未就绪”、旧模型及 RC/实验标签均为历史测试记录，不表示当前发布状态。

本文件记录实际完成情况，不根据 CI 绿灯自动修改状态。

| 项目 | 当前状态 | 验收标准 |
| --- | --- | --- |
| 本地脚本和配置检查 | 已通过（2026-09-28） | 见下面本次执行记录 |
| Docker amd64 完整构建 | 已通过（2026-09-28 首次 CI） | CPA、插件编译及上游 ABI mock 测试成功 |
| CPA 实际加载插件 | 已通过（CI mock） | 无 ABI/协议加载错误，`agy/default` 注册可用 |
| 无网络容器模拟推理 | **已通过：r2 路由与 SSE 补丁** | 普通响应、SSE、精确模型、401 和原生路由检查均通过 |
| agy 首次安装 | 未执行 | 官方安装器成功，版本与安装位置可确认 |
| 容器内 Google 登录 | 未执行 | 官方交互登录成功，无 keyring 阻断 |
| 文件凭证复用 | 未执行 | 新 agy 进程可多次完成真实推理 |
| 容器删除后重建 | 未执行 | `down` / `up` 后无需登录即可推理 |
| 镜像更新 | 未执行 | 保持卷后升级可复用配置与凭证 |
| 非流式响应 | 未执行 | `scripts/smoke.py` 成功 |
| 文本流式响应 | 未执行 | `scripts/smoke.py --stream` 成功 |
| 非流式工具闭环 | 未执行 | `scripts/smoke.py --tools` 成功 |
| 流式工具闭环 | 未执行 | Cline/RooCode 等客户端工具调用、参数、回传正确 |
| 并发请求 / 取消 | 未执行 | 无凭证竞争、会话串线和孤儿 agy 进程 |
| 超时 / 断网 / token 撤销 | 未执行 | 返回可诊断错误，不无限挂起或重试 |
| GHCR 发布 | 已通过（首次实验镜像，公开包） | 见下方发布记录；不能据此判定可用 |
| 干净机器拉取并运行 | 未执行 | 拉取 experimental 镜像并重复以上真实测试 |
| ARM64 / Docker Desktop | 未执行 | 不属于首版已支持范围 |

## 本次本地执行记录

日期：2026-09-28。

- `python3 -m unittest discover -s tests -v`：15/15 通过（包含版本与注册表检查）。
  覆盖配置重复初始化不会轮换 key、配置权限 0600、用户修改保留、
  错误模板不产生半成品、已有 agy 复用、禁用安装时缺失 agy 正确失败。
- `python3 -m compileall -q scripts tests`：通过。
- 逐个脚本执行 `bash -n`：通过。
- `compose.yaml`、`config.example.yaml`、GitHub workflow YAML 解析：通过。
- 核对插件路径和 API-key 模板占位符：通过。
- 当前执行环境无 Docker、Go、ShellCheck。因此未执行 `docker compose config`、
  Docker build、Go 单测、插件 ABI mock 或真实 agy/OAuth/API 测试。
  这些检查随后在 GitHub Actions 执行，结果见下方 CI 记录。

本地结果仅验证薄层脚本的离线行为；CI 构建结果另列，均不能证明真实账号可正常调用。

## 实机记录模板

复制此段，为每次测试单独填写，不能只写“通过”。

```text
日期：
宿主机 OS / CPU 架构：
Docker / Compose 版本：
发行层 git commit / 镜像 digest：
CPA commit / plugin commit：
agy --version：
安装器 SHA256：
首次登录结果：
新进程真实推理次数与结果：
down/up 后推理：
流式响应：
非流式与流式工具闭环：
并发/取消/超时：
失败日志（已去除 key、token、授权 URL、账号信息）：
```

文件持久化和认证成功要分别记录。`ls` 看见 token 文件、`agy models`
能输出内容、`/v1/models` 有静态模型、容器显示 healthy，都不能单独判定认证通过。
真实测试可能消耗额度，逐项显式执行，不要放进循环健康检查。

没有真实账号结果前，README、STATUS、镜像标签都必须保留未就绪标识。

## 首次 CI 构建证据

[Actions run 36367677092](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36367677092)
在提交 `4096e59e1c4590b85b81e2177d1260e71ff8e449` 上成功，完成 Docker 构建及构建内的插件测试。
这次运行没有发布镜像。后续发布工作流额外要求无网络 mock agy 容器测试；
它只验证打包与路由，不证明真实 Google 凭证有效。

## 发布、自动更新与已知阻塞（2026-09-28）

- 首次发布 [run 36368680680](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36368680680) 成功。
  公开镜像 `ghcr.io/eveloki/cliproxy-antigravity-docker:experimental` 对应发行层提交
  `4096e59e1c4590b85b81e2177d1260e71ff8e449`；该版本发布时尚无下面的容器路由检查。
- 自动更新试运行 [run 36369226939](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36369226939)
  成功查询两项上游正式 Release，确认 CPA v8.0.3 / 插件 v0.1.3 未变，
  并因当前发行层提交尚无镜像而进入发布重试；随后的集成检查正确阻止发布。
- 带诊断日志的复现 [run 36369485927](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36369485927)：
  编译、插件单测、ABI mock 均成功。容器以非 root、断网模式启动，插件加载成功，
  `/v1/models` 返回 `agy/default`；但 `/v1/chat/completions` 返回：

  ```text
  503 auth_not_found: no auth available (providers=agy, model=agy/default)
  ```

  测试使用本地 mock agy，不使用 Google 账号，错误发生在 CPA 选择 provider auth 的阶段。
  上游插件声明不注入伪造 CPA 凭证；因此没有通过伪造 auth 文件或删除测试绕过问题。
  当时判为该上游组合的集成阻塞；现由下方 r2 兼容补丁修复，未宣称上游版本自身已修复。
- 每 6 小时的检查已配置；有同主版本正式更新时，先构建并测试候选，成功后才提交版本锁并发布。
  当时未打补丁的组合被上述门禁拦下，旧 experimental 镜像仍不能视为可用版本。
  真正的上游版本变化、自动提交及后续成功发布路径仍需在兼容版本到来时验证。

## 固定版本发布策略（2026-09-28）

后续发布采用 `v<CPA版本>-<插件版本>`，打包修订追加 `-rN`；旧 `experimental` 标签冻结。
发布任务检查固定版本是否存在，已存在则保留原 digest；`latest` 在检查通过后才移动到该 digest。
版本与 latest 的发布分开进行，避免只改了 latest 而固定版本未成功；中断后允许重试。
注册表鉴权、网络故障不会被当成版本缺失。没有移除或放宽上述 `503 auth_not_found` 集成检查。
新增规则的离线测试覆盖版本组合、打包修订、上游更新重置修订号、digest 解析和注册表查询失败。
固定版本及 latest 的实际首次推送，仍等待集成阻塞修复后验证。

## 当前测试模型与凭据边界（2026-09-28）

- 测试模型固定在 `scripts/test-model.txt`：`gemini-3.5-flash-lite`。
- API 请求使用插件命名空间 `agy/gemini-3.5-flash-lite`，防止误测 CPA 内置 provider。
- 离线 mock 注册该模型，并要求插件传入精确的 `--model gemini-3.5-flash-lite`。
- 手动真实 smoke 先检查精确模型是否存在；不存在则失败，不自动切换模型。
- 上方历史日志的 `agy/default` 保留为原始复现证据，不代表当前测试模型。
- 未验证真实 agy/账号是否提供该模型。CPA 导出的 JSON 未被确认可用于 agy 登录，
  因而没有引用 `ANTIGRAVITY_JSON`，没有执行真实账号测试。官方认证依据见 README。

## 路由兼容补丁候选（2026-09-28）

针对上述失败，在插件构建时应用 `compat/plugin-model-router.patch` 和路由适配源码，
显式声明 `model_router`，处理 `model.route` 并对非空 `agy/*` 返回 `TargetKind=self`。
CPA 不修改；无伪造 auth 文件；非插件命名空间不接管。
打包修订递增为 r2，插件元数据标记 `0.1.3+cpa8-route1`。

新增 Go 回归测试验证 ABI 分发、非流式/流式路由、原生模型排除和畸形输入。
容器测试固定 `gemini-3.5-flash-lite`，同时验证 JSON、SSE 完整终止、实际 mock 进程调用记录、
无 CPA 凭据以及客户端 API key 缺失返回 401。CI 结果待记录，不提前声明修复成功。

第一次补丁 CI [36377577104](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36377577104)
已确认普通模拟请求返回 200 和预期内容，消除了 `auth_not_found`。
扩展 SSE 测试发现第二项兼容问题：插件发送完整 SSE 帧，而 CPA 再添加 `data:`，导致双层封装。
现在补丁在 host stream callback 边界发送纯 JSON，并由 CPA 统一发送 `[DONE]`；
测试同时拒绝重复终止帧。完整回归结果待下一次 CI。

## 路由修复验收通过（2026-09-28）

[完整 Actions 36377898486](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36377898486) 在提交
`c5128e09ffd9f22d40097a5247f44ea1bf6f5b89` 上全部成功。

- validate：脚本/配置/版本锁检查通过。
- image：CPA 构建、打补丁后的插件 Go 单测、上游 ABI smoke、Docker 构建通过。
- 无网络、非 root、无 CPA 上游凭据的容器内，
  `agy/gemini-3.5-flash-lite` 普通请求返回预期 mock 响应。
- 流式请求获得正确内容、finish_reason 和唯一 `[DONE]`；不再双重 SSE 封装。
- mock 子进程记录确认实际收到 `--model gemini-3.5-flash-lite`，普通和流式各一次。
- 无客户端 key 返回 401；不带 agy/ 前缀的原生请求没有被插件接管。
- 未读取 `ANTIGRAVITY_JSON`，未执行 Google OAuth 或真实推理。

结论：原 `auth_not_found` 阻塞与随后发现的 SSE 封装问题已在发行层兼容补丁中修复。
打包版本为 `v8.0.3-0.1.3-r2`，项目仍为 **NOT READY — PENDING TESTS**。
这次 main push 的完整 CI 为构建验证模式，发布步骤跳过；不等同于 r2/latest 已发布。

## CLI 固定打包候选（2026-09-28）

新版本 `v8.0.3-0.1.3-agy1.2.12-r1`：将官方 CLI 1.2.12 内置在镜像层，
保留此前 r2 的插件路由与 SSE 修复。上述不带 agy 的标签和运行时安装记录是历史结果。

- 已下载官方 Linux x64 安装包并验证 GitHub 公布的 SHA256。
- 本地真实二进制 `--version` 返回 `1.2.12`。
- 更新后的 15 项离线单测通过，包括 CLI 锁不随 CPA 更新而改变、非法 CLI 锁拒绝、三组件标签。
- CI 新增非 root、断网容器执行真实 `agy --version`，随后独立执行 mock JSON/SSE 路由测试。
- main push 与每六小时定时检查均自动检测 CPA/插件正式版，测试通过后发布固定标签和 latest。
- 本次容器构建/发布结果待 Actions 确认；真实凭据与 gemini-3.5-flash-lite 推理仍未验收。

## 官方 CLI 内置镜像发布通过（2026-09-28）

[Actions 36388336156](https://github.com/eveloki/cliproxy-antigravity-docker/actions/runs/36388336156)
在发行层提交 `5d44ee0a77e1e6e822ef6cfe8bcd5c57bb9d608c` 上全部成功。

- update：检查 CPA/插件最新正式发布，当前版本未变；CLI 锁保持 1.2.12。
- publish / validate：15 项单测、脚本、YAML/Compose 和版本锁验证通过。
- publish / image：完整镜像构建成功；真实 `agy 1.2.12` 在非 root、断网容器中通过版本检查。
- 独立 mock 测试通过非流式、SSE、客户端 401 和原生路由边界检查。
- 已发布 `ghcr.io/eveloki/cliproxy-antigravity-docker:v8.0.3-0.1.3-agy1.2.12-r1`。
- `latest` 已指向相同 digest，并由工作流从注册表重新读取校验：
  `sha256:a2242d813199a119fff4df331737a9845e400e0d69352ed9f3eb7ff5bb827988`。
- 原有 experimental 标签未改动；真实账号凭据、模型推理和工具调用仍待验收。

项目继续保持 **NOT READY — PENDING TESTS**。上面的“待 Actions 确认”是此次构建前记录。
