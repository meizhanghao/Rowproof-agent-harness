# Contributing

这是一个学习与实验原型。欢迎通过可复现的错误案例和小范围修改完善它。

## 本地环境

```bash
python -m venv .venv
# Windows: .venv/Scripts/python.exe
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m ruff check .
.venv/bin/python -m build
```

## 修改要求

- 改业务规则时同步修改契约文档、oracle、候选协议和独立 golden。
- 修复问题时增加能证明错误的测试；避免只检查函数是否被调用。
- 新模型后端默认产出不可信代码，沿用隔离执行限制。
- 区分 fixture、模拟 HTTP 测试和真实模型实验。
- 不添加虚构性能数字、未经运行的 CI 徽章或生产使用声明。

## 提交说明

说明具体问题、改后的行为、执行过的验证和剩余限制。保持一次修改对应一个可检查的主题。真实模型实验请提供配置、任务数据来源和原始结果。
