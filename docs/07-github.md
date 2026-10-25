# 建立自己的 GitHub 仓库

## 1. 名称核对

建议仓库名：`rowproof-agent-harness`；展示名：`RowProof Agent Harness`；中文项目名：基于数据契约与执行反馈的数据处理 Agent Harness。

本次公共仓库检索记录见 [name-check-2026-10-24.json](name-check-2026-10-24.json)。创建前可以重新检查：

```powershell
python tools/check_name.py --name rowproof-agent-harness --output docs/name-check-latest.json
```

公共检索不能保留未来名称。GitHub 仓库最终位于你的用户名命名空间下；这份检查也不代表 PyPI 包名可用。

## 2. 提交前检查

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m build
```

确认 `.gitignore` 已排除 `.venv/`、`runs/`、`.env`、`dist/`。如果后续使用真实业务数据，用合成样例替代后再公开。

## 3. 初始化本地仓库

本次文件生成不会替你创建远程 GitHub 仓库或推送代码。你复现并修改后，在项目根目录执行：

```powershell
git init -b main
git add .
git commit -m "Initial RowProof harness prototype"
```

如果当前目录已经是 Git 仓库，先检查 `git status`，不需要重复初始化。

## 4. 创建远程仓库并推送

在 GitHub 网页创建一个空的 `rowproof-agent-harness` 仓库，不额外初始化 README。将 `YOUR_USERNAME` 替换为自己的用户名：

```powershell
git remote add origin https://github.com/YOUR_USERNAME/rowproof-agent-harness.git
git push -u origin main
```

完成之后补上 README 的真实仓库链接、实际 CI 状态、你自己的实现说明和复现记录。

## 5. 推荐的开发记录

初始版本作为起点，后面分提交记录：理解契约与验收、接通真实模型、增加错误案例、开展策略消融、扩展新 profile。只记录实际完成的工作和结果。

## 6. 源码压缩包

```powershell
python tools/make_archive.py
```

生成 `dist/rowproof-agent-harness-0.1.0-source.zip`，排除虚拟环境、运行结果、Git 元数据和缓存。已有同名包时程序会拒绝覆盖。
