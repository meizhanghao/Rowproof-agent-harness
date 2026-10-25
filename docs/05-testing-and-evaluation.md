# 测试与评测

## 1. 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m build
```

业务测试用标准库 unittest，无需额外测试框架。Pydantic 是运行依赖；Ruff 和 build 来自 dev extra。

测试覆盖固定 golden、首条有效去重、逐笔舍入、错误日期、非有限金额、错误契约、行丢失、追踪记录伪造、重复 JSON 键、输出大小、符号链接、执行超时、日志限制、修复次数和模型协议。

`examples/orders/expected/` 是人工编写的样例期望结果。宿主 oracle 必须先与它匹配；独立 worker 再接受宿主校验，避免测试只证明两个模块调用了同一个函数。

## 2. 启用 Docker 集成测试

先确认镜像已存在：

```powershell
docker pull python:3.12-slim
$env:ROWPROOF_TEST_DOCKER = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux/macOS：

```bash
docker pull python:3.12-slim
ROWPROOF_TEST_DOCKER=1 .venv/bin/python -m unittest discover -s tests -v
```

没有设置环境变量时跳过容器测试，不会自动下载镜像。GitHub Actions 提供手动触发的可选 Docker 检查，不能把其配置存在当成已经运行通过。

## 3. 脚本化对照实验

```powershell
.\.venv\Scripts\python.exe -m rowproof benchmark --output runs/ablation-01 --repetitions 3
```

三个策略共享同一输入和首个错误候选：

| 策略 | 运行时验收 | 允许修复 | 实验关注点 |
|---|---|---|---|
| exit-code-only | 否 | 否 | 退出码正常，但结果错误的“假成功” |
| verify-only | 是 | 否 | 能发现错误，但任务未完成 |
| verify-and-repair | 是 | 是 | 用反馈重新生成候选，再验收 |

实验会额外使用一个离线验证器测量所有最终候选，防止把 baseline 自报成功当成正确。输出 `results.csv`、`summary.json`、`report.md`。

这是一项**控制流实验**：修复后的 fixture 是预先写好的；重复运行主要用于确认流程稳定和观察本机耗时。不能据此宣称模型准确率提升了多少，也不能把重复运行同一个样例当成独立任务集。

## 4. 真实模型评测方案

先建立独立任务集，再比较策略。建议逐步收集至少 20～30 份不同数据案例，而非只改一个文件名。记录：

- 模型 tag/digest、Ollama 版本、镜像 digest、硬件和本项目 commit。
- 每个案例的输入、契约、人工核对结果。
- 是否首次通过、预算内是否通过、失败类型、尝试次数和总耗时。
- 实际 token 计数、完整候选与验收证据。

代码已有 Ollama 单任务入口。多模型批量任务、跨案例统计和真实模型基线实验**尚未实现**，需要新增实验驱动程序后再报告结果。

## 5. 指标定义

- **任务通过率：**通过独立验收的任务数 / 任务总数。
- **首次通过率：**首轮就通过的任务数 / 任务总数。
- **假成功数：**策略宣称成功、离线验证器判定错误的次数。
- **平均尝试次数：**总尝试次数 / 任务数，并同时报告失败任务。
- **执行耗时与端到端耗时：**分别统计，避免把模型推理时间混同为脚本运行时间。

## 6. 下一批有价值的测试

优先添加跨实现的生成式案例、不同字符编码错误、CSV 多行字段、边界金额和日期格式子集，再研究错误反馈的消融。Hypothesis 是后续可选工具；首版没有使用它，不应提前写入简历技术栈。
