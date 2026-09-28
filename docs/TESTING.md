# 测试状态：未就绪，等待测试

本文件记录实际完成情况，不根据 CI 绿灯自动修改状态。

| 项目 | 当前状态 | 验收标准 |
| --- | --- | --- |
| 本地脚本和配置检查 | 已通过（2026-09-28） | 见下面本次执行记录 |
| Docker amd64 完整构建 | 已通过（2026-09-28 首次 CI） | CPA、插件编译及上游 ABI mock 测试成功 |
| CPA 实际加载插件 | 未执行 | 无 ABI/协议加载错误，`agy/default` 注册可用 |
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
| GHCR 发布与拉取 | 未执行 | 干净机器拉取 experimental 镜像并重复以上测试 |
| ARM64 / Docker Desktop | 未执行 | 不属于首版已支持范围 |

## 本次本地执行记录

日期：2026-09-28。

- `python3 -m unittest discover -s tests -v`：4/4 通过。
  覆盖配置重复初始化不会轮换 key、配置权限 0600、用户修改保留、
  错误模板不产生半成品、已有 agy 复用、禁用安装时缺失 agy 正确失败。
- `python3 -m compileall -q scripts tests`：通过。
- 逐个脚本执行 `bash -n`：通过。
- `compose.yaml`、`config.example.yaml`、GitHub workflow YAML 解析：通过。
- 核对插件路径和 API-key 模板占位符：通过。
- 当前执行环境无 Docker、Go、ShellCheck。因此未执行 `docker compose config`、
  Docker build、Go 单测、插件 ABI mock 或真实 agy/OAuth/API 测试。
  Dockerfile/CI 已定义相关构建检查，尚未运行。

这些结果仅验证薄层脚本的离线行为，不代表镜像可以成功构建或账号可正常调用。

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
