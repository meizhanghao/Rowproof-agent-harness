# 从这里开始

## 你将复现什么

RowProof 是围绕代码生成模型的一个小型 Agent Harness。模型提出候选 Python 程序，Harness 管理执行环境、验收条件、反馈修复次数和结果发布。

这份初版已经提供项目骨架和核心实现。建议先理解并改写，再逐步把固定演示扩展成自己的项目。

## 三层分工

| 层 | 模块 | 职责 |
|---|---|---|
| 数据规范与验收 | contracts / source / verifier | 明确什么结果才正确 |
| 执行与控制 | executors / harness | 管理候选、执行、反馈和发布 |
| 生成策略 | backends / prompts | 根据任务与失败反馈生成代码 |

fixture backend 用预设脚本模拟候选变化。Ollama backend 才调用实际模型。两者共用同一个闭环。

## 建议阅读顺序

1. 运行 [quickstart](01-quickstart.md)，先看到失败与修复。
2. 对照 [契约](02-contracts.md)，手工算出样例的 6 条保留记录。
3. 阅读 `source.expected_artifacts` 和 `verifier.verify`。
4. 阅读 `Harness.run`，找到三类失败进入修复的分支。
5. 阅读 `FixtureBackend.propose`，明确演示为何不能称为模型实验。
6. 按 [模型接入教程](04-connect-ollama.md) 使用自己的 Ollama 模型。
7. 按 [评测说明](05-testing-and-evaluation.md) 扩展案例。

## 版本定位

v0.1.0 的目标是可读、可运行、可验证。没有分布式队列、数据库持久化调度、多用户服务和 Web UI。JSONL 是执行记录，不等于实现了崩溃恢复。后续改进应以新增可复现实验和测试为依据。
