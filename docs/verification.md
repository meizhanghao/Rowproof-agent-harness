# 本次交付验证记录

验证日期：2026-10-24。环境：Windows、Python 3.10.8。以下记录对应本次本地初版，不代表 GitHub Actions 已在线运行。

## 环境与安装

独立 `.venv` 中已完成 editable 安装，Pydantic 2.14.1、Ruff 0.17.2、build 1.6.1。构建使用 setuptools 84.2.1 和 wheel 0.48.0。

机器可读摘要见 [verification.json](verification.json)，本机依赖版本见 [verified-py310.txt](../constraints/verified-py310.txt)。该约束文件记录本次环境，不是跨平台通用锁文件。

默认 PyPI 在本环境连接超时，使用清华镜像完成安装；没有修改全局 pip 配置。

## 已执行检查

| 检查 | 结果 |
|---|---|
| `python -m unittest discover -s tests -v` | 29 项：28 通过，1 项 Docker 集成测试跳过 |
| `python -m ruff check .` | 通过 |
| `python -m ruff format --check .` | 通过 |
| `python -m pip check` | 依赖关系通过 |
| `python -m build --no-isolation` | 成功构建 wheel 和 sdist |
| wheel 安装到独立目录并加载包内资源 | 成功运行 demo，第二次候选通过 |
| `python -m rowproof demo --output runs/release-demo` | passed，2 次尝试 |
| 对发布工件再次运行独立 validate | passed，无验收问题 |
| fixture 对照实验，每个策略运行 3 次 | 结果符合植入问题及控制流设计 |

验证命令实际使用本项目 `.venv` 解释器。构建日志和本机运行证据在被 Git 忽略的 `runs/` 中；源码包不包含这些可能较大的本地输出。

## 演示结果

输入 12 条，保留 6 条，拒绝 6 条，总金额 `52.53`。第一次候选执行退出码为 0，但因遗漏有效记录而验收失败；第二次候选通过后发布。

脚本化对照实验：

| 策略 | 运行数 | 宣称成功 | 正确工件 | 假成功 |
|---|---:|---:|---:|---:|
| exit-code-only | 3 | 3 | 0 | 3 |
| verify-only | 3 | 0 | 0 | 0 |
| verify-and-repair | 3 | 3 | 3 | 0 |

错误与修复由 fixture 预设，上表只说明控制流按设计工作，不代表真实模型成功率。

## 尚未验证

- 本机没有 Docker CLI，真实容器集成测试未执行。
- 未运行 Ollama 真实模型，适配器只完成模拟 HTTP 响应测试。
- 多平台 GitHub Actions 是配置文件，未在远程仓库运行。
- 真实任务集、真实模型策略消融、吞吐和生产部署均未完成。

## 后续复现

按 [01-quickstart.md](01-quickstart.md) 复现本地控制流，再按 [04-connect-ollama.md](04-connect-ollama.md) 接通真实容器和模型。将后续实验结果单独保存，保留失败案例，不用 fixture 结果替代模型实验。
