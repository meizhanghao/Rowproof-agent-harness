# 安装与首次复现

## 1. 环境

默认演示只需 Python 3.10+ 和 Pydantic 2，不需要 API Key、模型、Docker 或 GPU。开发工具通过 `dev` extra 安装。所有命令都在仓库根目录执行。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m rowproof --help
```

直接调用虚拟环境解释器即可，不必修改 PowerShell 执行策略。

Linux / macOS：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m rowproof --help
```

下面以 Windows 为例；其他系统将解释器路径替换为 `.venv/bin/python`。

## 2. 运行修复演示

```powershell
.\.venv\Scripts\python.exe -m rowproof demo --output runs/demo-01
```

预期最终 JSON 中 `status` 为 `passed`，`attempts` 为 `2`。第一次脚本故意漏掉最后一条有效订单，退出码仍为 0。你可以在 `attempts/001/execution.json` 与 `verification.json` 中分别确认这两个事实。

## 3. 查看证据

```text
runs/demo-01/
├── snapshot/source.csv              # 本次任务固定的原始输入
├── snapshot/contract.json           # 本次生效契约
├── attempts/001/
│   ├── program.py
│   ├── proposal.json
│   ├── execution.log
│   ├── execution.json
│   ├── artifacts/
│   ├── verification.json
│   └── feedback.json
├── attempts/002/                    # 修复后的独立目录
├── events.jsonl
├── result.json
└── published/
    ├── clean.csv
    ├── lineage.json
    ├── report.json
    └── manifest.json
```

PowerShell：

```powershell
Get-Content runs/demo-01/attempts/001/verification.json
Get-Content runs/demo-01/published/clean.csv
Get-Content runs/demo-01/published/report.json
```

`report.json` 应为输入 12 条、保留 6 条、拒绝 6 条、总金额 `52.53`。`manifest.json` 是宿主生成的元数据，包含契约与输入哈希、工件哈希；它不是数字签名。

## 4. 独立重新验收

```powershell
.\.venv\Scripts\python.exe -m rowproof validate --input runs/demo-01/snapshot/source.csv --contract runs/demo-01/snapshot/contract.json --artifacts runs/demo-01/published
```

查看退出码：PowerShell 使用 `$LASTEXITCODE`；Bash 使用 `$?`。

| 退出码 | 含义 |
|---|---|
| 0 | 运行或独立验收通过 |
| 1 | 候选未通过验收，或重试预算耗尽 |
| 2 | 参数、输入、依赖或运行环境错误 |

## 5. 观察失败封闭行为

```powershell
.\.venv\Scripts\python.exe -m rowproof demo --fixture always-broken --output runs/fail-01
```

预期退出码为 1，最终 `status=failed`，不存在 `published/`，每次失败的候选仍保存在 `attempts/`。不要把命令退出码 1 当成程序安装失败。

## 6. 使用自己的输入

复制 `examples/orders/input.csv` 和 `contract.json`，保持固定表头，改变数据。然后执行：

```powershell
.\.venv\Scripts\python.exe -m rowproof run --input examples/orders/input.csv --contract examples/orders/contract.json --output runs/custom-01 --backend fixture --executor process
```

fixture 适用于当前 `orders.v1`。如果输入没有有效记录，预设的“漏最后一条”变化可能不会产生错误，此时首轮就会通过；这也是固定 fixture 的边界。

## 常见问题

- `No module named rowproof`：确认使用安装项目的同一个虚拟环境解释器。
- 输出目录已存在：换一个新的目录，保留旧实验用于对比。
- `input header must be exactly ...`：首版要求列名与顺序完全匹配，不支持额外字段。
- 模型后端要求 Docker：这是运行约束；默认子进程执行器只运行内置信任脚本。
- 无法从软件源安装：项目运行依赖为 Pydantic 2；先排查本机网络或使用自己的 Python 包镜像。

本次环境访问 PyPI 超时，改用清华镜像安装。遇到相同网络情况可执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" --index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

这是本次安装命令的参数，不需要修改全局 pip 配置。
