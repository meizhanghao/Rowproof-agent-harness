# 接入 Ollama 与 Docker

## 1. 准备环境

先完成 [离线演示](01-quickstart.md)。真实模型路径需要：

- 本机安装并运行 Ollama，存在一个可用的代码生成模型。
- 安装并启动 Docker。Windows 使用 Docker Desktop 的 Linux containers 模式。
- 模型支持本地 `/api/generate` 和 JSON Schema 结构化输出。不同模型的遵循能力需要实际测试。

安装方式按 [Ollama 官方说明](https://docs.ollama.com/) 和 [Docker Desktop 文档](https://docs.docker.com/desktop/) 操作。模型选型取决于你的 CPU/GPU、内存及显存，本仓库不固定模型权重。

```powershell
ollama list
docker version
docker pull python:3.12-slim
```

镜像需要预先拉取。执行器使用 `--pull=never`，避免把下载时间混进候选程序的执行时限。若需精确复现实验，可以传入你实际验证的镜像 digest，并记录模型 tag/digest。

## 2. 先单独检查 Docker 路径

```powershell
.\.venv\Scripts\python.exe -m rowproof demo --executor docker --output runs/docker-fixture-01
```

这个命令仍使用固定 fixture，但在真实容器中运行。如果它失败，先解决挂载、镜像或容器启动问题，再排查模型。

## 3. 接入模型

将 `your-installed-model-tag` 替换为 `ollama list` 中的真实名称：

```powershell
.\.venv\Scripts\python.exe -m rowproof run --input examples/orders/input.csv --contract examples/orders/contract.json --output runs/ollama-01 --backend ollama --executor docker --model your-installed-model-tag
```

默认地址是 `http://127.0.0.1:11434`。远程部署时用 `--ollama-url` 指定地址。

`.env.example` 只说明支持的环境变量；程序没有自动加载 `.env` 的依赖。在 PowerShell 中可以显式设置：

```powershell
$env:ROWPROOF_OLLAMA_URL = "http://127.0.0.1:11434"
$env:ROWPROOF_OLLAMA_MODEL = "your-installed-model-tag"
```

## 4. 模型协议

`OllamaBackend` 调用官方 [`POST /api/generate`](https://docs.ollama.com/api/generate)，设置 `stream=false`，并将 `CodeProposal` 的 JSON Schema 传入 `format`。响应要求包含：

```json
{
  "summary": "候选程序实现说明",
  "python_code": "完整 Python 源代码"
}
```

候选只允许依赖 Python 标准库，接收 `--input/--contract/--output` 参数。容器镜像不包含 pandas，也不允许联网安装依赖。若想支持 pandas，应先制作自己的固定镜像、修改生成协议并补测试。

适配器设置请求超时 120 秒、`temperature=0` 和 `num_predict=4096`。这些设置不保证输出可复现或足够长；过长程序被截断时，会通过生成失败反馈进入下一次尝试。

`proposal.json` 保存模型返回的 token 计数（如果服务提供）；它不能用于推算未记录的服务价格或完整经济成本。

## 5. 容器配置

容器使用非 root 用户、只读根文件系统、关闭网络、移除 capabilities、限制内存/CPU/PID，只挂载当前程序、当前输入快照和候选输出目录。超时后除终止 Docker CLI，还执行容器清理。

它适用于个人实验，尚未经恶意代码安全审计。输出字节预算在验收阶段检查，不是实时磁盘配额。详见 [SECURITY.md](../SECURITY.md)。

## 6. 排错顺序

1. 确认离线 fixture 路径通过。
2. 确认容器 fixture 路径通过。
3. 确认本机 Ollama 模型可正常输出 JSON。
4. 查看当前尝试目录的 `program.py`、`execution.log`、`verification.json` 或 `feedback.json`。
5. 区分：生成协议错误、Python 执行错误、业务验收错误。

`model-produced code requires the Docker executor` 表示忘记传 `--executor docker`，不要通过关闭检查来绕过它。模型出现持续错误时，保留失败案例并加入后续评测。

## 当前验证状态

本次交付环境没有 Docker，也没有运行 Ollama 真实模型；接口通过模拟 HTTP 响应测试。完成上述真实运行后，在你的实验记录中补上模型、镜像、硬件、命令、样例及失败情况。
