# 数据契约与 orders.v1

## 契约是什么

契约是一份由宿主读取的 JSON，规定输入含义、允许的转换、输出结构及执行预算。模型可以读取它，但没有权限通过修改契约来放宽验收条件。

实际示例见 [`examples/orders/contract.json`](../examples/orders/contract.json)。完整格式见 [`schemas/task-contract.schema.json`](../schemas/task-contract.schema.json)。

```powershell
.\.venv\Scripts\python.exe -m rowproof schema --output schemas/task-contract.schema.json
```

首版只支持 `profile=orders.v1`，未声明字段被拒绝。`amount_min`、`amount_max` 用十进制字符串表达，避免 JSON 浮点表示引入误差。金额上下界在舍入前检查。

## 输入与记录 ID

输入表头必须是：

```csv
order_id,customer,amount,order_date
```

编码为 UTF-8，可有 BOM。`_row_id` 由数据记录位置确定，如 `r000001`，不是文本行号；带引号的多行 CSV 单元格仍是一条记录。首版拒绝空数据集、字段数不匹配和超预算输入。

## 判断顺序

先对四列去除首尾空白，再按下面的顺序确定唯一拒绝原因：

| 顺序 | 条件 | reason |
|---:|---|---|
| 1 | order_id 为空 | missing_order_id |
| 2 | customer 为空 | missing_customer |
| 3 | 金额无法解析、非有限数或超界 | invalid_amount |
| 4 | 日期不匹配格式或不存在 | invalid_date |
| 5 | 已出现相同 ID 的有效记录 | duplicate_order_id |
| 6 | 通过全部规则 | accepted |

**first_valid** 表示：`A003` 的第一条记录若金额为 `NaN`，不占用 ID；后面同 ID 的有效记录仍可以保留。

## 金额与日期

- 使用 Decimal，拒绝 NaN 与 Infinity。
- 每条保留订单先按 `ROUND_HALF_UP` 舍入到两位，再累加；`1.005 + 1.005` 的结果是 `1.01 + 1.01 = 2.02`。
- `-0` 规范为 `0.00`。金额上下界在舍入前检查。
- 日期只接受契约中列出的 `%Y-%m-%d` 和/或 `%Y/%m/%d`，月份、日期必须是两位，输出统一为 ISO 日期。

## 三份候选输出

1. `clean.csv`：列固定为 `_row_id,order_id,customer,amount,order_date`；保留源记录顺序。
2. `lineage.json`：为每条输入记录提供 `row_id/action/reason`，即使该记录被拒绝也必须出现。
3. `report.json`：包含 input_rows、kept_rows、rejected_rows 和 total_amount；前三项必须是 JSON 整数，最后一项是两位小数字符串。

宿主从源输入重新计算上述结果。候选输出三者互相一致仍不足以通过：它们必须与源输入和契约一致。

## 预算

`limits` 限定输入行数、输入与输出字节数、尝试次数、单次程序执行时限与日志大小。模型请求另有适配器级超时和生成长度设置。日志采用轮询限制，输出大小在候选验收时检查；这些设置不构成严格的文件系统磁盘配额。

宿主执行 JSON Schema 校验和业务语义校验。JSON Schema 本身无法表达全部“首条有效记录”及金额守恒规则。
