# 测试状态：未就绪，等待测试

本文件记录实际完成情况，不根据 CI 绿灯自动修改状态。

| 项目 | 当前状态 | 验收标准 |
| --- | --- | --- |
| 本地脚本和配置检查 | 已通过（2026-09-28） | 见下面本次执行记录 |
| Docker amd64 完整构建 | 已通过（2026-09-28 首次 CI） | CPA、插件编译及上游 ABI mock 测试成功 |
| CPA 实际加载插件 | 已通过（CI mock） | 无 ABI/协议加载错误，`agy/default` 注册可用 |
| 无网络容器模拟推理 | **失败：503 auth_not_found** | CPA 必须调用 mock agy 并返回模拟响应 |
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

- `python3 -m unittest discover -s tests -v`：10/10 通过（包含 6 项版本检测测试）。
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
  目前判为该上游组合的集成阻塞，具体上游修复尚未完成。
- 每 6 小时的检查已配置；有同主版本正式更新时，先构建并测试候选，成功后才提交版本锁并发布。
  当前组合仍会被上述门禁拦下，旧 experimental 镜像也不能视为可用版本。
  真正的上游版本变化、自动提交及后续成功发布路径仍需在兼容版本到来时验证。
