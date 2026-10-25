# 参考项目、定位与差异

以下资料用于理解工程边界，本仓库没有复制这些项目的实现代码。资料访问与名称检索日期为 2026-10-24。

| 资料 | 参考的内容 | RowProof 的实现范围 |
|---|---|---|
| [Deep Agents](https://github.com/langchain-ai/deepagents) | 成套 Harness 的组织方式与可替换组件 | 使用自己的小型同步循环，聚焦数据契约和独立验收 |
| [RubricMiddleware](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/rubric.py) | 根据评分反馈继续迭代 | orders.v1 使用宿主确定性 oracle，逐行核对数据 |
| [LangGraph](https://github.com/langchain-ai/langgraph) | 状态化编排与持久化的基础能力 | 首版只做显式状态转换，不声明持久化恢复能力 |
| [Harbor](https://github.com/harbor-framework/harbor) | 任务环境、Agent 执行和独立评测的组织 | 内置一个 CSV 任务和一个小型控制流实验，不替代通用评测框架 |
| [Anthropic 长任务 Harness 实践](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 具体完成条件和实际测试的重要性 | 数据验收通过后才发布工件 |
| [Ollama Generate API](https://docs.ollama.com/api/generate) | JSON Schema 输出、非流式生成、响应计数 | OllamaBackend 使用该接口生成和修复 Python 程序 |

## 差异化如何落到代码

本项目的重点是明确且可测试的 `orders.v1` 契约、逐条源记录的保留/拒绝判断、候选报告与独立 oracle 的交叉核对，以及错误候选不发布的闭环。

这些工程模式并非全球首创。个人贡献应通过新增 profile、验证规则、失败案例、真实模型实验和代码改进来体现，不能把上游的通用能力描述成自己的创新。

## 为什么首版没有强制使用 LangChain / 多 Agent / MCP

一个清晰的同步循环足以验证当前目标，便于从代码理解状态与数据流。后续可按实际需要接入 LangGraph 或 MCP；没有对应代码与测试之前，不应将其写为已实现技术栈。
