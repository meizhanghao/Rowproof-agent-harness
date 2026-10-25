# RowProof Agent Harness

**基于数据契约与执行反馈的数据处理 Agent Harness**

一个可复现的 Python 工程原型：围绕代码生成 Agent，组织 **契约 → 执行 → 独立验收 → 反馈修复 → 工件发布** 的闭环。

首版以订单 CSV 清洗为演示任务，重点研究：**程序正常退出时，如何确认数据处理结果真的符合约定。**

> 状态：v0.1.0 原始实现。内置 fixture 路径可离线复现；Ollama 适配器和 Docker 执行器已提供代码与测试入口，真实模型和容器运行需要在你的环境中验证。fixture 的修复行为由脚本预设，不能作为模型推理能力或准确率的证据。

## 快速体验

需要 Python 3.10+。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m rowproof demo --output runs/demo-01
```

Linux/macOS 的对应命令见 [安装教程](docs/01-quickstart.md)。每次使用新的输出目录，程序会拒绝覆盖旧实验。

默认 demo 的第一次候选程序会正常退出，但故意漏掉一条有效订单。宿主验证器发现问题，Harness 将反馈交给 fixture backend，第二次候选修复后才发布结果。

演示数据的人工核对结果：12 条输入、6 条保留、6 条拒绝、保留订单总金额 `52.53`。这些是该样例的确定性结果。

```text
CREATED → GENERATING → EXECUTING → VALIDATING
                                      ↓ 失败
             GENERATING ← REPAIRING ←─┘
                 ↓
       EXECUTING → VALIDATING → PASSED → published/
```

## 已实现

- **契约建模：**Pydantic 定义 `orders.v1` 业务规则、JSON Schema 和执行预算。
- **独立验收：**从原始输入计算应保留记录，核对 CSV、逐行追踪记录及汇总报告。
- **修复闭环：**区分代码生成、执行、结果验收失败，有限次反馈重试。
- **执行适配：**可信 fixture 使用本地子进程；模型产生的代码要求 Docker。
- **过程证据：**保存每轮代码、运行日志、验收结果、JSONL 事件和最终文件哈希。
- **受控发布：**验收通过后校对复制文件的哈希，再以目录重命名发布完整工件。
- **实验入口：**对比“仅看退出码”“只验收”“验收并修复”三种策略。

## 使用真实模型

安装并启动 Ollama、Docker，确认本地模型支持结构化代码输出，预先拉取执行镜像：

```powershell
docker pull python:3.12-slim
ollama list
# 将下面的 your-installed-model-tag 换成 ollama list 中的实际名称。
.\.venv\Scripts\python.exe -m rowproof run --input examples/orders/input.csv --contract examples/orders/contract.json --output runs/ollama-01 --backend ollama --executor docker --model your-installed-model-tag
```

完整步骤、资源设置和排错见 [接入 Ollama](docs/04-connect-ollama.md)。仓库不包含模型权重，也不会自动下载模型。

## 项目结构

```text
rowproof-agent-harness/
├── src/rowproof/
│   ├── contracts.py       # 数据契约、输出协议、执行预算
│   ├── source.py          # 有界输入读取、宿主业务 oracle
│   ├── verifier.py        # 独立验收、结构与语义检查
│   ├── backends.py        # fixture / Ollama 代码生成适配
│   ├── prompts.py         # 代码生成协议与反馈提示
│   ├── executors.py       # 本地 fixture / Docker 执行
│   ├── harness.py         # 状态机、修复预算、工件发布
│   ├── benchmark.py       # 明确标记为脚本化的对照实验
│   ├── cli.py             # 命令行入口
│   └── assets/            # 安装到 wheel 后仍可运行的内置样例
├── examples/orders/       # 输入、契约、人工编写的期望结果
├── tests/                 # 业务语义、篡改、超时、闭环、适配器测试
├── schemas/               # 导出的契约 JSON Schema
├── docs/                  # 从安装到复现、扩展、简历的教程
├── tools/                 # 名称检查、源码归档工具
├── .github/workflows/     # 多平台测试与可选 Docker 测试
├── pyproject.toml
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
└── LICENSE
```

## 文档导航

| 文档 | 读完之后能做什么 |
|---|---|
| [从这里开始](docs/00-start-here.md) | 明确项目目标、实现范围与阅读顺序 |
| [安装与首次复现](docs/01-quickstart.md) | 跑通演示并检查输出 |
| [契约和业务规则](docs/02-contracts.md) | 解释去重、舍入、拒绝原因和逐行追踪 |
| [架构与状态机](docs/03-architecture.md) | 跟踪一次任务的完整调用过程 |
| [接入 Ollama 和 Docker](docs/04-connect-ollama.md) | 将 fixture 换成真实代码生成模型 |
| [测试与评测](docs/05-testing-and-evaluation.md) | 复现对照实验，设计真实模型评测 |
| [扩展新任务](docs/06-extend-a-task.md) | 添加任务 profile 和独立验收器 |
| [提交 GitHub](docs/07-github.md) | 清理本地输出、建立自己的远程仓库 |
| [学习与改进路线](docs/08-learning-roadmap.md) | 分阶段理解和改写实现 |
| [简历与面试说明](docs/resume.md) | 按实际完成范围描述项目 |
| [参考与差异](docs/references.md) | 理解与 Deep Agents、Harbor 等项目的关系 |
| [本次验证记录](docs/verification.md) | 查看已执行检查与未验证路径 |

## 测试与实验

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m rowproof benchmark --output runs/ablation-01 --repetitions 3
```

对照实验仅使用预设的候选脚本和一个植入的数据丢失问题。结果用于检验控制流，不能推导真实 LLM 的成功率、生产可靠性或成本收益。

## 当前边界

首版支持固定表头的 UTF-8 订单 CSV 和 `orders.v1`，不支持任意 Excel/PDF/自然语言业务规则。规则被明确规定后，普通确定性 ETL 就能完成同一清洗任务；这里选择它，是为了给 Harness 提供可精确验证的实验任务。通用性体现在生成后端、执行器和闭环结构，业务验证仍需逐个 profile 编写。

模型不能修改宿主验证器。本地 ProcessExecutor 仅用于内置信任脚本，Docker 路径提供实际隔离配置，但不是经过安全审计的任意恶意代码执行服务。详见 [执行边界](SECURITY.md)。

## 名称

2026-10-24 的 GitHub 公共仓库检索未发现 `rowproof-agent-harness`、`RowProof Agent Harness` 或本项目中文标题的匹配仓库，原始返回见 [名称核对记录](docs/name-check-2026-10-24.json)。该结论仅对应检索时间和可见公共仓库，不表示包索引占名或商标注册。

## 声明

我是一名广西大学的研究生，在进行课题组项目“东盟语料库平台”中发现Agent存在误删记录、重复统计、错误转换金额，或者遗漏某些数据等行为，基于Agent Harness的工程化能力，实现并开发了此项目用于解决此类问题。 引言：此前Deep Agents 的 RubricMiddleware项目 （https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/rubric.py）已支持评分反馈与继续迭代;Anthropic 关于长任务 Harness（https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents） 的实践也强调了明确完成条件和实际测试的重要性。 而本项目核心贡献在数据契约、可执行验证规则、记录追踪及工件交付条件上

## License

[MIT](LICENSE)。本仓库提供原创最小实现；参考资料和上游能力见 [references.md](docs/references.md)。
